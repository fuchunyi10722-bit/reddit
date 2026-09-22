"""PerformanceClassifier:规则式 p25/p75 社区内表现分层。

基于该社区本次抓取样本的 score 分位计算,非 AI 产出。
不叫"内容质量",叫"表现层级"。
高 upvote 不等于内容质量高,也不推断因果。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from ..database import get_session
from ..models.reference import ReferenceItem
from ..models.analysis import PerformanceAnalysis


def _percentile(sorted_vals: list[float], p: float) -> float:
    """简单分位数计算。"""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def tier_items(subreddit: str, item_ids: Optional[list[str]] = None) -> list[PerformanceAnalysis]:
    """对该社区的帖子做表现分层。

    基于本次传入的 item_ids(若 None 则取该社区全部)的 score 计算分位。
    p75+ = high, p25-p75 = mid, p25- = low。
    落库为 PerformanceAnalysis(新版本),旧版本 is_current 置 false。
    """
    with get_session() as s:
        q = s.query(ReferenceItem).filter_by(subreddit=subreddit, retention_status="active")
        if item_ids:
            q = q.filter(ReferenceItem.id.in_(item_ids))
        items = q.all()

        if not items:
            return []

        scores = sorted([i.score for i in items])
        p25 = _percentile(scores, 0.25)
        p75 = _percentile(scores, 0.75)
        sample_size = len(items)

        results = []
        for item in items:
            if item.score >= p75:
                tier = "high"
            elif item.score >= p25:
                tier = "mid"
            else:
                tier = "low"

            # 旧版本 is_current 置 false
            s.query(PerformanceAnalysis).filter_by(
                reference_item_id=item.id, is_current=True
            ).update({"is_current": False})

            # 计算新版本号
            max_ver = s.query(PerformanceAnalysis).filter_by(
                reference_item_id=item.id
            ).count()
            new_ver = max_ver + 1

            pa = PerformanceAnalysis(
                reference_item_id=item.id,
                subreddit=subreddit,
                analysis_version=new_ver,
                is_current=True,
                performance_tier=tier,
                p25_score=p25,
                p75_score=p75,
                sample_size=sample_size,
                tier_computed_at=datetime.utcnow(),
            )
            s.add(pa)
            results.append(pa)
        s.flush()
        return results


def get_current_tier(reference_item_id: str) -> Optional[str]:
    """获取某帖当前表现层级。"""
    with get_session() as s:
        pa = s.query(PerformanceAnalysis).filter_by(
            reference_item_id=reference_item_id, is_current=True
        ).first()
        return pa.performance_tier if pa else None
