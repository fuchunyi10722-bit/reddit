"""Embedding 生成。

第一阶段沙箱无 embedding API,用简易哈希向量模拟(保证流程跑通)。
生产环境切真实 embedding(text-embedding-3-small 等),改 _generate 即可。
实体与向量解耦,重算时整体替换。
"""

from __future__ import annotations

import hashlib
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.embedding import Embedding


def _generate_simple_vector(text: str) -> list[float]:
    """简易向量:用文本 hash 生成固定维度向量(模拟,非真实语义)。

    仅用于第一阶段沙箱跑通流程。生产环境替换为真实 embedding API。
    """
    dim = settings.embedding_dim
    vec = [0.0] * dim
    for i in range(0, min(len(text), 500)):
        h = int(hashlib.md5((text + str(i)).encode()).hexdigest(), 16)
        vec[h % dim] += (h % 100) / 100.0
    # 归一化
    norm = sum(v * v for v in vec) ** 0.5
    if norm > 0:
        vec = [v / norm for v in vec]
    return vec


def generate_embedding(entity_type: str, entity_id: str, text: str) -> Embedding:
    """为实体生成 embedding 并落库。

    entity_type: reference_item | comment
    entity_id: ReferenceItem.id 或 Comment.id
    """
    text_hash = hashlib.sha256(text.encode()).hexdigest()
    with get_session() as s:
        # 文本未变则跳过
        existing = s.query(Embedding).filter_by(
            entity_type=entity_type, entity_id=entity_id, text_hash=text_hash
        ).first()
        if existing:
            return existing

        vec = _generate_simple_vector(text)
        emb = Embedding(
            entity_type=entity_type,
            entity_id=entity_id,
            embedding_model="simple_hash_v0.1",  # 生产改 settings.embedding_model
            vector=vec,
            text_hash=text_hash,
        )
        s.add(emb)
        s.flush()
        return emb


def find_similar(text: str, entity_type: str = "reference_item", top_k: int = 10) -> list[tuple[str, float]]:
    """余弦相似度召回 Top-K。

    第一阶段沙箱:遍历计算(数据量小)。生产:pgvector <=> 操作。
    """
    query_vec = _generate_simple_vector(text)
    with get_session() as s:
        embs = s.query(Embedding).filter_by(entity_type=entity_type).all()
        scored = []
        for e in embs:
            sim = sum(a * b for a, b in zip(query_vec, e.vector))
            scored.append((e.entity_id, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
