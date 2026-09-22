"""FastAPI 入口。

第一阶段 API:
- POST /community/init          社区初始化
- POST /content/analyze         新内容分析(保存发布前快照)
- POST /content/{id}/result     结果回填
- POST /content/{id}/review     复盘
- GET  /community/{sub}        查看社区画像
- GET  /content/{id}/snapshot   查看发布前快照
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .database import init_db
from .services import community_init, content_analyzer, review as review_svc


app = FastAPI(title="社区内容分析与学习系统", version="0.1.0")


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


class ResultRequest(BaseModel):
    ups: Optional[int] = None
    score: Optional[int] = None
    num_comments: Optional[int] = None
    is_deleted: bool = False
    is_edited: bool = False
    published_at: Optional[datetime] = None
    source_post_id: Optional[str] = None
    result_source: str = "manual"


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
    """新内容分析:判断适配度 + 2-3 问题 + 修改建议 + 评论参与 + 保存发布前快照。"""
    try:
        snapshot = content_analyzer.analyze_new_content(
            title=req.title,
            selftext=req.selftext,
            target_subreddit=req.target_subreddit,
            image_description=req.image_description,
        )
        return {
            "snapshot_id": snapshot.id,
            "verdict": snapshot.verdict,
            "verdict_reason": snapshot.verdict_reason,
            "key_issues": snapshot.key_issues,
            "modification_suggestions": snapshot.modification_suggestions,
            "comment_participation_advice": snapshot.comment_participation_advice,
            "predicted_engagement": snapshot.predicted_engagement,
            "prediction_basis": snapshot.prediction_basis,
            "evidence_count": len(snapshot.evidence_item_ids),
            "patterns_applied": len(snapshot.applied_pattern_ids),
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
    """复盘:判断 vs 实际 → 规律验证(追加 validation_history)。"""
    try:
        review = review_svc.review_snapshot(snapshot_id)
        return {
            "review_id": review.id,
            "validated_items": review.validated_items,
            "invalidated_items": review.invalidated_items,
            "discrepancy_attribution": review.discrepancy_attribution,
            "pattern_outcomes": review.pattern_outcomes,
            "reviewed_at": review.reviewed_at.isoformat(),
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
