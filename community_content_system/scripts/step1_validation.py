"""Step 1 技术链路验证脚本。

验证目标(P2-8):整套产品逻辑能不能跑通,以及哪些环节必须人工兜底。

注意:此脚本会修改数据库状态(创建快照/结果/复盘/迁移规律状态),
重复运行前需重置数据库。一键重置+运行:

    cd /workspace/community_content_system && \
    rm -f community.db && \
    python -c "import sys; sys.path.insert(0,'.'); from app.database import init_db; from app.services import community_init; init_db(); community_init.init_community('learnprogramming'); print('reinit done')" && \
    python scripts/step1_validation.py

使用 Mock LLM Provider(零成本)验证:
1. 社区已初始化(31 帖 + 3 规律)— 前置条件
2. 新内容分析:3 种测试内容(not_fit / fit_after_fix / fit)
3. 人工兜底:标签修正 / verdict 修正 / Retrieval 过滤
4. 结果回填 + 复盘闭环
5. 规律 validation_history 累计 + 状态迁移(多次确认达阈值)
6. LLM 调用日志(模型/输入/输出/耗时/结果)

关键原则:
- AI 不能自行把一次结果认定为"规律已验证"(必须人工确认)
- 单个案例只追加 validation_history,不直接改 status
- 状态迁移需累计达阈值(confirmed>=3 且 contradicted=0 → supported)
- 发布前快照 immutable,人工修正创建新快照
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import init_db, get_session
from app.models.reference import ReferenceItem, Comment
from app.models.analysis import ContentAnalysis, PerformanceAnalysis
from app.models.knowledge import CommunityProfile, KnowledgePattern
from app.models.snapshot import ContentAnalysisSnapshot, ActualResult, Review
from app.services import classifier, content_analyzer, review as review_svc, pattern_miner
from app.services.retrieval import retrieve_for_analysis, filter_retrieved_cases


# ============================================================
# 测试用例:3 种 verdict
# ============================================================
TEST_CONTENTS = [
    {
        "name": "not_fit(广告感重 + 违规)",
        "title": "NIIMBOT label printer — 50% off discount code inside!",
        "selftext": (
            "Check out the NIIMBOT label maker! Best label printer on the market. "
            "Use code REDDIT50 for 50% off. Buy now at our store. "
            "This label machine will change your organizing game."
        ),
    },
    {
        "name": "fit_after_fix(方向相关但需调整)",
        "title": "NIIMBOT label printer review — is it worth it for organizing?",
        "selftext": (
            "I've been using the NIIMBOT label printer for 3 months to organize my home office. "
            "It's been pretty good for labeling files and storage boxes. "
            "Has anyone else tried it? Wondering if there are better options for the price."
        ),
    },
    {
        "name": "fit(经验型 + 问题切入 + 产品自然出现)",
        "title": "How I finally organized my entire home office with a simple labeling system",
        "selftext": (
            "After 6 months of struggling with clutter, I built a labeling system that actually stuck. "
            "Here's what worked:\n\n"
            "1. Categorize first, label second. I spent 2 weeks just sorting before printing anything.\n"
            "2. Use consistent naming. 'Office/Cables/USB' not 'misc cables'.\n"
            "3. The tool: I ended up using a NIIMBOT label printer because it was cheap and the app "
            "let me batch-print. But honestly any label maker works — the system matters more than the tool.\n\n"
            "The breakthrough was realizing labeling isn't about the printer, it's about deciding "
            "what categories you actually need before you start."
        ),
    },
]


# ============================================================
# 工具函数
# ============================================================
def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def subsection(title: str) -> None:
    print(f"\n--- {title} ---")


def check(cond: bool, msg: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"  [{status}] {msg}")
    if not cond:
        raise AssertionError(f"CHECK FAILED: {msg}")


# ============================================================
# Step 1.0: 验证前置条件
# ============================================================
def verify_preconditions() -> None:
    section("Step 1.0 验证前置条件(社区已初始化)")
    with get_session() as s:
        profile = s.query(CommunityProfile).filter_by(subreddit="learnprogramming").first()
        check(profile is not None, "社区画像存在")
        check(profile.subscriber_count == 3500000, f"subscribers=3500000 (实际 {profile.subscriber_count})")

        ibu = profile.init_budget_used or {}
        check(ibu.get("total_unique_posts", 0) >= 30,
              f"unique_posts>=30 (实际 {ibu.get('total_unique_posts')})")

        ref_count = s.query(ReferenceItem).count()
        check(ref_count >= 30, f"ReferenceItems>=30 (实际 {ref_count})")

        ca_count = s.query(ContentAnalysis).filter_by(is_current=True).count()
        check(ca_count >= 30, f"ContentAnalyses(current)>=30 (实际 {ca_count})")

        pa_count = s.query(PerformanceAnalysis).filter_by(is_current=True).count()
        check(pa_count >= 30, f"PerformanceAnalyses(current)>=30 (实际 {pa_count})")

        pattern_count = s.query(KnowledgePattern).count()
        check(pattern_count >= 3, f"KnowledgePatterns>=3 (实际 {pattern_count})")

        # 验证 patterns 都是 candidate 状态(未被自动验证)
        for p in s.query(KnowledgePattern).all():
            check(p.status == "candidate",
                  f"pattern {p.id[:8]} status=candidate (实际 {p.status})")
            check(len(p.validation_history or []) == 0,
                  f"pattern {p.id[:8]} validation_history 为空 (实际 {len(p.validation_history or [])})")

    print("  前置条件全部通过")


# ============================================================
# Step 1.1: 新内容分析(3 种 verdict)
# ============================================================
def test_content_analysis() -> dict:
    section("Step 1.1 新内容分析(3 种 verdict)")
    results = {}

    for tc in TEST_CONTENTS:
        subsection(f"分析测试内容: {tc['name']}")
        print(f"  标题: {tc['title'][:80]}")

        snapshot = content_analyzer.analyze_new_content(
            title=tc["title"],
            selftext=tc["selftext"],
            target_subreddit="learnprogramming",
            use_llm=True,
        )
        results[tc["name"]] = snapshot

        print(f"  snapshot_id: {snapshot.id}")
        print(f"  verdict: {snapshot.verdict}")
        print(f"  verdict_reason: {snapshot.verdict_reason[:120]}")
        print(f"  model_version: {snapshot.model_version}")
        print(f"  key_issues count: {len(snapshot.key_issues)}")
        print(f"  modification_suggestions count: {len(snapshot.modification_suggestions)}")
        print(f"  evidence_item_ids count: {len(snapshot.evidence_item_ids)}")
        print(f"  applied_pattern_ids count: {len(snapshot.applied_pattern_ids)}")

        # 验证快照 immutable 关键字段已保存
        check(snapshot.verdict in ("fit", "fit_after_fix", "not_fit"),
              f"verdict 合法 (实际 {snapshot.verdict})")
        check("llm_mock" in snapshot.model_version or "fallback" in snapshot.model_version or "forced" in snapshot.model_version,
              f"model_version 含 llm/fallback (实际 {snapshot.model_version})")
        check(snapshot.submitted_content["title"] == tc["title"],
              "快照保存了原始标题")
        check(snapshot.target_subreddit == "learnprogramming",
              "快照保存了目标社区")

        # 验证 evidence_item_ids 来自召回集(不凭空捏造)
        if snapshot.evidence_item_ids:
            with get_session() as s:
                for eid in snapshot.evidence_item_ids:
                    item = s.query(ReferenceItem).filter_by(id=eid).first()
                    check(item is not None, f"evidence_item_id {eid[:8]} 在 ReferenceItem 中存在")

    # 验证 3 种 verdict 都出现过
    verdicts = {results[tc["name"]].verdict for tc in TEST_CONTENTS}
    print(f"\n  3 种测试内容的 verdict: {verdicts}")
    check(len(verdicts) >= 2, f"至少出现 2 种 verdict (实际 {len(verdicts)})")

    return results


# ============================================================
# Step 1.2: 人工兜底验证
# ============================================================
def test_human_override(snapshot_results: dict) -> dict:
    section("Step 1.2 人工兜底验证")

    # 取 fit_after_fix 的快照做 verdict 修正测试
    fit_after_fix_snapshot = None
    not_fit_snapshot = None
    for name, snap in snapshot_results.items():
        if snap.verdict == "fit_after_fix":
            fit_after_fix_snapshot = snap
        if snap.verdict == "not_fit":
            not_fit_snapshot = snap

    override_results = {}

    # ---- 1.2a: 人工修正 verdict ----
    if fit_after_fix_snapshot:
        subsection("1.2a 人工修正 verdict(fit_after_fix → not_fit)")
        print(f"  原快照: {fit_after_fix_snapshot.id}, verdict={fit_after_fix_snapshot.verdict}")

        new_snapshot = content_analyzer.human_override_verdict(
            snapshot_id=fit_after_fix_snapshot.id,
            verdict="not_fit",
            verdict_reason="人工判断:该社区对品牌露出较敏感,品牌名出现在标题中风险较高",
            key_issues=[{
                "issue": "标题含品牌名,该社区高互动内容多从场景/问题切入",
                "why": "人工复核:查看 high tier 案例,标题多不含具体品牌名",
                "evidence_type": ["high_performance_content"],
                "evidence_item_ids": fit_after_fix_snapshot.evidence_item_ids[:1] if fit_after_fix_snapshot.evidence_item_ids else [],
                "fix": "把品牌名从标题移除,改为场景型标题",
            }],
            modification_suggestions=[{
                "target": "title",
                "current": fit_after_fix_snapshot.submitted_content["title"][:60],
                "suggested": "How I organized my home office with a simple labeling system",
                "reason": "场景型标题更符合该社区高互动内容",
            }],
            override_reason="human_review_brand_sensitivity",
        )

        print(f"  新快照: {new_snapshot.id}, verdict={new_snapshot.verdict}")
        print(f"  model_version: {new_snapshot.model_version}")

        # 验证:原快照 immutable 不变
        with get_session() as s:
            orig = s.query(ContentAnalysisSnapshot).filter_by(id=fit_after_fix_snapshot.id).first()
            check(orig.verdict == "fit_after_fix",
                  f"原快照 immutable 不变 verdict={orig.verdict} (应为 fit_after_fix)")
            check(new_snapshot.verdict == "not_fit",
                  f"新快照 verdict=not_fit (实际 {new_snapshot.verdict})")
            check("human_override" in new_snapshot.model_version,
                  f"新快照 model_version 含 human_override (实际 {new_snapshot.model_version})")
            # 提交内容相同
            check(orig.submitted_content_hash == new_snapshot.submitted_content_hash,
                  "原快照与新快照 submitted_content_hash 相同(同一内容)")

        override_results["verdict_override"] = new_snapshot

    # ---- 1.2b: 人工修正标签 ----
    subsection("1.2b 人工修正标签(给某条 ReferenceItem 修正 topic/scenario)")
    with get_session() as s:
        item = s.query(ReferenceItem).filter_by(subreddit="learnprogramming").first()
        item_id = item.id
        orig_title = item.title
    print(f"  目标 ReferenceItem: {item_id[:8]}, 标题: {orig_title[:60]}")

    with get_session() as s:
        orig_ca = s.query(ContentAnalysis).filter_by(
            reference_item_id=item_id, is_current=True
        ).first()
        orig_ver = orig_ca.analysis_version if orig_ca else 0
        print(f"  原 ContentAnalysis: version={orig_ver}, topics={orig_ca.topic_tags}")

    new_ca = classifier.human_override_label(
        reference_item_id=item_id,
        topic_tags=["organizing", "personal_experience"],
        scenario_tags=["personal_experience"],
        structure_tags=["experience"],
        product_visibility="none",
        search_value="high",
        override_reason="human_correct_topic",
    )

    print(f"  新 ContentAnalysis: version={new_ca.analysis_version}, topics={new_ca.topic_tags}")

    with get_session() as s:
        # 旧版本 is_current=false
        old_versions = s.query(ContentAnalysis).filter_by(
            reference_item_id=item_id, is_current=False
        ).all()
        check(len(old_versions) >= 1, "旧版本 is_current=false")
        # 新版本 is_current=true
        cur = s.query(ContentAnalysis).filter_by(
            reference_item_id=item_id, is_current=True
        ).first()
        check(cur.id == new_ca.id, "新版本 is_current=true")
        check("human_override" in cur.model_version,
              f"新版本 model_version 含 human_override (实际 {cur.model_version})")
        check(cur.topic_tags == ["organizing", "personal_experience"],
              f"新版本 topic_tags 正确 (实际 {cur.topic_tags})")

    override_results["label_override"] = new_ca

    # ---- 1.2c: 人工过滤召回案例 ----
    subsection("1.2c 人工过滤召回案例(Retrieval filter)")
    new_content = "How I finally learned Python after 6 months of struggle"
    new_tags = {"topic_tags": ["python"], "structure_tags": ["experience"],
                "scenario_tags": [], "keywords": ["python", "learned"]}

    retrieval = retrieve_for_analysis(
        subreddit="learnprogramming",
        new_content=new_content,
        new_content_tags=new_tags,
    )
    print(f"  召回 high: {len(retrieval.similar_high)} 条")
    print(f"  召回 failure: {len(retrieval.similar_failure)} 条")
    print(f"  召回 patterns: fire={len(retrieval.fire_patterns)}, "
          f"search={len(retrieval.search_patterns)}, failure={len(retrieval.failure_patterns)}")

    check(len(retrieval.similar_high) > 0, "召回 high 案例非空")
    check(len(retrieval.fire_patterns) > 0, "召回 fire 规律非空")

    # 人工排除第一条 high 案例(模拟"明显不相关")
    # 注意:filter_retrieved_cases 会就地修改 retrieval,所以先记录原始数量
    if retrieval.similar_high:
        excluded_id = retrieval.similar_high[0].reference_item_id
        orig_high_count = len(retrieval.similar_high)
        print(f"  人工排除 high 案例: {excluded_id[:8]} (原 high 数 {orig_high_count})")
        filtered = filter_retrieved_cases(retrieval, {excluded_id})
        check(len(filtered.similar_high) == orig_high_count - 1,
              f"过滤后 high 案例数减 1 (实际 {len(filtered.similar_high)}, 期望 {orig_high_count - 1})")
        check(excluded_id not in filtered.all_retrieved_item_ids,
              "被排除的 ID 不在过滤后的召回集中")

    return override_results


# ============================================================
# Step 1.3: 结果回填 + 复盘闭环
# ============================================================
def test_result_and_review(snapshot_results: dict) -> dict:
    section("Step 1.3 结果回填 + 复盘闭环")

    review_results = {}

    for tc_name, snapshot in snapshot_results.items():
        subsection(f"结果回填 + 复盘: {tc_name}")

        # 模拟实际发布结果
        if snapshot.verdict == "not_fit":
            # 不适合发布 → 模拟被删
            result = review_svc.record_result(
                snapshot_id=snapshot.id,
                score=-10,
                num_comments=2,
                is_deleted=True,
                result_source="manual",
            )
            print(f"  模拟结果: 被删, score=-10")
        elif snapshot.verdict == "fit_after_fix":
            # 修改后发布 → 中等表现
            result = review_svc.record_result(
                snapshot_id=snapshot.id,
                score=120,
                num_comments=35,
                is_deleted=False,
                result_source="manual",
            )
            print(f"  模拟结果: 未删, score=120")
        else:
            # fit → 高表现
            result = review_svc.record_result(
                snapshot_id=snapshot.id,
                score=450,
                num_comments=80,
                is_deleted=False,
                result_source="manual",
            )
            print(f"  模拟结果: 未删, score=450")

        print(f"  result_id: {result.id}")

        # 复盘
        review = review_svc.review_snapshot(snapshot.id)
        print(f"  review_id: {review.id}")
        print(f"  validated_items: {len(review.validated_items)}")
        print(f"  invalidated_items: {len(review.invalidated_items)}")
        print(f"  discrepancy_attribution: {review.discrepancy_attribution}")
        print(f"  pattern_outcomes: {review.pattern_outcomes}")

        check(review.validated_items or review.invalidated_items,
              "复盘产出 validated/invalidated 项")

        review_results[tc_name] = review

    # 验证规律 validation_history 已追加(但 status 仍为 candidate)
    with get_session() as s:
        for p in s.query(KnowledgePattern).all():
            history = p.validation_history or []
            print(f"\n  pattern {p.id[:8]}: status={p.status}, validation_count={len(history)}")
            check(p.status == "candidate",
                  f"pattern status 仍为 candidate(单次复盘不自动迁移) (实际 {p.status})")

    return review_results


# ============================================================
# Step 1.4: 规律 validation_history 累计 + 状态迁移
# ============================================================
def test_pattern_validation_accumulation() -> None:
    section("Step 1.4 规律 validation_history 累计 + 状态迁移")

    # 取第一个 candidate 规律
    with get_session() as s:
        kp = s.query(KnowledgePattern).filter_by(status="candidate").first()
        pattern_id = kp.id
        # 取一个 ReferenceItem 作为 case
        item = s.query(ReferenceItem).first()
        case_item_id = item.id
        print(f"  目标规律: {pattern_id[:8]} (type={kp.pattern_type}, status={kp.status})")
        print(f"  初始 validation_count: {len(kp.validation_history or [])}")

    # 阈值默认: confirmed>=3 且 contradicted=0 → supported
    from app.config import settings
    threshold = settings.pattern_promote_threshold
    print(f"  promote_threshold: {threshold}")

    # 1. 累计 confirmed(threshold - 1 次,应仍为 candidate)
    subsection(f"累计 {threshold - 1} 次 confirmed(应仍为 candidate)")
    for i in range(threshold - 1):
        kp = pattern_miner.human_confirm_validation(
            pattern_id=pattern_id,
            case_item_id=case_item_id,
            outcome="confirmed",
            reviewer=f"tester_{i}",
            note=f"第 {i+1} 次确认",
        )
        print(f"  第 {i+1} 次 confirmed → status={kp.status}, count={len(kp.validation_history)}")

    check(kp.status == "candidate",
          f"{threshold - 1} 次 confirmed 后 status 仍为 candidate (实际 {kp.status})")
    check(len(kp.validation_history) == threshold - 1,
          f"validation_history 长度={threshold - 1} (实际 {len(kp.validation_history)})")

    # 2. 第 threshold 次 confirmed → 应迁移为 supported
    subsection(f"第 {threshold} 次 confirmed(应迁移为 supported)")
    kp = pattern_miner.human_confirm_validation(
        pattern_id=pattern_id,
        case_item_id=case_item_id,
        outcome="confirmed",
        reviewer=f"tester_{threshold}",
        note=f"第 {threshold} 次确认(达阈值)",
    )
    print(f"  第 {threshold} 次 confirmed → status={kp.status}, count={len(kp.validation_history)}")
    check(kp.status == "supported",
          f"达阈值后 status 迁移为 supported (实际 {kp.status})")
    check(len(kp.validation_history) == threshold,
          f"validation_history 长度={threshold} (实际 {len(kp.validation_history)})")

    # 3. 验证 AI 不能自行迁移状态
    subsection("验证 AI 不能自行认定规律已验证")
    # 模拟:不经过 human_confirm_validation,直接调 record_validation(模拟 AI 自动追加)
    with get_session() as s:
        before_kp = s.query(KnowledgePattern).filter_by(id=pattern_id).first()
        before_status = before_kp.status
        before_count = len(before_kp.validation_history)

    # AI 自动追加一条(AI 模式,不经过人工确认)
    pattern_miner.record_validation(
        pattern_id=pattern_id,
        case_item_id=case_item_id,
        outcome="confirmed",
        note="AI 自动追加(不应触发迁移)",
    )
    # AI 追加后 status 不应改变(只有 human_confirm_validation 才调 update_pattern_status)
    with get_session() as s:
        after_kp = s.query(KnowledgePattern).filter_by(id=pattern_id).first()
        check(after_kp.status == before_status,
              f"AI 追加不改变 status (前 {before_status} → 后 {after_kp.status})")
        check(len(after_kp.validation_history) == before_count + 1,
              f"AI 追加只增加 history (+1) (实际 {len(after_kp.validation_history)})")

    # 4. 测试反驳路径:另取一个 candidate,累计 contradicted 达阈值 → refuted
    subsection("测试反驳路径(contradicted 累计 → refuted)")
    with get_session() as s:
        kp2 = s.query(KnowledgePattern).filter_by(status="candidate").first()
        if kp2:
            kp2_id = kp2.id
            print(f"  目标规律2: {kp2_id[:8]} (type={kp2.pattern_type})")
            refute_threshold = settings.pattern_refute_threshold
            for i in range(refute_threshold):
                kp2 = pattern_miner.human_confirm_validation(
                    pattern_id=kp2_id,
                    case_item_id=case_item_id,
                    outcome="contradicted",
                    reviewer=f"refuter_{i}",
                    note=f"第 {i+1} 次反驳",
                )
                print(f"  第 {i+1} 次 contradicted → status={kp2.status}")
            check(kp2.status == "refuted",
                  f"{refute_threshold} 次 contradicted 后 status=refuted (实际 {kp2.status})")
        else:
            print("  (无 candidate 规律可测试反驳,跳过)")

    # 5. 人工强制覆盖状态
    subsection("测试人工强制覆盖状态(human_override_pattern_status)")
    with get_session() as s:
        kp3 = s.query(KnowledgePattern).filter(KnowledgePattern.status != "candidate").first()
        if kp3:
            kp3_id = kp3.id
            old_status = kp3.status
            print(f"  目标规律3: {kp3_id[:8]} (旧 status={old_status})")
            kp3 = pattern_miner.human_override_pattern_status(
                pattern_id=kp3_id,
                new_status="inconclusive",
                reason="人工判定证据矛盾",
            )
            check(kp3.status == "inconclusive",
                  f"强制覆盖 status=inconclusive (实际 {kp3.status})")
            # 验证审计记录
            last_entry = (kp3.validation_history or [])[-1]
            check(last_entry.get("outcome") == "human_override",
                  f"审计记录 outcome=human_override (实际 {last_entry.get('outcome')})")
            check("human_override" in (last_entry.get("note") or ""),
                  f"审计记录 note 含 human_override")
        else:
            print("  (无非 candidate 规律可测试覆盖,跳过)")


# ============================================================
# Step 1.5: LLM 调用日志验证
# ============================================================
def test_llm_call_logs() -> None:
    section("Step 1.5 LLM 调用日志验证(模型/输入/输出/耗时/结果)")

    # 触发一次 classifier + analyzer 调用
    subsection("触发 LLM 调用(classifier + analyzer)")

    # 触发 classifier(对一条新 ReferenceItem 打标签)
    with get_session() as s:
        item = s.query(ReferenceItem).first()
        item_id = item.id
    classifier.label_item(item_id, use_llm=True)

    clf_log = classifier.get_last_call_log()
    check(clf_log is not None, "classifier 调用日志非空")
    if clf_log:
        print(f"  classifier log:")
        print(f"    task: {clf_log.task}")
        print(f"    model: {clf_log.model}")
        print(f"    source: {clf_log.source}")
        print(f"    success: {clf_log.success}")
        print(f"    latency_ms: {clf_log.latency_ms}")
        print(f"    prompt_version: {clf_log.prompt_version}")
        print(f"    user_prompt 长度: {len(clf_log.user_prompt or '')}")
        print(f"    response_text 长度: {len(clf_log.response_text or '')}")
        print(f"    parsed_json keys: {list((clf_log.parsed_json or {}).keys())}")

        check(clf_log.task == "classify", f"task=classify (实际 {clf_log.task})")
        check(clf_log.model == "qwen2.5:7b", f"model=qwen2.5:7b (实际 {clf_log.model})")
        check(clf_log.source == "mock", f"source=mock (实际 {clf_log.source})")
        check(clf_log.success is True, f"success=True")
        check(clf_log.latency_ms >= 0, f"latency_ms>=0 (实际 {clf_log.latency_ms})")
        check(clf_log.user_prompt is not None and len(clf_log.user_prompt) > 0,
              "user_prompt 非空")
        check(clf_log.response_text is not None and len(clf_log.response_text) > 0,
              "response_text 非空")
        check(clf_log.parsed_json is not None, "parsed_json 非空")

    # 触发 analyzer
    content_analyzer.analyze_new_content(
        title="Test content for LLM log",
        selftext="This is a test to verify LLM call logging.",
        target_subreddit="learnprogramming",
        use_llm=True,
    )

    anr_log = content_analyzer.get_last_call_log()
    check(anr_log is not None, "analyzer 调用日志非空")
    if anr_log:
        print(f"  analyzer log:")
        print(f"    task: {anr_log.task}")
        print(f"    model: {anr_log.model}")
        print(f"    source: {anr_log.source}")
        print(f"    success: {anr_log.success}")
        print(f"    latency_ms: {anr_log.latency_ms}")
        print(f"    parsed_json keys: {list((anr_log.parsed_json or {}).keys())}")

        check(anr_log.task == "analyze", f"task=analyze (实际 {anr_log.task})")
        check(anr_log.model == "qwen2.5:14b", f"model=qwen2.5:14b (实际 {anr_log.model})")
        check(anr_log.source == "mock", f"source=mock (实际 {anr_log.source})")
        check(anr_log.success is True, f"success=True")

    print("\n  LLM 调用日志验证通过(模型/输入/输出/耗时/结果 均已记录)")


# ============================================================
# Step 1.6: 验证哪些环节必须人工兜底
# ============================================================
def test_human_in_loop_gates() -> None:
    section("Step 1.6 验证人工兜底关键关卡")

    subsection("关卡1: AI 不能自行认定规律已验证")
    with get_session() as s:
        # 所有 supported/refuted 状态的规律,必须有 human_override 或 human_confirm 记录
        non_candidate = s.query(KnowledgePattern).filter(
            KnowledgePattern.status.in_(["supported", "refuted", "inconclusive"])
        ).all()
        for kp in non_candidate:
            history = kp.validation_history or []
            human_confirmed = [h for h in history if "human" in str(h.get("note", "")).lower()
                              or h.get("outcome") == "human_override"]
            check(len(human_confirmed) > 0,
                  f"pattern {kp.id[:8]} status={kp.status} 有人工确认记录")

    subsection("关卡2: 发布前快照 immutable")
    with get_session() as s:
        snap = s.query(ContentAnalysisSnapshot).first()
        if snap:
            # 验证快照核心字段不可变(无 update 方法暴露)
            # 这里只能验证 human_override 创建的是新快照,原快照不变
            orig_verdict = snap.verdict
            check(orig_verdict in ("fit", "fit_after_fix", "not_fit"),
                  f"原快照 verdict 保留 (实际 {orig_verdict})")

    subsection("关卡3: 人工可修正 verdict / 标签 / 召回")
    print("  (已在 Step 1.2 验证:verdict 修正创建新快照,标签修正创建新版本)")

    print("\n  人工兜底关键关卡验证通过")


# ============================================================
# 主流程
# ============================================================
def main() -> None:
    print("=" * 70)
    print("Step 1 技术链路验证(Mock LLM Provider, 零成本)")
    print("=" * 70)
    print(f"数据库: community.db")
    print(f"LLM Provider: mock (确定性规则输出)")

    # 确保数据库已初始化
    init_db()

    # 1.0 前置条件
    verify_preconditions()

    # 1.1 新内容分析
    snapshot_results = test_content_analysis()

    # 1.2 人工兜底
    test_human_override(snapshot_results)

    # 1.3 结果回填 + 复盘
    test_result_and_review(snapshot_results)

    # 1.4 规律 validation_history 累计 + 状态迁移
    test_pattern_validation_accumulation()

    # 1.5 LLM 调用日志
    test_llm_call_logs()

    # 1.6 人工兜底关键关卡
    test_human_in_loop_gates()

    # 总结
    section("Step 1 验证完成")
    print("""
验证结论:
1. 整套产品逻辑能跑通(社区初始化 → 分析 → 人工兜底 → 结果回填 → 复盘 → 规律验证)
2. Mock LLM Provider 可完成 Classifier + ContentAnalyzer 全链路
3. LLM Provider 抽象层正确:每次调用记录模型/输入/输出/耗时/结果
4. 人工兜底关卡有效:
   - AI 不能自行把一次结果认定为"规律已验证"(必须 human_confirm_validation)
   - 单次复盘只追加 validation_history,不直接改 status
   - 状态迁移需累计达阈值(confirmed>=3 且 contradicted=0 → supported)
   - 发布前快照 immutable,人工修正创建新快照
   - 标签修正创建新版本(版本化,不覆盖历史)
5. 必须人工兜底的环节:
   - 社区画像(初始化后可人工复核)
   - ContentAnalysis verdict(人工可修正)
   - topic/scenario/product_visibility 标签(人工可修正)
   - Retrieval 召回案例(人工可过滤不相关案例)
   - 修改建议是否采用(发布前人工决定)
   - 规律验证确认(人工确认 outcome)

下一步(第二阶段):
- 用同一批测试内容比较 2-3 个可实际付费的 LLM provider
- 选型基于:实际可付费 + 实际效果 + 实际成本
""")


if __name__ == "__main__":
    main()
