import json, time, sys, os
import urllib.request

BASE = "http://localhost:11434"
MODEL = "qwen2.5:7b"

SYS = """You are a Reddit content analyst for a label printer product (NIIMBOT).
You help decide whether planned content fits a target subreddit and how to improve it.
Output valid JSON only, no markdown, no explanation.

Schema:
{"verdict":"fit|fit_after_fix|not_fit","verdict_reason":"string","key_issues":[{"issue":"specific problem","why":"why this is a problem in THIS community","evidence_type":["community_rule","similar_content","high_performance_content","low_performance_content","knowledge_pattern"],"evidence_item_ids":["id1"],"fix":"specific actionable fix"}],"modification_suggestions":[{"target":"title|body","current":"whats wrong","suggested":"replacement","reason":"why better"}],"comment_participation_advice":{"should_reply_natural_comments":true,"should_supplement_own_comment":false,"should_wait_for_natural_discussion":true,"should_share_product_in_comments":false,"should_participate_before_posting":false,"confidence":"high|medium|low|insufficient","reasoning":"based on","evidence_insufficient":false},"potential_value":{"value_types":["interaction","discussion","search","product_awareness","community_penetration"],"reasoning":"based on"},"evidence":{"community_rule":true,"similar_content_count":5,"high_performance_count":2,"mid_performance_count":2,"low_performance_count":1,"knowledge_patterns_applied":["pattern_id1"]}}

Rules:
- Base your verdict, key_issues, and suggestions PRIMARILY on the evidence provided in the context above (community rules, similar posts, patterns). Do NOT apply generic Reddit advice that is not supported by the provided evidence for THIS community.
- key_issues: max 3, each must be SPECIFIC to THIS community (not generic like "improve quality")
- evidence_item_ids: MUST come from the cases provided in context; do NOT invent IDs.
- comment_participation_advice: if evidence insufficient, set evidence_insufficient=true and confidence="insufficient", do NOT fabricate advice
- Do NOT predict exact engagement numbers; use potential_value for value TYPE only"""

RULES = "rules: [{'short_name':'Be polite.'},{'short_name':'Report Your Affiliations','description':'If you link to your own site, you need to disclose that fact.'},{'short_name':'Low-Quality Spam','description':'Astroturfing is not allowed. Will result in a ban.'},{'short_name':'You must be 18 or older'},{'short_name':'No sourcing of prescribed GLP-1 peptides','description':'These compounds cannot be sourced here, no vendor discussion for them.'},{'short_name':'No source discussion','description':''}]"
SUMMARY = "top_topics: [{'topic':'general','count':4},{'topic':'baking','count':1}]\ncommon_structures: [{'structure':'question','count':5},{'structure':'experience','count':4}]\nproduct_acceptance: {'high':{'none':2},'mid':{'none':2},'low':{'none':1}}"
HIGH = "[high, score=131, comments=78] No more source discussion. At least for now, none can be allowed. | structure=question,experience, product=none, search=low, topics=general\n[high, score=11, comments=11] Is my reta and tesa water supposded to look like this? | structure=question,experience, product=none, search=high, topics=general"
FAIL = "[failure, score=0, comments=12] Thinking of stacking Reta with GHK-Cu, MOTS-C | structure=question,experience, product=none, search=mid, topics=general"
PAT = "[fire, status=candidate, samples=2] mid tier posts, question structure 2/2 times. example: how to store unreconstituted glutathion?\n[fire, status=candidate, samples=2] high tier posts, question structure 2/2 times. example: Is my reta and tesa water supposded to look like this?"

ALLOWED_IDS = ["8a57eb3b-e929-4d42-b239-0163a119a751","618a646f-6d2a-4848-82c3-a617929b799a","75c97de5-174e-43bd-8050-950ac18a6e51"]

TESTS = [
    {"id":"T1_experience","title":"Finally organized my pantry with a label maker — here's what I learned","selftext":"I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it."},
    {"id":"T2_question","title":"Looking for recommendations: label maker for organizing my home office files?","selftext":"Setting up a home office and need to label file folders, cable runs, and storage bins. Anyone have a label printer they recommend? Budget-friendly preferred."},
    {"id":"T3_promotional","title":"The Niimbot label printer changed my organizing game — 40% off this week!","selftext":"Just sharing a great deal I found. Niimbot label printer 40% off on Amazon this week. Link in comments. Perfect for home organization."},
]

def build_prompt(t):
    return f"""=== COMMUNITY RULES ===
{RULES}

=== COMMUNITY SUMMARY ===
{SUMMARY}

=== SIMILAR HIGH-PERFORMANCE CASES ===
{HIGH}

=== SIMILAR FAILURE/LOW CASES ===
{FAIL}

=== KNOWLEDGE PATTERNS ===
{PAT}

=== NEW CONTENT TO ANALYZE ===
{t['title']}
{t['selftext']}"""

def call_ollama(system, user):
    payload = {"model":MODEL,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"stream":False,"options":{"temperature":0.3,"num_predict":2000},"format":"json"}
    req = urllib.request.Request(BASE+"/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            data = json.loads(r.read().decode())
            raw = (data.get("message") or {}).get("content","")
            try: parsed = json.loads(raw)
            except:
                import re
                m = re.search(r"\{.*\}", raw, re.DOTALL)
                parsed = json.loads(m.group(0)) if m else None
            return {"raw":raw,"parsed":parsed,"ok":parsed is not None,"ms":round((time.time()-t0)*1000)}
    except Exception as e:
        return {"raw":"","parsed":None,"ok":False,"ms":round((time.time()-t0)*1000),"err":str(e)}

# 1) Check Ollama
print("=== 检查 Ollama ===")
try:
    with urllib.request.urlopen(BASE+"/api/tags", timeout=5) as r:
        models = [m["name"] for m in json.loads(r.read().decode()).get("models",[])]
    print("OK, models:", models)
    if not any("qwen" in m.lower() for m in models):
        print("没有 Qwen 模型! 请先运行: ollama pull qwen2.5:7b")
        sys.exit(1)
    global MODEL
    match = [m for m in models if MODEL in m or MODEL.split(":")[0] in m]
    if match: MODEL = match[0]
    print("使用模型:", MODEL)
except Exception as e:
    print("Ollama 不可达:", e)
    print("请先在另一个窗口运行: ollama serve")
    sys.exit(1)

# 2) Run 3 tests
results = []
for i, t in enumerate(TESTS):
    print(f"\n--- [{i+1}/3] {t['id']} ---")
    print("Title:", t["title"][:60])
    call = call_ollama(SYS, build_prompt(t))
    if call["ok"]:
        p = call["parsed"]
        claimed = set()
        for issue in (p.get("key_issues") or []):
            for eid in (issue.get("evidence_item_ids") or []):
                claimed.add(eid)
        invalid = [x for x in claimed if x not in set(ALLOWED_IDS)]
        v = {"valid": len(invalid)==0, "claimed": sorted(claimed), "invalid": sorted(invalid)}
        print(f"OK ({call['ms']}ms) verdict={p.get('verdict','?')}")
        print(f"  evidence_ids: {v['claimed']}")
        if invalid: print(f"  ⚠ 无效 ID: {invalid}")
    else:
        v = {"valid": False, "reason": "no parsed JSON"}
        print(f"FAIL: {call.get('err','parse failed')}")
        if call.get("raw"): print("  raw:", call["raw"][:300])
    results.append({"test_id":t["id"],"title":t["title"],"selftext":t["selftext"],"allowed_ids":ALLOWED_IDS,"llm":call,"evidence_check":v})

# 3) Save
out = {"model":MODEL, "base":BASE, "results":results}
out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "peptides_results.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
print(f"\n=== 完成 ===")
print(f"结果已保存到: {out_path}")
print("请把这个 JSON 文件的内容贴回沙箱。")
