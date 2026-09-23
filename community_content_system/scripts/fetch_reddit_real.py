"""Reddit 真实数据采集脚本(零 auth,公共 JSON API)。

用途:为 Phase 2 Step 2 抓取 3 个社区的真实数据,
输出与 FileAdapter 完全兼容的 fixture 格式,现有 pipeline 无需修改。

目标社区:
  organization  (organizing 场景)
  Etsy          (small business 场景)
  Peptides      (peptide/GLP-1 场景)

每社区采集:
  - about.json          社区元信息
  - rules.json          社区规则
  - top_month.json      Top(月) listing
  - hot.json            Hot listing
  - new.json            New listing
  - posts/<id>.json     ~8 帖的评论树(分层采样:高/中/低表现)
  合计 ~50 帖去重入库

运行方式(在能访问 Reddit 的环境):

  pip install requests
  python scripts/fetch_reddit_real.py

或只抓部分社区:

  python scripts/fetch_reddit_real.py --subreddits organization,Etsy
  python scripts/fetch_reddit_real.py --subreddits Peptides

注意事项:
  - Reddit 公共 .json 端点通常无需 OAuth,但需要合理 User-Agent。
  - 如返回 429(限流),脚本会自动退避重试;如持续 403,可能需配置 OAuth
    (见脚本末尾注释的 OAuth 升级路径)。
  - 抓取速度温和(每请求间隔 2 秒),全部 3 社区约 5-10 分钟。
  - 增量保存:中途失败重跑会跳过已存在的文件。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Optional

import requests

# —— 配置 —— #

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_ROOT = os.path.join(ROOT, "fixtures")

DEFAULT_SUBS = ["organization", "Etsy", "Peptides"]

# Reddit 要求描述性 UA,禁止用默认 python-requests
USER_AGENT = "community-content-research/0.1 (personal research; contact: researcher@example.com)"

BASE = "https://www.reddit.com"

# 每请求间隔(秒),温和抓取
REQUEST_DELAY = 2.0
# 429 退避最大重试次数
MAX_RETRIES = 4
# 每社区抓评论的帖子数(高/中/低分层)
COMMENTS_SAMPLE_SIZE = 8
# 每帖评论上限(避免抓过大帖)
COMMENT_LIMIT = 30


# —— HTTP —— #

def _get(url: str, params: Optional[dict] = None) -> Optional[dict]:
    """带退避重试的 GET。返回 JSON dict 或 None。"""
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=20)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 429:
                wait = 2 ** attempt * 5
                print(f"    [429 限流] 等待 {wait}s 后重试 ({attempt+1}/{MAX_RETRIES})")
                time.sleep(wait)
                continue
            if r.status_code == 403:
                print(f"    [403 禁止] {url} — 可能需要 OAuth 或 UA 被拒")
                return None
            print(f"    [{r.status_code}] {url}")
            return None
        except requests.RequestException as e:
            wait = 2 ** attempt * 2
            print(f"    [网络错误] {e}; {wait}s 后重试 ({attempt+1}/{MAX_RETRIES})")
            time.sleep(wait)
    print(f"    [失败] 达最大重试次数: {url}")
    return None


def _save(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _exists(path: str) -> bool:
    return os.path.exists(path)


# —— 抓取单个社区 —— #

def fetch_subreddit(sub: str) -> dict:
    """抓取一个社区的完整 fixture。返回统计。"""
    print(f"\n{'=' * 60}\n抓取社区: r/{sub}\n{'=' * 60}")
    sub_dir = os.path.join(FIXTURE_ROOT, sub)
    os.makedirs(sub_dir, exist_ok=True)
    stats = {"subreddit": sub, "posts_unique": 0, "comments_fetched": 0, "rules": 0}

    # 1. about.json
    about_path = os.path.join(sub_dir, "about.json")
    if _exists(about_path):
        print("  [skip] about.json 已存在")
    else:
        print(f"  [fetch] about ...")
        data = _get(f"{BASE}/r/{sub}/about.json")
        if data:
            _save(about_path, data)
            sub_data = data.get("data", {})
            print(f"    subscribers: {sub_data.get('subscribers')}")
            print(f"    title: {sub_data.get('title')}")
            stats["subscribers"] = sub_data.get("subscribers")
        time.sleep(REQUEST_DELAY)

    # 2. rules.json
    rules_path = os.path.join(sub_dir, "rules.json")
    if _exists(rules_path):
        print("  [skip] rules.json 已存在")
    else:
        print(f"  [fetch] rules ...")
        data = _get(f"{BASE}/r/{sub}/about/rules.json")
        if data:
            _save(rules_path, data)
            rules = data.get("rules") or []
            print(f"    rules: {len(rules)} 条")
            for r in rules[:5]:
                print(f"      - {r.get('short_name', '')[:60]}")
            stats["rules"] = len(rules)
        time.sleep(REQUEST_DELAY)

    # 3. listings: top(month) / hot / new
    listings = [
        ("top", "month", "top_month.json"),
        ("hot", None, "hot.json"),
        ("new", None, "new.json"),
    ]
    all_post_ids = []   # 保留顺序的 t3_xxx
    seen_ids = set()

    for sort, tf, fname in listings:
        path = os.path.join(sub_dir, fname)
        if _exists(path):
            print(f"  [skip] {fname} 已存在,读取其帖 ID 用于去重")
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
            children = (existing.get("data") or {}).get("children", [])
            for c in children:
                d = c.get("data", {})
                pid = d.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_post_ids.append(pid)
            continue

        params = {"limit": 100}
        if tf:
            params["t"] = tf
        print(f"  [fetch] {sort}" + (f"?t={tf}" if tf else "") + " ...")
        data = _get(f"{BASE}/r/{sub}/{sort}.json", params=params)
        if data:
            _save(path, data)
            children = (data.get("data") or {}).get("children", [])
            new_count = 0
            for c in children:
                d = c.get("data", {})
                pid = d.get("id")
                if pid and pid not in seen_ids:
                    seen_ids.add(pid)
                    all_post_ids.append(pid)
                    new_count += 1
            print(f"    帖子: {len(children)} 条 (新增唯一 {new_count})")
        time.sleep(REQUEST_DELAY)

    stats["posts_unique"] = len(all_post_ids)
    print(f"  → 去重后唯一帖子: {len(all_post_ids)}")

    if len(all_post_ids) < 30:
        print(f"  [警告] 帖子数 < 30,可能该社区帖子较少或抓取受限")

    # 4. 评论采样:按 score 分层选 COMMENTS_SAMPLE_SIZE 帖
    # 先从 listings 收集每帖的 score
    post_scores = {}
    for sort, tf, fname in listings:
        path = os.path.join(sub_dir, fname)
        if not _exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for c in (data.get("data") or {}).get("children", []):
            d = c.get("data", {})
            pid = d.get("id")
            if pid:
                score = d.get("score", 0) or 0
                if pid not in post_scores or score > post_scores[pid]:
                    post_scores[pid] = score

    # 按 score 排序,分层采样
    sorted_ids = sorted(post_scores.keys(), key=lambda p: post_scores[p], reverse=True)
    n = len(sorted_ids)
    if n == 0:
        print("  [警告] 无帖可采样评论")
        return stats

    # 高/中/低三层各取一部分
    high = sorted_ids[:max(1, COMMENTS_SAMPLE_SIZE // 3)]
    mid_start = n // 3
    mid = sorted_ids[mid_start:mid_start + max(1, COMMENTS_SAMPLE_SIZE // 3)]
    low = sorted_ids[-max(1, COMMENTS_SAMPLE_SIZE - len(high) - len(mid)):]
    sample_ids = list(dict.fromkeys(high + mid + low))[:COMMENTS_SAMPLE_SIZE]

    print(f"  [sample] 评论采样帖: {len(sample_ids)} 帖 (高{len(high)}/中{len(mid)}/低{len(low)})")

    posts_dir = os.path.join(sub_dir, "posts")
    os.makedirs(posts_dir, exist_ok=True)

    for i, pid in enumerate(sample_ids):
        post_path = os.path.join(posts_dir, f"{pid}.json")
        if _exists(post_path):
            print(f"  [skip] posts/{pid}.json 已存在")
            continue
        print(f"  [fetch] posts/{pid}.json ({i+1}/{len(sample_ids)}) ...")
        data = _get(f"{BASE}/r/{sub}/comments/{pid}.json",
                    params={"limit": COMMENT_LIMIT, "depth": 10, "sort": "top"})
        if data:
            # Reddit /comments 返回 [post_listing, comment_listing]
            if isinstance(data, list) and len(data) >= 2:
                _save(post_path, data)
                n_comments = len((data[1].get("data") or {}).get("children", []))
                stats["comments_fetched"] += n_comments
                print(f"    评论: {n_comments} 条")
            else:
                print(f"    [警告] 返回结构异常,保存原始")
                _save(post_path, data)
        time.sleep(REQUEST_DELAY)

    return stats


# —— 主流程 —— #

def main() -> None:
    parser = argparse.ArgumentParser(description="抓取 Reddit 真实数据为 fixture")
    parser.add_argument("--subreddits", type=str, default=",".join(DEFAULT_SUBS),
                        help=f"社区列表(逗号分隔),默认: {','.join(DEFAULT_SUBS)}")
    args = parser.parse_args()
    subs = [s.strip() for s in args.subreddits.split(",") if s.strip()]
    print(f"目标社区: {subs}")
    print(f"fixture 输出目录: {FIXTURE_ROOT}")
    print(f"请求间隔: {REQUEST_DELAY}s, 评论采样: {COMMENTS_SAMPLE_SIZE} 帖/社区")

    all_stats = []
    for sub in subs:
        stats = fetch_subreddit(sub)
        all_stats.append(stats)

    # 总结
    print(f"\n{'=' * 60}\n采集完成总结\n{'=' * 60}")
    for s in all_stats:
        print(f"  r/{s['subreddit']}: "
              f"唯一帖 {s.get('posts_unique',0)}, "
              f"规则 {s.get('rules',0)} 条, "
              f"评论采样 {s.get('comments_fetched',0)} 条, "
              f"subscribers {s.get('subscribers','N/A')}")
    print(f"\n下一步: 在沙箱运行 Step 2 验证脚本读取这些 fixture")


if __name__ == "__main__":
    main()
