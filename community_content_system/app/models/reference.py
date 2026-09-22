"""结构化事实层:从 RawPost 解析得到,纯事实,不含 AI 标签。

事实字段(ups/score/created_utc)不可被 AI 改写。
合规字段(fetched_at/deleted_at/retention_status)由 retention job 维护,第一版仅预留。
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


class ReferenceItem(Base):
    """一条内容的结构化事实。不含 AI 标签、不含评论、不含 embedding。"""

    __tablename__ = "reference_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_post_id: Mapped[str] = mapped_column(String(64), index=True)  # t3_xxx
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)
    raw_post_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("raw_posts.id"), nullable=True)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    permalink: Mapped[str] = mapped_column(Text)

    # 内容事实
    title: Mapped[str] = mapped_column(Text)
    selftext: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    is_self: Mapped[bool] = mapped_column(Boolean, default=False)
    post_hint: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # image|link|video|self
    domain: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    flair_text: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    flair_template_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_utc: Mapped[float] = mapped_column(Float, index=True)

    # 表现数据(事实层)
    ups: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    upvote_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    num_comments: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # 内容形式(事实分类,非 AI 标签)
    content_form: Mapped[str] = mapped_column(String(32), default="text")  # text|image|video|link|poll

    # 合规字段(第一版预留,retention job 第一阶段不实现)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retention_status: Mapped[str] = mapped_column(String(32), default="active")  # active|pending_deletion|deleted


class Comment(Base):
    """独立评论实体。通过 parent_post_id 关联 ReferenceItem,可独立查询/保留/删除。"""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_comment_id: Mapped[str] = mapped_column(String(64), index=True)  # t1_xxx
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)
    raw_comment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("raw_comments.id"), nullable=True)
    parent_post_id: Mapped[str] = mapped_column(String(36), ForeignKey("reference_items.id"), index=True)
    parent_comment_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("comments.id"), nullable=True)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    author: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    body: Mapped[str] = mapped_column(Text, default="")
    score: Mapped[int] = mapped_column(Integer, default=0)
    created_utc: Mapped[float] = mapped_column(Float)
    depth: Mapped[int] = mapped_column(Integer, default=0)

    # 合规字段
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    retention_status: Mapped[str] = mapped_column(String(32), default="active")
