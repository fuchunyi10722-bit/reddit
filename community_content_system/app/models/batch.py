"""批量分析层:跟踪一次批量导入任务及其每个 URL 的处理状态。

复用现有 ReferenceItem/ContentAnalysis/PerformanceAnalysis/Snapshot/ActualResult/Review,
本表只做"批量任务编排 + 状态跟踪",不重复存内容数据。
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


class BatchJob(Base):
    """一次批量导入任务。

    一个 job 包含 N 个 BatchItem(每个 URL 一条)。
    """

    __tablename__ = "batch_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    # pending | processing | completed | partial_completed | failed
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0)  # 去重跳过
    summary: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)  # 完成后聚合
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class BatchItem(Base):
    """批量任务中的一个 URL 处理条目。

    状态机: pending → fetching → fetched → classifying → tiering
              → analyzing → recording → reviewing → completed
            ↘ failed (任意阶段可跳 failed,error_message 记录原因)

    reference_item_id 在 fetched 之后填入,用于关联已有的内容数据。
    snapshot_id 在 analyzing 之后填入。
    result_id 在 recording 之后填入。
    review_id 在 reviewing 之后填入。
    """

    __tablename__ = "batch_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    batch_id: Mapped[str] = mapped_column(String(36), ForeignKey("batch_jobs.id"), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    source_post_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    subreddit: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    # pending|fetched|completed|failed|skipped_duplicate
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_stage: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    # fetch|ingest|classify|tier|analyze|record|review

    # 关联到现有数据(都不重复存内容,只存 id)
    reference_item_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actual_result_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    review_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # 处理时关键事实摘要(便于列表查看,不重复完整内容)
    title_snapshot: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    score_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    num_comments_snapshot: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    verdict_snapshot: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # CSV/Excel 导入时,直接存原始行数据(JSON),跳过 fetch_post
    # 字段: subreddit/title/selftext/score/num_comments/created_utc/author/url/comments_text
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    # 标记缺失字段(便于报告"数据完整度")
    missing_fields: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
