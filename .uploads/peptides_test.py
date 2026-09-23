"""Peptides LLM 测试一体化脚本(用户本地运行)。

用法:
1. 复制本文件全部内容,保存为 peptides_test.py
2. 确保 Ollama 已启动(ollama serve)
3. 确保 ollama pull qwen2.5:7b (或 14b)
4. 运行: python peptides_test.py
5. 把 stdout 输出的 JSON 全部复制,粘贴回沙箱对话

可选参数:
  python peptides_test.py --model qwen2.5:14b
  python peptides_test.py --base http://localhost:11434
"""
from __future__ import annotations
import argparse, json, re, sys, time
try:
    import requests
except ImportError:
    print("ERROR: 缺少 requests。请运行: pip install requests", file=sys.stderr)
    sys.exit(1)


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
- key_issues: max 3, each must be SPECIFIC (not generic like "improve quality")
- evidence_item_ids: MUST come from the cases provided in context; do NOT invent IDs
- comment_participation_advice: if evidence is insufficient, set evidence_insufficient=true and confidence="insufficient", do NOT fabricate advice
- Do NOT predict exact engagement numbers; use potential_value for value TYPE only
"""


TESTS = [
    {
        "id": "T1_experience",
        "title": "Finally organized my pantry with a label maker \u2014 here's what I learned",
        "selftext": "I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it.",
        "new_content_tags": {"topic_tags": ["organizing", "labeling"], "scenario_tags": [], "structure_tags": ["experience"], "product_visibility": "subtle", "brand_mentions": [], "search_value": "mid", "search_value_reasoning": "rule_based_fallback", "keywords": ["with", "what", "organized", "pantry", "finally", "learned", "maker", "label", "here's"]},
        "all_retrieved_item_ids": ["8a57eb3b-e929-4d42-b239-0163a119a751", "618a646f-6d2a-4848-82c3-a617929b799a", "75c97de5-174e-43bd-8050-950ac18a6e51"],
        "similar_high_count": 2,
        "similar_failure_count": 1,
        "patterns_count": 2,
        "user_prompt": """=== COMMUNITY RULES ===
rules: [{'short_name': 'Be polite.', 'description': "You shouldn't ever be personally attacking another user in this subreddit."}, {'short_name': 'Report Your Affiliations', 'description': "If you're linking to your own site, you need to disclose that fact. Either through getting flair from a moderator or by telling people when you're linking your own site."}, {'short_name': 'Low-Quality Spam', 'description': 'Low-Quality Spam/Astroturfing is not allowed. Necroing posts, using throwaways to shill sites, spamming random posts/comment chains and more will result in a ban. '}, {'short_name': 'You must be 18 or older', 'description': 'You must be 18 years of age or older to view and engage in this subreddit.'}, {'short_name': 'No sourcing of prescribed GLP-1 peptides ', 'description': 'These compounds cannot be sourced here, no vendor discussion for them. '}, {'short_name': 'No source discussion', 'description': ''}]
karma_requirement: None
account_age_requirement: None
flair_required: False
link_restricted: False
commercial_content_restricted: False
post_frequency_limit: None
sensitive_content_rules: []

=== COMMUNITY SUMMARY ===
top_topics: [{'topic': 'general', 'count': 4}, {'topic': 'baking', 'count': 1}]
common_structures: [{'structure': 'question', 'count': 5}, {'structure': 'experience', 'count': 4}]
product_acceptance: {'high': {'none': 2}, 'mid': {'none': 2}, 'low': {'none': 1}, 'unknown': {}}

=== SIMILAR HIGH-PERFORMANCE CASES ===
[high, score=131, comments=78] No more source discussion. At least for now, none can be allowed. | structure=question,experience, product=none, search=low, topics=general
[high, score=11, comments=11] Is my reta and tesa water supposded to look like this? | structure=question,experience, product=none, search=high, topics=general

=== SIMILAR FAILURE/LOW CASES ===
[failure, score=0, comments=12] Thinking of stacking Reta with GHK-Cu, MOTS-C | structure=question,experience, product=none, search=mid, topics=general

=== KNOWLEDGE PATTERNS ===
[fire, status=candidate, samples=2] mid tier 帖子中,question 结构出现 2/2 次。代表性帖子: how to store unreconstituted glutathion?
[fire, status=candidate, samples=2] high tier 帖子中,question 结构出现 2/2 次。代表性帖子: Is my reta and tesa water supposded to look like this?

=== NEW CONTENT TO ANALYZE ===
Finally organized my pantry with a label maker — here's what I learned
I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it.""",
    },
    {
        "id": "T2_question",
        "title": "Looking for recommendations: label maker for organizing my home office files?",
        "selftext": "Setting up a home office and need to label file folders, cable runs, and storage bins. Anyone have a label printer they recommend? Budget-friendly preferred.",
        "new_content_tags": {"topic_tags": ["organizing", "labeling"], "scenario_tags": [], "structure_tags": ["question"], "product_visibility": "none", "brand_mentions": [], "search_value": "mid", "search_value_reasoning": "rule_based_fallback", "keywords": ["organizing", "files?", "home", "recommendations:", "office", "maker", "looking", "label"]},
        "all_retrieved_item_ids": ["8a57eb3b-e929-4d42-b239-0163a119a751", "618a646f-6d2a-4848-82c3-a617929b799a", "75c97de5-174e-43bd-8050-950ac18a6e51"],
        "similar_high_count": 2,
        "similar_failure_count": 1,
        "patterns_count": 2,
        "user_prompt": """=== COMMUNITY RULES ===
rules: [{'short_name': 'Be polite.', 'description': "You shouldn't ever be personally attacking another user in this subreddit."}, {'short_name': 'Report Your Affiliations', 'description': "If you're linking to your own site, you need to disclose that fact. Either through getting flair from a moderator or by telling people when you're linking your own site."}, {'short_name': 'Low-Quality Spam', 'description': 'Low-Quality Spam/Astroturfing is not allowed. Necroing posts, using throwaways to shill sites, spamming random posts/comment chains and more will result in a ban. '}, {'short_name': 'You must be 18 or older', 'description': 'You must be 18 years of age or older to view and engage in this subreddit.'}, {'short_name': 'No sourcing of prescribed GLP-1 peptides ', 'description': 'These compounds cannot be sourced here, no vendor discussion for them. '}, {'short_name': 'No source discussion', 'description': ''}]
karma_requirement: None
account_age_requirement: None
flair_required: False
link_restricted: False
commercial_content_restricted: False
post_frequency_limit: None
sensitive_content_rules: []

=== COMMUNITY SUMMARY ===
top_topics: [{'topic': 'general', 'count': 4}, {'topic': 'baking', 'count': 1}]
common_structures: [{'structure': 'question', 'count': 5}, {'structure': 'experience', 'count': 4}]
product_acceptance: {'high': {'none': 2}, 'mid': {'none': 2}, 'low': {'none': 1}, 'unknown': {}}

=== SIMILAR HIGH-PERFORMANCE CASES ===
[high, score=131, comments=78] No more source discussion. At least for now, none can be allowed. | structure=question,experience, product=none, search=low, topics=general
[high, score=11, comments=11] Is my reta and tesa water supposded to look like this? | structure=question,experience, product=none, search=high, topics=general

=== SIMILAR FAILURE/LOW CASES ===
[failure, score=0, comments=12] Thinking of stacking Reta with GHK-Cu, MOTS-C | structure=question,experience, product=none, search=mid, topics=general

=== KNOWLEDGE PATTERNS ===
[fire, status=candidate, samples=2] mid tier 帖子中,question 结构出现 2/2 次。代表性帖子: how to store unreconstituted glutathion?
[fire, status=candidate, samples=2] high tier 帖子中,question 结构出现 2/2 次。代表性帖子: Is my reta and tesa water supposded to look like this?

=== NEW CONTENT TO ANALYZE ===
Looking for recommendations: label maker for organizing my home office files?
Setting up a home office and need to label file folders, cable runs, and storage bins. Anyone have a label printer they recommend? Budget-friendly preferred.""",
    },
    {
        "id": "T3_promotional",
        "title": "The Niimbot label printer changed my organizing game \u2014 40% off this week!",
        "selftext": "Just sharing a great deal I found. Niimbot label printer 40% off on Amazon this week. Link in comments. Perfect for home organization.",
        "new_content_tags": {"topic_tags": ["organizing", "labeling"], "scenario_tags": [], "structure_tags": ["promotional"], "product_visibility": "promotional", "brand_mentions": [], "search_value": "low", "search_value_reasoning": "rule_based_fallback", "keywords": ["changed", "this", "game", "week!", "organizing", "niimbot", "printer", "label"]},
        "all_retrieved_item_ids": ["8a57eb3b-e929-4d42-b239-0163a119a751", "618a646f-6d2a-4848-82c3-a617929b799a", "75c97de5-174e-43bd-8050-950ac18a6e51"],
        "similar_high_count": 2,
        "similar_failure_count": 1,
        "patterns_count": 2,
        "user_prompt": """=== COMMUNITY RULES ===
rules: [{'short_name': 'Be polite.', 'description': "You shouldn't ever be personally attacking another user in this subreddit."}, {'short_name': 'Report Your Affiliations', 'description': "If you're linking to your own site, you need to disclose that fact. Either through getting flair from a moderator or by telling people when you're linking your own site."}, {'short_name': 'Low-Quality Spam', 'description': 'Low-Quality Spam/Astroturfing is not allowed. Necroing posts, using throwaways to shill sites, spamming random posts/comment chains and more will result in a ban. '}, {'short_name': 'You must be 18 or older', 'description': 'You must be 18 years of age or older to view and engage in this subreddit.'}, {'short_name': 'No sourcing of prescribed GLP-1 peptides ', 'description': 'These compounds cannot be sourced here, no vendor discussion for them. '}, {'short_name': 'No source discussion', 'description': ''}]
karma_requirement: None
account_age_requirement: None
flair_required: False
link_restricted: False
commercial_content_restricted: False
post_frequency_limit: None
sensitive_content_rules: []

=== COMMUNITY SUMMARY ===
top_topics: [{'topic': 'general', 'count': 4}, {'topic': 'baking', 'count': 1}]
common_structures: [{'structure': 'question', 'count': 5}, {'structure': 'experience', 'count': 4}]
product_acceptance: {'high': {'none': 2}, 'mid': {'none': 2}, 'low': {'none': 1}, 'unknown': {}}

=== SIMILAR HIGH-PERFORMANCE CASES ===
[high, score=131, comments=78] No more source discussion. At least for now, none can be allowed. | structure=question,experience, product=none, search=low, topics=general
[high, score=11, comments=11] Is my reta and tesa water supposded to look like this? | structure=question,experience, product=none, search=high, topics=general

=== SIMILAR FAILURE/LOW CASES ===
[failure, score=0, comments=12] Thinking of stacking Reta with GHK-Cu, MOTS-C | structure=question,experience, product=none, search=mid, topics=general

=== KNOWLEDGE PATTERNS ===
[fire, status=candidate, samples=2] mid tier 帖子中,question 结构出现 2/2 次。代表性帖子: how to store unreconstituted glutathion?
[fire, status=candidate, samples=2] high tier 帖子中,question 结构出现 2/2 次。代表性帖子: Is my reta and tesa water supposded to look like this?

=== NEW CONTENT TO ANALYZE ===
The Niimbot label printer changed my organizing game — 40% off this week!
Just sharing a great deal I found. Niimbot label printer 40% off on Amazon this week. Link in comments. Perfect for home organization.""",
    },
]


def extract_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def call_ollama(base, model, system_prompt, user_prompt, temperature, max_tokens, timeout=300):
    start = time.time()
    raw = ""
    parsed = None
    success = False
    error = None
    try:
        resp = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "format": "json",
            },
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get("message", {}).get("content", "")
        parsed = extract_json(raw)
        success = parsed is not None
        if not success:
            error = "JSON parse failed"
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
    latency = int((time.time() - start) * 1000)
    return {
        "model": model,
        "response_text": raw,
        "parsed_json": parsed,
        "success": success,
        "error": error,
        "latency_ms": latency,
    }


def validate_evidence(parsed, allowed_ids):
    if not parsed:
        return {"valid": False, "reason": "no parsed JSON"}
    allowed = set(allowed_ids)
    claimed = set()
    for issue in parsed.get("key_issues", []):
        for eid in issue.get("evidence_item_ids", []):
            claimed.add(eid)
    invalid = claimed - allowed
    return {
        "valid": len(invalid) == 0,
        "llm_claimed_ids": sorted(claimed),
        "invalid_ids": sorted(invalid),
        "allowed_ids": sorted(allowed),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", default="qwen2.5:7b")
    p.add_argument("--base", default="http://localhost:11434")
    p.add_argument("--temperature", type=float, default=0.3)
    p.add_argument("--max-tokens", type=int, default=2000)
    args = p.parse_args()

    # 检查 Ollama
    try:
        r = requests.get(f"{args.base}/api/tags", timeout=5)
        r.raise_for_status()
        tags = r.json()
        available = [m["name"] for m in tags.get("models", [])]
        print(f"Ollama 在线,模型: {available}", file=sys.stderr)
    except Exception as e:
        print(f"ERROR: Ollama 不可用 ({args.base}): {e}", file=sys.stderr)
        sys.exit(1)

    print(f"开始 {len(TESTS)} 条测试,模型={args.model}", file=sys.stderr)

    results = []
    for i, t in enumerate(TESTS):
        print(f"\n[{i+1}/{len(TESTS)}] {t['id']}: {t['title'][:60]}", file=sys.stderr)
        print(f"  调用 Ollama...", file=sys.stderr)
        call = call_ollama(
            base=args.base,
            model=args.model,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=t["user_prompt"],
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        v = validate_evidence(call["parsed_json"], t["all_retrieved_item_ids"])
        result = {
            "test_id": t["id"],
            "title": t["title"],
            "selftext": t["selftext"],
            "new_content_tags": t["new_content_tags"],
            "all_retrieved_item_ids": t["all_retrieved_item_ids"],
            "similar_high_count": t["similar_high_count"],
            "similar_failure_count": t["similar_failure_count"],
            "patterns_count": t["patterns_count"],
            "llm_call": call,
            "evidence_validation": v,
        }
        results.append(result)
        if call["success"]:
            parsed = call["parsed_json"]
            print(f"  OK {call['latency_ms']}ms verdict={parsed.get('verdict')}", file=sys.stderr)
        else:
            print(f"  FAIL: {call['error']}", file=sys.stderr)

    output = {
        "model": args.model,
        "base": args.base,
        "temperature": args.temperature,
        "results": results,
    }
    # 结果输出到 stdout(用户复制)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
