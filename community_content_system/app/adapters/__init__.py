"""Adapter 工厂。根据配置返回对应 Adapter 实例。

切换 adapter 只改配置(CCS_ADAPTER=reddit|file|manual|excel),下游零改动。
"""

from __future__ import annotations

from .base import SourceAdapter
from ..config import settings, AdapterType


def get_adapter() -> SourceAdapter:
    """根据配置返回 Adapter。"""
    if settings.adapter == AdapterType.FILE:
        return __import__("app.adapters.file_adapter", fromlist=["FileAdapter"]).FileAdapter(
            fixtures_root=settings.fixtures_root
        )
    if settings.adapter == AdapterType.REDDIT:
        return __import__("app.adapters.reddit_adapter", fromlist=["RedditAdapter"]).RedditAdapter()
    if settings.adapter == AdapterType.MANUAL:
        from .fallback_adapters import ManualAdapter
        return ManualAdapter()
    if settings.adapter == AdapterType.EXCEL:
        from .fallback_adapters import ExcelAdapter
        return ExcelAdapter()
    raise ValueError(f"未知 adapter: {settings.adapter}")
