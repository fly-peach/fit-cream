"""
用户级 Token 用量 Schemas
"""
from datetime import date

from pydantic import BaseModel, Field


class TokenSourceStat(BaseModel):
    source: str = ""
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0


class TokenDailyPoint(BaseModel):
    usage_date: date
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class UserTokenUsageOut(BaseModel):
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    by_source: list[TokenSourceStat] = Field(default_factory=list)
    daily: list[TokenDailyPoint] = Field(default_factory=list)