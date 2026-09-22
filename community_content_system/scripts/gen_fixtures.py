"""生成 r/learnprogramming 的 mock fixture。

schema 与 Reddit API 真实响应逐字段一致(Listing{kind,data{children[],after}})。
FileAdapter 读这些文件,输出与 RedditAdapter 完全相同的 DTO。
"""

import json
import os
import random
import time

FIXTURE_ROOT = os.path.join(os.path.dirname(__file__), "..", "fixtures", "learnprogramming")
os.makedirs(os.path.join(FIXTURE_ROOT, "posts"), exist_ok=True)

random.seed(42)
now = time.time()

# —— 社区元信息 —— #
about = {
    "kind": "t5",
    "data": {
        "display_name": "learnprogramming",
        "subscribers": 3500000,
        "created_utc": 1292251200,
        "subreddit_type": "public",
        "description": "A subreddit for all questions related to programming in any language.",
        "public_description": "Ask questions about programming.",
    },
}

# —— 社区规则 —— #
rules = {
    "rules": [
        {"short_name": "No advertising/self-promotion", "description": "Do not post links to your own content for promotional purposes. This includes blogs, YouTube channels, courses, and products. Read the self-promotion rules before posting.", "priority": 1},
        {"short_name": "No complete solutions", "description": "Do not ask for or post complete solutions. Ask for guidance, not the answer.", "priority": 2},
        {"short_name": "Be civil and respectful", "description": "Treat others with respect. No harassment or insults.", "priority": 3},
        {"short_name": "Use clear titles", "description": "Make your title descriptive. 'Help' is not a good title.", "priority": 4},
        {"short_name": "No off-topic posts", "description": "Posts must be related to learning programming. Job posts belong in r/cscareerquestions.", "priority": 5},
    ],
    "description": {"rules_reason": "These rules help keep the community focused on learning."},
}

# —— 帖子生成 —— #
POST_TEMPLATES = [
    # 高表现:经验型 + 具体问题 + 解决过程
    {
        "title": "After 3 months of struggling, I finally understood pointers in C. Here's what clicked.",
        "selftext": "I kept hitting a wall with pointers. Every tutorial showed memory diagrams but never explained WHY you need a pointer to a pointer. What finally clicked was realizing it's about ownership: when you pass &x to a function, you're saying 'this function can change what x points to.'\n\nThe exercise that made it real: write a function that swaps two integers. Without pointers it's impossible; with pointers you see exactly why indirection matters.\n\nFor anyone struggling: draw boxes. Seriously. Paper and pencil. Draw what's at each address before and after each line of code.",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Discussion", "ups_base": 850, "comments_base": 120,
        "topic": "pointers", "scenario": "learning_struggle", "structure": "experience",
        "product_visibility": "none", "search_value": "mid",
    },
    {
        "title": "How I went from zero to my first junior dev job in 14 months (no CS degree)",
        "selftext": "Background: 26, working retail, decided to learn to code. Here's what actually mattered and what didn't.\n\nWhat mattered:\n1. Building projects instead of tutorial-hopping. I built a CLI budget tracker first, then a Flask blog, then a React todo with auth.\n2. Actually reading other people's code on GitHub. I'd clone a repo, break it, fix it.\n3. Getting rejected 47 times before the first yes.\n\nWhat didn't matter:\n- Bootcamp certificate (nobody asked)\n- Leetcode grinding (only 2 interviews tested algorithms)\n- Knowing 5 frameworks (they wanted depth in one)\n\nThe job: junior Python/Flask role. They asked me to debug a broken endpoint during the interview. I'd done that exact thing 100 times on my own projects.",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Success Story", "ups_base": 2100, "comments_base": 280,
        "topic": "career_transition", "scenario": "job_search", "structure": "experience",
        "product_visibility": "none", "search_value": "high",
    },
    {
        "title": "I kept getting stuck on recursion until I tried this one approach",
        "selftext": "Everyone says 'think of the base case' but that never worked for me. What worked: writing the iterative version first, then noticing the pattern, then converting.\n\nExample with factorial:\n```python\n# Iterative\ndef fact(n):\n    result = 1\n    for i in range(1, n+1):\n        result *= i\n    return result\n\n# Recursive — notice result accumulates the same way\ndef fact(n):\n    if n <= 1: return 1\n    return n * fact(n-1)\n```\n\nThe key insight: recursion is just a loop where the 'state' (result) is implicitly passed via the call stack instead of an explicit variable.",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Discussion", "ups_base": 1200, "comments_base": 95,
        "topic": "recursion", "scenario": "learning_struggle", "structure": "experience",
        "product_visibility": "none", "search_value": "high",
    },
    # 中表现:问题型 + 资源型
    {
        "title": "What's the difference between == and is in Python? When do I use which?",
        "selftext": "I keep mixing these up. From what I understand:\n\n`==` checks if values are equal\n`is` checks if they're the same object in memory\n\nBut when does it actually matter? The only case I've seen is checking `if x is None`. Are there others?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Question", "ups_base": 340, "comments_base": 60,
        "topic": "python_basics", "scenario": "concept_confusion", "structure": "question",
        "product_visibility": "none", "search_value": "high",
    },
    {
        "title": "Best resources for learning data structures in 2024?",
        "selftext": "I know basic Python and want to learn data structures properly. Not just 'memorize what a stack is' but actually implement them and understand trade-offs.\n\nI've looked at LeetCode but it feels like it's testing memorization. Any book/course that explains the WHY behind each structure?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Question", "ups_base": 220, "comments_base": 45,
        "topic": "resources", "scenario": "self_study", "structure": "question",
        "product_visibility": "subtle", "search_value": "high",
    },
    {
        "title": "Is it normal to forget syntax after switching languages?",
        "selftext": "I learned Python first, then tried Go. I keep writing `func` as `def` and forgetting semicolons in JS. Does this get better or am I just not cut out for multiple languages?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Question", "ups_base": 180, "comments_base": 40,
        "topic": "language_switching", "scenario": "learning_struggle", "structure": "question",
        "product_visibility": "none", "search_value": "mid",
    },
    # 低表现:模糊标题 / 过于宽泛 / 略带广告感
    {
        "title": "Help with Python",
        "selftext": "I'm stuck. Can someone help?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": None, "ups_base": 5, "comments_base": 8,
        "topic": "unspecified", "scenario": "unspecified", "structure": "vague",
        "product_visibility": "none", "search_value": "low",
    },
    {
        "title": "Check out my new course on learning to code fast!",
        "selftext": "I just launched a course that teaches you Python in 7 days. Use code LEARN20 for 20% off. Link in bio. This is the fastest way to become a developer.",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": None, "ups_base": -15, "comments_base": 3,
        "topic": "promotion", "scenario": "promotion", "structure": "promotional",
        "product_visibility": "explicit", "search_value": "low",
    },
    {
        "title": "How do I learn programming?",
        "selftext": "I want to learn programming. Where do I start? Any tips?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": None, "ups_base": 12, "comments_base": 15,
        "topic": "getting_started", "scenario": "getting_started", "structure": "vague",
        "product_visibility": "none", "search_value": "low",
    },
    # 图片帖(高表现)
    {
        "title": "When you finally fix a bug after 4 hours and it was a missing semicolon",
        "selftext": "",
        "is_self": False, "post_hint": "image", "domain": "i.redd.it",
        "url": "https://i.redd.it/example_meme.jpg",
        "flair": "Meme", "ups_base": 3400, "comments_base": 150,
        "topic": "debugging", "scenario": "relatable", "structure": "meme",
        "product_visibility": "none", "search_value": "low",
    },
    # 链接帖(中表现)
    {
        "title": "Stack Overflow's 2024 survey shows Python overtook JavaScript in new questions",
        "selftext": "",
        "is_self": False, "post_hint": "link", "domain": "stackoverflow.blog",
        "url": "https://stackoverflow.blog/example",
        "flair": "News", "ups_base": 450, "comments_base": 70,
        "topic": "industry_trends", "scenario": "industry", "structure": "link_share",
        "product_visibility": "none", "search_value": "mid",
    },
    {
        "title": "Why does my for loop run twice?",
        "selftext": "```python\nfor i in range(5):\n    print(i)\n    i = i + 1\n```\nIt prints 0 1 2 3 4 not 0 2 4. Why?",
        "is_self": True, "post_hint": None, "domain": "self.learnprogramming",
        "flair": "Question", "ups_base": 95, "comments_base": 25,
        "topic": "loop_mechanics", "scenario": "concept_confusion", "structure": "question",
        "product_visibility": "none", "search_value": "high",
    },
]

# 评论模板
COMMENT_TEMPLATES = [
    ("Great explanation, the box-drawing tip actually helped me too.", 45, 0),
    ("This is why I love this sub. Actual explanations, not just 'google it'.", 32, 0),
    ("Can you elaborate on ownership? I think I get it but not 100%.", 12, 0),
    ("Tried the swap exercise. Mind blown. Why didn't my professor explain it this way?", 28, 0),
    ("This is gold. Saving for later.", 8, 0),
    ("Hot take: pointers are easy if you understand memory. The problem is most courses skip memory.", 15, 0),
    ("Your iterative-to-recursive trick is underrated. Teaching it this way should be standard.", 22, 0),
    ("Same here. Took me 6 months and it was a drawing on paper that did it.", 18, 0),
    ("`is None` is basically the only case you need `is` in Python. Everything else, use `==`.", 35, 0),
    ("Also matters for small integers due to interning: `a = 256; b = 256; a is b` is True, but 257 is False. CPython caches -5 to 256.", 41, 0),
    ("Have you looked at 'Grokking Algorithms'? It explains the why behind each structure with visual examples.", 19, 0),
    ("Totally normal. After 3 languages you stop noticing. Your brain compartmentalizes.", 14, 0),
    ("You need to be way more specific. What are you stuck ON? What have you tried? What's the error?", -5, 0),
    ("Read the wiki. This question gets asked every week.", 3, 0),
    ("Reported for self-promotion. Read rule 1.", 2, 0),
    ("This is a known FAQ: https://wiki.learnprogramming/GettingStarted", 7, 0),
    ("Memes like this are why I keep coming back lol", 67, 0),
    ("Not surprising. Python's growth has been obvious for years.", 11, 0),
    ("Because `range` produces values 0-4 and reassigning `i` inside the loop doesn't change what range yields next. The loop variable is reassigned at the top of each iteration.", 38, 0),
    ("Same confusion when I started. The loop doesn't read your modified `i`.", 9, 0),
]


def make_post_dto(template, idx):
    post_id = f"learnprog_post_{idx:02d}"
    fullname = f"t3_{post_id}"
    created = now - random.randint(86400 * 2, 86400 * 60)  # 2-60 days ago
    ups = template["ups_base"] + random.randint(-50, 50)
    comments = template["comments_base"] + random.randint(-10, 10)
    content_form = "text"
    if template.get("post_hint") == "image":
        content_form = "image"
    elif not template.get("is_self", True):
        content_form = "link"

    return {
        "kind": "t3",
        "data": {
            "id": post_id,
            "name": fullname,
            "subreddit": "learnprogramming",
            "title": template["title"],
            "selftext": template["selftext"],
            "url": template.get("url", ""),
            "is_self": template.get("is_self", True),
            "post_hint": template.get("post_hint"),
            "domain": template.get("domain", "self.learnprogramming"),
            "link_flair_text": template.get("flair"),
            "link_flair_template_id": f"flair_{idx:02d}" if template.get("flair") else None,
            "author": f"user_{random.randint(1, 50):02d}",
            "created_utc": created,
            "permalink": f"/r/learnprogramming/comments/{post_id}/slug/",
            "ups": ups,
            "score": ups,
            "upvote_ratio": round(random.uniform(0.7, 0.98), 2),
            "num_comments": comments,
            "view_count": None,
            "is_video": template.get("post_hint") == "video",
            "poll_data": None,
            "url_overridden_by_dest": template.get("url"),
        },
    }


def make_comment_dto(post_fullname, post_subreddit, idx, depth=0, parent_id=None):
    comment_id = f"cmt_{idx:04d}"
    fullname = f"t1_{comment_id}"
    body, score, _ = COMMENT_TEMPLATES[idx % len(COMMENT_TEMPLATES)]
    return {
        "kind": "t1",
        "data": {
            "id": comment_id,
            "name": fullname,
            "link_id": post_fullname,
            "subreddit": post_subreddit,
            "author": f"user_{random.randint(1, 50):02d}",
            "body": body,
            "score": score + random.randint(-3, 3),
            "created_utc": now - random.randint(3600, 86400 * 10),
            "depth": depth,
            "parent_id": parent_id or post_fullname,
        },
    }


def make_listing(posts, sort, time_filter=None):
    children = [make_post_dto(p, i) for i, p in enumerate(posts)]
    return {
        "kind": "Listing",
        "data": {
            "children": children,
            "after": None,
            "before": None,
        },
    }


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    write_json(os.path.join(FIXTURE_ROOT, "about.json"), about)
    write_json(os.path.join(FIXTURE_ROOT, "rules.json"), rules)

    # 按 score 分配到 top/hot/new
    sorted_by_score = sorted(POST_TEMPLATES, key=lambda p: p["ups_base"], reverse=True)
    top_posts = sorted_by_score[:6]
    hot_posts = sorted_by_score[1:7]
    new_posts = list(reversed(POST_TEMPLATES[:6]))

    write_json(os.path.join(FIXTURE_ROOT, "top_month.json"), make_listing(top_posts, "top", "month"))
    write_json(os.path.join(FIXTURE_ROOT, "hot.json"), make_listing(hot_posts, "hot"))
    write_json(os.path.join(FIXTURE_ROOT, "new.json"), make_listing(new_posts, "new"))

    # 搜索 fixture
    search_python = [p for p in POST_TEMPLATES if "python" in p["title"].lower() or "python" in p["selftext"].lower()]
    write_json(os.path.join(FIXTURE_ROOT, "search_python.json"), make_listing(search_python, "relevance"))
    search_recursion = [p for p in POST_TEMPLATES if "recursion" in p["title"].lower()]
    write_json(os.path.join(FIXTURE_ROOT, "search_recursion.json"), make_listing(search_recursion, "relevance"))
    search_pointers = [p for p in POST_TEMPLATES if "pointer" in p["title"].lower()]
    write_json(os.path.join(FIXTURE_ROOT, "search_pointers.json"), make_listing(search_pointers, "relevance"))

    # 为代表性帖子生成评论(fixture:posts/<id>.json)
    # 选高/中/低各代表
    representative = [
        sorted_by_score[0],   # 最高表现(经验型)
        POST_TEMPLATES[3],    # 中表现(问题型)
        sorted_by_score[-1],  # 低表现(模糊标题)
        POST_TEMPLATES[7],    # 低表现(广告感)
    ]
    for i, tmpl in enumerate(representative):
        post_dto = make_post_dto(tmpl, i)
        post_id = post_dto["data"]["id"]
        post_fullname = post_dto["data"]["name"]
        sub = post_dto["data"]["subreddit"]

        # 生成 8-12 条评论
        n_comments = random.randint(8, 12)
        comments = []
        for j in range(n_comments):
            c = make_comment_dto(post_fullname, sub, j, depth=0)
            comments.append(c)
            # 随机加 1-2 条回复
            if random.random() < 0.4:
                reply = make_comment_dto(post_fullname, sub, j + 100, depth=1, parent_id=c["data"]["name"])
                comments.append(reply)

        # Reddit API 格式:[{post listing}, {comment listing}]
        post_listing = {"kind": "Listing", "data": {"children": [post_dto], "after": None, "before": None}}
        comment_listing = {"kind": "Listing", "data": {"children": comments, "after": None, "before": None}}
        write_json(os.path.join(FIXTURE_ROOT, "posts", f"{post_id}.json"), [post_listing, comment_listing])

    print(f"fixture 生成完成: {FIXTURE_ROOT}")
    print(f"  about.json / rules.json")
    print(f"  top_month.json ({len(top_posts)} posts)")
    print(f"  hot.json ({len(hot_posts)} posts)")
    print(f"  new.json ({len(new_posts)} posts)")
    print(f"  search_python/recursion/pointers.json")
    print(f"  posts/ ({len(representative)} posts with comments)")


if __name__ == "__main__":
    main()
