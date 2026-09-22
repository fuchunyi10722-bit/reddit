"""模型包入口。导入所有模型模块以触发 Base.metadata 注册。"""

from .raw import RawPost, RawComment, RawRules, RawSubredditMeta
from .reference import ReferenceItem, Comment
from .analysis import ContentAnalysis, PerformanceAnalysis
from .knowledge import KnowledgePattern, CommunityProfile
from .embedding import Embedding
from .snapshot import ContentAnalysisSnapshot, ActualResult, Review

__all__ = [
    "RawPost", "RawComment", "RawRules", "RawSubredditMeta",
    "ReferenceItem", "Comment",
    "ContentAnalysis", "PerformanceAnalysis",
    "KnowledgePattern", "CommunityProfile",
    "Embedding",
    "ContentAnalysisSnapshot", "ActualResult", "Review",
]
