"""Parser:RawPost DTO → ReferenceItem/Comment/RawPost 落库。

只做字段映射 + 类型清洗,不做 AI 判断。
事实层(ups/score/created_utc)不可被 AI 改写。
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from ..adapters.base import RawPostDTO, RawCommentDTO, RawListingDTO
from ..database import get_session
from ..models.raw import RawPost, RawComment, RawRules, RawSubredditMeta
from ..models.reference import ReferenceItem, Comment


def ingest_raw_post(dto: RawPostDTO, adapter_name: str) -> tuple[RawPost, ReferenceItem]:
    """RawPostDTO → RawPost + ReferenceItem 落库。去重(按 source_post_id + adapter)。"""
    with get_session() as s:
        # 查是否已存在(按 source_post_id + adapter)
        existing = s.query(RawPost).filter_by(
            source_post_id=dto.source_post_id, source_adapter=adapter_name
        ).first()
        if existing:
            raw = existing
        else:
            raw = RawPost(
                source_adapter=adapter_name,
                source_post_id=dto.source_post_id,
                subreddit=dto.subreddit,
                raw_payload=dto.raw_payload,
            )
            s.add(raw)
            s.flush()

        # ReferenceItem 查重
        existing_ref = s.query(ReferenceItem).filter_by(
            source_post_id=dto.source_post_id, source_adapter=adapter_name
        ).first()
        if existing_ref:
            return raw, existing_ref

        ref = ReferenceItem(
            source_post_id=dto.source_post_id,
            source_adapter=adapter_name,
            raw_post_id=raw.id,
            subreddit=dto.subreddit,
            permalink=dto.permalink,
            title=dto.title,
            selftext=dto.selftext,
            url=dto.url,
            is_self=dto.is_self,
            post_hint=dto.post_hint,
            domain=dto.domain,
            flair_text=dto.flair_text,
            flair_template_id=dto.flair_template_id,
            author=dto.author,
            created_utc=dto.created_utc,
            ups=dto.ups,
            score=dto.score,
            upvote_ratio=dto.upvote_ratio,
            num_comments=dto.num_comments,
            view_count=dto.view_count,
            content_form=dto.content_form,
            fetched_at=datetime.utcnow(),
            retention_status="active",
        )
        s.add(ref)
        s.flush()
        return raw, ref


def ingest_raw_comment(dto: RawCommentDTO, adapter_name: str, parent_post_id: str) -> Comment:
    """RawCommentDTO → RawComment + Comment 落库。去重(按 source_comment_id + adapter)。"""
    with get_session() as s:
        existing = s.query(RawComment).filter_by(
            source_comment_id=dto.source_comment_id, source_adapter=adapter_name
        ).first()
        if existing:
            raw = existing
        else:
            raw = RawComment(
                source_adapter=adapter_name,
                source_comment_id=dto.source_comment_id,
                source_post_id=dto.source_post_id,
                subreddit=dto.subreddit,
                raw_payload=dto.raw_payload,
            )
            s.add(raw)
            s.flush()

        existing_cmt = s.query(Comment).filter_by(
            source_comment_id=dto.source_comment_id, source_adapter=adapter_name
        ).first()
        if existing_cmt:
            return existing_cmt

        # 解析 parent_comment_id(去掉 t1_ 前缀找到 Comment.id)
        parent_comment_id = None
        if dto.parent_comment_id and dto.parent_comment_id.startswith("t1_"):
            pc = s.query(Comment).filter_by(
                source_comment_id=dto.parent_comment_id, source_adapter=adapter_name
            ).first()
            if pc:
                parent_comment_id = pc.id

        cmt = Comment(
            source_comment_id=dto.source_comment_id,
            source_adapter=adapter_name,
            raw_comment_id=raw.id,
            parent_post_id=parent_post_id,
            parent_comment_id=parent_comment_id,
            subreddit=dto.subreddit,
            author=dto.author,
            body=dto.body,
            score=dto.score,
            created_utc=dto.created_utc,
            depth=dto.depth,
            fetched_at=datetime.utcnow(),
            retention_status="active",
        )
        s.add(cmt)
        s.flush()
        return cmt


def ingest_listing(listing: RawListingDTO, adapter_name: str) -> list[ReferenceItem]:
    """整个 listing 批量落库。返回 ReferenceItem 列表。"""
    refs = []
    for dto in listing.children:
        _, ref = ingest_raw_post(dto, adapter_name)
        refs.append(ref)
    return refs
