"""Classifier:AI 对单条内容打标签(ContentAnalysis,版本化)。

Phase 2:
- 调用 LLM(通过 LLMProvider 抽象)做 topic/scenario/structure/product_visibility/brand/search_value 判断
- LLM 失败或 schema 校验不通过时降级到规则式 fallback
- 保留人工修正入口(human_override_label)
- 版本化机制不变:旧版本 is_current=false,新版本永远新行

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
from .llm_client import get_llm_provider, LLMCallLog
from .llm_schemas import CLASSIFIER_SCHEMA, validate_and_fallback


# ============================================================
# 规则式 fallback(Phase 1 实现,LLM 失败时降级)
# ============================================================
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
    is_question_title = bool(re.match(r"^(how|what|why|when|where|which|can|is|are)\b", title_low))
    has_substance = len(selftext) > 200
    has_code = "```" in selftext or "def " in selftext or "    " in selftext
    has_steps = bool(re.search(r"\b(first|second|step \d|1\.|2\.|3\.)\b", text_low))
    time_sensitive = bool(re.search(r"\b(2024|2025|2026|today|this week|breaking|just happened)\b", title_low))

    if is_question_title and has_substance and (has_code or has_steps) and not time_sensitive:
        return "high"
    if is_question_title and has_substance:
        return "mid"
    if time_sensitive or len(selftext) < 50:
        return "low"
    return "mid"


def _extract_topics(title: str, selftext: str) -> list[str]:
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
        "organizing": ["organizing", "organization", "organize", "declutter", "storage"],
        "labeling": ["label", "labeling", "label machine", "labelmaker", "niimbot"],
        "business": ["business", "selling", "etsy", "shop", "product", "inventory"],
        "craft": ["craft", "diy", "handmade", "making"],
        "gardening": ["garden", "plant", "seed"],
        "baking": ["baking", "food", "meal prep", "freezer"],
    }
    for topic, kws in keyword_map.items():
        if any(kw in combined for kw in kws):
            topics.append(topic)
    return topics or ["general"]


def _rule_based_classify(title: str, selftext: str) -> dict:
    """规则式 fallback(Phase 1 实现,LLM 失败时降级)。"""
    return {
        "topic_tags": _extract_topics(title, selftext),
        "scenario_tags": [],
        "structure_tags": _classify_structure(title, selftext),
        "product_visibility": _classify_product_visibility(title, selftext),
        "brand_mentions": [],
        "search_value": _classify_search_value(title, selftext),
        "search_value_reasoning": "rule_based_fallback",
    }


# ============================================================
# LLM Classifier Prompt
# ============================================================
CLASSIFIER_SYSTEM_PROMPT = """You are a content classifier for a Reddit community analysis system.
You analyze Reddit posts and extract structured labels.

Output valid JSON only, no markdown, no explanation.

Schema:
{
  "topic_tags": ["string", ...],          // main topics (e.g. organizing, labeling, python, business)
  "scenario_tags": ["string", ...],       // usage scenarios (e.g. learning_struggle, personal_experience, recommendation_request)
  "structure_tags": ["string", ...],      // content structure: question | experience | resource_share | promotional | general
  "product_visibility": "none|subtle|natural|explicit|promotional",
  "brand_mentions": ["string", ...],
  "search_value": "low|mid|high",
  "search_value_reasoning": "string"
}

Rules:
- product_visibility: none=no product; subtle=product mentioned indirectly; natural=product appears naturally in context; explicit=product is main subject; promotional=contains buy/discount/sale keywords
- search_value: judge by content itself, NOT by source. high=question-type title + complete answer + timeless; low=time-sensitive or thin; mid=in-between
- scenario_tags: infer from content (learning_struggle, personal_experience, recommendation_request, etc.)
"""


def _build_classifier_prompt(title: str, selftext: str, subreddit: str) -> str:
    text_preview = selftext[:2000] if selftext else "(no body)"
    return f"Subreddit: r/{subreddit}\nTitle: {title}\nBody:\n{text_preview}"


# ============================================================
# LLM Classifier 主流程
# ============================================================
# 最近一次 LLM 调用日志(便于测试时检查)
_last_call_log: Optional[LLMCallLog] = None


def get_last_call_log() -> Optional[LLMCallLog]:
    """获取最近一次 LLM 调用日志(测试用)。"""
    return _last_call_log


def label_item(
    reference_item_id: str,
    model_version: Optional[str] = None,
    use_llm: bool = True,
) -> ContentAnalysis:
    """对单条 ReferenceItem 打标签,落库为 ContentAnalysis(新版本)。

    流程:
    1. 调 LLM(若 use_llm=True)分类
    2. schema 校验 LLM 输出
    3. 失败则降级到规则式 fallback
    4. 版本化落库(旧版本 is_current=false,新版本新行)

    Args:
        reference_item_id: ReferenceItem.id
        model_version: 标记模型版本(默认从 settings 推断)
        use_llm: True=调 LLM; False=直接用规则式(测试/fallback)
    """
    global _last_call_log

    with get_session() as s:
        item = s.query(ReferenceItem).filter_by(id=reference_item_id).first()
        if not item:
            raise ValueError(f"ReferenceItem 不存在: {reference_item_id}")

        result: dict
        source: str  # llm | rule_based_fallback | rule_based_forced

        if use_llm:
            provider = get_llm_provider()
            user_prompt = _build_classifier_prompt(
                item.title, item.selftext, item.subreddit
            )
            resp, log = provider.complete(
                task="classify",
                system_prompt=CLASSIFIER_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=settings.llm_classifier_model,
                temperature=settings.llm_temperature,
                response_format="json",
                max_tokens=1000,
            )
            _last_call_log = log

            if resp.success and resp.parsed_json:
                # schema 校验 + fallback
                result, source = validate_and_fallback(
                    CLASSIFIER_SCHEMA,
                    resp.parsed_json,
                    lambda: _rule_based_classify(item.title, item.selftext),
                    context_label="classifier",
                )
            else:
                # LLM 调用失败,降级
                result = _rule_based_classify(item.title, item.selftext)
                source = "rule_based_fallback"
        else:
            result = _rule_based_classify(item.title, item.selftext)
            source = "rule_based_forced"

        # 推断 model_version
        if model_version is None:
            if source == "llm":
                model_version = f"llm_{settings.llm_provider}_{settings.llm_classifier_model}"
            else:
                model_version = f"{source}_v0.1"

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
            topic_tags=result.get("topic_tags", ["general"]),
            scenario_tags=result.get("scenario_tags", []),
            structure_tags=result.get("structure_tags", ["general"]),
            product_visibility=result.get("product_visibility", "none"),
            brand_mentions=result.get("brand_mentions", []),
            search_value=result.get("search_value", "mid"),
            analyzed_at=datetime.utcnow(),
        )
        s.add(analysis)
        s.flush()
        return analysis


def label_items(
    reference_item_ids: list[str],
    model_version: Optional[str] = None,
    use_llm: bool = True,
) -> list[ContentAnalysis]:
    """批量打标签。"""
    return [label_item(rid, model_version, use_llm) for rid in reference_item_ids]


# ============================================================
# 人工修正入口
# ============================================================
def human_override_label(
    reference_item_id: str,
    topic_tags: Optional[list[str]] = None,
    scenario_tags: Optional[list[str]] = None,
    structure_tags: Optional[list[str]] = None,
    product_visibility: Optional[str] = None,
    brand_mentions: Optional[list[str]] = None,
    search_value: Optional[str] = None,
    override_reason: str = "",
) -> ContentAnalysis:
    """人工修正标签。

    不修改已有版本,而是新增一个版本(保持 immutable history)。
    model_version 标记为 human_override。
    """
    with get_session() as s:
        item = s.query(ReferenceItem).filter_by(id=reference_item_id).first()
        if not item:
            raise ValueError(f"ReferenceItem 不存在: {reference_item_id}")

        # 取当前版本作为基础
        current = (
            s.query(ContentAnalysis)
            .filter_by(reference_item_id=item.id, is_current=True)
            .first()
        )

        # 旧版本 is_current 置 false
        s.query(ContentAnalysis).filter_by(
            reference_item_id=item.id, is_current=True
        ).update({"is_current": False})

        max_ver = s.query(ContentAnalysis).filter_by(
            reference_item_id=item.id
        ).count()
        new_ver = max_ver + 1

        # 继承当前版本未覆盖的字段
        base = current
        analysis = ContentAnalysis(
            reference_item_id=item.id,
            model_version=f"human_override_{override_reason or 'manual'}"[:60],
            analysis_version=new_ver,
            is_current=True,
            topic_tags=topic_tags if topic_tags is not None else (base.topic_tags if base else ["general"]),
            scenario_tags=scenario_tags if scenario_tags is not None else (base.scenario_tags if base else []),
            structure_tags=structure_tags if structure_tags is not None else (base.structure_tags if base else ["general"]),
            product_visibility=product_visibility if product_visibility is not None else (base.product_visibility if base else "none"),
            brand_mentions=brand_mentions if brand_mentions is not None else (base.brand_mentions if base else []),
            search_value=search_value if search_value is not None else (base.search_value if base else "mid"),
            analyzed_at=datetime.utcnow(),
        )
        s.add(analysis)
        s.flush()
        return analysis
