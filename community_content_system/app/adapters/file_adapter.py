"""FileAdapter:开发期 mock。读 fixture 文件,schema 与 Reddit API 响应一致。

fixture 文件结构:
  fixtures/<subreddit>/about.json          — RawSubredditMeta 响应
  fixtures/<subreddit>/rules.json         — RawRules 响应
  fixtures/<subreddit>/<sort>_<tf>.json   — listing (e.g. top_month.json, hot.json, new.json)
  fixtures/<subreddit>/search_<slug>.json — search 结果
  fixtures/<subreddit>/posts/<post_id>.json — 单帖 + 评论树

输出与 RedditAdapter 完全相同的 DTO。切换只改 adapter 配置,下游零改动。
"""

from __future__ import annotations

import json
import os
import re
from typing import Optional

from .base import (
    SourceAdapter,
    RawPostDTO,
    RawCommentDTO,
    RawRulesDTO,
    RawSubredditMetaDTO,
    RawListingDTO,
)


def _slugify(query: str) -> str:
    """搜索词 → 文件名 slug。"""
    s = re.sub(r"[^\w\s-]", "", query.lower()).strip()
    s = re.sub(r"[\s_-]+", "_", s)
    return s or "empty"


class FileAdapter(SourceAdapter):
    adapter_name = "file"

    def __init__(self, fixtures_root: str = "fixtures"):
        self.root = fixtures_root

    def _path(self, subreddit: str, filename: str) -> str:
        return os.path.join(self.root, subreddit, filename)

    def _load_json(self, path: str) -> Optional[dict]:
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # —— Reddit API 响应解析(与生产 RedditAdapter 共用逻辑) —— #

    @staticmethod
    def _parse_reddit_post(child: dict) -> RawPostDTO:
        """从 Reddit API 的 child 节点解析为 DTO。fixture 与生产响应结构一致。"""
        d = child.get("data", child)
        post_hint = d.get("post_hint") or (None if d.get("is_self") else "link")
        content_form = "text"
        if d.get("is_video"):
            content_form = "video"
        elif d.get("post_hint") == "image":
            content_form = "image"
        elif d.get("is_self"):
            content_form = "text"
        elif d.get("url_overridden_by_dest") or d.get("url"):
            content_form = "link"
        if d.get("poll_data"):
            content_form = "poll"

        return RawPostDTO(
            source_post_id=child.get("name", d.get("name", "")) or f"t3_{d.get('id','')}",
            subreddit=d.get("subreddit", ""),
            title=d.get("title", ""),
            selftext=d.get("selftext", "") or "",
            url=d.get("url", "") or "",
            is_self=d.get("is_self", False),
            post_hint=post_hint,
            domain=d.get("domain"),
            flair_text=d.get("link_flair_text"),
            flair_template_id=d.get("link_flair_template_id"),
            author=d.get("author"),
            created_utc=float(d.get("created_utc", 0) or 0),
            permalink=d.get("permalink", ""),
            ups=d.get("ups", 0) or 0,
            score=d.get("score", 0) or 0,
            upvote_ratio=d.get("upvote_ratio"),
            num_comments=d.get("num_comments", 0) or 0,
            view_count=d.get("view_count"),
            content_form=content_form,
            raw_payload=child,
        )

    @staticmethod
    def _parse_reddit_comment(child: dict) -> RawCommentDTO:
        """从评论 child 节点解析为 DTO。"""
        d = child.get("data", child)
        return RawCommentDTO(
            source_comment_id=child.get("name", d.get("name", "")) or f"t1_{d.get('id','')}",
            source_post_id=d.get("link_id", ""),       # t3_xxx
            subreddit=d.get("subreddit", ""),
            author=d.get("author"),
            body=d.get("body", "") or "",
            score=d.get("score", 0) or 0,
            created_utc=float(d.get("created_utc", 0) or 0),
            depth=d.get("depth", 0) or 0,
            parent_comment_id=d.get("parent_id"),       # t1_xxx or t3_xxx
            raw_payload=child,
        )

    def _parse_listing(self, payload: dict, sort: str = "", time_filter: Optional[str] = None) -> RawListingDTO:
        """解析 Reddit listing 响应。fixture 与生产结构一致。"""
        data = payload.get("data", payload)
        children_raw = data.get("children", [])
        children = [self._parse_reddit_post(c) for c in children_raw]
        return RawListingDTO(
            children=children,
            after=data.get("after"),
            before=data.get("before"),
            sort=sort,
            time_filter=time_filter,
        )

    # —— SourceAdapter 实现 —— #

    def fetch_subreddit_about(self, subreddit: str) -> RawSubredditMetaDTO:
        payload = self._load_json(self._path(subreddit, "about.json"))
        if payload is None:
            raise FileNotFoundError(f"社区 fixture 不存在: {subreddit}/about.json")
        d = payload.get("data", payload)
        return RawSubredditMetaDTO(
            subreddit=subreddit,
            subscriber_count=d.get("subscribers"),
            created_utc=float(d.get("created_utc", 0)) if d.get("created_utc") else None,
            subreddit_type=d.get("subreddit_type", "public"),
            description=d.get("description", "") or d.get("public_description", ""),
            raw_payload=payload,
        )

    def fetch_rules(self, subreddit: str) -> RawRulesDTO:
        payload = self._load_json(self._path(subreddit, "rules.json"))
        if payload is None:
            raise FileNotFoundError(f"规则 fixture 不存在: {subreddit}/rules.json")
        rules_raw = payload.get("rules") or payload.get("data", {}).get("rules", [])
        parsed_rules = []
        commercial_restricted = False
        link_restricted = False
        flair_required = False
        sensitive = []
        for r in rules_raw:
            short = r.get("short_name", "")
            desc = r.get("description", "") or ""
            parsed_rules.append({"short_name": short, "description": desc})
            low = (short + desc).lower()
            if "no self-promotion" in low or "no spam" in low or "no advertising" in low or "promotional" in low:
                commercial_restricted = True
            if "no link" in low or "no linking" in low:
                link_restricted = True
            if "flair" in low and "required" in low:
                flair_required = True
            if "nsfw" in low or "nsfl" in low or "sensitive" in low:
                sensitive.append(short)
        return RawRulesDTO(
            subreddit=subreddit,
            rules=parsed_rules,
            flair_required=flair_required,
            link_restricted=link_restricted,
            commercial_content_restricted=commercial_restricted,
            sensitive_content_rules=sensitive,
            raw_payload=payload,
        )

    def fetch_listing(
        self,
        subreddit: str,
        sort: str,
        time_filter: Optional[str] = None,
        limit: int = 100,
        after: Optional[str] = None,
    ) -> RawListingDTO:
        # 文件名约定:<sort>.json 或 <sort>_<time_filter>.json
        if time_filter and sort in ("top", "controversial"):
            fname = f"{sort}_{time_filter}.json"
        else:
            fname = f"{sort}.json"
        payload = self._load_json(self._path(subreddit, fname))
        if payload is None:
            return RawListingDTO(sort=sort, time_filter=time_filter)
        listing = self._parse_listing(payload, sort=sort, time_filter=time_filter)
        listing.children = listing.children[:limit]
        return listing

    def fetch_post(self, post_id_or_permalink: str) -> tuple[RawPostDTO, list[RawCommentDTO]]:
        post_id = post_id_or_permalink.strip("/").split("/")[-1] if "/" in post_id_or_permalink else post_id_or_permalink
        # 兼容 t3_xxx
        if post_id.startswith("t3_"):
            post_id = post_id[3:]
        # 尝试 fixtures/<sub>/posts/<post_id>.json
        for sub_dir in os.listdir(self.root):
            post_path = self._path(sub_dir, f"posts/{post_id}.json")
            payload = self._load_json(post_path)
            if payload is not None:
                # Reddit API: [{post listing}, {comment listing}]
                if isinstance(payload, list) and len(payload) >= 2:
                    post_listing = self._parse_listing(payload[0])
                    post = post_listing.children[0] if post_listing.children else None
                    comment_data = payload[1].get("data", {})
                    comment_children = comment_data.get("children", [])
                    comments = [self._parse_reddit_comment(c) for c in comment_children if c.get("kind") == "t1"]
                    return post, comments
                elif isinstance(payload, dict):
                    post = self._parse_reddit_post(payload)
                    return post, []
        raise FileNotFoundError(f"帖子 fixture 不存在: posts/{post_id}.json")

    def fetch_comments(
        self,
        post_id: str,
        sort: str = "top",
        limit: int = 20,
        depth: int = 10,
    ) -> list[RawCommentDTO]:
        if post_id.startswith("t3_"):
            post_id = post_id[3:]
        for sub_dir in os.listdir(self.root):
            post_path = self._path(sub_dir, f"posts/{post_id}.json")
            payload = self._load_json(post_path)
            if payload is not None and isinstance(payload, list) and len(payload) >= 2:
                comment_data = payload[1].get("data", {})
                comment_children = comment_data.get("children", [])
                comments = [self._parse_reddit_comment(c) for c in comment_children if c.get("kind") == "t1"]
                # 按 sort 排序(fixture 已预排,这里做兜底)
                if sort == "top":
                    comments.sort(key=lambda c: c.score, reverse=True)
                elif sort == "new":
                    comments.sort(key=lambda c: c.created_utc, reverse=True)
                elif sort == "old":
                    comments.sort(key=lambda c: c.created_utc)
                return comments[:limit]
        return []

    def search(
        self,
        subreddit: str,
        query: str,
        sort: str = "relevance",
        time_filter: Optional[str] = None,
        limit: int = 20,
        restrict_sr: bool = True,
    ) -> RawListingDTO:
        slug = _slugify(query)
        payload = self._load_json(self._path(subreddit, f"search_{slug}.json"))
        if payload is None:
            return RawListingDTO(sort="relevance")
        listing = self._parse_listing(payload, sort=sort, time_filter=time_filter)
        listing.children = listing.children[:limit]
        return listing
