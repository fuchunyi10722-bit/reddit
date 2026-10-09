"""批量历史 Reddit 内容分析编排服务。

只做编排:URL → fetch_post → ingest → tier → label → analyze → record_result → review
每步独立 try/except,单条失败不影响其他。

严格复用现有链路,不重写:
- adapter.fetch_post():单帖 + 评论抓取
- parser.ingest_raw_post / ingest_raw_comment:落库
- performance.tier_items:统计分层
- classifier.label_item:AI 标签
- content_analyzer.analyze_new_content:AI 判断(把历史帖当成"拟发布内容"分析)
- review_svc.record_result:把帖子自身的 ups/score 当成"实际结果"回填
- review_svc.review_snapshot:复盘判断 vs 实际
- pattern_miner:不在本层调用,沉淀留给后续(本批只产出 ReferenceItem,不直接产 Pattern)
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import datetime
from typing import Optional

from ..adapters import get_adapter
from ..config import settings
from ..database import get_session
from ..models.batch import BatchJob, BatchItem
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.knowledge import KnowledgePattern, CommunityProfile
from ..models.snapshot import ContentAnalysisSnapshot, ActualResult, Review
from . import parser as parser_svc, performance, classifier as classifier_svc
from . import content_analyzer, review as review_svc


# ============================================================
# URL 解析
# ============================================================
_URL_PATTERNS = [
    # https://www.reddit.com/r/Subreddit/comments/POSTID/...
    re.compile(r"reddit\.com/r/([^/]+)/comments/([a-z0-9]+)", re.IGNORECASE),
    # https://redd.it/POSTID
    re.compile(r"redd\.it/([a-z0-9]+)", re.IGNORECASE),
    # t3_xxx
    re.compile(r"^t3_([a-z0-9]+)$", re.IGNORECASE),
]


def parse_url(url: str) -> tuple[Optional[str], str]:
    """从 Reddit URL/permalink 提取 (subreddit, source_post_id)。

    subreddit 可能无法从短链提取(redd.it/t3_xxx),返回 None。
    source_post_id 统一为 t3_ 前缀的 fullname。
    """
    url = url.strip()
    if not url:
        return None, ""

    for pat in _URL_PATTERNS:
        m = pat.search(url) or pat.match(url)
        if m:
            groups = m.groups()
            if len(groups) == 2:
                sub, pid = groups
                return sub, f"t3_{pid}"
            elif len(groups) == 1:
                return None, f"t3_{groups[0]}"
    # 兜底:把字符串本身当 post_id
    return None, url


# ============================================================
# 批量导入
# ============================================================
def create_batch(name: str, urls: list[str]) -> BatchJob:
    """创建批量任务,落库 BatchJob + N 个 BatchItem(pending)。

    URL 自动去重(同一批内同 source_post_id 只入一次,重复的标记 skipped_duplicate)。
    """
    if not urls:
        raise ValueError("urls 不能为空")

    with get_session() as s:
        job = BatchJob(name=name or f"batch-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        job.total_count = len(urls)
        s.add(job)
        s.flush()

        seen_pids: set[str] = set()
        for url in urls:
            _, source_post_id = parse_url(url)
            item = BatchItem(
                batch_id=job.id,
                source_url=url,
                source_post_id=source_post_id or None,
                status="pending",
            )
            # 同批去重(用 source_post_id 作 key;若解析不出 post_id 则用 url)
            key = source_post_id or url
            if key in seen_pids:
                item.status = "skipped_duplicate"
                item.error_message = "duplicate in same batch"
            else:
                seen_pids.add(key)
            s.add(item)
        s.flush()
        return job


# ============================================================
# 批量处理主流程
# ============================================================
def process_batch(
    job_id: str,
    use_llm: bool = True,
    skip_existing: bool = True,
) -> BatchJob:
    """处理一个批量任务。

    每个 BatchItem 独立 try/except,失败只标记 item.status=failed,
    不中断其他 item。

    Args:
        job_id: BatchJob.id
        use_llm: 是否调 LLM(False=规则式 fallback,用于沙箱无 LLM 时)
        skip_existing: 若 source_post_id 已存在 ReferenceItem,
                       直接复用(标记 skipped_duplicate 但保留 reference_item_id),
                       不重新抓取
    """
    with get_session() as s:
        job = s.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            raise ValueError(f"批量任务不存在: {job_id}")
        job.status = "processing"
        job.started_at = datetime.utcnow()
        items = s.query(BatchItem).filter_by(batch_id=job_id).all()
        s.flush()

    adapter = get_adapter()
    adapter_name = adapter.adapter_name

    for item in items:
        if item.status in ("completed", "skipped_duplicate"):
            continue
        try:
            _process_one(item, adapter, adapter_name, use_llm, skip_existing)
        except Exception as e:
            _mark_failed(item, str(e)[:500], "unknown")
        # 每条独立提交,避免一条失败回滚整批
        with get_session() as s:
            s.merge(item)

    # 汇总
    _finalize_job(job_id)
    with get_session() as s:
        return s.query(BatchJob).filter_by(id=job_id).first()


def _process_one(
    item: BatchItem,
    adapter,
    adapter_name: str,
    use_llm: bool,
    skip_existing: bool,
) -> None:
    """处理单个 BatchItem:抓取 → 入库 → 分层 → 标签 → 分析 → 回填 → 复盘。"""
    # 1. 抓取
    try:
        post_dto, comment_dtos = adapter.fetch_post(item.source_url)
    except FileNotFoundError as e:
        _mark_failed(item, f"fixture 不存在或帖子不存在: {e}", "fetch")
        return
    except Exception as e:
        _mark_failed(item, f"抓取失败: {e}", "fetch")
        return

    item.subreddit = post_dto.subreddit
    item.source_post_id = post_dto.source_post_id

    # 2. 入库(去重:若已有 ReferenceItem 直接复用,但仍继续后续 analyze 步骤)
    with get_session() as s:
        existing = s.query(ReferenceItem).filter_by(
            source_post_id=post_dto.source_post_id,
            source_adapter=adapter_name,
        ).first()

    if existing and skip_existing:
        # 已存在,不重复入库,但后续 analyze/record/review 仍要执行
        ref_id = existing.id
        ref_title = existing.title
        ref_selftext = existing.selftext
        item.title_snapshot = existing.title[:200]
        item.score_snapshot = existing.score
        item.num_comments_snapshot = existing.num_comments
    else:
        try:
            raw_post, ref = parser_svc.ingest_raw_post(post_dto, adapter_name)
        except Exception as e:
            _mark_failed(item, f"入库失败: {e}", "ingest")
            return
        ref_id = ref.id
        ref_title = ref.title
        ref_selftext = ref.selftext
        item.title_snapshot = ref.title[:200]
        item.score_snapshot = ref.score
        item.num_comments_snapshot = ref.num_comments

        # 评论入库(失败不影响主流程)
        for cdto in comment_dtos:
            try:
                parser_svc.ingest_raw_comment(cdto, adapter_name, ref_id)
            except Exception:
                pass  # 单条评论失败忽略

    item.reference_item_id = ref_id

    # 3. 统计分层(可能因社区未初始化无基线而跳过)
    try:
        performance.tier_items(item.subreddit or "", [ref_id])
    except Exception as e:
        # 分层失败不阻断后续,只是 tier 未知
        item.error_message = (item.error_message or "") + f"; tier skipped: {e}"

    # 4. AI 标签(若已存在且已有 current 标签,则跳过避免重复打标)
    with get_session() as s:
        from ..models.analysis import ContentAnalysis
        has_current_label = s.query(ContentAnalysis).filter_by(
            reference_item_id=ref_id, is_current=True
        ).first() is not None
    if not has_current_label:
        try:
            classifier_svc.label_item(ref_id, use_llm=use_llm)
        except Exception as e:
            _mark_failed(item, f"标签失败: {e}", "classify")
            return

    # 5. AI 分析(把历史帖当"拟发布内容"分析,产 verdict/issues/suggestions)
    try:
        snap = content_analyzer.analyze_new_content(
            title=ref_title,
            selftext=ref_selftext,
            target_subreddit=item.subreddit,
            use_llm=use_llm,
        )
    except ValueError as e:
        # 社区未初始化,跳过 analyze
        item.error_message = (item.error_message or "") + f"; analyze skipped: {e}"
        snap = None
    except Exception as e:
        _mark_failed(item, f"分析失败: {e}", "analyze")
        return

    if snap:
        item.snapshot_id = snap.id
        item.verdict_snapshot = snap.verdict

    # 6. 回填实际结果(用帖子自身的 ups/score/num_comments 作为"实际表现")
    if snap:
        try:
            result = review_svc.record_result(
                snapshot_id=snap.id,
                ups=post_dto.ups,
                score=post_dto.score,
                num_comments=post_dto.num_comments,
                is_deleted=False,
                is_edited=False,
                published_at=datetime.fromtimestamp(post_dto.created_utc) if post_dto.created_utc else None,
                source_post_id=post_dto.source_post_id,
                result_source="historical_import",
            )
            item.actual_result_id = result.id
        except Exception as e:
            _mark_failed(item, f"结果回填失败: {e}", "record")
            return

        # 7. 复盘
        try:
            review = review_svc.review_snapshot(snap.id)
            item.review_id = review.id
        except Exception as e:
            item.error_message = (item.error_message or "") + f"; review skipped: {e}"

    # 8. 完成
    item.status = "completed"
    item.error_message = None
    item.processed_at = datetime.utcnow()


def _mark_failed(item: BatchItem, message: str, stage: str) -> None:
    """标记 item 失败。"""
    item.status = "failed"
    item.error_message = message
    item.error_stage = stage
    item.processed_at = datetime.utcnow()


def _finalize_job(job_id: str) -> None:
    """完成时聚合统计。"""
    with get_session() as s:
        job = s.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            return
        items = s.query(BatchItem).filter_by(batch_id=job_id).all()
        job.success_count = sum(1 for i in items if i.status == "completed")
        job.failed_count = sum(1 for i in items if i.status == "failed")
        job.skipped_count = sum(1 for i in items if i.status == "skipped_duplicate")
        job.status = "completed" if job.failed_count == 0 else "partial_completed"
        job.finished_at = datetime.utcnow()
        job.summary = _build_summary_dict(items)
        s.flush()


# ============================================================
# 聚合统计
# ============================================================
def _build_summary_dict(items: list[BatchItem]) -> dict:
    """从 items 聚合主要统计(不查 ReferenceItem 详情,只用 item 上的快照字段)。"""
    subreddits = Counter()
    verdicts = Counter()
    score_buckets = {"high(>=50)": 0, "mid(10-49)": 0, "low(<10)": 0, "unknown": 0}
    comment_buckets = {"0": 0, "1-5": 0, "6-20": 0, "21+": 0, "unknown": 0}

    for it in items:
        if it.status not in ("completed", "skipped_duplicate"):
            continue
        if it.subreddit:
            subreddits[it.subreddit] += 1
        if it.verdict_snapshot:
            verdicts[it.verdict_snapshot] += 1

        score = it.score_snapshot
        if score is None:
            score_buckets["unknown"] += 1
        elif score >= 50:
            score_buckets["high(>=50)"] += 1
        elif score >= 10:
            score_buckets["mid(10-49)"] += 1
        else:
            score_buckets["low(<10)"] += 1

        nc = it.num_comments_snapshot
        if nc is None:
            comment_buckets["unknown"] += 1
        elif nc == 0:
            comment_buckets["0"] += 1
        elif nc <= 5:
            comment_buckets["1-5"] += 1
        elif nc <= 20:
            comment_buckets["6-20"] += 1
        else:
            comment_buckets["21+"] += 1

    # 高分/低分 top3 (用 item 上的 snapshot)
    eligible = [it for it in items if it.status in ("completed", "skipped_duplicate") and it.score_snapshot is not None]
    top_by_score = sorted(eligible, key=lambda x: x.score_snapshot, reverse=True)[:3]
    low_by_score = sorted(eligible, key=lambda x: x.score_snapshot)[:3]

    return {
        "subreddit_distribution": dict(subreddits),
        "verdict_distribution": dict(verdicts),
        "score_buckets": score_buckets,
        "comment_buckets": comment_buckets,
        "top_by_score": [
            {"title": it.title_snapshot, "score": it.score_snapshot,
             "subreddit": it.subreddit, "item_id": it.id}
            for it in top_by_score
        ],
        "low_by_score": [
            {"title": it.title_snapshot, "score": it.score_snapshot,
             "subreddit": it.subreddit, "item_id": it.id}
            for it in low_by_score
        ],
    }


def get_summary(job_id: str) -> dict:
    """返回 job 的聚合统计 + 相关规律提示。"""
    with get_session() as s:
        job = s.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            raise ValueError(f"批量任务不存在: {job_id}")
        items = s.query(BatchItem).filter_by(batch_id=job_id).all()

        # 拉出关联规律(本批引用的 pattern_id)
        pattern_ids: set[str] = set()
        for it in items:
            if it.snapshot_id:
                snap = s.query(ContentAnalysisSnapshot).filter_by(id=it.snapshot_id).first()
                if snap:
                    pattern_ids.update(snap.applied_pattern_ids or [])

        patterns_touched = []
        for pid in pattern_ids:
            p = s.query(KnowledgePattern).filter_by(id=pid).first()
            if p:
                patterns_touched.append({
                    "pattern_id": pid,
                    "pattern_type": p.pattern_type,
                    "description": p.description[:200],
                    "status": p.status,
                    "sample_count": p.sample_count,
                })

        return {
            "job_id": job.id,
            "name": job.name,
            "status": job.status,
            "total": job.total_count,
            "success": job.success_count,
            "failed": job.failed_count,
            "skipped": job.skipped_count,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "summary": job.summary or {},
            "patterns_touched": patterns_touched,
        }


# ============================================================
# 查询
# ============================================================
def list_items(
    job_id: str,
    status: Optional[str] = None,
    subreddit: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """列出某批的 items(支持过滤)。"""
    with get_session() as s:
        q = s.query(BatchItem).filter_by(batch_id=job_id)
        if status:
            q = q.filter_by(status=status)
        if subreddit:
            q = q.filter_by(subreddit=subreddit)
        items = q.order_by(BatchItem.created_at).offset(offset).limit(limit).all()
        return [_item_to_dict(i) for i in items]


def get_item_detail(item_id: str) -> dict:
    """查看单 item 详情:含原始 ReferenceItem + 当前标签 + 分析 snapshot + Review。"""
    with get_session() as s:
        item = s.query(BatchItem).filter_by(id=item_id).first()
        if not item:
            raise ValueError(f"BatchItem 不存在: {item_id}")

        result: dict = _item_to_dict(item)

        # 原始帖子事实
        if item.reference_item_id:
            ref = s.query(ReferenceItem).filter_by(id=item.reference_item_id).first()
            if ref:
                result["reference_item"] = {
                    "id": ref.id, "title": ref.title, "selftext": ref.selftext[:500],
                    "subreddit": ref.subreddit, "score": ref.score,
                    "ups": ref.ups, "num_comments": ref.num_comments,
                    "author": ref.author, "url": ref.url,
                    "created_utc": ref.created_utc,
                    "permalink": ref.permalink,
                }
            # 当前标签
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=item.reference_item_id, is_current=True
            ).first()
            if ca:
                result["current_analysis"] = {
                    "topic_tags": ca.topic_tags,
                    "scenario_tags": ca.scenario_tags,
                    "structure_tags": ca.structure_tags,
                    "product_visibility": ca.product_visibility,
                    "search_value": ca.search_value,
                    "model_version": ca.model_version,
                }
            # tier
            pa = s.query(PerformanceAnalysis).filter_by(
                reference_item_id=item.reference_item_id, is_current=True
            ).first()
            if pa:
                result["performance_tier"] = pa.performance_tier

        # 分析 snapshot
        if item.snapshot_id:
            snap = s.query(ContentAnalysisSnapshot).filter_by(id=item.snapshot_id).first()
            if snap:
                result["snapshot"] = {
                    "id": snap.id,
                    "verdict": snap.verdict,
                    "verdict_reason": snap.verdict_reason,
                    "key_issues": snap.key_issues,
                    "modification_suggestions": snap.modification_suggestions,
                    "evidence_item_ids": snap.evidence_item_ids,
                    "applied_pattern_ids": snap.applied_pattern_ids,
                    "model_version": snap.model_version,
                }

        # 复盘
        if item.review_id:
            review = s.query(Review).filter_by(id=item.review_id).first()
            if review:
                result["review"] = {
                    "id": review.id,
                    "validated_items": review.validated_items,
                    "invalidated_items": review.invalidated_items,
                    "discrepancy_attribution": review.discrepancy_attribution,
                    "pattern_outcomes": review.pattern_outcomes,
                }

        # 实际结果
        if item.actual_result_id:
            ar = s.query(ActualResult).filter_by(id=item.actual_result_id).first()
            if ar:
                result["actual_result"] = {
                    "id": ar.id,
                    "ups": ar.ups, "score": ar.score,
                    "num_comments": ar.num_comments,
                    "is_deleted": ar.is_deleted,
                    "result_source": ar.result_source,
                }

        return result


def _item_to_dict(item: BatchItem) -> dict:
    return {
        "id": item.id,
        "batch_id": item.batch_id,
        "source_url": item.source_url,
        "source_post_id": item.source_post_id,
        "subreddit": item.subreddit,
        "status": item.status,
        "error_message": item.error_message,
        "error_stage": item.error_stage,
        "reference_item_id": item.reference_item_id,
        "snapshot_id": item.snapshot_id,
        "actual_result_id": item.actual_result_id,
        "review_id": item.review_id,
        "title_snapshot": item.title_snapshot,
        "score_snapshot": item.score_snapshot,
        "num_comments_snapshot": item.num_comments_snapshot,
        "verdict_snapshot": item.verdict_snapshot,
        "processed_at": item.processed_at.isoformat() if item.processed_at else None,
    }


def list_jobs(limit: int = 20) -> list[dict]:
    """列出最近的批量任务。"""
    with get_session() as s:
        jobs = s.query(BatchJob).order_by(BatchJob.created_at.desc()).limit(limit).all()
        return [{
            "id": j.id, "name": j.name, "status": j.status,
            "total": j.total_count, "success": j.success_count,
            "failed": j.failed_count, "skipped": j.skipped_count,
            "created_at": j.created_at.isoformat() if j.created_at else None,
            "finished_at": j.finished_at.isoformat() if j.finished_at else None,
        } for j in jobs]


# ============================================================
# 重试
# ============================================================
def retry_failed(job_id: str) -> int:
    """把 failed 状态的 item 重置为 pending,返回重置数量。"""
    with get_session() as s:
        items = s.query(BatchItem).filter_by(
            batch_id=job_id, status="failed"
        ).all()
        for it in items:
            it.status = "pending"
            it.error_message = None
            it.error_stage = None
            it.processed_at = None
        s.flush()
        return len(items)


# ============================================================
# 导出
# ============================================================
def export_items_csv(job_id: str) -> str:
    """导出 items 为 CSV 字符串。"""
    items = list_items(job_id, limit=10000)
    if not items:
        return ""

    output = io.StringIO()
    fieldnames = [
        "id", "source_url", "subreddit", "status",
        "title_snapshot", "score_snapshot", "num_comments_snapshot",
        "verdict_snapshot", "error_stage", "error_message",
        "reference_item_id", "snapshot_id", "review_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for it in items:
        row = dict(it)
        # 截断长字段
        if row.get("error_message"):
            row["error_message"] = row["error_message"][:200]
        writer.writerow(row)
    return output.getvalue()


def export_summary_md(job_id: str) -> str:
    """导出 job summary 为 Markdown 字符串。"""
    summary = get_summary(job_id)
    lines = [
        f"# 批量分析报告: {summary['name']}",
        "",
        f"- 任务 ID: `{summary['job_id']}`",
        f"- 状态: {summary['status']}",
        f"- 总数: {summary['total']}  成功: {summary['success']}  "
        f"失败: {summary['failed']}  跳过: {summary['skipped']}",
        f"- 创建: {summary['created_at']}",
        f"- 完成: {summary['finished_at']}",
        "",
        "## 社区分布",
        "",
    ]
    sd = summary["summary"].get("subreddit_distribution", {})
    if sd:
        for k, v in sorted(sd.items(), key=lambda x: -x[1]):
            lines.append(f"- r/{k}: {v}")
    else:
        lines.append("(无数据)")

    lines += ["", "## Verdict 分布", ""]
    vd = summary["summary"].get("verdict_distribution", {})
    if vd:
        for k, v in sorted(vd.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("(无数据)")

    lines += ["", "## 评分分布", ""]
    sb = summary["summary"].get("score_buckets", {})
    for k, v in sb.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "## 评论数分布", ""]
    cb = summary["summary"].get("comment_buckets", {})
    for k, v in cb.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "## 高分 Top 3", ""]
    for t in summary["summary"].get("top_by_score", []):
        lines.append(f"- [{t['score']}] {t['title'][:80]} (r/{t['subreddit']})")

    lines += ["", "## 低分 Top 3", ""]
    for t in summary["summary"].get("low_by_score", []):
        lines.append(f"- [{t['score']}] {t['title'][:80]} (r/{t['subreddit']})")

    lines += ["", "## 本批引用的规律", ""]
    for p in summary.get("patterns_touched", []):
        lines.append(f"- `{p['pattern_id']}` [{p['pattern_type']}/{p['status']}] "
                     f"samples={p['sample_count']}: {p['description'][:120]}")

    return "\n".join(lines)
