"""原始事实层:Adapter 拉回的原始数据镜像,不可被 AI 改写。

RedditAdapter 拿到的 Reddit API 原始 JSON 全文存这里,
FileAdapter 拿到的 fixture JSON 同样存这里。下游 Parser 从这里读出 → ReferenceItem。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RawPost(Base):
    """原始帖子镜像。schema 与 Reddit API 响应一致。"""

    __tablename__ = "raw_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)  # reddit|file|manual|excel
    source_post_id: Mapped[str] = mapped_column(String(64), index=True)  # t3_xxx fullname
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)  # Reddit API 原始响应全文
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    raw_schema_version: Mapped[str] = mapped_column(String(32), default="reddit_api_v1")


class RawComment(Base):
    """原始评论镜像。独立于 RawPost 存,通过 source_post_id 关联。"""

    __tablename__ = "raw_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)
    source_comment_id: Mapped[str] = mapped_column(String(64), index=True)  # t1_xxx
    source_post_id: Mapped[str] = mapped_column(String(64), index=True)  # 所属 t3_xxx
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RawRules(Base):
    """社区规则原始镜像。"""

    __tablename__ = "raw_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RawSubredditMeta(Base):
    """社区元信息原始镜像。"""

    __tablename__ = "raw_subreddit_meta"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_adapter: Mapped[str] = mapped_column(String(32), index=True)
    subreddit: Mapped[str] = mapped_column(String(128), index=True)
    raw_payload: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
