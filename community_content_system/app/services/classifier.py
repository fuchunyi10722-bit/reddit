"""Classifier:AI 对单条内容打标签(ContentAnalysis,版本化)。

第一阶段:规则式占位 + 预留 LLM 接口。
生产环境:调 LLM 做 topic/scenario/structure/product_visibility/brand/search_value 判断。

search_value 由内容本身判断(标题是否接近搜索语言/是否完整回答问题/是否长期信息价值),
不因来自 Search 召回就 = high。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis


# 规则式标签(第一阶段占位)
QUESTION_PATTERNS = [
    r"^(how|what|why|when|where|which|can|is|are|do|does|should)\b",
    r"\?$",
]
EXPERIENCE_PATTERNS = [
    r"\b(i|my|me)\b.*\b(finally|struggled|learned|understood|realized|tired|started|built)\b",
    r"\b(after \d+ (months|weeks|days|hours))\b",
]
RESOURCE_PATTERNS = [
    r"\b(resources|tutorial|course|book|guide|link|blog)\b",
    r"best .{3,30} (for|to)",
]
PROMOTION_PATTERNS = [
    r"\b(buy|course|discount|coupon|promo|free trial|sign up|link in bio|checkout|check out my)\b",
    r"\$\d+",
    r"\d+% off",
]


def _match_patterns(text: str, patterns: list[str]) -> bool:
    low = text.lower()
    return any(re.search(p, low, re.IGNORECASE) for p in patterns)


def _classify_structure(title: str, selftext: str) -> list[str]:
    combined = f"{title}\n{selftext}"
    tags = []
    if _match_patterns(title, QUESTION_PATTERNS):
        tags.append("question")
    if _match_patterns(combined, EXPERIENCE_PATTERNS):
        tags.append("experience")
    if _match_patterns(title, RESOURCE_PATTERNS):
        tags.append("resource_share")
    if _match_patterns(combined, PROMOTION_PATTERNS):
        tags.append("promotional")
    if not tags:
        tags.append("general")
    return tags


def _classify_product_visibility(title: str, selftext: str) -> str:
    combined = f"{title}\n{selftext}".lower()
    if _match_patterns(combined, PROMOTION_PATTERNS):
        return "promotional"
    brand_words = ["my course", "my app", "my product", "my service", "checkout", "sign up"]
    if any(w in combined for w in brand_words):
        return "explicit"
    product_hints = ["using x", "with x", "tried x", "tool", "library", "framework"]
    if any(w in combined for w in product_hints):
        return "natural"
    if any(w in combined for w in ["mentioned", "uses"]):
        return "subtle"
    return "none"


def _classify_search_value(title: str, selftext: str) -> str:
    """由内容本身判断搜索价值。

    高搜索价值:标题接近真实用户搜索语言 + 正文完整回答具体问题 + 长期信息价值
    不因来自 Search 召回就 = high。
    """
    title_low = title.lower()
    text_low = selftext.lower()
    # 是否是问题型标题(接近搜索语言)
    is_question_title = bool(re.match(r"^(how|what|why|when|where|which|can|is|are)\b", title_low))
    # 正文是否有实质内容(>200 字符,有代码或步骤)
    has_substance = len(selftext) > 200
    has_code = "```" in selftext or "def " in selftext or "    " in selftext
    has_steps = bool(re.search(r"\b(first|second|step \d|1\.|2\.|3\.)\b", text_low))
    # 非时效性(标题不含年份/今天/本周)
    time_sensitive = bool(re.search(r"\b(2024|2025|2026|today|this week|breaking|just happened)\b", title_low))

    if is_question_title and has_substance and (has_code or has_steps) and not time_sensitive:
        return "high"
    if is_question_title and has_substance:
        return "mid"
    if time_sensitive or len(selftext) < 50:
        return "low"
    return "mid"


def _extract_topics(title: str, selftext: str) -> list[str]:
    """简易主题提取(第一阶段占位)。生产用 LLM。"""
    combined = f"{title} {selftext}".lower()
    topics = []
    keyword_map = {
        "python": ["python", "django", "flask", "pandas", "numpy"],
        "javascript": ["javascript", "js", "react", "vue", "node"],
        "c_language": ["c ", "c++", "pointers", "malloc"],
        "career": ["job", "interview", "career", "junior dev", "bootcamp"],
        "data_structures": ["data structure", "algorithm", "recursion", "linked list", "stack", "queue"],
        "debugging": ["bug", "error", "debug", "fix"],
        "getting_started": ["where do i start", "beginner", "new to programming"],
    }
    for topic, kws in keyword_map.items():
        if any(kw in combined for kw in kws):
            topics.append(topic)
    return topics or ["general"]


def label_item(reference_item_id: str, model_version: Optional[str] = None) -> ContentAnalysis:
    """对单条 ReferenceItem 打标签,落库为 ContentAnalysis(新版本)。

    旧版本 is_current 置 false,新版本永远是新行(immutable history)。
    """
    model_version = model_version or "rule_based_v0.1"
    with get_session() as s:
        item = s.query(ReferenceItem).filter_by(id=reference_item_id).first()
        if not item:
            raise ValueError(f"ReferenceItem 不存在: {reference_item_id}")

        # 旧版本 is_current 置 false
        s.query(ContentAnalysis).filter_by(
            reference_item_id=item.id, is_current=True
        ).update({"is_current": False})

        max_ver = s.query(ContentAnalysis).filter_by(
            reference_item_id=item.id
        ).count()
        new_ver = max_ver + 1

        analysis = ContentAnalysis(
            reference_item_id=item.id,
            model_version=model_version,
            analysis_version=new_ver,
            is_current=True,
            topic_tags=_extract_topics(item.title, item.selftext),
            scenario_tags=[],  # 第一阶段规则式不深采场景
            structure_tags=_classify_structure(item.title, item.selftext),
            product_visibility=_classify_product_visibility(item.title, item.selftext),
            brand_mentions=[],
            search_value=_classify_search_value(item.title, item.selftext),
            analyzed_at=datetime.utcnow(),
        )
        s.add(analysis)
        s.flush()
        return analysis


def label_items(reference_item_ids: list[str], model_version: Optional[str] = None) -> list[ContentAnalysis]:
    """批量打标签。"""
    return [label_item(rid, model_version) for rid in reference_item_ids]
