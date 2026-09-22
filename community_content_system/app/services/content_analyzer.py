"""新内容分析:计划内容 + 目标社区 → AI 判断。

流程:
1. 解析新内容(抽取 content_variables)
2. 召回目标社区 CommunityProfile + KnowledgePattern + 相似 ReferenceItem
3. 五层证据召回(规则层/社区规律/用户行为/自有历史/搜索)
4. 对照召回(高/中/低/失败四档)
5. 判断:适配度(fit/fit_after_fix/not_fit) + 2-3 问题 + 修改建议 + 评论参与 + 证据
6. 保存发布前快照(immutable)

第一阶段:规则式判断 + 预留 LLM 接口。
不平均成单一分数,各层证据分别呈现。
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Optional

from ..database import get_session
from ..models.knowledge import CommunityProfile, KnowledgePattern
from ..models.reference import ReferenceItem
from ..models.analysis import ContentAnalysis, PerformanceAnalysis
from ..models.snapshot import ContentAnalysisSnapshot
from . import embedder, classifier as classifier_svc


def analyze_new_content(
    title: str,
    selftext: str,
    target_subreddit: str,
    image_description: Optional[str] = None,
    content_variables: Optional[dict] = None,
    env_variables: Optional[dict] = None,
) -> ContentAnalysisSnapshot:
    """分析新内容是否适合目标社区,保存发布前快照(immutable)。

    返回 ContentAnalysisSnapshot。
    """
    # 1. 召回社区画像
    with get_session() as s:
        profile = s.query(CommunityProfile).filter_by(subreddit=target_subreddit).first()
        if not profile:
            raise ValueError(f"社区画像不存在: {target_subreddit},请先初始化社区")

        rules_summary = profile.rules_summary or {}
        # 召回相关规律
        all_patterns = s.query(KnowledgePattern).filter(
            KnowledgePattern.applicable_conditions.contains({"subreddit": target_subreddit})
        ).all()

        # 2. 相似召回(高/中/低/失败四档)
        new_text = f"{title}\n{selftext}"
        similar = embedder.find_similar(new_text, entity_type="reference_item", top_k=20)
        similar_items = []
        for eid, score in similar:
            item = s.query(ReferenceItem).filter_by(id=eid).first()
            if item:
                pa = s.query(PerformanceAnalysis).filter_by(
                    reference_item_id=item.id, is_current=True
                ).first()
                tier = pa.performance_tier if pa else "mid"
                ca = s.query(ContentAnalysis).filter_by(
                    reference_item_id=item.id, is_current=True
                ).first()
                similar_items.append({
                    "item_id": item.id,
                    "title": item.title[:80],
                    "score": item.score,
                    "tier": tier,
                    "structure_tags": ca.structure_tags if ca else [],
                    "product_visibility": ca.product_visibility if ca else None,
                    "search_value": ca.search_value if ca else None,
                    "similarity": round(score, 3),
                })

        # 按 tier 分组对照
        by_tier = {"high": [], "mid": [], "low": []}
        for si in similar_items:
            if si["tier"] in by_tier:
                by_tier[si["tier"]].append(si)

    # 3. 新内容自身分析(用 classifier 的标签逻辑)
    new_structure = classifier_svc._classify_structure(title, selftext)
    new_product_visibility = classifier_svc._classify_product_visibility(title, selftext)
    new_search_value = classifier_svc._classify_search_value(title, selftext)
    new_topics = classifier_svc._extract_topics(title, selftext)

    # 4. 五层证据 + 判断
    # 规则层
    rule_evidence = {
        "commercial_restricted": rules_summary.get("commercial_content_restricted", False),
        "link_restricted": rules_summary.get("link_restricted", False),
        "flair_required": rules_summary.get("flair_required", False),
    }

    # 社区规律层:对比新内容结构 vs 社区高表现结构
    community_structure_evidence = []
    for st in (profile.common_structures or []):
        community_structure_evidence.append(st)
    high_structs = [st.get("structure") for st in (profile.common_structures or []) if st.get("count", 0) >= 2]

    # 自有历史层:相似案例
    history_evidence = similar_items[:5]

    # 5. 判断逻辑(规则式第一阶段)
    issues = []
    suggestions = []
    evidence_item_ids = [si["item_id"] for si in similar_items[:5]]
    applied_pattern_ids = [p.id for p in all_patterns if p.status in ("candidate", "supported")][:3]

    # 适配度判断
    verdict = "fit"
    verdict_reason = ""

    # 检查1:产品露出过早(开头直接品牌/产品介绍)
    if new_product_visibility in ("explicit", "promotional"):
        issues.append({
            "issue": "开头直接出现产品/品牌,容易产生广告感",
            "detail": "该社区对商业内容限制较严(commercial_restricted=True),"
                      "高表现案例中 product_visibility 多为 none/natural。"
                      "当前内容 product_visibility=" + new_product_visibility + "。",
            "fix": "建议从具体问题/使用场景切入,在解决过程中自然带出产品,而非开头直接介绍。",
        })
        suggestions.append("将产品介绍后移:先用具体问题或使用经历吸引读者,在解决过程中再自然提及产品。")
        verdict = "fit_after_fix"
        verdict_reason = "内容方向相关但产品露出方式需调整。"

    # 检查2:标题是否接近用户搜索语言/是否模糊
    if new_search_value == "low" and len(title) < 15:
        issues.append({
            "issue": "标题过于模糊,未体现用户关心的具体问题",
            "detail": f"该社区高表现帖子标题多含具体问题或经验,"
                      f"当前标题'{title[:40]}'过于宽泛。",
            "fix": "标题应直接体现用户会搜索的具体问题或场景。",
        })
        suggestions.append("重写标题:将模糊表述改为具体问题,例如'How do I ...'或'What's the difference between X and Y'。")
        if verdict == "fit":
            verdict = "fit_after_fix"
            verdict_reason = (verdict_reason + " " if verdict_reason else "") + "标题需更具体。"

    # 检查3:内容结构 vs 社区偏好
    if new_structure and new_structure[0] not in high_structs and high_structs:
        issues.append({
            "issue": f"内容结构({new_structure[0]})与该社区高互动内容的常见结构({','.join(high_structs[:3])})差异较大",
            "detail": "基于历史案例,该社区高表现内容多采用特定结构。",
            "fix": f"参考高表现案例的结构,如'具体问题 → 个人经历 → 解决过程'。",
        })
        if verdict == "fit":
            verdict = "fit_after_fix"
            verdict_reason = (verdict_reason + " " if verdict_reason else "") + "内容结构需调整。"

    # 检查4:规则合规
    if new_product_visibility == "promotional" and rule_evidence["commercial_restricted"]:
        issues.append({
            "issue": "社区规则禁止自我推广/广告,当前内容会被删除",
            "detail": "该社区 rules 中明确 'No advertising/self-promotion'。",
            "fix": "去除所有推广语言、折扣码、链接,改为纯经验分享或问题讨论。",
        })
        verdict = "not_fit"
        verdict_reason = "违反社区商业内容规则,发布后大概率被删除。"

    # 若无明显问题
    if not issues:
        verdict_reason = "内容主题、结构、产品露出方式与社区历史高表现案例基本匹配。"

    # 评论参与建议
    if verdict == "not_fit":
        comment_advice = "不建议发布。如确需发布,需先按建议修改。"
    elif new_structure and "question" in new_structure:
        comment_advice = "发布后建议回复自然评论,主动回答用户追问;不建议人为制造互动。"
    elif new_structure and "experience" in new_structure:
        comment_advice = "发布后建议等待自然讨论,在评论中补充使用细节;适合主动回答用户问题。"
    else:
        comment_advice = "数据不足,无法判断评论参与策略。建议先观察该社区类似内容的评论模式。"

    # 预测(低/中/高 + 依据)
    if verdict == "not_fit":
        predicted = "low"
        prediction_basis = "违反社区规则,发布后大概率被删除。"
    elif len(issues) >= 2:
        predicted = "low"
        prediction_basis = "存在多个关键问题,如不修改预计表现较差。"
    elif verdict == "fit_after_fix":
        predicted = "mid"
        prediction_basis = "修改后预计具有中等互动潜力,基于历史相似案例。"
    elif by_tier.get("high"):
        predicted = "mid"
        prediction_basis = f"存在 {len(by_tier['high'])} 个高表现相似案例,但样本量不足以精确预测。"
    else:
        predicted = "mid"
        prediction_basis = "当前样本量不足,只能给出中等估计。"

    # 补齐 content_variables / env_variables
    cv = content_variables or {
        "title": title,
        "structure_tags": new_structure,
        "product_visibility": new_product_visibility,
        "search_value": new_search_value,
        "topics": new_topics,
        "has_image": image_description is not None,
    }
    ev = env_variables or {
        "target_subreddit": target_subreddit,
        "subreddit_type": profile.subreddit_type,
    }

    # 6. 保存发布前快照(immutable)
    content_hash = hashlib.sha256(f"{title}|{selftext}|{target_subreddit}".encode()).hexdigest()
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
            verdict=verdict,
            verdict_reason=verdict_reason,
            key_issues=issues[:3],  # 最多 3 个最关键问题
            modification_suggestions=suggestions,
            comment_participation_advice=comment_advice,
            evidence_item_ids=evidence_item_ids,
            applied_pattern_ids=applied_pattern_ids,
            predicted_engagement=predicted,
            prediction_basis=prediction_basis,
            model_version="rule_based_v0.1",
            created_at=datetime.utcnow(),
        )
        s.add(snapshot)
        s.flush()
        return snapshot
