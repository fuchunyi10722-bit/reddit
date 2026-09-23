"""Retrieval: 独立召回层。

从社区数据中召回 ContentAnalyzer 需要的上下文:
- 社区规则
- 相似案例(high + failure 两档)
- 相关 KnowledgePattern
- CommunityProfile 摘要

Phase 2 起步用两档(high + failure),标签规则式召回(不依赖真实 embedding)。
后续可扩展四档 + 真实 embedding 召回。

核心原则:
- 不只召回爆款(必须包含 failure 案例)
- 不平均成总分(fire/search/failure 三类规律分别呈现)
- 上下文长度可控(可配参数)
- 证据可追溯(每条案例带 ReferenceItem.id)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.knowledge import KnowledgePattern, CommunityProfile


# ============================================================
# 召回结果结构
# ============================================================
@dataclass
class CaseSummary:
    """单条案例摘要(用于 LLM 上下文)。"""
    reference_item_id: str
    title: str
    selftext_preview: str  # 截断的正文
    score: int
    num_comments: int
    performance_tier: str  # high|mid|low|failure
    structure_tags: list[str]
    product_visibility: str
    search_value: str
    topic_tags: list[str]

    def to_context_line(self) -> str:
        """格式化为单行上下文(控制 token)。"""
        return (
            f"[{self.performance_tier}, score={self.score}, comments={self.num_comments}] "
            f"{self.title[:100]} | "
            f"structure={','.join(self.structure_tags)}, "
            f"product={self.product_visibility}, "
            f"search={self.search_value}, "
            f"topics={','.join(self.topic_tags[:3])}"
        )


@dataclass
class PatternSummary:
    """单条规律摘要。"""
    pattern_id: str
    pattern_type: str  # fire|search|failure
    description: str
    status: str  # candidate|supported|refuted|inconclusive
    sample_count: int

    def to_context_line(self) -> str:
        return (
            f"[{self.pattern_type}, status={self.status}, samples={self.sample_count}] "
            f"{self.description[:150]}"
        )


@dataclass
class RetrievalResult:
    """召回结果。"""
    # A. 社区规则
    rules_summary: dict = field(default_factory=dict)
    # B. 相似案例
    similar_high: list[CaseSummary] = field(default_factory=list)
    similar_failure: list[CaseSummary] = field(default_factory=list)
    # C. 相关 KnowledgePattern
    fire_patterns: list[PatternSummary] = field(default_factory=list)
    search_patterns: list[PatternSummary] = field(default_factory=list)
    failure_patterns: list[PatternSummary] = field(default_factory=list)
    # D. CommunityProfile 摘要
    community_summary: dict = field(default_factory=dict)
    # 召回的所有 ReferenceItem.id(用于校验 LLM 引用的 evidence_item_ids)
    all_retrieved_item_ids: set = field(default_factory=set)

    def build_llm_context(self, new_content: str) -> str:
        """构建 LLM 上下文(控制 token 长度)。"""
        lines: list[str] = []

        # 社区规则
        lines.append("=== COMMUNITY RULES ===")
        rules = self.rules_summary
        if rules:
            for key, val in rules.items():
                lines.append(f"{key}: {val}")
        else:
            lines.append("(no rules collected)")

        # CommunityProfile 摘要
        lines.append("\n=== COMMUNITY SUMMARY ===")
        cs = self.community_summary
        if cs:
            lines.append(f"top_topics: {cs.get('top_topics', [])}")
            lines.append(f"common_structures: {cs.get('common_structures', [])}")
            lines.append(f"product_acceptance: {cs.get('product_acceptance', {})}")
        else:
            lines.append("(no profile)")

        # 相似案例 — high
        lines.append("\n=== SIMILAR HIGH-PERFORMANCE CASES ===")
        if self.similar_high:
            for c in self.similar_high:
                lines.append(c.to_context_line())
        else:
            lines.append("(no high-performance cases retrieved)")

        # 相似案例 — failure
        lines.append("\n=== SIMILAR FAILURE/LOW CASES ===")
        if self.similar_failure:
            for c in self.similar_failure:
                lines.append(c.to_context_line())
        else:
            lines.append("(no failure cases retrieved)")

        # KnowledgePattern
        lines.append("\n=== KNOWLEDGE PATTERNS ===")
        all_patterns = self.fire_patterns + self.search_patterns + self.failure_patterns
        if all_patterns:
            for p in all_patterns:
                lines.append(p.to_context_line())
        else:
            lines.append("(no patterns)")

        # 新内容
        lines.append("\n=== NEW CONTENT TO ANALYZE ===")
        lines.append(new_content[:2000])

        return "\n".join(lines)


# ============================================================
# 召回逻辑
# ============================================================
def _build_case_summary(
    item: ReferenceItem,
    analysis: Optional[ContentAnalysis],
    perf: Optional[PerformanceAnalysis],
    tier_override: Optional[str] = None,
) -> CaseSummary:
    """构建案例摘要。"""
    preview = (item.selftext or "")[:200]
    tier = tier_override or (perf.performance_tier if perf else "unknown")

    # failure 判定:被删 / score < 0 / product_visibility=promotional
    if tier_override is None:
        if item.retention_status == "deleted":
            tier = "failure"
        elif item.score is not None and item.score < 0:
            tier = "failure"
        elif analysis and analysis.product_visibility == "promotional":
            tier = "failure"
        elif perf:
            tier = perf.performance_tier

    return CaseSummary(
        reference_item_id=item.id,
        title=item.title,
        selftext_preview=preview,
        score=item.score or 0,
        num_comments=item.num_comments or 0,
        performance_tier=tier,
        structure_tags=analysis.structure_tags if analysis else [],
        product_visibility=analysis.product_visibility if analysis else "none",
        search_value=analysis.search_value if analysis else "mid",
        topic_tags=analysis.topic_tags if analysis else [],
    )


def _tokenize(text: str) -> set[str]:
    """简单 token 化(小写、去标点、去停用词)。

    用于 new_content 与历史帖标题/正文的 token 重叠打分,
    补足 new_content_tags.keywords 缺失时的内容匹配能力。
    """
    import re
    if not text:
        return set()
    text_lower = text.lower()
    # 去标点
    text_clean = re.sub(r"[^\w\s]", " ", text_lower)
    words = [w for w in text_clean.split() if w]
    # 停用词(英文)
    stop = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "i", "my", "me", "we", "you", "your", "he", "she", "it", "they",
        "to", "in", "on", "for", "with", "of", "at", "by", "from", "and",
        "or", "but", "this", "that", "these", "those", "do", "does", "did",
        "how", "what", "why", "when", "where", "which", "can", "should",
    }
    return {w for w in words if w not in stop and len(w) > 2}


def _retrieve_by_tags(
    subreddit: str,
    new_content: str,
    new_content_tags: dict,
    tier_filter: str,
    limit: int,
) -> list[tuple[ReferenceItem, ContentAnalysis, PerformanceAnalysis]]:
    """标签规则式召回(Phase 2 起步,不依赖真实 embedding)。

    匹配优先级:
    1. topic_tags 交集(权重 3)
    2. structure_tags 交集(权重 2)
    3. scenario_tags 交集(权重 2)
    4. new_content token 与历史帖标题/正文 token 重叠(权重 1)
    5. 关键词显式匹配(new_content_tags.keywords,权重 1)

    内容匹配的加入,让相同标签但不同具体内容的 new_content,
    也能召回不同的 similar 案例,而不是只按 tier+tags 召回。
    """
    with get_session() as s:
        query = (
            s.query(ReferenceItem, ContentAnalysis, PerformanceAnalysis)
            .join(ContentAnalysis, ContentAnalysis.reference_item_id == ReferenceItem.id)
            .join(PerformanceAnalysis, PerformanceAnalysis.reference_item_id == ReferenceItem.id)
            .filter(ReferenceItem.subreddit == subreddit)
            .filter(ContentAnalysis.is_current == True)
            .filter(PerformanceAnalysis.is_current == True)
        )

        if tier_filter == "high":
            query = query.filter(PerformanceAnalysis.performance_tier == "high")
        elif tier_filter == "failure":
            query = query.filter(
                (ReferenceItem.retention_status == "deleted")
                | (ReferenceItem.score < 0)
                | (ContentAnalysis.product_visibility == "promotional")
                | (PerformanceAnalysis.performance_tier == "low")
            )
        else:
            query = query.filter(PerformanceAnalysis.performance_tier == tier_filter)

        rows = query.all()

        new_topics = set(new_content_tags.get("topic_tags", []))
        new_structures = set(new_content_tags.get("structure_tags", []))
        new_scenarios = set(new_content_tags.get("scenario_tags", []))
        new_keywords = set(new_content_tags.get("keywords", []))
        new_tokens = _tokenize(new_content)

        scored: list[tuple[int, tuple]] = []
        for item, analysis, perf in rows:
            score = 0
            item_topics = set(analysis.topic_tags or [])
            score += len(new_topics & item_topics) * 3
            item_structures = set(analysis.structure_tags or [])
            score += len(new_structures & item_structures) * 2
            item_scenarios = set(analysis.scenario_tags or [])
            score += len(new_scenarios & item_scenarios) * 2

            # new_content token 重叠(标题 + 正文)
            item_text = f"{item.title or ''} {item.selftext or ''}"
            item_tokens = _tokenize(item_text)
            score += len(new_tokens & item_tokens)

            # 显式 keywords 匹配
            text_lower = item_text.lower()
            for kw in new_keywords:
                if kw.lower() in text_lower:
                    score += 1

            scored.append((score, (item, analysis, perf)))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [t[1] for t in scored[:limit]]


def retrieve_for_analysis(
    subreddit: str,
    new_content: str,
    new_content_tags: dict,
    high_count: int = 3,
    failure_count: int = 2,
    pattern_count: int = 3,
) -> RetrievalResult:
    """为新内容分析召回上下文。

    Args:
        subreddit: 目标社区
        new_content: 用户准备发布的内容(标题+正文)
        new_content_tags: 新内容的标签(由 Classifier 产出)
        high_count: 召回 high 表现案例数
        failure_count: 召回 failure 案例数
        pattern_count: 召回规律数(每类)

    Returns:
        RetrievalResult
    """
    result = RetrievalResult()

    with get_session() as s:
        # A. 社区规则
        profile = s.query(CommunityProfile).filter_by(subreddit=subreddit).first()
        if profile:
            result.rules_summary = profile.rules_summary or {}
            result.community_summary = {
                "top_topics": profile.top_topics or [],
                "common_structures": profile.common_structures or [],
                "product_acceptance": profile.product_acceptance or {},
            }
        else:
            result.rules_summary = {"note": "community not initialized"}

        # B. 相似案例 — high
        high_rows = _retrieve_by_tags(subreddit, new_content, new_content_tags, "high", high_count)
        for item, analysis, perf in high_rows:
            result.similar_high.append(
                _build_case_summary(item, analysis, perf, tier_override="high")
            )
            result.all_retrieved_item_ids.add(item.id)

        # B. 相似案例 — failure
        failure_rows = _retrieve_by_tags(subreddit, new_content, new_content_tags, "failure", failure_count)
        for item, analysis, perf in failure_rows:
            result.similar_failure.append(
                _build_case_summary(item, analysis, perf, tier_override="failure")
            )
            result.all_retrieved_item_ids.add(item.id)

        # C. 相关 KnowledgePattern
        # 注意:KnowledgePattern 没有 subreddit 列,只能用 applicable_conditions 中的
        # subreddit 字段做内存过滤(确保不召回其他社区的规律)。
        def _matches_sub(p: KnowledgePattern) -> bool:
            cond = p.applicable_conditions or {}
            return cond.get("subreddit") == subreddit

        # fire 规律
        fire_patterns = [
            p for p in (
                s.query(KnowledgePattern)
                .filter(KnowledgePattern.pattern_type == "fire")
                .filter(KnowledgePattern.status.in_(["candidate", "supported"]))
                .order_by(KnowledgePattern.created_at.desc())
                .all()
            ) if _matches_sub(p)
        ][:pattern_count]
        for p in fire_patterns:
            result.fire_patterns.append(PatternSummary(
                pattern_id=p.id,
                pattern_type=p.pattern_type,
                description=p.description,
                status=p.status,
                sample_count=p.sample_count,
            ))

        # search 规律
        search_patterns = [
            p for p in (
                s.query(KnowledgePattern)
                .filter(KnowledgePattern.pattern_type == "search")
                .filter(KnowledgePattern.status.in_(["candidate", "supported"]))
                .order_by(KnowledgePattern.created_at.desc())
                .all()
            ) if _matches_sub(p)
        ][:pattern_count]
        for p in search_patterns:
            result.search_patterns.append(PatternSummary(
                pattern_id=p.id,
                pattern_type=p.pattern_type,
                description=p.description,
                status=p.status,
                sample_count=p.sample_count,
            ))

        # failure 规律
        failure_patterns = [
            p for p in (
                s.query(KnowledgePattern)
                .filter(KnowledgePattern.pattern_type == "failure")
                .filter(KnowledgePattern.status.in_(["candidate", "supported"]))
                .order_by(KnowledgePattern.created_at.desc())
                .all()
            ) if _matches_sub(p)
        ][:pattern_count]
        for p in failure_patterns:
            result.failure_patterns.append(PatternSummary(
                pattern_id=p.id,
                pattern_type=p.pattern_type,
                description=p.description,
                status=p.status,
                sample_count=p.sample_count,
            ))

    return result


def filter_retrieved_cases(
    retrieval: RetrievalResult,
    excluded_ids: set[str],
) -> RetrievalResult:
    """人工过滤召回结果(移除明显不相关的案例)。

    人工兜底入口:用户可以标记某些召回案例不相关,系统移除它们。
    """
    retrieval.similar_high = [
        c for c in retrieval.similar_high if c.reference_item_id not in excluded_ids
    ]
    retrieval.similar_failure = [
        c for c in retrieval.similar_failure if c.reference_item_id not in excluded_ids
    ]
    retrieval.all_retrieved_item_ids -= excluded_ids
    return retrieval
