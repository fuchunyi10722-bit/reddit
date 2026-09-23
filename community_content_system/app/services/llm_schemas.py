"""LLM 输出 JSON Schema 校验 + fallback 机制。

三个核心 Schema:
- CLASSIFIER_SCHEMA: 单条内容打标签
- ANALYZER_SCHEMA: 新内容适配判断(含 verdict/issues/suggestions/comment_advice/potential_value/evidence)
- PATTERN_MINER_SCHEMA: 规律提炼

校验失败时降级到规则式 fallback。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional, Tuple


# ---------------- Classifier Schema ----------------
CLASSIFIER_SCHEMA: dict = {
    "type": "object",
    "required": ["topic_tags", "structure_tags", "product_visibility", "search_value"],
    "properties": {
        "topic_tags": {"type": "array", "items": {"type": "string"}},
        "scenario_tags": {"type": "array", "items": {"type": "string"}},
        "structure_tags": {"type": "array", "items": {"type": "string"}},
        "product_visibility": {
            "enum": ["none", "subtle", "natural", "explicit", "promotional"]
        },
        "brand_mentions": {"type": "array", "items": {"type": "string"}},
        "search_value": {"enum": ["low", "mid", "high"]},
        "search_value_reasoning": {"type": "string"},
    },
}


# ---------------- ContentAnalyzer Schema ----------------
ANALYZER_SCHEMA: dict = {
    "type": "object",
    "required": [
        "verdict",
        "verdict_reason",
        "key_issues",
        "modification_suggestions",
        "comment_participation_advice",
        "potential_value",
        "evidence",
    ],
    "properties": {
        "verdict": {"enum": ["fit", "fit_after_fix", "not_fit"]},
        "verdict_reason": {"type": "string"},
        "key_issues": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "required": ["issue", "why", "evidence_type", "evidence_item_ids", "fix"],
                "properties": {
                    "issue": {"type": "string"},
                    "why": {"type": "string"},
                    "evidence_type": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "evidence_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "fix": {"type": "string"},
                },
            },
        },
        "modification_suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["target", "current", "suggested", "reason"],
                "properties": {
                    "target": {"type": "string"},
                    "current": {"type": "string"},
                    "suggested": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
        "comment_participation_advice": {
            "type": "object",
            "required": [
                "should_reply_natural_comments",
                "should_supplement_own_comment",
                "should_wait_for_natural_discussion",
                "should_share_product_in_comments",
                "should_participate_before_posting",
                "confidence",
                "evidence_insufficient",
            ],
            "properties": {
                "should_reply_natural_comments": {"type": "boolean"},
                "should_supplement_own_comment": {"type": "boolean"},
                "should_wait_for_natural_discussion": {"type": "boolean"},
                "should_share_product_in_comments": {"type": "boolean"},
                "should_participate_before_posting": {"type": "boolean"},
                "confidence": {
                    "enum": ["high", "medium", "low", "insufficient"]
                },
                "reasoning": {"type": "string"},
                "evidence_insufficient": {"type": "boolean"},
            },
        },
        "potential_value": {
            "type": "object",
            "required": ["value_types", "reasoning"],
            "properties": {
                "value_types": {
                    "type": "array",
                    "items": {
                        "enum": [
                            "interaction",
                            "discussion",
                            "search",
                            "product_awareness",
                            "community_penetration",
                        ]
                    },
                },
                "reasoning": {"type": "string"},
            },
        },
        "evidence": {
            "type": "object",
            "required": [
                "community_rule",
                "similar_content_count",
                "high_performance_count",
                "mid_performance_count",
                "low_performance_count",
                "knowledge_patterns_applied",
            ],
            "properties": {
                "community_rule": {"type": "boolean"},
                "similar_content_count": {"type": "integer"},
                "high_performance_count": {"type": "integer"},
                "mid_performance_count": {"type": "integer"},
                "low_performance_count": {"type": "integer"},
                "knowledge_patterns_applied": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
        },
    },
}


# ---------------- PatternMiner Schema ----------------
PATTERN_MINER_SCHEMA: dict = {
    "type": "object",
    "required": ["patterns"],
    "properties": {
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "required": [
                    "pattern_type",
                    "description",
                    "applicable_conditions",
                    "evidence_item_ids",
                    "sample_count",
                ],
                "properties": {
                    "pattern_type": {"enum": ["fire", "search", "failure"]},
                    "description": {"type": "string"},
                    "applicable_conditions": {"type": "object"},
                    "evidence_item_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "sample_count": {"type": "integer"},
                },
            },
        }
    },
}


def validate_schema(
    schema: dict, data: Any
) -> Tuple[bool, Optional[str]]:
    """轻量 schema 校验(不引 jsonschema 依赖,手写校验覆盖核心约束)。

    返回 (ok, error)。ok=False 时调用方应降级到规则式 fallback。
    """
    if not isinstance(data, dict):
        return False, "root not object"

    # required
    for field in schema.get("required", []):
        if field not in data:
            return False, f"missing required field: {field}"

    for field, spec in schema.get("properties", {}).items():
        if field not in data:
            continue
        val = data[field]
        spec_type = spec.get("type")

        # type 检查
        type_map = {
            "object": dict,
            "array": list,
            "string": str,
            "integer": int,
            "boolean": bool,
        }
        if spec_type in type_map:
            # 注意: bool 是 int 的子类,要单独处理
            if spec_type == "boolean" and not isinstance(val, bool):
                return False, f"{field} not boolean"
            elif spec_type == "integer" and isinstance(val, bool):
                return False, f"{field} not integer"
            elif spec_type != "boolean" and not isinstance(val, type_map[spec_type]):
                return False, f"{field} not {spec_type}"

        # enum 检查
        if "enum" in spec and val not in spec["enum"]:
            return False, f"{field} not in enum: {spec['enum']}"

        # maxItems 检查
        if spec_type == "array" and "maxItems" in spec:
            if len(val) > spec["maxItems"]:
                return False, f"{field} exceeds maxItems {spec['maxItems']}"

        # array items 校验
        if spec_type == "array" and "items" in spec:
            items_spec = spec["items"]
            if isinstance(items_spec, dict):
                if items_spec.get("type") == "string":
                    for i, item in enumerate(val):
                        if not isinstance(item, str):
                            return False, f"{field}[{i}] not string"
                elif items_spec.get("enum"):
                    for i, item in enumerate(val):
                        if item not in items_spec["enum"]:
                            return False, f"{field}[{i}] not in enum"
                elif items_spec.get("type") == "object":
                    # 递归校验 array of objects
                    for i, item in enumerate(val):
                        ok, err = validate_schema(items_spec, item)
                        if not ok:
                            return False, f"{field}[{i}]: {err}"

        # object 递归校验
        if spec_type == "object" and isinstance(val, dict):
            ok, err = validate_schema(spec, val)
            if not ok:
                return False, f"{field}: {err}"

    return True, None


def validate_and_fallback(
    schema: dict,
    llm_output: Any,
    fallback_fn: Callable[[], dict],
    context_label: str = "",
) -> Tuple[dict, str]:
    """校验 LLM 输出,失败降级到 fallback。

    返回 (data, source)。source ∈ {"llm", "rule_based_fallback"}。
    """
    # 先尝试解析为 dict
    if isinstance(llm_output, str):
        try:
            llm_output = json.loads(llm_output)
        except json.JSONDecodeError:
            pass  # 继续走 fallback

    ok, err = validate_schema(schema, llm_output)
    if ok:
        return llm_output, "llm"

    # 降级
    fallback = fallback_fn()
    return fallback, "rule_based_fallback"
