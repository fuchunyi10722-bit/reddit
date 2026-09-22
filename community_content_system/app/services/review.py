"""结果回填 + 复盘闭环。

流程:
1. 录入实际结果(自动/截图/URL/手动)
2. AI 复盘:判断 vs 实际
3. 验证规律:追加 validation_history(单个案例只追加,不直接改 status)
4. 状态迁移需累计达阈值(update_pattern_status)

差异归因层:data_error|classification_error|community_error|pattern_error|prediction_error|external_change
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.snapshot import ContentAnalysisSnapshot, ActualResult, Review
from ..models.knowledge import KnowledgePattern
from . import pattern_miner


def record_result(
    snapshot_id: str,
    ups: Optional[int] = None,
    score: Optional[int] = None,
    num_comments: Optional[int] = None,
    is_deleted: bool = False,
    is_edited: bool = False,
    published_at: Optional[datetime] = None,
    source_post_id: Optional[str] = None,
    result_source: str = "manual",  # auto|screenshot|url|manual
    result_assets: Optional[list] = None,
) -> ActualResult:
    """录入实际发布结果。"""
    with get_session() as s:
        result = ActualResult(
            snapshot_id=snapshot_id,
            source_post_id=source_post_id,
            ups=ups,
            score=score,
            num_comments=num_comments,
            is_deleted=is_deleted,
            is_edited=is_edited,
            published_at=published_at,
            result_source=result_source,
            result_assets=result_assets or [],
            recorded_at=datetime.utcnow(),
        )
        s.add(result)
        s.flush()
        return result


def _determine_actual_tier(snapshot: ContentAnalysisSnapshot, result: ActualResult, subreddit: str) -> str:
    """基于实际 score 判断实际表现层级(用该社区 p25/p75 基线)。"""
    if result.score is None:
        return "unknown"
    with get_session() as s:
        # 取该社区任意一帖的 PerformanceAnalysis 获取基线
        pa = s.query(ActualResult).join(
            ContentAnalysisSnapshot, ActualResult.snapshot_id == ContentAnalysisSnapshot.id
        )  # noqa: unused — 仅为说明
        baseline = s.query(__import__("app.models.analysis", fromlist=["PerformanceAnalysis"]).PerformanceAnalysis).filter_by(
            subreddit=subreddit
        ).first()
        if not baseline:
            return "unknown"
        if result.score >= baseline.p75_score:
            return "high"
        if result.score >= baseline.p25_score:
            return "mid"
        return "low"


def review_snapshot(snapshot_id: str) -> Review:
    """复盘:比较判断 vs 实际。

    产出 validation_history 追加到相关 KnowledgePattern。
    单个案例只追加,不改 Pattern 状态。
    状态迁移由 update_pattern_status 单独触发(累计达阈值)。
    """
    with get_session() as s:
        snapshot = s.query(ContentAnalysisSnapshot).filter_by(id=snapshot_id).first()
        if not snapshot:
            raise ValueError(f"快照不存在: {snapshot_id}")
        result = s.query(ActualResult).filter_by(snapshot_id=snapshot_id).first()
        if not result:
            raise ValueError(f"结果不存在: {snapshot_id},请先录入结果")

        subreddit = snapshot.target_subreddit

        # 1. 实际表现层级
        actual_tier = _determine_actual_tier(snapshot, result, subreddit)

        # 2. 判断 vs 实际对照
        validated = []
        invalidated = []

        # 判断1:适配度
        verdict_was = snapshot.verdict
        if result.is_deleted:
            if verdict_was == "not_fit":
                validated.append({
                    "judgment": "verdict: not_fit",
                    "actual": "post deleted",
                    "outcome": "confirmed",
                })
            else:
                invalidated.append({
                    "judgment": f"verdict: {verdict_was}",
                    "actual": "post deleted",
                    "outcome": "contradicted",
                })
        else:
            # 未删除,判断预测 vs 实际
            predicted = snapshot.predicted_engagement or "mid"
            if actual_tier == "high":
                if predicted in ("mid", "high"):
                    validated.append({
                        "judgment": f"predicted: {predicted}",
                        "actual": f"tier: {actual_tier}",
                        "outcome": "confirmed",
                    })
                else:
                    invalidated.append({
                        "judgment": f"predicted: {predicted}",
                        "actual": f"tier: {actual_tier}",
                        "outcome": "contradicted",
                    })
            elif actual_tier == "low":
                if predicted in ("low",):
                    validated.append({
                        "judgment": f"predicted: {predicted}",
                        "actual": f"tier: {actual_tier}",
                        "outcome": "confirmed",
                    })
                else:
                    invalidated.append({
                        "judgment": f"predicted: {predicted}",
                        "actual": f"tier: {actual_tier}",
                        "outcome": "contradicted",
                    })
            else:
                validated.append({
                    "judgment": f"predicted: {predicted}",
                    "actual": f"tier: {actual_tier}",
                    "outcome": "confirmed",
                })

        # 3. 差异归因
        attribution = "prediction_error"
        if invalidated:
            if result.is_deleted and snapshot.verdict != "not_fit":
                attribution = "community_error"  # 社区规则判断失误
            elif actual_tier == "low" and snapshot.predicted_engagement in ("mid", "high"):
                attribution = "pattern_error"  # 规律预测失误
        else:
            attribution = "prediction_error"  # 预测正确

        # 4. 规律验证:追加 validation_history
        pattern_outcomes = []
        affected_pattern_ids = []
        for pid in (snapshot.applied_pattern_ids or []):
            # 单个案例只追加,不改状态
            outcome = "confirmed" if validated else ("contradicted" if invalidated else "inconclusive")
            pattern_miner.record_validation(
                pattern_id=pid,
                case_item_id=snapshot.submitted_content_hash,  # 用提交内容 hash 作 case 标识
                outcome=outcome,
                note=f"复盘:实际 tier={actual_tier}, deleted={result.is_deleted}",
            )
            affected_pattern_ids.append(pid)
            pattern_outcomes.append({"pattern_id": pid, "outcome": outcome})

        # 5. 落库 Review
        review = Review(
            result_id=result.id,
            snapshot_id=snapshot_id,
            validated_items=validated,
            invalidated_items=invalidated,
            discrepancy_attribution=attribution,
            affected_pattern_ids=affected_pattern_ids,
            pattern_outcomes=pattern_outcomes,
            new_pattern_ids=[],
            revised_pattern_ids=[],
            reviewed_at=datetime.utcnow(),
        )
        s.add(review)
        s.flush()

        # 6. 触发状态迁移检查(累计达阈值才迁移)
        for pid in affected_pattern_ids:
            pattern_miner.update_pattern_status(pid)

        return review
