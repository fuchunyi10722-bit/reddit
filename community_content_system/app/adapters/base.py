"""SourceAdapter 抽象基类 + 统一 DTO。

子类只负责把外部数据"翻译"成统一 DTO,不做业务判断。
RedditAdapter/FileAdapter 输出结构完全一致,下游零改动。
PRAW 不出现在业务层,只在 RedditAdapter 内部。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RawPostDTO:
    """统一帖子 DTO。RedditAdapter/FileAdapter 都输出此结构。"""
    source_post_id: str          # t3_xxx fullname
    subreddit: str
    title: str
    selftext: str = ""
    url: str = ""
    is_self: bool = False
    post_hint: Optional[str] = None     # image|link|video|self
    domain: Optional[str] = None
    flair_text: Optional[str] = None
    flair_template_id: Optional[str] = None
    author: Optional[str] = None
    created_utc: float = 0.0
    permalink: str = ""
    ups: int = 0
    score: int = 0
    upvote_ratio: Optional[float] = None
    num_comments: int = 0
    view_count: Optional[int] = None
    content_form: str = "text"          # text|image|video|link|poll
    raw_payload: dict = field(default_factory=dict)  # 原始响应全文


@dataclass
class RawCommentDTO:
    """统一评论 DTO。"""
    source_comment_id: str      # t1_xxx
    source_post_id: str         # 所属 t3_xxx
    subreddit: str
    author: Optional[str] = None
    body: str = ""
    score: int = 0
    created_utc: float = 0.0
    depth: int = 0
    parent_comment_id: Optional[str] = None  # t1_xxx, reply 链
    raw_payload: dict = field(default_factory=dict)


@dataclass
class RawRulesDTO:
    """统一社区规则 DTO。"""
    subreddit: str
    rules: list = field(default_factory=list)           # [{short_name, description, priority}]
    karma_requirement: Optional[int] = None
    account_age_requirement: Optional[str] = None        # 描述性,如 "30 days"
    flair_required: bool = False
    link_restricted: bool = False
    commercial_content_restricted: bool = False
    post_frequency_limit: Optional[str] = None
    sensitive_content_rules: list = field(default_factory=list)
    raw_payload: dict = field(default_factory=dict)


@dataclass
class RawSubredditMetaDTO:
    """统一社区元信息 DTO。"""
    subreddit: str
    subscriber_count: Optional[int] = None
    created_utc: Optional[float] = None
    subreddit_type: Optional[str] = None     # public|restricted|private
    description: str = ""
    raw_payload: dict = field(default_factory=dict)


@dataclass
class RawListingDTO:
    """分页 listing。children 是 RawPostDTO 列表。"""
    children: list[RawPostDTO] = field(default_factory=list)
    after: Optional[str] = None      # 下一页 cursor (t3_xxx fullname)
    before: Optional[str] = None
    sort: str = ""
    time_filter: Optional[str] = None


class SourceAdapter(abc.ABC):
    """数据获取抽象基类。子类实现各方法,输出统一 DTO。"""

    adapter_name: str = "base"

    @abc.abstractmethod
    def fetch_subreddit_about(self, subreddit: str) -> RawSubredditMetaDTO:
        """获取社区元信息。验证社区存在 + public + 可访问。"""

    @abc.abstractmethod
    def fetch_rules(self, subreddit: str) -> RawRulesDTO:
        """获取社区规则。"""

    @abc.abstractmethod
    def fetch_listing(
        self,
        subreddit: str,
        sort: str,                          # hot|new|top|rising|controversial|best
        time_filter: Optional[str] = None,  # hour|day|week|month|year|all (仅 top/controversial)
        limit: int = 100,
        after: Optional[str] = None,
    ) -> RawListingDTO:
        """拉取帖子 listing。"""

    @abc.abstractmethod
    def fetch_post(self, post_id_or_permalink: str) -> tuple[RawPostDTO, list[RawCommentDTO]]:
        """指定帖子深采:正文 + 全评论树。"""

    @abc.abstractmethod
    def fetch_comments(
        self,
        post_id: str,
        sort: str = "top",      # top|new|controversial|old
        limit: int = 20,
        depth: int = 10,
    ) -> list[RawCommentDTO]:
        """单帖评论深采。"""

    @abc.abstractmethod
    def search(
        self,
        subreddit: str,
        query: str,
        sort: str = "relevance",   # relevance|hot|top|new|comments
        time_filter: Optional[str] = None,
        limit: int = 20,
        restrict_sr: bool = True,
    ) -> RawListingDTO:
        """搜索。restrict_sr=True 限定在 subreddit 内。"""
