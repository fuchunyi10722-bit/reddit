"""规律层:KnowledgePattern。独立于单条内容存在,被多个 ReferenceItem 引用作证据。

第一阶段状态机:candidate → supported / refuted / inconclusive
单个案例只追加 validation_history,不直接改 status。
状态迁移需要累计证据达到阈值(默认 confirmed>=3 且 contradicted=0 → supported)。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class KnowledgePattern(Base):
    """内容规律。从多个案例提炼,独立存在。

    pattern_type:
      fire    — 火内容规律(什么结构在社区容易获得互动)
      search  — 搜索型内容规律(什么内容覆盖搜索需求)
      failure — 失败规律(什么结构容易被删/低互动/广告感)

    status:
      candidate     — 初始
      supported     — 多案例累计证据后确认
      refuted       — 多案例累计反例后
      inconclusive  — 证据矛盾,长期无法判定

    第一阶段不做可信度数值,只跑状态迁移。
    """

    __tablename__ = "knowledge_patterns"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    pattern_type: Mapped[str] = mapped_column(String(16), index=True)  # fire|search|failure
    description: Mapped[str] = mapped_column(Text)  # 结构 → 条件 → 结果(自然语言)
    applicable_conditions: Mapped[dict] = mapped_column(JSON, default=dict)  # 适用条件(社区类型/场景)

    # 证据关联(双向溯源)
    evidence_item_ids: Mapped[list] = mapped_column(JSON, default=list)  # → ReferenceItem.id[]
    evidence_analysis_ids: Mapped[list] = mapped_column(JSON, default=list)  # → ContentAnalysis.id[]
    sample_count: Mapped[int] = mapped_column(Integer, default=0)

    # 状态与验证历史
    status: Mapped[str] = mapped_column(String(16), default="candidate", index=True)
    validation_history: Mapped[list] = mapped_column(JSON, default=list)
    # 每条记录: {case_item_id, outcome: confirmed|contradicted|inconclusive, review_id, validated_at, note}

    source_review_ids: Mapped[list] = mapped_column(JSON, default=list)  # → Review.id[]

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class CommunityProfile(Base):
    """社区画像聚合视图。引用 KnowledgePattern,不重复存储规律。

    规律永远以 KnowledgePattern 为准,CommunityProfile 只是当前画像的聚合视图。
    """

    __tablename__ = "community_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    subreddit: Mapped[str] = mapped_column(String(128), unique=True, index=True)

    rules_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    subscriber_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_utc: Mapped[Optional[float]] = mapped_column(Integer, nullable=True)
    subreddit_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # 聚合统计(从 ContentAnalysis 聚合)
    top_topics: Mapped[list] = mapped_column(JSON, default=list)  # 主题分布
    common_structures: Mapped[list] = mapped_column(JSON, default=list)  # 结构分布
    common_comment_patterns: Mapped[list] = mapped_column(JSON, default=list)

    # 规律引用(只引用 ID,不复制内容)
    high_performance_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)
    low_performance_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)
    search_content_pattern_ids: Mapped[list] = mapped_column(JSON, default=list)

    # 产品/品牌接受度
    product_acceptance: Mapped[dict] = mapped_column(JSON, default=dict)  # {tier → product_visibility 分布}

    init_budget_used: Mapped[dict] = mapped_column(JSON, default=dict)
    last_initialized_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
