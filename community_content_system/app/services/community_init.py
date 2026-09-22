"""社区初始化流水线。

流程(确认后版本):
1. fetch_subreddit_about → 验证社区存在
2. fetch_rules → 提取规则
3. 拉 Top/Hot/New(不含 Search)
4. Parser → ReferenceItem 落库
5. PerformanceClassifier → high/mid/low 分层
6. Classifier → ContentAnalysis 打标签
7. Embedding 生成
8. 主题/场景识别(基于 ContentAnalysis 聚合)
9. 生成候选搜索词(基于高频 topic_tags)
10. Search 补充采集(此时已有主题认知)
11. 评论选择性深采(规则式采样)
12. PatternMiner → KnowledgePattern 候选规律
13. CommunityProfile 落库

关键:Search 在主题识别后(Step 10)进入,基于高频 topic_tags 生成搜索词,
不是预先猜关键词。
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from typing import Optional

from ..adapters import get_adapter
from ..adapters.base import RawRulesDTO, RawSubredditMetaDTO
from ..config import settings
from ..database import get_session
from ..models.raw import RawRules, RawSubredditMeta
from ..models.reference import ReferenceItem, Comment
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.knowledge import KnowledgePattern, CommunityProfile
from . import parser, performance, classifier, sampler, embedder, pattern_miner


def _generate_search_queries(item_ids: list[str], top_k: int = 3) -> list[str]:
    """基于高频 topic_tags + 用户问题型标题生成候选搜索词。"""
    with get_session() as s:
        topic_counter = Counter()
        question_titles = []
        for iid in item_ids:
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=iid, is_current=True
            ).first()
            if ca:
                for t in ca.topic_tags:
                    if t != "general":
                        topic_counter[t] += 1
            item = s.query(ReferenceItem).filter_by(id=iid).first()
            if item and re.match(r"^(how|what|why|when|where|which|can|is|are)\b", item.title, re.IGNORECASE):
                # 取问题型标题的关键词
                words = re.sub(r"[^\w\s]", "", item.title.lower()).split()
                question_words = [w for w in words if w not in ("how", "what", "why", "the", "a", "an", "is", "are", "do", "does", "i", "my", "me", "to", "in", "on", "for", "and", "or")]
                if len(question_words) >= 2:
                    question_titles.append(" ".join(question_words[:3]))

        queries = []
        # 高频 topic
        for topic, _ in topic_counter.most_common(top_k):
            queries.append(topic.replace("_", " "))
        # 问题型标题关键词
        for qt in question_titles[:top_k]:
            if qt not in queries:
                queries.append(qt)
        return queries[:top_k] if queries else ["programming"]


def _aggregate_topics(item_ids: list[str], top_k: int = 10) -> list[dict]:
    """聚合 ContentAnalysis.topic_tags → 主题分布。"""
    counter = Counter()
    with get_session() as s:
        for iid in item_ids:
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=iid, is_current=True
            ).first()
            if ca:
                for t in ca.topic_tags:
                    counter[t] += 1
    return [{"topic": t, "count": c} for t, c in counter.most_common(top_k)]


def _aggregate_structures(item_ids: list[str], top_k: int = 10) -> list[dict]:
    """聚合 ContentAnalysis.structure_tags → 结构分布。"""
    counter = Counter()
    with get_session() as s:
        for iid in item_ids:
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=iid, is_current=True
            ).first()
            if ca:
                for t in ca.structure_tags:
                    counter[t] += 1
    return [{"structure": t, "count": c} for t, c in counter.most_common(top_k)]


def _aggregate_product_acceptance(item_ids: list[str]) -> dict:
    """聚合 product_visibility 分布(按 tier)。"""
    result = {"high": {}, "mid": {}, "low": {}, "unknown": {}}
    with get_session() as s:
        for iid in item_ids:
            ca = s.query(ContentAnalysis).filter_by(
                reference_item_id=iid, is_current=True
            ).first()
            pa = s.query(PerformanceAnalysis).filter_by(
                reference_item_id=iid, is_current=True
            ).first()
            tier = pa.performance_tier if pa else "unknown"
            pv = ca.product_visibility if ca else "none"
            result.setdefault(tier, {})
            result[tier][pv] = result[tier].get(pv, 0) + 1
    return result


def _extract_comment_patterns(subreddit: str) -> list[dict]:
    """评论模式提取(第一阶段简易:统计高频评论开头词)。"""
    counter = Counter()
    with get_session() as s:
        comments = s.query(Comment).filter_by(subreddit=subreddit).all()
        for c in comments:
            body = c.body.strip().lower()
            if body:
                first_words = " ".join(body.split()[:3])
                counter[first_words] += 1
    return [{"pattern": p, "count": c} for p, c in counter.most_common(10) if c >= 2]


def init_community(subreddit: str) -> CommunityProfile:
    """社区初始化完整流程。

    返回 CommunityProfile。
    """
    adapter = get_adapter()
    adapter_name = adapter.adapter_name

    # Step 1: 验证社区存在
    about_dto = adapter.fetch_subreddit_about(subreddit)
    with get_session() as s:
        raw_meta = RawSubredditMeta(
            source_adapter=adapter_name,
            subreddit=subreddit,
            raw_payload=about_dto.raw_payload,
        )
        s.add(raw_meta)

    # Step 2: 规则
    rules_dto = adapter.fetch_rules(subreddit)
    with get_session() as s:
        raw_rules = RawRules(
            source_adapter=adapter_name,
            subreddit=subreddit,
            raw_payload=rules_dto.raw_payload,
        )
        s.add(raw_rules)

    rules_summary = {
        "rules": rules_dto.rules,
        "karma_requirement": rules_dto.karma_requirement,
        "account_age_requirement": rules_dto.account_age_requirement,
        "flair_required": rules_dto.flair_required,
        "link_restricted": rules_dto.link_restricted,
        "commercial_content_restricted": rules_dto.commercial_content_restricted,
        "post_frequency_limit": rules_dto.post_frequency_limit,
        "sensitive_content_rules": rules_dto.sensitive_content_rules,
    }

    # Step 3: 拉 Top/Hot/New(不含 Search)
    all_refs = []
    top_listing = adapter.fetch_listing(subreddit, "top", time_filter="month", limit=settings.init_top_limit)
    top_refs = parser.ingest_listing(top_listing, adapter_name)
    all_refs.extend(top_refs)

    hot_listing = adapter.fetch_listing(subreddit, "hot", limit=settings.init_hot_limit)
    hot_refs = parser.ingest_listing(hot_listing, adapter_name)
    all_refs.extend(hot_refs)

    new_listing = adapter.fetch_listing(subreddit, "new", limit=settings.init_new_limit)
    new_refs = parser.ingest_listing(new_listing, adapter_name)
    all_refs.extend(new_refs)

    # 去重(按 source_post_id)
    seen = set()
    unique_refs = []
    for r in all_refs:
        if r.source_post_id not in seen:
            seen.add(r.source_post_id)
            unique_refs.append(r)
    all_ref_ids = [r.id for r in unique_refs]

    # Step 4: PerformanceClassifier 分层
    performance.tier_items(subreddit, all_ref_ids)

    # Step 5: Classifier 打标签
    classifier.label_items(all_ref_ids)

    # Step 6: Embedding 生成
    for ref in unique_refs:
        text = f"{ref.title}\n{ref.selftext}"
        embedder.generate_embedding("reference_item", ref.id, text)

    # Step 7: 主题/场景识别(基于 ContentAnalysis 聚合)
    top_topics = _aggregate_topics(all_ref_ids)
    common_structures = _aggregate_structures(all_ref_ids)

    # Step 8: 生成候选搜索词(基于高频 topic_tags)
    search_queries = _generate_search_queries(all_ref_ids, top_k=settings.init_search_query_count)

    # Step 9: Search 补充采集(此时已有主题认知)
    search_refs = []
    for q in search_queries:
        search_listing = adapter.search(subreddit, q, sort="relevance", limit=settings.init_search_limit)
        s_refs = parser.ingest_listing(search_listing, adapter_name)
        search_refs.extend(s_refs)

    # Search 结果去重 + 合并
    search_new_ids = []
    for r in search_refs:
        if r.source_post_id not in seen:
            seen.add(r.source_post_id)
            search_new_ids.append(r.id)
            unique_refs.append(r)

    # 对 Search 新增的帖子也分层 + 打标签 + embedding
    if search_new_ids:
        performance.tier_items(subreddit, search_new_ids)
        classifier.label_items(search_new_ids)
        for r in search_refs:
            if r.id in search_new_ids:
                text = f"{r.title}\n{r.selftext}"
                embedder.generate_embedding("reference_item", r.id, text)

    all_ref_ids_final = [r.id for r in unique_refs]

    # Step 10: 评论选择性深采(规则式采样)
    selected_post_ids = sampler.select_posts_for_deep_fetch(subreddit)
    for post_id in selected_post_ids:
        item = None
        with get_session() as s:
            item = s.query(ReferenceItem).filter_by(id=post_id).first()
        if not item:
            continue
        comment_dtos = adapter.fetch_comments(
            item.source_post_id, sort=settings.per_post_comment_sort,
            limit=settings.per_post_comment_limit,
        )
        for cdto in comment_dtos:
            parser.ingest_raw_comment(cdto, adapter_name, post_id)

    # Step 11: PatternMiner 提炼候选规律
    patterns = pattern_miner.mine_patterns(subreddit, all_ref_ids_final)
    high_pattern_ids = [p.id for p in patterns if p.pattern_type == "fire"]
    low_pattern_ids = [p.id for p in patterns if p.pattern_type == "failure"]
    search_pattern_ids = [p.id for p in patterns if p.pattern_type == "search"]

    # Step 12: 评论模式
    comment_patterns = _extract_comment_patterns(subreddit)

    # Step 13: Product acceptance 聚合
    product_acceptance = _aggregate_product_acceptance(all_ref_ids_final)

    # Step 14: CommunityProfile 落库
    with get_session() as s:
        existing = s.query(CommunityProfile).filter_by(subreddit=subreddit).first()
        if existing:
            profile = existing
        else:
            profile = CommunityProfile(subreddit=subreddit)
            s.add(profile)
            s.flush()

        profile.rules_summary = rules_summary
        profile.subscriber_count = about_dto.subscriber_count
        profile.created_utc = about_dto.created_utc
        profile.subreddit_type = about_dto.subreddit_type
        profile.top_topics = top_topics
        profile.common_structures = common_structures
        profile.common_comment_patterns = comment_patterns
        profile.high_performance_pattern_ids = high_pattern_ids
        profile.low_performance_pattern_ids = low_pattern_ids
        profile.search_content_pattern_ids = search_pattern_ids
        profile.product_acceptance = product_acceptance
        profile.init_budget_used = {
            "top": len(top_refs), "hot": len(hot_refs), "new": len(new_refs),
            "search_queries": search_queries, "search_new": len(search_new_ids),
            "comments_deep_fetched": len(selected_post_ids),
            "total_unique_posts": len(all_ref_ids_final),
            "patterns_mined": len(patterns),
        }
        profile.last_initialized_at = datetime.utcnow()
        profile.last_refreshed_at = datetime.utcnow()
        s.flush()

    return profile
