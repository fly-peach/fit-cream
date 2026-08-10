"""
Lint Pydantic Schemas（知识库健康检查）
"""
from typing import List
from uuid import UUID

from pydantic import BaseModel


class KBLintIssue(BaseModel):
    severity: str  # error / warn
    code: str
    path: str
    message: str


class KBLintReport(BaseModel):
    kb_id: UUID
    total: int
    errors: int
    warnings: int
    issues: List[KBLintIssue]