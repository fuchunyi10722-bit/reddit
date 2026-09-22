"""分析层:AI 对单条内容的理解(ContentAnalysis,版本化) + 统计分层(PerformanceAnalysis)。

ContentAnalysis 写入后 immutable,新版本永远是新行。
PerformanceAnalysis 基于事实层统计,社区样本变化后可重算(新版本也是新行)。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ContentAnalysis(Base):
    """AI 对单条内容的标签/理解。版本化,不覆盖历史。

    每次重新分析 → 插入新行,analysis_version+1,旧版本 is_current 置 false。
    KnowledgePattern.evidence_analysis_ids 可指向任一版本,复盘时可回看
    "当时是基于哪一版分析提炼的"。
    """

    __tablename__ = "content_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reference_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("reference_items.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(64))  # 调用时的模型标识
    analysis_version: Mapped[int] = mapped_column(Integer)  # v1 / v2 / v3 ...
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # AI 标签(分析层)
    topic_tags: Mapped[list] = mapped_column(JSON, default=list)  # 主题
    scenario_tags: Mapped[list] = mapped_column(JSON, default=list)  # 使用场景
    structure_tags: Mapped[list] = mapped_column(JSON, default=list)  # 问题型/经验型/资源分享型/讨论型...
    product_visibility: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # none|subtle|natural|explicit|promotional
    brand_mentions: Mapped[list] = mapped_column(JSON, default=list)
    search_value: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)  # low|mid|high
    # search_value 由内容本身判断(标题是否接近搜索语言/是否完整回答问题/是否长期信息价值),
    # 不因来自 Search 召回就 = high。

    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    # immutable: 写入后不可改,新版本永远是新行


class PerformanceAnalysis(Base):
    """统计分层。基于 ReferenceItem.score 做社区内分位计算,非 AI 产出。

    社区样本变化后可重算(新版本也是新行),旧版本保留。
    不叫"内容质量",叫"表现层级"。
    """

    __tablename__ = "performance_analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    reference_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("reference_items.id"), index=True)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    analysis_version: Mapped[int] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    performance_tier: Mapped[str] = mapped_column(String(16))  # high|mid|low
    p25_score: Mapped[float] = mapped_column(Float)  # 该社区本次样本的 p25 基线
    p75_score: Mapped[float] = mapped_column(Float)  # p75 基线
    sample_size: Mapped[int] = mapped_column(Integer)  # 本次分位计算样本数

    tier_computed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
