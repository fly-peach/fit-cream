"""
知识图谱 Pydantic Schemas
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class KBGraphNode(BaseModel):
    id: str
    title: str
    path: str
    tags: List[str] = Field(default_factory=list)
    stale_since: Optional[str] = None
    uncited: bool = False
    degree: int = 0
    semantic_group: str = "其他"


class KBGraphEdge(BaseModel):
    source: str
    target: str
    type: str  # cites / links_to
    page: Optional[int] = None


class KBGraphData(BaseModel):
    nodes: List[KBGraphNode]
    edges: List[KBGraphEdge]
    stats: dict = Field(default_factory=dict)