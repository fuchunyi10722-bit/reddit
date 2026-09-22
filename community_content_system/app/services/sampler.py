"""评论规则式采样器:多维度覆盖,不锁死 30/30/30。

采样优先级:
1. 高/中/低表现层级覆盖(比例可配,默认 0.4/0.4/0.2)
2. 内容类型覆盖(text/image/video/link 各有代表)
3. 与社区主要主题/场景相关
4. 避免样本高度同质化:
   - 同一作者最多 N 帖
   - 相似标题(embedding cosine > 阈值)只保留 1 帖
   - 时间分桶,每桶最多 M 帖(避免事件驱动扎堆)

第一阶段实现规则式,不做复杂加权算法。
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.reference import ReferenceItem
from ..models.analysis import PerformanceAnalysis


@dataclass
class SampleBudget:
    total: int = 90
    tier_high_ratio: float = 0.4
    tier_mid_ratio: float = 0.4
    tier_low_ratio: float = 0.2
    per_post_comment_limit: int = 20
    per_post_comment_sort: str = "top"
    max_per_author: int = 2
    title_similarity_threshold: float = 0.9
    time_bucket_hours: int = 6
    max_per_bucket: int = 5


def _cosine_simple(a: str, b: str) -> float:
    """简易文本相似度(基于词集 Jaccard)。第一阶段不依赖 embedding。"""
    sa, sb = set(a.lower().split()), set(b.lower().split())
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _time_bucket(ts: float, hours: int) -> int:
    return int(ts // (hours * 3600))


def select_posts_for_deep_fetch(
    subreddit: str,
    budget: Optional[SampleBudget] = None,
) -> list[str]:
    """从该社区已分层的帖子中选出代表性帖子 ID,用于评论深采。

    返回 ReferenceItem.id 列表。
    """
    budget = budget or SampleBudget(
        total=settings.comment_deep_fetch_total,
        tier_high_ratio=settings.tier_allocation_high,
        tier_mid_ratio=settings.tier_allocation_mid,
        tier_low_ratio=settings.tier_allocation_low,
        per_post_comment_limit=settings.per_post_comment_limit,
        per_post_comment_sort=settings.per_post_comment_sort,
        max_per_author=settings.sample_max_per_author,
        title_similarity_threshold=settings.sample_title_similarity_threshold,
        time_bucket_hours=settings.sample_time_bucket_hours,
        max_per_bucket=settings.sample_max_per_bucket,
    )

    with get_session() as s:
        # 取该社区已分层的帖子 + 当前 tier
        items = s.query(ReferenceItem).filter_by(
            subreddit=subreddit, retention_status="active"
        ).all()
        item_map = {i.id: i for i in items}
        tier_map = {}
        for i in items:
            pa = s.query(PerformanceAnalysis).filter_by(
                reference_item_id=i.id, is_current=True
            ).first()
            tier_map[i.id] = pa.performance_tier if pa else "mid"

        # 按 tier 分组
        by_tier = {"high": [], "mid": [], "low": []}
        for i in items:
            t = tier_map.get(i.id, "mid")
            if t in by_tier:
                by_tier[t].append(i)

        # 各 tier 配额
        quotas = {
            "high": int(budget.total * budget.tier_high_ratio),
            "mid": int(budget.total * budget.tier_mid_ratio),
            "low": int(budget.total * budget.tier_low_ratio),
        }
        # 兜底:若某 tier 不够,把配额分给其他 tier
        for t in ["high", "mid", "low"]:
            if len(by_tier[t]) < quotas[t]:
                overflow = quotas[t] - len(by_tier[t])
                quotas[t] = len(by_tier[t])
                # 把 overflow 分给其他 tier
                for other in ["high", "mid", "low"]:
                    if other != t and len(by_tier[other]) > quotas[other]:
                        extra = min(overflow, len(by_tier[other]) - quotas[other])
                        quotas[other] += extra
                        overflow -= extra
                        if overflow <= 0:
                            break

        selected = []
        author_count = defaultdict(int)
        bucket_count = defaultdict(int)
        selected_titles = []

        for tier in ["high", "mid", "low"]:
            pool = by_tier[tier]
            # 在 pool 内按 score 排序(高 tier 取高分,低 tier 取低分)
            if tier == "low":
                pool.sort(key=lambda x: x.score)
            else:
                pool.sort(key=lambda x: x.score, reverse=True)

            tier_selected = 0
            for item in pool:
                if tier_selected >= quotas[tier]:
                    break
                # 作者去重
                if item.author and author_count[item.author] >= budget.max_per_author:
                    continue
                # 时间分桶
                bucket = _time_bucket(item.created_utc, budget.time_bucket_hours)
                if bucket_count[bucket] >= budget.max_per_bucket:
                    continue
                # 标题相似度去重
                too_similar = False
                for prev_title in selected_titles:
                    if _cosine_simple(item.title, prev_title) >= budget.title_similarity_threshold:
                        too_similar = True
                        break
                if too_similar:
                    continue

                selected.append(item.id)
                selected_titles.append(item.title)
                if item.author:
                    author_count[item.author] += 1
                bucket_count[bucket] += 1
                tier_selected += 1

        # 内容形式覆盖补齐:确保各 content_form 至少有 1 帖
        forms_present = {item_map[i].content_form for i in selected}
        for form in ["text", "image", "video", "link"]:
            if form not in forms_present:
                candidate = next(
                    (i for i in items if i.content_form == form and i.id not in selected), None
                )
                if candidate and len(selected) < budget.total + 10:
                    selected.append(candidate.id)
                    selected_titles.append(candidate.title)

        return selected
