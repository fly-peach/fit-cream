"""
Thread Token 用量模型

存储每个对话线程的累计 token 使用量。
每次对话结束时 upsert（累加）。
"""
from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from src.agents.models.thread_base import ThreadBase


class ThreadUsage(ThreadBase, Base):
    __tablename__ = "thread_usages"

    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
