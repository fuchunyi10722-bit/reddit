"""FastAPI 入口。

Phase 1 + Phase 2 API:

Phase 1 基础:
- POST /community/init          社区初始化
- POST /content/analyze         新内容分析(保存发布前快照)
- POST /content/{id}/result     结果回填
- POST /content/{id}/review     复盘
- GET  /community/{sub}         查看社区画像
- GET  /content/{id}/snapshot   查看发布前快照

Phase 2 人工兜底:
- PUT  /human/label/{item_id}           人工修正标签
- PUT  /human/verdict/{snapshot_id}     人工修正判断
- POST /human/retrieval/filter           人工过滤召回案例
- POST /human/pattern/{id}/confirm      人工确认规律验证
- PUT  /human/pattern/{id}/status       人工覆盖规律状态
- GET  /llm/last-call-log               查看最近 LLM 调用日志
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .database import init_db
from .services import community_init, content_analyzer, review as review_svc


app = FastAPI(title="社区内容分析与学习系统", version="0.2.0")


@app.on_event("startup")
def _startup():
    init_db()


# —— 请求/响应模型 —— #

class InitRequest(BaseModel):
    subreddit: str


class AnalyzeRequest(BaseModel):
    title: str
    selftext: str = ""
    target_subreddit: str
    image_description: Optional[str] = None
    use_llm: bool = True  # Phase 2: 默认调 LLM,可关闭走规则式


class ResultRequest(BaseModel):
    ups: Optional[int] = None
    score: Optional[int] = None
    num_comments: Optional[int] = None
    is_deleted: bool = False
    is_edited: bool = False
    published_at: Optional[datetime] = None
    source_post_id: Optional[str] = None
    result_source: str = "manual"


# —— 人工兜底请求模型 —— #

class HumanOverrideLabelRequest(BaseModel):
    topic_tags: Optional[list[str]] = None
    scenario_tags: Optional[list[str]] = None
    structure_tags: Optional[list[str]] = None
    product_visibility: Optional[str] = None
    brand_mentions: Optional[list[str]] = None
    search_value: Optional[str] = None
    override_reason: str = ""


class HumanOverrideVerdictRequest(BaseModel):
    verdict: Optional[str] = None
    verdict_reason: Optional[str] = None
    key_issues: Optional[list] = None
    modification_suggestions: Optional[list] = None
    override_reason: str = ""


class RetrievalFilterRequest(BaseModel):
    subreddit: str
    new_content: str
    new_content_tags: dict
    excluded_item_ids: list[str] = []


class PatternConfirmRequest(BaseModel):
    case_item_id: str
    outcome: str  # confirmed | contradicted | inconclusive
    reviewer: str = ""
    note: str = ""


class PatternOverrideRequest(BaseModel):
    new_status: str  # candidate | supported | refuted | inconclusive
    reason: str = ""


# —— 路由 —— #

@app.post("/community/init")
def init_community(req: InitRequest):
    """社区初始化:自动拉取 Top/Hot/New + 主题识别后 Search + 评论深采 + PatternMiner。"""
    try:
        profile = community_init.init_community(req.subreddit)
        return {
            "subreddit": profile.subreddit,
            "subscribers": profile.subscriber_count,
            "rules_count": len((profile.rules_summary or {}).get("rules", [])),
            "commercial_restricted": (profile.rules_summary or {}).get("commercial_content_restricted"),
            "posts_ingested": (profile.init_budget_used or {}).get("total_unique_posts"),
            "comments_deep_fetched": (profile.init_budget_used or {}).get("comments_deep_fetched"),
            "patterns_mined": (profile.init_budget_used or {}).get("patterns_mined"),
            "search_queries_used": (profile.init_budget_used or {}).get("search_queries"),
            "top_topics": profile.top_topics[:5],
        }
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/content/analyze")
def analyze_content(req: AnalyzeRequest):
    """新内容分析:判断适配度 + 2-3 问题 + 修改建议 + 评论参与 + 保存发布前快照。

    Phase 2: 默认调 LLM,失败自动降级规则式。use_llm=False 可强制走规则式。
    """
    try:
        snapshot = content_analyzer.analyze_new_content(
            title=req.title,
            selftext=req.selftext,
            target_subreddit=req.target_subreddit,
            image_description=req.image_description,
            use_llm=req.use_llm,
        )
        return {
            "snapshot_id": snapshot.id,
            "verdict": snapshot.verdict,
            "verdict_reason": snapshot.verdict_reason,
            "key_issues": snapshot.key_issues,
            "modification_suggestions": snapshot.modification_suggestions,
            "comment_participation_advice": snapshot.comment_participation_advice,
            "evidence_count": len(snapshot.evidence_item_ids),
            "patterns_applied": len(snapshot.applied_pattern_ids),
            "model_version": snapshot.model_version,
            "created_at": snapshot.created_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/content/{snapshot_id}/result")
def record_result(snapshot_id: str, req: ResultRequest):
    """结果回填。"""
    try:
        result = review_svc.record_result(
            snapshot_id=snapshot_id,
            ups=req.ups,
            score=req.score,
            num_comments=req.num_comments,
            is_deleted=req.is_deleted,
            is_edited=req.is_edited,
            published_at=req.published_at,
            source_post_id=req.source_post_id,
            result_source=req.result_source,
        )
        return {
            "result_id": result.id,
            "snapshot_id": snapshot_id,
            "recorded_at": result.recorded_at.isoformat(),
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/content/{snapshot_id}/review")
def do_review(snapshot_id: str):
    """复盘:判断 vs 实际 → 规律验证(追加 validation_history)。

    注意:AI 不能自行认定规律已验证。复盘后需人工确认。
    """
    try:
        review = review_svc.review_snapshot(snapshot_id)
        return {
            "review_id": review.id,
            "validated_items": review.validated_items,
            "invalidated_items": review.invalidated_items,
            "discrepancy_attribution": review.discrepancy_attribution,
            "pattern_outcomes": review.pattern_outcomes,
            "reviewed_at": review.reviewed_at.isoformat(),
            "note": "规律验证需人工确认后才迁移状态",
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/community/{subreddit}")
def get_profile(subreddit: str):
    """查看社区画像。"""
    from .database import get_session
    from .models.knowledge import CommunityProfile, KnowledgePattern
    with get_session() as s:
        profile = s.query(CommunityProfile).filter_by(subreddit=subreddit).first()
        if not profile:
            raise HTTPException(404, f"社区画像不存在: {subreddit}")
        patterns = s.query(KnowledgePattern).filter(
            KnowledgePattern.applicable_conditions.contains({"subreddit": subreddit})
        ).all()
        return {
            "subreddit": profile.subreddit,
            "subscribers": profile.subscriber_count,
            "rules_summary": profile.rules_summary,
            "top_topics": profile.top_topics,
            "common_structures": profile.common_structures,
            "common_comment_patterns": profile.common_comment_patterns,
            "product_acceptance": profile.product_acceptance,
            "patterns": [
                {
                    "id": p.id, "type": p.pattern_type, "status": p.status,
                    "description": p.description[:120],
                    "evidence_count": len(p.evidence_item_ids),
                    "validation_count": len(p.validation_history or []),
                } for p in patterns
            ],
            "init_budget_used": profile.init_budget_used,
            "last_initialized_at": profile.last_initialized_at.isoformat() if profile.last_initialized_at else None,
        }


@app.get("/content/{snapshot_id}/snapshot")
def get_snapshot(snapshot_id: str):
    """查看发布前快照(immutable)。"""
    from .database import get_session
    from .models.snapshot import ContentAnalysisSnapshot
    with get_session() as s:
        snapshot = s.query(ContentAnalysisSnapshot).filter_by(id=snapshot_id).first()
        if not snapshot:
            raise HTTPException(404, f"快照不存在: {snapshot_id}")
        return {
            "id": snapshot.id,
            "submitted_content": snapshot.submitted_content,
            "target_subreddit": snapshot.target_subreddit,
            "verdict": snapshot.verdict,
            "verdict_reason": snapshot.verdict_reason,
            "key_issues": snapshot.key_issues,
            "modification_suggestions": snapshot.modification_suggestions,
            "comment_participation_advice": snapshot.comment_participation_advice,
            "evidence_item_ids": snapshot.evidence_item_ids,
            "applied_pattern_ids": snapshot.applied_pattern_ids,
            "model_version": snapshot.model_version,
            "created_at": snapshot.created_at.isoformat(),
        }


# ============================================================
# Phase 2: 人工兜底 API
# ============================================================

@app.put("/human/label/{reference_item_id}")
def human_override_label(reference_item_id: str, req: HumanOverrideLabelRequest):
    """人工修正标签。

    新增版本(不覆盖历史),model_version 标记为 human_override。
    """
    from .services import classifier as classifier_svc
    try:
        analysis = classifier_svc.human_override_label(
            reference_item_id=reference_item_id,
            topic_tags=req.topic_tags,
            scenario_tags=req.scenario_tags,
            structure_tags=req.structure_tags,
            product_visibility=req.product_visibility,
            brand_mentions=req.brand_mentions,
            search_value=req.search_value,
            override_reason=req.override_reason,
        )
        return {
            "analysis_id": analysis.id,
            "reference_item_id": reference_item_id,
            "analysis_version": analysis.analysis_version,
            "is_current": analysis.is_current,
            "model_version": analysis.model_version,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/human/verdict/{snapshot_id}")
def human_override_verdict(snapshot_id: str, req: HumanOverrideVerdictRequest):
    """人工修正发布前判断。

    原快照 immutable 不变,创建新快照引用同一 submitted_content。
    """
    try:
        new_snapshot = content_analyzer.human_override_verdict(
            snapshot_id=snapshot_id,
            verdict=req.verdict,
            verdict_reason=req.verdict_reason,
            key_issues=req.key_issues,
            modification_suggestions=req.modification_suggestions,
            override_reason=req.override_reason,
        )
        return {
            "new_snapshot_id": new_snapshot.id,
            "original_snapshot_id": snapshot_id,
            "verdict": new_snapshot.verdict,
            "model_version": new_snapshot.model_version,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/human/retrieval/filter")
def filter_retrieval(req: RetrievalFilterRequest):
    """人工过滤召回案例(移除明显不相关的案例)。

    返回过滤后的召回结果。
    """
    from .services.retrieval import retrieve_for_analysis, filter_retrieved_cases
    try:
        retrieval = retrieve_for_analysis(
            subreddit=req.subreddit,
            new_content=req.new_content,
            new_content_tags=req.new_content_tags,
        )
        filtered = filter_retrieved_cases(retrieval, set(req.excluded_item_ids))
        return {
            "high_cases": [c.to_context_line() for c in filtered.similar_high],
            "failure_cases": [c.to_context_line() for c in filtered.similar_failure],
            "fire_patterns": [p.to_context_line() for p in filtered.fire_patterns],
            "search_patterns": [p.to_context_line() for p in filtered.search_patterns],
            "failure_patterns": [p.to_context_line() for p in filtered.failure_patterns],
            "rules_summary": filtered.rules_summary,
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/human/pattern/{pattern_id}/confirm")
def human_confirm_pattern(pattern_id: str, req: PatternConfirmRequest):
    """人工确认规律验证。

    AI 不能自行认定规律已验证,必须人工确认。
    确认后追加 validation_history,累计达阈值自动迁移状态。
    """
    from .services import pattern_miner
    try:
        kp = pattern_miner.human_confirm_validation(
            pattern_id=pattern_id,
            case_item_id=req.case_item_id,
            outcome=req.outcome,
            reviewer=req.reviewer,
            note=req.note,
        )
        return {
            "pattern_id": kp.id,
            "status": kp.status,
            "validation_count": len(kp.validation_history or []),
            "last_validated_at": kp.last_validated_at.isoformat() if kp.last_validated_at else None,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.put("/human/pattern/{pattern_id}/status")
def human_override_pattern_status(pattern_id: str, req: PatternOverrideRequest):
    """人工强制覆盖规律状态(谨慎使用)。

    用于规律明显错误或已被充分验证的场景。
    """
    from .services import pattern_miner
    try:
        kp = pattern_miner.human_override_pattern_status(
            pattern_id=pattern_id,
            new_status=req.new_status,
            reason=req.reason,
        )
        return {
            "pattern_id": kp.id,
            "status": kp.status,
            "validation_count": len(kp.validation_history or []),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/llm/last-call-log")
def get_last_llm_call_log():
    """查看最近一次 LLM 调用日志(模型/输入/输出/耗时/结果)。

    便于后续比较不同 provider/model 的效果。
    """
    from .services.classifier import get_last_call_log as get_classifier_log
    from .services.content_analyzer import get_last_call_log as get_analyzer_log

    clf_log = get_classifier_log()
    anr_log = get_analyzer_log()

    def _serialize(log):
        if log is None:
            return None
        return {
            "task": log.task,
            "model": log.model,
            "source": log.source,
            "success": log.success,
            "error": log.error,
            "latency_ms": log.latency_ms,
            "prompt_version": log.prompt_version,
            "timestamp": log.timestamp,
            "user_prompt_preview": log.user_prompt[:500] if log.user_prompt else None,
            "response_text_preview": log.response_text[:500] if log.response_text else None,
            "parsed_json": log.parsed_json,
        }

    return {
        "classifier_last_call": _serialize(clf_log),
        "analyzer_last_call": _serialize(anr_log),
    }
