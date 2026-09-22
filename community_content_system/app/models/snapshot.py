"""新内容分析 + 发布前快照 + 实际结果 + 复盘。

发布前快照 immutable,发布后不可回写。
复盘比较"判断 vs 实际",产出 validation_history 追加到 KnowledgePattern。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ContentAnalysisSnapshot(Base):
    """发布前 AI 判断快照。immutable。

    用户发布前 AI 认为:社区适合 / 最大问题 / 修改建议 / 评论参与建议 / 证据。
    发布后不可回写。这是系统能否学习的关键——必须能回看当时判断。
    """

    __tablename__ = "content_analysis_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    submitted_content_hash: Mapped[str] = mapped_column(String(64), index=True)  # 提交内容 hash
    submitted_content: Mapped[dict] = mapped_column(JSON)  # 标题+正文+图描述+目标社区
    target_subreddit: Mapped[str] = mapped_column(String(128), index=True)

    # 内容变量 / 环境变量
    content_variables: Mapped[dict] = mapped_column(JSON, default=dict)
    env_variables: Mapped[dict] = mapped_column(JSON, default=dict)

    # AI 判断
    verdict: Mapped[str] = mapped_column(String(32))  # fit|fit_after_fix|not_fit
    verdict_reason: Mapped[str] = mapped_column(Text)
    key_issues: Mapped[list] = mapped_column(JSON, default=list)  # 2-3 个最关键问题
    modification_suggestions: Mapped[list] = mapped_column(JSON, default=list)
    comment_participation_advice: Mapped[str] = mapped_column(Text)

    # 证据
    evidence_item_ids: Mapped[list] = mapped_column(JSON, default=list)  # → ReferenceItem.id[]
    applied_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)  # → KnowledgePattern.id[]

    # 预测(低/中/高 + 依据,不追求虚假精确)
    predicted_engagement: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # low|mid|high
    prediction_basis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    model_version: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # immutable: 发布后不可回写


class ActualResult(Base):
    """实际发布结果。来自自动获取/截图/URL/手动。"""

    __tablename__ = "actual_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_analysis_snapshots.id"), index=True)
    source_post_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 发布后的 t3_xxx

    ups: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_comments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    result_source: Mapped[str] = mapped_column(String(32), default="manual")  # auto|screenshot|url|manual

    result_assets: Mapped[list] = mapped_column(JSON, default=list)  # 截图/Excel 引用
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Review(Base):
    """复盘:比较判断 vs 实际。

    产出 validation_history 追加到 KnowledgePattern,不改 Pattern 状态直接。
    状态迁移需累计证据达阈值。
    """

    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    result_id: Mapped[str] = mapped_column(String(36), ForeignKey("actual_results.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(String(36), ForeignKey("content_analysis_snapshots.id"), index=True)

    # 判断 vs 实际对照
    validated_items: Mapped[list] = mapped_column(JSON, default=list)  # 被验证的判断项
    invalidated_items: Mapped[list] = mapped_column(JSON, default=list)  # 未被验证的判断项

    # 差异归因层
    discrepancy_attribution: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    # data_error|classification_error|community_error|pattern_error|prediction_error|external_change

    # 产出:追加到哪些 KnowledgePattern 的 validation_history
    affected_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)
    pattern_outcomes: Mapped[list] = mapped_column(JSON, default=list)
    # 每条: {pattern_id, outcome: confirmed|contradicted|inconclusive, note}

    new_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)  # 产出新规律
    revised_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)  # 修正的规律

    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
