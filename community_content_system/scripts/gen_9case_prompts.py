"""生成 9 条跨社区对比测试的 prompts。

调用真实 Retrieval(organization/Etsy/Peptides 各 3 条内容),
输出 JSON,包含每条测试的:
- user_prompt (build_llm_context 产出)
- allowed_ids (用于校验 LLM 的 evidence_item_ids)
- test_id, subreddit, content_title

输出文件:/workspace/.uploads/9case_test_data.json

之后用 peptides_test_min.py 的格式,把 9 条塞进去,在本地 Ollama 跑。
"""
import json
import sys
import os

# 加 app 包
sys.path.insert(0, "/workspace/community_content_system")
from app.services.retrieval import retrieve_for_analysis
from app.services import classifier as classifier_svc

# 3 社区 × 3 内容 = 9 条
# 每条内容相同,跨社区对比
TESTS = [
    {
        "test_id": "T1_experience",
        "title": "Finally organized my pantry with a label maker — here's what I learned",
        "selftext": "I've been struggling with pantry chaos for years. Bought a Niimbot label printer last month, and it completely changed how my family uses the kitchen. Sharing before/after photos and what worked/didn't. Not affiliated, just genuinely happy with it.",
    },
    {
        "test_id": "T2_question",
        "title": "Looking for recommendations: label maker for organizing my home office files?",
        "selftext": "Setting up a home office and need to label file folders, cable runs, and storage bins. Anyone have a label printer they recommend? Budget-friendly preferred.",
    },
    {
        "test_id": "T3_promotional",
        "title": "The Niimbot label printer changed my organizing game — 40% off this week!",
        "selftext": "Just sharing a great deal I found. Niimbot label printer 40% off on Amazon this week. Link in comments. Perfect for home organization.",
    },
]

SUBREDDITS = ["organization", "Etsy", "Peptides"]


def get_classifier_tags(title: str, selftext: str) -> dict:
    """调用 Classifier 规则式打标签(用于 Retrieval)。

    Classifier 的 LLM 入口是 label_item(需 ReferenceItem),
    但本轮只需要标签,直接用规则式 _rule_based_classify 即可,
    跟 production 链路的 fallback 路径一致。
    """
    return classifier_svc._rule_based_classify(title, selftext)


def build_one(subreddit: str, test: dict) -> dict:
    """对单条内容,在指定社区上跑 Retrieval,生成 user_prompt + allowed_ids。"""
    title = test["title"]
    selftext = test["selftext"]
    new_content = f"{title}\n{selftext}"

    # Classifier 打标签
    try:
        new_content_tags = get_classifier_tags(title, selftext)
    except Exception as e:
        print(f"  [warn] classifier 失败,用空 tags: {e}")
        new_content_tags = {
            "topic_tags": [],
            "scenario_tags": [],
            "structure_tags": [],
            "product_visibility": "none",
            "brand_mentions": [],
            "search_value": "mid",
            "search_value_reasoning": "fallback",
            "keywords": [],
        }

    # 真实 Retrieval
    result = retrieve_for_analysis(
        subreddit=subreddit,
        new_content=new_content,
        new_content_tags=new_content_tags,
        high_count=3,
        failure_count=2,
        pattern_count=3,
    )

    # build_llm_context 内部会更新 all_retrieved_item_ids
    user_prompt = result.build_llm_context(new_content)
    allowed_ids = sorted(result.all_retrieved_item_ids)

    return {
        "test_id": test["test_id"],
        "subreddit": subreddit,
        "title": title,
        "selftext": selftext,
        "new_content_tags": new_content_tags,
        "user_prompt": user_prompt,
        "allowed_ids": allowed_ids,
        "retrieval_stats": {
            "high_count": len(result.similar_high),
            "failure_count": len(result.similar_failure),
            "fire_patterns": len(result.fire_patterns),
            "search_patterns": len(result.search_patterns),
            "failure_patterns": len(result.failure_patterns),
            "rules_count": len((result.rules_summary or {}).get("rules", [])),
        },
    }


def main():
    print("=== 生成 9 条跨社区对比测试数据 ===\n")
    all_cases = []
    for sub in SUBREDDITS:
        print(f"\n--- Subreddit: {sub} ---")
        for t in TESTS:
            print(f"  Generating: {sub} / {t['test_id']} ...")
            case = build_one(sub, t)
            stats = case["retrieval_stats"]
            print(f"    high={stats['high_count']}, fail={stats['failure_count']}, "
                  f"fire={stats['fire_patterns']}, rules={stats['rules_count']}, "
                  f"allowed_ids={len(case['allowed_ids'])}")
            all_cases.append(case)

    out_path = "/workspace/.uploads/9case_test_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"cases": all_cases}, f, ensure_ascii=False, indent=2)
    print(f"\n=== 已保存到: {out_path} ===")
    print(f"共 {len(all_cases)} 条测试用例")


if __name__ == "__main__":
    main()
