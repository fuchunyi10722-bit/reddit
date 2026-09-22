"""Embedding:独立基础设施。与实体解耦,重算时整体替换,不影响 ReferenceItem/Comment。

第一阶段沙箱无 pgvector,向量以 JSON 存(召回时用余弦相似度计算)。
生产切 PostgreSQL 时改 vector 列类型。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class Embedding(Base):
    """向量与实体解耦。

    entity_type:
      reference_item — 引用 ReferenceItem.id
      comment        — 引用 Comment.id
    """

    __tablename__ = "embeddings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    entity_type: Mapped[str] = mapped_column(String(32), index=True)  # reference_item|comment
    entity_id: Mapped[str] = mapped_column(String(36), index=True)
    embedding_model: Mapped[str] = mapped_column(String(64))
    # 沙箱:JSON 存向量;生产:pgvector.Vector(dim)
    vector: Mapped[list] = mapped_column(JSON)  # 第一阶段用 JSON,召回时余弦计算
    text_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # 源文本 hash,避免重复计算
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
