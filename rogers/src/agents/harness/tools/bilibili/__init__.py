"""
B 站视频直读工具

导出 read_bilibili_video，供 Agent 读取 B 站视频字幕/转写文本。
"""
from src.agents.harness.tools.bilibili.bilibili_tool import read_bilibili_video

__all__ = ["read_bilibili_video"]