"""RedditAdapter:生产核心。OAuth + PRAW。

当前沙箱无法访问 Reddit(TLS 层阻断),本类为第一阶段骨架。
部署到能联网 Reddit 的服务器后,设置 adapter=reddit 即启用。
PRAW 只在本类内部使用,不渗透到业务层。

切换数据源只换 Adapter,下游 Parser/Classifier/PerformanceClassifier/PatternMiner 零改动。
"""

from __future__ import annotations

from typing import Optional

from .base import (
    SourceAdapter,
    RawPostDTO,
    RawCommentDTO,
    RawRulesDTO,
    RawSubredditMetaDTO,
    RawListingDTO,
)
from ..config import settings


class RedditAdapter(SourceAdapter):
    """生产环境 Reddit 数据获取层。

    第一阶段骨架。部署到能联网 Reddit 的服务器后:
      1. pip install praw
      2. 在 .env 设置 CCS_ADAPTER=reddit + RedditCredentials
      3. 本类自动激活
    """

    adapter_name = "reddit"

    def __init__(self):
        if not settings.reddit_client_id:
            raise RuntimeError(
                "RedditAdapter 需要 CCS_REDDIT_CLIENT_ID / CCS_REDDIT_CLIENT_SECRET / "
                "CCS_REDDIT_USERNAME / CCS_REDDIT_PASSWORD。当前沙箱无法访问 Reddit。"
            )
        # 生产环境初始化 PRAW(沙箱期不执行到这里,因凭据为空)
        import praw  # 生产期才装
        self.reddit = praw.Reddit(
            client_id=settings.reddit_client_id,
            client_secret=settings.reddit_client_secret,
            username=settings.reddit_username,
            password=settings.reddit_password,
            user_agent=settings.reddit_user_agent,
        )

    def fetch_subreddit_about(self, subreddit: str) -> RawSubredditMetaDTO:
        sub = self.reddit.subreddit(subreddit)
        return RawSubredditMetaDTO(
            subreddit=subreddit,
            subscriber_count=sub.subscribers,
            created_utc=sub.created_utc,
            subreddit_type=sub.subreddit_type,
            description=sub.description or sub.public_description,
            raw_payload={"description": sub.description, "subscribers": sub.subscribers},
        )

    def fetch_rules(self, subreddit: str) -> RawRulesDTO:
        sub = self.reddit.subreddit(subreddit)
        rules = list(sub.rules)
        parsed = [{"short_name": r.short_name, "description": getattr(r, "description", "")} for r in rules]
        # 规则解析逻辑与 FileAdapter 一致
        commercial = link = flair = False
        sensitive = []
        for r in parsed:
            low = (r["short_name"] + r["description"]).lower()
            if any(k in low for k in ["no self-promotion", "no spam", "no advertising", "promotional"]):
                commercial = True
            if "no link" in low:
                link = True
            if "flair" in low and "required" in low:
                flair = True
            if any(k in low for k in ["nsfw", "nsfl", "sensitive"]):
                sensitive.append(r["short_name"])
        return RawRulesDTO(
            subreddit=subreddit,
            rules=parsed,
            flair_required=flair,
            link_restricted=link,
            commercial_content_restricted=commercial,
            sensitive_content_rules=sensitive,
        )

    def fetch_listing(
        self, subreddit, sort, time_filter=None, limit=100, after=None
    ) -> RawListingDTO:
        sub = self.reddit.subreddit(subreddit)
        if sort == "top":
            items = list(sub.top(time_filter=time_filter or "month", limit=limit, params={"after": after} if after else None))
        elif sort == "hot":
            items = list(sub.hot(limit=limit, params={"after": after} if after else None))
        elif sort == "new":
            items = list(sub.new(limit=limit, params={"after": after} if after else None))
        elif sort == "rising":
            items = list(sub.rising(limit=limit))
        else:
            items = list(getattr(sub, sort)(limit=limit))
        children = [self._praw_post_to_dto(p) for p in items]
        # PRAW 自动处理速率限制与 cursor;after 由 last item fullname 决定
        after_token = items[-1].fullname if items and len(items) >= limit else None
        return RawListingDTO(children=children, after=after_token, sort=sort, time_filter=time_filter)

    def fetch_post(self, post_id_or_permalink) -> tuple[RawPostDTO, list[RawCommentDTO]]:
        sid = post_id_or_permalink.split("/")[-1] if "/" in post_id_or_permalink else post_id_or_permalink
        if sid.startswith("t3_"):
            sid = sid[3:]
        submission = self.reddit.submission(id=sid)
        submission.comment_sort = "top"
        post = self._praw_post_to_dto(submission)
        comments = []
        submission.comments.replace_more(limit=0)
        for top_c in submission.comments.list():
            comments.append(self._praw_comment_to_dto(top_c))
        return post, comments

    def fetch_comments(self, post_id, sort="top", limit=20, depth=10) -> list[RawCommentDTO]:
        sid = post_id[3:] if post_id.startswith("t3_") else post_id
        submission = self.reddit.submission(id=sid)
        submission.comment_sort = sort
        submission.comments.replace_more(limit=0)
        result = [self._praw_comment_to_dto(c) for c in submission.comments.list()[:limit]]
        return result

    def search(self, subreddit, query, sort="relevance", time_filter=None, limit=20, restrict_sr=True) -> RawListingDTO:
        sub = self.reddit.subreddit(subreddit)
        results = list(sub.search(query, sort=sort, time_filter=time_filter or "all", limit=limit))
        children = [self._praw_post_to_dto(p) for p in results]
        return RawListingDTO(children=children, sort=sort, time_filter=time_filter)

    # —— PRAW → DTO 转换(内部) —— #

    def _praw_post_to_dto(self, submission) -> RawPostDTO:
        import praw  # 生产期
        content_form = "text"
        if getattr(submission, "is_video", False):
            content_form = "video"
        elif getattr(submission, "post_hint", "") == "image":
            content_form = "image"
        elif getattr(submission, "is_self", False):
            content_form = "text"
        elif getattr(submission, "url", None):
            content_form = "link"
        if getattr(submission, "poll_data", None):
            content_form = "poll"
        return RawPostDTO(
            source_post_id=submission.fullname,  # t3_xxx
            subreddit=submission.subreddit.display_name,
            title=submission.title,
            selftext=submission.selftext or "",
            url=submission.url or "",
            is_self=submission.is_self,
            post_hint=getattr(submission, "post_hint", None),
            domain=getattr(submission, "domain", None),
            flair_text=getattr(submission, "link_flair_text", None),
            flair_template_id=getattr(submission, "link_flair_template_id", None),
            author=str(submission.author) if submission.author else None,
            created_utc=float(submission.created_utc),
            permalink=submission.permalink,
            ups=submission.ups,
            score=submission.score,
            upvote_ratio=getattr(submission, "upvote_ratio", None),
            num_comments=submission.num_comments,
            view_count=getattr(submission, "view_count", None),
            content_form=content_form,
            raw_payload={"id": submission.id, "title": submission.title},
        )

    def _praw_comment_to_dto(self, comment) -> RawCommentDTO:
        return RawCommentDTO(
            source_comment_id=comment.fullname,  # t1_xxx
            source_post_id=comment.link_id,       # t3_xxx
            subreddit=str(comment.subreddit),
            author=str(comment.author) if comment.author else None,
            body=comment.body or "",
            score=comment.score,
            created_utc=float(comment.created_utc),
            depth=getattr(comment, "depth", 0) or 0,
            parent_comment_id=comment.parent_id,
            raw_payload={"id": comment.id, "body": comment.body},
        )
