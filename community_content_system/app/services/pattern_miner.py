"""PatternMiner:从多个案例提炼候选规律。

第一阶段:
- 产出候选规律(status=candidate)
- 关联 evidence_item_ids / evidence_analysis_ids
- 单个案例只追加 validation_history,不直接改 status
- 状态迁移需累计证据达阈值(confirmed>=3 且 contradicted=0 → supported)

不做可信度数值,只跑状态迁移。
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.knowledge import KnowledgePattern


def _gather_evidence(items: list[ReferenceItem], tier: str) -> list[dict]:
    """收集某 tier 的证据(帖子 + 标签视角)。"""
    evidence = []
    with get_session() as s:
        for item in items:
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=item.id, is_current=True
            ).first()
            if ca:
                evidence.append({
                    "item_id": item.id,
                    "title": item.title[:80],
                    "score": item.score,
                    "structure_tags": ca.structure_tags,
                    "product_visibility": ca.product_visibility,
                    "search_value": ca.search_value,
                    "topic_tags": ca.topic_tags,
                })
    return evidence


def _mine_patterns_for_tier(
    subreddit: str, items: list[ReferenceItem], tier: str
) -> list[dict]:
    """对某 tier 的帖子提炼候选规律(第一阶段规则式)。"""
    evidence = _gather_evidence(items, tier)
    if len(evidence) < 2:
        return []

    patterns = []

    # 结构规律:统计 structure_tags 分布
    struct_counts = {}
    for e in evidence:
        for tag in e["structure_tags"]:
            struct_counts[tag] = struct_counts.get(tag, 0) + 1
    top_struct = max(struct_counts, key=struct_counts.get) if struct_counts else None
    if top_struct:
        patterns.append({
            "pattern_type": "fire" if tier == "high" else ("failure" if tier == "low" else "fire"),
            "description": f"{tier} tier 帖子中,{top_struct} 结构出现 {struct_counts[top_struct]}/{len(evidence)} 次。"
                           f"代表性帖子: {evidence[0]['title']}",
            "applicable_conditions": {
                "subreddit": subreddit,
                "tier": tier,
                "structure": top_struct,
            },
            "evidence": evidence,
        })

    # 产品可见性规律(高/低 tier 对比)
    prod_counts = {}
    for e in evidence:
        pv = e.get("product_visibility", "none") or "none"
        prod_counts[pv] = prod_counts.get(pv, 0) + 1
    if "promotional" in prod_counts:
        patterns.append({
            "pattern_type": "failure",
            "description": f"{tier} tier 中存在 promotional 内容({prod_counts['promotional']}/{len(evidence)}),"
                           "在部分社区中更容易被认为是推广内容。",
            "applicable_conditions": {
                "subreddit": subreddit,
                "tier": tier,
                "product_visibility": "promotional",
            },
            "evidence": [e for e in evidence if e.get("product_visibility") == "promotional"],
        })

    return patterns


def _mine_search_patterns(subreddit: str, items: list[ReferenceItem]) -> list[dict]:
    """搜索型内容规律:基于 search_value=high 的帖子共性。"""
    evidence = _gather_evidence(items, "high")
    search_high = [e for e in evidence if e.get("search_value") == "high"]
    if len(search_high) < 2:
        return []

    # 统计高搜索价值帖子的结构特征
    struct_counts = {}
    for e in search_high:
        for tag in e["structure_tags"]:
            struct_counts[tag] = struct_counts.get(tag, 0) + 1

    patterns = []
    if struct_counts:
        top_struct = max(struct_counts, key=struct_counts.get)
        patterns.append({
            "pattern_type": "search",
            "description": f"高搜索价值(search_value=high)帖子中,{top_struct} 结构出现 "
                           f"{struct_counts[top_struct]}/{len(search_high)} 次。"
                           "更接近用户搜索语言 + 完整回答具体问题。",
            "applicable_conditions": {
                "subreddit": subreddit,
                "search_value": "high",
                "structure": top_struct,
            },
            "evidence": search_high,
        })
    return patterns


def mine_patterns(subreddit: str, item_ids: list[str]) -> list[KnowledgePattern]:
    """对该社区的帖子提炼候选规律。

    流程:
    1. 按 tier 分组(high/mid/low)
    2. 各 tier 提炼结构规律
    3. 搜索型内容规律
    4. 落库为 KnowledgePattern(status=candidate)
    """
    with get_session() as s:
        items = s.query(ReferenceItem).filter(
            ReferenceItem.id.in_(item_ids)
        ).all()
        if not items:
            return []

        # 按 tier 分组
        tier_items = {"high": [], "mid": [], "low": []}
        for item in items:
            pa = s.query(PerformanceAnalysis).filter_by(
                reference_item_id=item.id, is_current=True
            ).first()
            tier = pa.performance_tier if pa else "mid"
            if tier in tier_items:
                tier_items[tier].append(item)

        all_patterns_raw = []
        for tier in ["high", "mid", "low"]:
            all_patterns_raw.extend(_mine_patterns_for_tier(subreddit, tier_items[tier], tier))
        all_patterns_raw.extend(_mine_search_patterns(subreddit, tier_items.get("high", [])))

        # 落库
        results = []
        for p in all_patterns_raw:
            evidence = p.pop("evidence", [])
            evidence_item_ids = [e["item_id"] for e in evidence]
            # 取这些帖子的当前 ContentAnalysis.id 作为 evidence_analysis_ids
            evidence_analysis_ids = []
            for e in evidence:
                ca = s.query(ContentAnalysis).filter_by(
                    reference_item_id=e["item_id"], is_current=True
                ).first()
                if ca:
                    evidence_analysis_ids.append(ca.id)

            kp = KnowledgePattern(
                pattern_type=p["pattern_type"],
                description=p["description"],
                applicable_conditions=p["applicable_conditions"],
                evidence_item_ids=evidence_item_ids,
                evidence_analysis_ids=evidence_analysis_ids,
                sample_count=len(evidence),
                status="candidate",
                validation_history=[],
                source_review_ids=[],
                created_at=datetime.utcnow(),
            )
            s.add(kp)
            results.append(kp)
        s.flush()
        return results


def record_validation(
    pattern_id: str,
    case_item_id: str,
    outcome: str,  # confirmed | contradicted | inconclusive
    review_id: Optional[str] = None,
    note: str = "",
) -> KnowledgePattern:
    """新案例验证:只追加 validation_history,不改 status。

    状态迁移由 update_pattern_status 单独触发(需累计达阈值)。
    """
    with get_session() as s:
        kp = s.query(KnowledgePattern).filter_by(id=pattern_id).first()
        if not kp:
            raise ValueError(f"KnowledgePattern 不存在: {pattern_id}")

        entry = {
            "case_item_id": case_item_id,
            "outcome": outcome,
            "review_id": review_id,
            "validated_at": datetime.utcnow().isoformat(),
            "note": note,
        }
        # 追加(不改旧记录)
        history = list(kp.validation_history or [])
        history.append(entry)
        kp.validation_history = history
        kp.last_validated_at = datetime.utcnow()

        if review_id and review_id not in (kp.source_review_ids or []):
            reviews = list(kp.source_review_ids or [])
            reviews.append(review_id)
            kp.source_review_ids = reviews
        s.flush()
        return kp


def update_pattern_status(pattern_id: str) -> KnowledgePattern:
    """根据累计 validation_history 判断是否迁移状态。

    第一阶段阈值(可配):
    confirmed >= promote_threshold 且 contradicted = 0 → supported
    contradicted >= refute_threshold 且 confirmed = 0 → refuted
    confirmed 与 contradicted 同时存在 → inconclusive
    其余 → 保持 candidate
    """
    with get_session() as s:
        kp = s.query(KnowledgePattern).filter_by(id=pattern_id).first()
        if not kp:
            raise ValueError(f"KnowledgePattern 不存在: {pattern_id}")
        if kp.status not in ("candidate",):
            # 已 supported/refuted 的第一阶段不再自动迁移回 candidate
            return kp

        history = kp.validation_history or []
        confirmed = sum(1 for h in history if h.get("outcome") == "confirmed")
        contradicted = sum(1 for h in history if h.get("outcome") == "contradicted")
        inconclusive = sum(1 for h in history if h.get("outcome") == "inconclusive")

        if confirmed >= settings.pattern_promote_threshold and contradicted == 0:
            kp.status = "supported"
        elif contradicted >= settings.pattern_refute_threshold and confirmed == 0:
            kp.status = "refuted"
        elif confirmed > 0 and contradicted > 0:
            kp.status = "inconclusive"
        # 否则保持 candidate
        s.flush()
        return kp


def get_patterns_for_subreddit(subreddit: str, status: Optional[str] = None) -> list[KnowledgePattern]:
    """获取某社区的规律。"""
    with get_session() as s:
        q = s.query(KnowledgePattern).filter(
            KnowledgePattern.applicable_conditions.contains({"subreddit": subreddit})
        )
        if status:
            q = q.filter_by(status=status)
        return q.all()
