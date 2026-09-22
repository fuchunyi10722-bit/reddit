"""ManualAdapter / ExcelAdapter:异常/批量兜底。

第一阶段仅占位实现,主流程不依赖。
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


class ManualAdapter(SourceAdapter):
    """截图/图片手动补充 → 多模态 LLM 结构化 → 生成与 RawPost 同结构对象。

    第一阶段占位:主流程不依赖。
    """
    adapter_name = "manual"

    def fetch_subreddit_about(self, subreddit: str) -> RawSubredditMetaDTO:
        raise NotImplementedError("ManualAdapter 不支持 fetch_subreddit_about")

    def fetch_rules(self, subreddit: str) -> RawRulesDTO:
        raise NotImplementedError("ManualAdapter 不支持 fetch_rules")

    def fetch_listing(self, *args, **kwargs) -> RawListingDTO:
        raise NotImplementedError("ManualAdapter 不支持 fetch_listing")

    def fetch_post(self, *args, **kwargs):
        raise NotImplementedError("ManualAdapter 不支持 fetch_post")

    def fetch_comments(self, *args, **kwargs):
        raise NotImplementedError("ManualAdapter 不支持 fetch_comments")

    def search(self, *args, **kwargs) -> RawListingDTO:
        raise NotImplementedError("ManualAdapter 不支持 search")


class ExcelAdapter(SourceAdapter):
    """CSV/Excel 列映射 → RawPost。第一阶段占位。"""
    adapter_name = "excel"

    def fetch_subreddit_about(self, subreddit: str) -> RawSubredditMetaDTO:
        raise NotImplementedError("ExcelAdapter 不支持 fetch_subreddit_about")

    def fetch_rules(self, subreddit: str) -> RawRulesDTO:
        raise NotImplementedError("ExcelAdapter 不支持 fetch_rules")

    def fetch_listing(self, *args, **kwargs) -> RawListingDTO:
        raise NotImplementedError("ExcelAdapter 不支持 fetch_listing")

    def fetch_post(self, *args, **kwargs):
        raise NotImplementedError("ExcelAdapter 不支持 fetch_post")

    def fetch_comments(self, *args, **kwargs):
        raise NotImplementedError("ExcelAdapter 不支持 fetch_comments")

    def search(self, *args, **kwargs) -> RawListingDTO:
        raise NotImplementedError("ExcelAdapter 不支持 search")
