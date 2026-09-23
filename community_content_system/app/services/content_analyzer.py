"""新内容分析:计划内容 + 目标社区 → AI 判断。

Phase 2:
- 调用 LLM 做综合判断(通过 LLMProvider 抽象)
- LLM 失败时降级到规则式 fallback
- 保留人工修正入口(human_override_verdict)
- 发布前快照 immutable 不变
- 不做精确互动量预测(已从 Schema 删除 prediction.engagement_level)

流程:
1. Classifier 给新内容打标签
2. Retrieval 召回(社区规则 + high/failure 案例 + KnowledgePattern)
3. LLM 综合判断(verdict + issues + suggestions + comment_advice + evidence)
4. schema 校验 + fallback
5. 保存发布前快照(immutable)
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Optional

from ..config import settings
from ..database import get_session
from ..models.knowledge import CommunityProfile, KnowledgePattern
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.snapshot import ContentAnalysisSnapshot
from . import embedder, classifier as classifier_svc
from .llm_client import get_llm_provider, LLMCallLog
from .llm_schemas import ANALYZER_SCHEMA, validate_and_fallback
from .retrieval import retrieve_for_analysis, RetrievalResult


# ============================================================
# LLM Analyzer Prompt
# ============================================================
ANALYZER_SYSTEM_PROMPT = """You are a Reddit content analyst for a label printer product (NIIMBOT).
You help decide whether planned content fits a target subreddit and how to improve it.

Output valid JSON only, no markdown, no explanation.

Schema:
{
  "verdict": "fit|fit_after_fix|not_fit",
  "verdict_reason": "string",
  "key_issues": [
    {
      "issue": "specific problem",
      "why": "why this is a problem in THIS community",
      "evidence_type": ["community_rule", "similar_content", "high_performance_content", "low_performance_content", "knowledge_pattern"],
      "evidence_item_ids": ["id1", "id2"],
      "fix": "specific actionable fix"
    }
  ],
  "modification_suggestions": [
    {
      "target": "title|body|opening|...",
      "current": "what's wrong now",
      "suggested": "specific suggested replacement",
      "reason": "why this is better"
    }
  ],
  "comment_participation_advice": {
    "should_reply_natural_comments": true,
    "should_supplement_own_comment": false,
    "should_wait_for_natural_discussion": true,
    "should_share_product_in_comments": false,
    "should_participate_before_posting": false,
    "confidence": "high|medium|low|insufficient",
    "reasoning": "based on...",
    "evidence_insufficient": false
  },
  "potential_value": {
    "value_types": ["interaction", "discussion", "search", "product_awareness", "community_penetration"],
    "reasoning": "based on..."
  },
  "evidence": {
    "community_rule": true,
    "similar_content_count": 5,
    "high_performance_count": 2,
    "mid_performance_count": 2,
    "low_performance_count": 1,
    "knowledge_patterns_applied": ["pattern_id1"]
  }
}

Rules:
- verdict: fit=suitable as-is; fit_after_fix=needs modification; not_fit=violates rules or fundamentally mismatched
- key_issues: max 3, each must be SPECIFIC (not generic like "improve quality")
- evidence_item_ids: MUST come from the cases provided in context; do NOT invent IDs
- comment_participation_advice: if evidence is insufficient, set evidence_insufficient=true and confidence="insufficient", do NOT fabricate advice
- Do NOT predict exact engagement numbers; use potential_value for value TYPE only
"""


# ============================================================
# 规则式 fallback(Phase 1 实现,LLM 失败时降级)
# ============================================================
def _rule_based_analyze(
    title: str,
    selftext: str,
    target_subreddit: str,
    retrieval: RetrievalResult,
    new_content_tags: dict,
) -> dict:
    """规则式判断 fallback。"""
    new_product_visibility = new_content_tags.get("product_visibility", "none")
    new_search_value = new_content_tags.get("search_value", "mid")
    new_structure = new_content_tags.get("structure_tags", [])

    rules = retrieval.rules_summary
    commercial_restricted = rules.get("commercial_content_restricted", False)

    issues = []
    suggestions = []

    # 检查1:产品露出过早
    if new_product_visibility in ("explicit", "promotional"):
        issues.append({
            "issue": "开头直接出现产品/品牌,容易产生广告感",
            "why": "该社区对商业内容限制较严,高表现案例中 product_visibility 多为 none/natural",
            "evidence_type": ["community_rule", "high_performance_content"],
            "evidence_item_ids": [c.reference_item_id for c in retrieval.similar_high[:2]],
            "fix": "从具体问题/使用场景切入,在解决过程中自然带出产品",
        })
        suggestions.append({
            "target": "opening",
            "current": title[:80],
            "suggested": "Start with a specific problem or use case, not the product",
            "reason": "高表现案例多从具体问题切入",
        })

    # 检查2:标题模糊
    if new_search_value == "low" and len(title) < 15:
        issues.append({
            "issue": "标题过于模糊,未体现用户关心的具体问题",
            "why": "该社区高表现帖子标题多含具体问题或经验",
            "evidence_type": ["similar_content"],
            "evidence_item_ids": [c.reference_item_id for c in retrieval.similar_high[:1]],
            "fix": "标题应直接体现用户会搜索的具体问题或场景",
        })
        suggestions.append({
            "target": "title",
            "current": title,
            "suggested": "How I [specific action] with [specific tool/method]",
            "reason": "问题型标题更接近用户搜索语言",
        })

    # 检查3:规则合规
    if new_product_visibility == "promotional" and commercial_restricted:
        issues.append({
            "issue": "社区规则禁止自我推广/广告,当前内容会被删除",
            "why": "该社区 rules 中明确禁止商业推广",
            "evidence_type": ["community_rule"],
            "evidence_item_ids": [],
            "fix": "去除所有推广语言、折扣码、链接,改为纯经验分享",
        })

    # verdict
    if any(i["evidence_type"] == ["community_rule"] for i in issues):
        verdict = "not_fit"
        verdict_reason = "违反社区商业内容规则,发布后大概率被删除"
    elif issues:
        verdict = "fit_after_fix"
        verdict_reason = "内容方向相关但需调整"
    else:
        verdict = "fit"
        verdict_reason = "内容主题、结构与社区历史高表现案例基本匹配"

    # comment_participation_advice
    if verdict == "not_fit":
        comment_advice = {
            "should_reply_natural_comments": False,
            "should_supplement_own_comment": False,
            "should_wait_for_natural_discussion": False,
            "should_share_product_in_comments": False,
            "should_participate_before_posting": False,
            "confidence": "insufficient",
            "reasoning": "内容不适合发布,无需评论参与建议",
            "evidence_insufficient": True,
        }
    else:
        comment_advice = {
            "should_reply_natural_comments": True,
            "should_supplement_own_comment": False,
            "should_wait_for_natural_discussion": True,
            "should_share_product_in_comments": False,
            "should_participate_before_posting": False,
            "confidence": "medium",
            "reasoning": "基于该社区评论模式,用户多追问具体细节",
            "evidence_insufficient": False,
        }

    # potential_value
    value_types = ["interaction"]
    if "?" in title or "how" in title.lower():
        value_types.append("discussion")
    if verdict == "fit":
        value_types.append("community_penetration")

    # evidence
    evidence_item_ids = [c.reference_item_id for c in retrieval.similar_high] + \
                         [c.reference_item_id for c in retrieval.similar_failure]
    applied_patterns = [p.pattern_id for p in retrieval.fire_patterns] + \
                       [p.pattern_id for p in retrieval.failure_patterns]

    return {
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "key_issues": issues[:3],
        "modification_suggestions": suggestions,
        "comment_participation_advice": comment_advice,
        "potential_value": {
            "value_types": value_types,
            "reasoning": "基于内容结构和社区规律的规则式判断",
        },
        "evidence": {
            "community_rule": commercial_restricted,
            "similar_content_count": len(retrieval.similar_high) + len(retrieval.similar_failure),
            "high_performance_count": len(retrieval.similar_high),
            "mid_performance_count": 0,
            "low_performance_count": len(retrieval.similar_failure),
            "knowledge_patterns_applied": applied_patterns,
        },
        # 额外字段(用于落库,不在 schema 内)
        "_evidence_item_ids": list(set(evidence_item_ids)),
        "_applied_pattern_ids": applied_patterns,
    }


# ============================================================
# LLM Analyzer 主流程
# ============================================================
_last_call_log: Optional[LLMCallLog] = None


def get_last_call_log() -> Optional[LLMCallLog]:
    return _last_call_log


def analyze_new_content(
    title: str,
    selftext: str,
    target_subreddit: str,
    image_description: Optional[str] = None,
    content_variables: Optional[dict] = None,
    env_variables: Optional[dict] = None,
    use_llm: bool = True,
) -> ContentAnalysisSnapshot:
    """分析新内容是否适合目标社区,保存发布前快照(immutable)。

    流程:
    1. Classifier 给新内容打标签
    2. Retrieval 召回上下文
    3. LLM 综合判断(schema 校验 + fallback)
    4. 保存发布前快照

    Args:
        use_llm: True=调 LLM; False=直接用规则式(测试/fallback)
    """
    global _last_call_log

    # 1. 验证社区已初始化
    with get_session() as s:
        profile = s.query(CommunityProfile).filter_by(subreddit=target_subreddit).first()
        if not profile:
            raise ValueError(f"社区画像不存在: {target_subreddit},请先初始化社区")

    # 2. 给新内容打标签(用 Classifier,但不落库——新内容不是 ReferenceItem)
    new_content = f"{title}\n{selftext}"
    new_content_tags = classifier_svc._rule_based_classify(title, selftext)

    # 添加关键词用于召回
    keywords = set()
    for word in title.lower().split():
        if len(word) > 3:
            keywords.add(word)
    new_content_tags["keywords"] = list(keywords)

    # 3. Retrieval 召回
    retrieval = retrieve_for_analysis(
        subreddit=target_subreddit,
        new_content=new_content,
        new_content_tags=new_content_tags,
    )

    # 4. LLM 判断
    result: dict
    source: str

    if use_llm:
        provider = get_llm_provider()
        context = retrieval.build_llm_context(new_content)

        resp, log = provider.complete(
            task="analyze",
            system_prompt=ANALYZER_SYSTEM_PROMPT,
            user_prompt=context,
            model=settings.llm_analyzer_model,
            temperature=settings.llm_temperature,
            response_format="json",
            max_tokens=2000,
        )
        _last_call_log = log

        if resp.success and resp.parsed_json:
            result, source = validate_and_fallback(
                ANALYZER_SCHEMA,
                resp.parsed_json,
                lambda: _rule_based_analyze(
                    title, selftext, target_subreddit, retrieval, new_content_tags
                ),
                context_label="analyzer",
            )
        else:
            result = _rule_based_analyze(
                title, selftext, target_subreddit, retrieval, new_content_tags
            )
            source = "rule_based_fallback"
    else:
        result = _rule_based_analyze(
            title, selftext, target_subreddit, retrieval, new_content_tags
        )
        source = "rule_based_forced"

    # 5. 提取 evidence_item_ids(校验:必须来自召回集)
    retrieved_ids = retrieval.all_retrieved_item_ids
    llm_evidence_ids = set()
    for issue in result.get("key_issues", []):
        for eid in issue.get("evidence_item_ids", []):
            if eid in retrieved_ids:
                llm_evidence_ids.add(eid)
    # 补充 fallback 的 evidence
    evidence_item_ids = list(llm_evidence_ids | set(result.get("_evidence_item_ids", [])))

    applied_pattern_ids = result.get("evidence", {}).get("knowledge_patterns_applied", [])
    applied_pattern_ids = result.get("_applied_pattern_ids", applied_pattern_ids)

    # 6. 推断 model_version
    if source == "llm":
        model_version = f"llm_{settings.llm_provider}_{settings.llm_analyzer_model}"
    else:
        model_version = f"{source}_v0.1"

    # 7. 构建快照数据
    cv = content_variables or {
        "title": title,
        "structure_tags": new_content_tags.get("structure_tags", []),
        "product_visibility": new_content_tags.get("product_visibility", "none"),
        "search_value": new_content_tags.get("search_value", "mid"),
        "topics": new_content_tags.get("topic_tags", []),
        "has_image": image_description is not None,
    }
    ev = env_variables or {
        "target_subreddit": target_subreddit,
        "subreddit_type": profile.subreddit_type,
    }

    # comment_participation_advice 转为字符串(Phase 1 snapshot 字段是 Text)
    comment_advice = result.get("comment_participation_advice", {})
    if isinstance(comment_advice, dict):
        comment_advice_str = json.dumps(comment_advice, ensure_ascii=False)
    else:
        comment_advice_str = str(comment_advice)

    content_hash = hashlib.sha256(
        f"{title}|{selftext}|{target_subreddit}".encode()
    ).hexdigest()

    # 8. 保存发布前快照(immutable)
    with get_session() as s:
        snapshot = ContentAnalysisSnapshot(
            submitted_content_hash=content_hash,
            submitted_content={
                "title": title,
                "selftext": selftext,
                "image_description": image_description,
                "target_subreddit": target_subreddit,
            },
            target_subreddit=target_subreddit,
            content_variables=cv,
            env_variables=ev,
            verdict=result.get("verdict", "fit"),
            verdict_reason=result.get("verdict_reason", ""),
            key_issues=result.get("key_issues", [])[:3],
            modification_suggestions=result.get("modification_suggestions", []),
            comment_participation_advice=comment_advice_str,
            evidence_item_ids=evidence_item_ids,
            applied_pattern_ids=applied_pattern_ids,
            predicted_engagement=None,  # Phase 2 不做精确预测
            prediction_basis=None,
            model_version=model_version,
            created_at=datetime.utcnow(),
        )
        s.add(snapshot)
        s.flush()
        return snapshot


# ============================================================
# 人工修正入口
# ============================================================
def human_override_verdict(
    snapshot_id: str,
    verdict: Optional[str] = None,
    verdict_reason: Optional[str] = None,
    key_issues: Optional[list] = None,
    modification_suggestions: Optional[list] = None,
    override_reason: str = "",
) -> ContentAnalysisSnapshot:
    """人工修正发布前判断。

    注意:原快照 immutable 不可改,这里创建新快照引用同一 submitted_content。
    新快照 model_version 标记为 human_override。
    """
    with get_session() as s:
        original = s.query(ContentAnalysisSnapshot).filter_by(id=snapshot_id).first()
        if not original:
            raise ValueError(f"快照不存在: {snapshot_id}")

        new_snapshot = ContentAnalysisSnapshot(
            submitted_content_hash=original.submitted_content_hash,
            submitted_content=original.submitted_content,
            target_subreddit=original.target_subreddit,
            content_variables=original.content_variables,
            env_variables=original.env_variables,
            verdict=verdict if verdict is not None else original.verdict,
            verdict_reason=verdict_reason if verdict_reason is not None else original.verdict_reason,
            key_issues=key_issues if key_issues is not None else original.key_issues,
            modification_suggestions=modification_suggestions if modification_suggestions is not None else original.modification_suggestions,
            comment_participation_advice=original.comment_participation_advice,
            evidence_item_ids=original.evidence_item_ids,
            applied_pattern_ids=original.applied_pattern_ids,
            predicted_engagement=None,
            prediction_basis=None,
            model_version=f"human_override_{override_reason or 'manual'}"[:60],
            created_at=datetime.utcnow(),
        )
        s.add(new_snapshot)
        s.flush()
        return new_snapshot
