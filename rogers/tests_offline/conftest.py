"""
离线测试专用 conftest（与 tests/ 的 DB 集成 conftest 完全隔离）。

这些测试只测 agent harness 的健壮性 / 安全不变量，不连 PostgreSQL、不 import 生产 DB。
导入 src.agents.harness.* 会触发 agent_graph 构建默认 graph（无 checkpointer，不连 DB），
仅需一个非空 DASHSCOPE_API_KEY 即可构造模型客户端（不产生网络调用），故在导入前
setdefault 一个占位值保证测试可离线运行。
"""
import os

os.environ.setdefault("DASHSCOPE_API_KEY", "test-dummy-key")
