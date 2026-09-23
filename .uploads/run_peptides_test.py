#!/usr/bin/env python3
"""
Peptides LLM 测试脚本(本地运行)
用法:
    python3 run_peptides_test.py
    # 或指定参数
    python3 run_peptides_test.py --base http://localhost:11434 --model qwen2.5:7b

运行后会:
1. 检查 Ollama 服务
2. 列出可用模型
3. 跑 3 条 Peptides 测试
4. 保存完整结果到 peptides_results.json
5. 打印结果摘要

把 peptides_results.json 的内容贴回沙箱即可。
"""
import json
import time
import argparse
import urllib.request
import urllib.error
import sys
import os

SYSTEM_PROMPT = """You are a Reddit content analyst for a label printer product (NIIMBOT).
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
- Base your verdict, key_issues, and suggestions PRIMARILY on the evidence provided in the context above (community rules, similar posts, patterns). Do NOT apply generic Reddit advice that is not supported by the provided evidence for THIS community.
- key_issues: max 3, each must be SPECIFIC to THIS community (not generic like "improve quality")
- evidence_item_ids: MUST come from the cases provided in context; do NOT invent IDs. If an issue cites a community rule, reference the rule; if it cites a similar post, reference that post's id.
- comment_participation_advice: if evidence is insufficient, set evidence_insufficient=true and confidence="insufficient", do NOT fabricate advice
- Do NOT predict exact engagement numbers; use potential_value for value TYPE only
"""

COMMUNITY_RULES = """rules: [{'short_name': 'Be polite.', 'description': "You shouldn't ever be personally attacking another user in this subreddit."}, {'short_name': 'Report Your Affiliations', 'description': "If you're linking to your own site, you need to disclose that fact. Either through getting flair from a moderator or by telling people when you're linking your own site."}, {'short_name': 'Low-Quality Spam', 'description': 'Low-Quality Spam/Astroturfing is not allowed. Necroing posts, using throwaways to shill sites, spamming random posts/comment chains and more will result in a ban. '}, {'short_name': 'You must be 18 or older', 'description': 'You must be 18 years of age or older to view and engage in this subreddit.'}, {'short_name': 'No sourcing of prescribed GLP-1 peptides ', 'description': 'These compounds cannot be sourced here, no vendor discussion for them. '}, {'short_name': 'No source discussion', 'description': ''}]
karma_requirement: None
account_age_requirement: None
flair_required: False
link_restricted: False
commercial_content_restricted: False
post_frequency_limit: None
sensitive_content_rules: []"""

COMMUNITY_SUMMARY = """top_topics: [{'topic': 'general', 'count': 4}, {'topic': 'baking', 'count': 1}]
common_structures: [{'structure': 'question', 'count': 5}, {'structure': 'experience', 'count': 4}]
product_acceptance: {'high': {'none': 2}, 'mid': {'none': 2}, 'low': {'none': 1}, 'unknown': {}}"""

SIMILAR_HIGH = """[high, score=131, comments=78] No more source discussion. At least for now, none can be allowed. | structure=question,experience, product=none, search=low, topics=general
[high, score=11, comments=11] Is my reta and tesa water supposded to look like this? | structure=question,experience, product=none, search=high, topics=general"""

SIMILAR_FAILURE = """[failure, score=0, comments=12] Thinking of stacking Reta with GHK-Cu, MOTS-C | structure=question,experience, product=none, search=mid, topics=general"""

KNOWLEDGE_PATTERNS = """[fire, status=candidate, samples=2] mid tier 帖子中,question 结构出现 2/2 次。代表性帖子: how to store unreconstituted glutathion?
[fire, status=candidate, samples=2] high tier 帖子中,question 结构出现 2/2 次。代表性帖子: Is my reta and tesa water supposded to look like this?"""

ALL_RETRIEVED_IDS = [
    "8a57eb3b-e929-4d42-b239-0163a119a751",
    "618a646f-6d2a-4848-82c3-a617929b799a",
    "75c97de5-174e-43bd-8050-950ac18a6e51",
]

TESTS = [
    {
        "id": "T1_experience",
        "title": "Finally organized my pantry with a label maker — here's what I learned",
        "selftext": "I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it.",
        "new_content_tags": {
            "topic_tags": ["organizing", "labeling"],
            "scenario_tags": [],
            "structure_tags": ["experience"],
            "product_visibility": "subtle",
            "brand_mentions": [],
            "search_value": "mid",
            "search_value_reasoning": "rule_based_fallback",
        },
    },
    {
        "id": "T2_question",
        "title": "Looking for recommendations: label maker for organizing my home office files?",
        "selftext": "Setting up a home office and need to label file folders, cable runs, and storage bins. Anyone have a label printer they recommend? Budget-friendly preferred.",
        "new_content_tags": {
            "topic_tags": ["organizing", "labeling"],
            "scenario_tags": [],
            "structure_tags": ["question"],
            "product_visibility": "none",
            "brand_mentions": [],
            "search_value": "mid",
            "search_value_reasoning": "rule_based_fallback",
        },
    },
    {
        "id": "T3_promotional",
        "title": "The Niimbot label printer changed my organizing game — 40% off this week!",
        "selftext": "Just sharing a great deal I found. Niimbot label printer 40% off on Amazon this week. Link in comments. Perfect for home organization.",
        "new_content_tags": {
            "topic_tags": ["organizing", "labeling"],
            "scenario_tags": [],
            "structure_tags": ["promotional"],
            "product_visibility": "promotional",
            "brand_mentions": [],
            "search_value": "low",
            "search_value_reasoning": "rule_based_fallback",
        },
    },
]


def build_user_prompt(test):
    return f"""=== COMMUNITY RULES ===
{COMMUNITY_RULES}

=== COMMUNITY SUMMARY ===
{COMMUNITY_SUMMARY}

=== SIMILAR HIGH-PERFORMANCE CASES ===
{SIMILAR_HIGH}

=== SIMILAR FAILURE/LOW CASES ===
{SIMILAR_FAILURE}

=== KNOWLEDGE PATTERNS ===
{KNOWLEDGE_PATTERNS}

=== NEW CONTENT TO ANALYZE ===
{test['title']}
{test['selftext']}"""


def check_ollama(base):
    try:
        req = urllib.request.Request(base + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            return True, data
    except Exception as e:
        return False, str(e)


def call_ollama(base, model, system_prompt, user_prompt, temperature=0.3, max_tokens=2000):
    start = time.time()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
        "format": "json",
    }
    try:
        req = urllib.request.Request(
            base + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode())
            raw = (data.get("message") or {}).get("content", "")
            parsed = None
            try:
                parsed = json.loads(raw)
            except Exception:
                import re
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                if m:
                    try:
                        parsed = json.loads(m.group(0))
                    except Exception:
                        pass
            latency = round((time.time() - start) * 1000)
            return {
                "model": model,
                "response_text": raw,
                "parsed_json": parsed,
                "success": parsed is not None,
                "error": None if parsed is not None else "JSON parse failed",
                "latency_ms": latency,
            }
    except Exception as e:
        return {
            "model": model,
            "response_text": "",
            "parsed_json": None,
            "success": False,
            "error": str(e),
            "latency_ms": round((time.time() - start) * 1000),
        }


def validate_evidence(parsed, allowed_ids):
    if not parsed:
        return {"valid": False, "reason": "no parsed JSON"}
    allowed = set(allowed_ids)
    claimed = set()
    for issue in (parsed.get("key_issues") or []):
        for eid in (issue.get("evidence_item_ids") or []):
            claimed.add(eid)
    invalid = [x for x in claimed if x not in allowed]
    return {
        "valid": len(invalid) == 0,
        "llm_claimed_ids": sorted(claimed),
        "invalid_ids": sorted(invalid),
        "allowed_ids": sorted(allowed),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:11434")
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--temp", type=float, default=0.3)
    parser.add_argument("--maxtok", type=int, default=2000)
    args = parser.parse_args()

    print("=" * 60)
    print("Peptides LLM 测试 (本地 Ollama)")
    print("=" * 60)

    # Step 1: Check Ollama
    print("\n[1/4] 检查 Ollama 服务...")
    ok, info = check_ollama(args.base)
    if not ok:
        print(f"  ✗ Ollama 不可达: {info}")
        print(f"  请确认 Ollama 已启动: ollama serve")
        sys.exit(1)
    models = [m.get("name", "?") for m in info.get("models", [])]
    print(f"  ✓ Ollama 正常, 共 {len(models)} 个模型")
    for m in models:
        print(f"    - {m}")

    # Check if target model exists
    has_qwen = any("qwen" in m.lower() for m in models)
    if not has_qwen:
        print(f"\n  ⚠ 未找到 Qwen 模型,可用模型: {models}")
        print(f"  请先拉取: ollama pull {args.model}")
        sys.exit(1)
    if args.model not in models:
        # Try partial match
        match = [m for m in models if args.model.split(":")[0] in m]
        if match:
            print(f"  ⚠ 精确匹配 {args.model} 不在列表,使用相近模型: {match[0]}")
            args.model = match[0]
        else:
            print(f"  ⚠ 模型 {args.model} 不在列表,仍尝试调用...")
    else:
        print(f"  ✓ 目标模型 {args.model} 可用")

    # Step 2: Quick model test
    print(f"\n[2/4] 快速测试模型 {args.model} (简单 JSON)...")
    quick = call_ollama(
        args.base, args.model,
        "Output valid JSON only.",
        'Output this exact JSON: {"status": "ok", "model": "qwen"}',
        0.0, 100,
    )
    if quick["success"]:
        print(f"  ✓ JSON 返回正常 ({quick['latency_ms']}ms)")
    else:
        print(f"  ✗ JSON 返回失败: {quick['error']}")
        print(f"  原始 response: {quick['response_text'][:500]}")
        print(f"  继续 3 条测试...")

    # Step 3: Run 3 Peptides tests
    print(f"\n[3/4] 运行 3 条 Peptides 测试...")
    results = []
    for i, test in enumerate(TESTS):
        print(f"\n  --- [{i+1}/3] {test['id']} ---")
        print(f"  Title: {test['title'][:60]}...")
        user_prompt = build_user_prompt(test)
        call = call_ollama(
            args.base, args.model,
            SYSTEM_PROMPT, user_prompt,
            args.temp, args.maxtok,
        )
        v = validate_evidence(call["parsed_json"], ALL_RETRIEVED_IDS)

        if call["success"]:
            print(f"  ✓ 成功 ({call['latency_ms']}ms) verdict={call['parsed_json'].get('verdict', '?')}")
            print(f"  evidence_ids: {v['llm_claimed_ids']}")
            if not v["valid"]:
                print(f"  ⚠ evidence 校验失败! 无效 ID: {v['invalid_ids']}")
        else:
            print(f"  ✗ 失败: {call['error']}")

        results.append({
            "test_id": test["id"],
            "title": test["title"],
            "selftext": test["selftext"],
            "new_content_tags": test["new_content_tags"],
            "all_retrieved_item_ids": ALL_RETRIEVED_IDS,
            "llm_call": call,
            "evidence_validation": v,
        })

    # Step 4: Save results
    print(f"\n[4/4] 保存结果...")
    output = {
        "model": args.model,
        "base": args.base,
        "temperature": args.temp,
        "max_tokens": args.maxtok,
        "ollama_models": models,
        "results": results,
    }
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "peptides_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"  ✓ 已保存到: {out_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("摘要")
    print("=" * 60)
    for r in results:
        c = r["llm_call"]
        v = r["evidence_validation"]
        print(f"\n{r['test_id']}:")
        if c["success"]:
            p = c["parsed_json"]
            print(f"  verdict: {p.get('verdict', '?')}")
            print(f"  verdict_reason: {str(p.get('verdict_reason', '?'))[:100]}")
            ki = p.get("key_issues", [])
            print(f"  key_issues ({len(ki)}):")
            for j, issue in enumerate(ki[:3]):
                print(f"    [{j+1}] {issue.get('issue', '?')[:80]}")
                print(f"        evidence_ids: {issue.get('evidence_item_ids', [])}")
            print(f"  evidence 校验: {'✓ 有效' if v['valid'] else '✗ 有无效 ID: ' + str(v['invalid_ids'])}")
            print(f"  LLM 引用的 evidence_ids: {v['llm_claimed_ids']}")
            print(f"  允许的 evidence_ids: {v['allowed_ids']}")
        else:
            print(f"  ✗ 失败: {c['error']}")

    print("\n" + "=" * 60)
    print(f"完整结果已保存到: {out_path}")
    print("请将此文件内容贴回沙箱以供分析。")
    print("=" * 60)


if __name__ == "__main__":
    main()
