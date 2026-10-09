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
# CSV/Excel 批量导入(不依赖 Reddit API)
# ============================================================
# 字段别名映射:把用户可能用的列名归一化为标准字段
_FIELD_ALIASES = {
    "url": ["url", "link", "permalink", "post_url", "reddit_url"],
    "subreddit": ["subreddit", "community", "sub", "sub_name", "reddit"],
    "title": ["title", "subject", "post_title"],
    "selftext": ["selftext", "body", "text", "content", "post_body", "正文", "内容"],
    "score": ["score", "ups", "upvotes"],
    "num_comments": ["num_comments", "comments", "comment_count", "评论数"],
    "created_utc": ["created_utc", "created_at", "published_at", "date", "发布时间", "post_date"],
    "author": ["author", "user", "poster", "作者"],
    "comments_text": ["comments_text", "top_comments", "comment_text", "comments_content", "评论"],
}


def _normalize_csv_row(row: dict) -> tuple[dict, list[str]]:
    """把一行 CSV 字典归一化为标准字段 + 标记缺失字段。

    返回 (normalized_dict, missing_fields)。
    """
    # 构建反向查找:任意别名 → 标准字段
    alias_to_std = {}
    for std, aliases in _FIELD_ALIASES.items():
        for a in aliases:
            alias_to_std[a.lower()] = std

    normalized = {}
    for k, v in row.items():
        if v is None:
            continue
        v_str = str(v).strip() if not isinstance(v, str) else v.strip()
        if not v_str:
            continue
        std = alias_to_std.get(k.lower().strip())
        if std:
            # 数值字段尝试转换
            if std in ("score", "num_comments"):
                try:
                    normalized[std] = int(float(v_str))
                except ValueError:
                    pass
            else:
                normalized[std] = v_str

    # 标记缺失的关键字段
    missing = []
    for required in ("title", "selftext"):
        if not normalized.get(required):
            missing.append(required)
    # subreddit 缺失会严重影响社区差异分析,也标记
    if not normalized.get("subreddit"):
        missing.append("subreddit")

    return normalized, missing


def create_batch_from_csv(
    name: str,
    csv_content: str,
    has_header: bool = True,
    delimiter: str = ",",
) -> BatchJob:
    """从 CSV 文本创建批量任务,跳过 Reddit API 抓取。

    每行解析为 raw_payload 存入 BatchItem,_process_one 时跳过 fetch_post。
    支持字段别名(见 _FIELD_ALIASES),允许部分字段缺失(标记到 missing_fields)。

    Args:
        name: 任务名
        csv_content: CSV 文本(UTF-8)
        has_header: 第一行是否为表头(默认 True)
        delimiter: 分隔符(默认逗号,支持 \\t 制表符)
    """
    if not csv_content.strip():
        raise ValueError("csv_content 不能为空")

    # 制表符转义
    if delimiter == "\\t":
        delimiter = "\t"

    reader = csv.DictReader(io.StringIO(csv_content), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValueError("CSV 无有效表头")

    rows = list(reader)
    if not rows:
        raise ValueError("CSV 无数据行")

    with get_session() as s:
        job = BatchJob(name=name or f"csv-batch-{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}")
        job.total_count = len(rows)
        s.add(job)
        s.flush()

        seen_keys: set[str] = set()
        for row in rows:
            normalized, missing = _normalize_csv_row(row)
            url = normalized.get("url", "")
            sub, post_id = parse_url(url) if url else (None, "")

            # 同批去重 key: post_id 优先,其次 url,再次 title
            key = post_id or url or normalized.get("title", "")

            item = BatchItem(
                batch_id=job.id,
                source_url=url or f"csv-row-{len(seen_keys)+1}",
                source_post_id=post_id or None,
                subreddit=normalized.get("subreddit"),
                status="pending",
                raw_payload=normalized,
                missing_fields=missing if missing else None,
            )
            if key in seen_keys:
                item.status = "skipped_duplicate"
                item.error_message = "duplicate in same batch"
            else:
                seen_keys.add(key)
            # 即使缺失关键字段也入库,让 _process_one 决定能否继续
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
    """处理单个 BatchItem:抓取 → 入库 → 分层 → 标签 → 分析 → 回填 → 复盘。

    若 item.raw_payload 存在(CSV 导入路径),跳过 fetch_post,
    直接用 CSV 数据构造 PostDTO 内存对象。
    """
    # 1. 获取内容:CSV raw_payload 优先,否则 adapter.fetch_post
    if item.raw_payload:
        # CSV 路径:不依赖 Reddit API,直接用已有数据
        payload = item.raw_payload
        # 标题或正文缺失则无法分析
        if not payload.get("title") and not payload.get("selftext"):
            _mark_failed(item, "CSV 缺失 title 和 selftext,无法分析", "fetch")
            return
        # 构造 PostDTO 内存对象(不落 RawPost,直接给 ingest_raw_post)
        post_dto = _build_post_dto_from_payload(payload, item)
        comment_dtos = []  # CSV 评论暂不结构化入库,仅 raw_payload 存档
        adapter_name = "csv_import"  # 覆盖 adapter 名,区分来源
    else:
        # URL 路径:走 adapter.fetch_post
        try:
            post_dto, comment_dtos = adapter.fetch_post(item.source_url)
        except FileNotFoundError as e:
            _mark_failed(item, f"fixture 不存在或帖子不存在: {e}", "fetch")
            return
        except Exception as e:
            _mark_failed(item, f"抓取失败(可能 Reddit API 未授权): {e}", "fetch")
            return

    item.subreddit = post_dto.subreddit
    if post_dto.source_post_id:
        item.source_post_id = post_dto.source_post_id

    # 2. 入库(去重:若已有 ReferenceItem 直接复用,但仍继续后续 analyze 步骤)
    #    注意:CSV 路径 adapter_name="csv_import",但 existing 查询按 source_post_id
    #    跨 adapter 查找(同一帖子可能被 file/reddit/csv 多次导入)
    with get_session() as s:
        if post_dto.source_post_id:
            existing = s.query(ReferenceItem).filter_by(
                source_post_id=post_dto.source_post_id,
            ).first()
        else:
            existing = None

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


def _parse_created_utc(value) -> float:
    """把 created_utc 字段(可能是 ISO 字符串、unix 秒、unix 毫秒)统一为 unix 秒 float。"""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        # 毫秒判定:> 1e11 视为毫秒
        v = float(value)
        return v / 1000.0 if v > 1e11 else v
    s = str(value).strip()
    if not s:
        return 0.0
    # 尝试数字
    try:
        v = float(s)
        return v / 1000.0 if v > 1e11 else v
    except ValueError:
        pass
    # 尝试 ISO 字符串
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            from datetime import datetime as _dt
            return _dt.strptime(s[:len(fmt.replace("%", "x")) + 8], fmt).timestamp()
        except ValueError:
            continue
    # 最后尝试 fromisoformat
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _build_post_dto_from_payload(payload: dict, item: BatchItem):
    """从 CSV raw_payload 构造 RawPostDTO 内存对象(不依赖 adapter)。"""
    from ..adapters.base import RawPostDTO

    sub = payload.get("subreddit") or item.subreddit or "unknown"
    post_id = item.source_post_id or f"t3_csv_{item.id[:8]}"
    title = payload.get("title") or ""
    selftext = payload.get("selftext") or ""

    # 如果有评论文本,拼到 selftext 末尾供分析参考(标注来源)
    comments_text = payload.get("comments_text")
    if comments_text:
        selftext = selftext + "\n\n[CSV 评论摘录]\n" + comments_text[:2000]

    created_utc = _parse_created_utc(payload.get("created_utc"))

    return RawPostDTO(
        source_post_id=post_id,
        subreddit=sub,
        title=title,
        selftext=selftext,
        url=payload.get("url", ""),
        author=payload.get("author"),
        created_utc=created_utc,
        permalink=payload.get("url", ""),
        ups=payload.get("score", 0) or 0,
        score=payload.get("score", 0) or 0,
        num_comments=payload.get("num_comments", 0) or 0,
        content_form="text",
        raw_payload=payload,  # 原始 CSV 行
    )


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
    """返回 job 的聚合统计 + 相关规律提示 + 标签/tier 分布。"""
    with get_session() as s:
        job = s.query(BatchJob).filter_by(id=job_id).first()
        if not job:
            raise ValueError(f"批量任务不存在: {job_id}")
        items = s.query(BatchItem).filter_by(batch_id=job_id).all()

        # 拉出关联规律(本批引用的 pattern_id)
        pattern_ids: set[str] = set()
        # 标签分布(来自 ContentAnalysis)
        topic_counter = Counter()
        scenario_counter = Counter()
        structure_counter = Counter()
        product_visibility_counter = Counter()
        search_value_counter = Counter()
        tier_counter = Counter()
        # 缺失字段统计
        missing_counter = Counter()

        for it in items:
            if it.missing_fields:
                for f in it.missing_fields:
                    missing_counter[f] += 1
            if it.snapshot_id:
                snap = s.query(ContentAnalysisSnapshot).filter_by(id=it.snapshot_id).first()
                if snap:
                    pattern_ids.update(snap.applied_pattern_ids or [])
            if it.reference_item_id:
                ca = s.query(ContentAnalysis).filter_by(
                    reference_item_id=it.reference_item_id, is_current=True
                ).first()
                if ca:
                    for t in (ca.topic_tags or []):
                        topic_counter[t] += 1
                    for t in (ca.scenario_tags or []):
                        scenario_counter[t] += 1
                    for t in (ca.structure_tags or []):
                        structure_counter[t] += 1
                    if ca.product_visibility:
                        product_visibility_counter[ca.product_visibility] += 1
                    if ca.search_value:
                        search_value_counter[ca.search_value] += 1
                pa = s.query(PerformanceAnalysis).filter_by(
                    reference_item_id=it.reference_item_id, is_current=True
                ).first()
                if pa and pa.performance_tier:
                    tier_counter[pa.performance_tier] += 1

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
            "tag_distribution": {
                "topic": dict(topic_counter),
                "scenario": dict(scenario_counter),
                "structure": dict(structure_counter),
                "product_visibility": dict(product_visibility_counter),
                "search_value": dict(search_value_counter),
            },
            "tier_distribution": dict(tier_counter),
            "missing_fields_distribution": dict(missing_counter),
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

        # CSV 原始行数据(若有)
        if item.raw_payload:
            result["raw_payload"] = item.raw_payload

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
        "missing_fields": item.missing_fields,
        "has_raw_payload": item.raw_payload is not None,
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
    """导出 job summary 为 Markdown 字符串,含业务洞察。

    严格区分:
    - 【客观事实】:来自 ActualResult 的真实互动数据(score/comments/tier)
    - 【AI 推断】:来自 ContentAnalysis 的标签 + Snapshot 的 verdict
    - 【规律】:来自 KnowledgePattern,标注 status(candidate/fire/supported/refuted)
    """
    summary = get_summary(job_id)
    items = list_items(job_id, limit=10000)

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
    ]

    # ---------- 数据完整度 ----------
    lines += ["## 1. 数据完整度", ""]
    mf = summary.get("missing_fields_distribution", {})
    if mf:
        lines.append("以下字段在部分帖子中缺失(影响分析覆盖度):")
        for field, cnt in sorted(mf.items(), key=lambda x: -x[1]):
            lines.append(f"- `{field}`: {cnt} 条缺失")
    else:
        lines.append("所有帖子关键字段完整。")
    csv_count = sum(1 for it in items if it.get("has_raw_payload"))
    url_count = sum(1 for it in items if not it.get("has_raw_payload") and it.get("source_url"))
    lines.append("")
    lines.append(f"- 数据来源: CSV 导入 {csv_count} 条, URL 抓取 {url_count} 条")

    # ---------- 客观事实 ----------
    lines += ["", "## 2. 客观事实(基于真实互动数据)", ""]
    sd = summary["summary"].get("subreddit_distribution", {})
    if sd:
        lines.append("### 2.1 社区分布")
        for k, v in sorted(sd.items(), key=lambda x: -x[1]):
            lines.append(f"- r/{k}: {v} 条")

    lines += ["", "### 2.2 评分分布"]
    sb = summary["summary"].get("score_buckets", {})
    for k, v in sb.items():
        lines.append(f"- {k}: {v}")

    lines += ["", "### 2.3 评论数分布"]
    cb = summary["summary"].get("comment_buckets", {})
    for k, v in cb.items():
        lines.append(f"- {k}: {v}")

    td = summary.get("tier_distribution", {})
    if td:
        lines += ["", "### 2.4 表现分层(基于本批内评分基线)"]
        for k, v in sorted(td.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

    lines += ["", "### 2.5 高分 Top 3"]
    for t in summary["summary"].get("top_by_score", []):
        lines.append(f"- [{t['score']}] {t['title'][:80]} (r/{t['subreddit']}) [详情](item_id={t['item_id']})")

    lines += ["", "### 2.6 低分 Top 3"]
    for t in summary["summary"].get("low_by_score", []):
        lines.append(f"- [{t['score']}] {t['title'][:80]} (r/{t['subreddit']}) [详情](item_id={t['item_id']})")

    # ---------- AI 推断 ----------
    lines += ["", "## 3. AI 推断(基于内容标签 + LLM 判断)", ""]
    lines.append("> 注:以下为 AI 对内容的标签化判断,非客观事实。verdict 反映 AI 认为该内容是否适合该社区。")

    lines += ["", "### 3.1 Verdict 分布"]
    vd = summary["summary"].get("verdict_distribution", {})
    if vd:
        for k, v in sorted(vd.items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")
    else:
        lines.append("(无 verdict 数据)")

    tg = summary.get("tag_distribution", {})
    if tg.get("topic"):
        lines += ["", "### 3.2 主题分布(topic_tags)"]
        for k, v in sorted(tg["topic"].items(), key=lambda x: -x[1])[:8]:
            lines.append(f"- {k}: {v}")

    if tg.get("structure"):
        lines += ["", "### 3.3 内容结构分布"]
        for k, v in sorted(tg["structure"].items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

    if tg.get("product_visibility"):
        lines += ["", "### 3.4 产品露出程度分布"]
        for k, v in sorted(tg["product_visibility"].items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

    if tg.get("search_value"):
        lines += ["", "### 3.5 搜索价值分布"]
        for k, v in sorted(tg["search_value"].items(), key=lambda x: -x[1]):
            lines.append(f"- {k}: {v}")

    # ---------- 规律 ----------
    lines += ["", "## 4. 本批引用的规律(KnowledgePattern)", ""]
    pts = summary.get("patterns_touched", [])
    if pts:
        lines.append("> 注:规律状态标注其验证程度。`candidate`=待验证,`fire/supported`=多案例支持,`refuted`=被反例推翻。")
        for p in pts:
            lines.append(f"- `{p['pattern_id']}` [{p['pattern_type']}/{p['status']}] "
                         f"samples={p['sample_count']}: {p['description'][:120]}")
    else:
        lines.append("(本批未引用已有规律,可能社区未初始化或 Retrieval 未召回)")

    # ---------- 业务观察 ----------
    lines += ["", "## 5. 业务观察(客观事实 + AI 推断的综合解读)", ""]

    # 高分案例的共同特征
    top_items = [it for it in items if it["status"] == "completed" and it.get("score_snapshot") and it["score_snapshot"] >= 50]
    if top_items:
        lines.append("### 5.1 高分案例特征(score>=50)")
        for it in top_items[:3]:
            lines.append(f"- [{it['score_snapshot']}] {it['title_snapshot'][:60]} (r/{it['subreddit']}) verdict={it['verdict_snapshot']}")

    # 低分案例
    low_items = [it for it in items if it["status"] == "completed" and it.get("score_snapshot") is not None and it["score_snapshot"] < 10]
    if low_items:
        lines += ["", "### 5.2 低分案例特征(score<10)"]
        for it in low_items[:3]:
            lines.append(f"- [{it['score_snapshot']}] {it['title_snapshot'][:60]} (r/{it['subreddit']}) verdict={it['verdict_snapshot']}")

    # 产品植入观察
    pv = tg.get("product_visibility", {})
    if pv:
        lines += ["", "### 5.3 产品植入观察"]
        none_count = pv.get("none", 0)
        subtle_count = pv.get("subtle", 0)
        explicit_count = pv.get("explicit", 0)
        promo_count = pv.get("promotional", 0)
        total_labeled = none_count + subtle_count + explicit_count + promo_count
        if total_labeled > 0:
            lines.append(f"- 无产品露出(none): {none_count} ({none_count*100//total_labeled}%)")
            lines.append(f"- 隐性植入(subtle): {subtle_count} ({subtle_count*100//total_labeled}%)")
            lines.append(f"- 显性植入(explicit): {explicit_count} ({explicit_count*100//total_labeled}%)")
            lines.append(f"- 促销型(promotional): {promo_count} ({promo_count*100//total_labeled}%)")
            if explicit_count > 0 or promo_count > 0:
                lines.append("- **观察**:存在显性/促销型产品露出,需结合其 verdict 和实际 score 判断社区容忍度")
            if subtle_count > explicit_count:
                lines.append("- **观察**:隐性植入多于显性,符合 Reddit 社区反感硬广的一般规律")

    # 社区差异
    if len(sd) > 1:
        lines += ["", "### 5.4 社区差异"]
        lines.append("不同社区的内容表现存在差异(基于客观评分 + AI verdict):")
        for sub, cnt in sorted(sd.items(), key=lambda x: -x[1]):
            sub_items = [it for it in items if it["subreddit"] == sub and it["status"] == "completed"]
            if sub_items:
                scores = [it["score_snapshot"] or 0 for it in sub_items]
                avg = sum(scores) / len(scores) if scores else 0
                verdicts = [it["verdict_snapshot"] for it in sub_items if it["verdict_snapshot"]]
                lines.append(f"- r/{sub}: {cnt} 条, 平均分 {avg:.1f}, verdict 分布 {verdicts}")

    # ---------- NIIMBOT 建议 ----------
    lines += ["", "## 6. NIIMBOT 后续 Reddit 内容规划建议", ""]
    lines.append("> 以下建议基于本批数据的客观事实 + AI 推断,**非定论**,需结合更多样本验证。")
    lines.append("")

    suggestions = []
    # 规则 1: 高分案例的结构特征
    if top_items:
        structures_of_top = []
        for it in top_items:
            # 需要从 ContentAnalysis 获取 structure,但 item 上没有,用 verdict 代替
            if it.get("verdict_snapshot") == "fit":
                structures_of_top.append("fit")
        if structures_of_top:
            suggestions.append("高分帖子中存在 AI 判为 fit 的内容,可作为后续内容参考方向")

    # 规则 2: 显性植入若表现差
    if pv.get("explicit", 0) > 0:
        explicit_low = [it for it in items if it["status"] == "completed"
                        and it.get("score_snapshot") is not None
                        and it["score_snapshot"] < 10]
        if explicit_low:
            suggestions.append("存在显性植入且评分较低的帖子,建议后续内容降低品牌露出程度,优先经验分享/提问型")

    # 规则 3: 社区差异
    if len(sd) > 1:
        suggestions.append("不同社区对内容的接受度不同,后续投放需按社区定制,而非一套内容通用")

    # 规则 4: 缺失字段提醒
    if mf.get("subreddit", 0) > 0:
        suggestions.append(f"有 {mf['subreddit']} 条帖子缺失 subreddit 字段,无法做社区差异分析,后续采集需补齐")

    # 规则 5: 提问型/经验型
    if tg.get("structure"):
        st = tg["structure"]
        if st.get("question", 0) > 0 or st.get("experience", 0) > 0:
            suggestions.append("本批含提问型/经验型内容,这两类在 Reddit 通常接受度较高,可作为 NIIMBOT 后续内容的主结构方向")

    if not suggestions:
        suggestions.append("数据不足,无法给出明确建议。建议补充更多样本(目标 20+ 条)后重新分析。")

    for i, sug in enumerate(suggestions, 1):
        lines.append(f"{i}. {sug}")

    # ---------- 免责声明 ----------
    lines += ["", "---", "",
              "**免责声明**:",
              "- 客观事实部分(评分/评论数/tier)来自导入数据,如实反映历史互动表现",
              "- AI 推断部分(verdict/标签)由 LLM 生成,反映模型对内容的判断,不等于客观正确",
              "- 规律部分来自已有 KnowledgePattern,其状态反映多案例验证程度,单条结果不改变规律状态",
              "- 历史互动数据不能直接证明 AI 事前预测准确;单条案例不能直接定性为普遍规律",
              "- 所有案例可通过 `GET /batch/items/{item_id}` 查看原始数据与分析详情",
              "- 明细数据可通过 `GET /batch/{job_id}/export?format=csv` 导出",
             ]

    return "\n".join(lines)
