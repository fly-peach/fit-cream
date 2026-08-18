"""
知识库回答开关中间件（按请求门控 KB 工具 + 注入 KB 优先提示词）

前端输入栏「知识库回答」开关（默认关闭，localStorage 全局偏好）：
- 开启：本轮请求模型可见 3 个 KB 工具，且在用户新消息时注入
  KB_ANSWER_PROMPT（优先检索用户订阅的知识库作答，带站内出处链接）
- 关闭：wrap_model_call 从 request.tools 移除 3 个 KB 工具（模型完全看不到），
  等价于未注入

共享 graph 架构：工具在 create_fitcream_agent 编译时固化，无法按请求真正增删，
故通过 wrap_model_call 过滤本轮模型可见工具实现等价效果。

运行时标志解析：chat.py 把请求体 kb_enabled 写入 RunnableConfig.configurable，
本中间件经 langgraph.config.get_config() 读取（仿 memory_update._resolve_ids 模式），
中间件自身无实例级可变状态，并发 run 互不影响。

注意：KB_ANSWER_PROMPT 必须是模块常量，不能放进
orchestration/prompts/injection_prompt/ 目录（system.py _load_intent_prompts
会自动扫描该目录每个 .md 为意图键，造成误注入）。
"""

import logging
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import HumanMessage, SystemMessage
from langgraph.runtime import Runtime

logger = logging.getLogger("fitcream.agent")

# 受门控的知识库工具名（须与 knowledge_tools.py 中 @tool 函数名一致）
KB_TOOLS = ("search_knowledge_base", "read_kb_document", "list_my_knowledge_bases")

KB_ANSWER_PROMPT = """本轮对话已开启「知识库回答」模式，请遵循以下规则：

1. 用户询问训练、营养、康复、健身知识类问题时，**优先**调用 `search_knowledge_base` 检索
   （不传 kb_id，即检索用户已订阅及自有的全部知识库），再基于检索结果回答。
2. 回答流程：检索命中内容 -> 整理归纳 -> 分析与用户问题最相关的答案 -> 组织成清晰的回复。
3. 回答涉及具体文档时，必须用工具返回的 `url` 以 markdown 链接形式附上站内出处
   （如 [《文档标题》](/knowledge-bases/...)），只使用工具返回的 url，禁止编造；
   文档内容中出现的外部视频/资源链接也一并推荐给用户；禁止用反引号包裹链接。
4. 知识库未命中相关内容时，如实告知用户未在知识库中找到，
   再基于通用知识回答并注明该部分非知识库来源。
5. 打卡、计划、饮食记录等指令类请求不受影响，正常调用对应工具处理。
注： 
1. 如用户无订阅的知识库，则先让用户去知识库界面阅读知识库，查看相关博主并订阅感兴趣的知识库，
   避免用户无订阅知识库时无法使用知识库回答。
2. 本模式下，显然用户已经对健身的知识有所追求，则在回答问题的时候不仅需要整理相关的文章，
    并且需要给出文章内附着的内部视频链接，提醒用户如想获得完整的知识与指导，博主的视频会更有帮助。
"""


def kb_enabled_from_config() -> bool:
    """从当前 run 的 RunnableConfig.configurable 解析 kb_enabled 标志。

    缺失 / falsy / 解析异常（如 LangGraph Studio 无 configurable）一律视为关闭，
    保证旧客户端与开发环境行为不变。
    """
    try:
        from langgraph.config import get_config

        cfg = get_config() or {}
        conf = cfg.get("configurable") or {}
        return bool(conf.get("kb_enabled"))
    except Exception:
        return False


def _tool_name(tool: Any) -> str:
    """兼容 BaseTool 与 provider 工具 dict 两种形态取工具名。"""
    if isinstance(tool, dict):
        return str(tool.get("name") or "")
    return getattr(tool, "name", "") or ""


class KBGateMiddleware(AgentMiddleware):
    """知识库回答开关中间件 - 按请求过滤 KB 工具 + 注入 KB 优先提示词。

    - wrap_model_call：kb_enabled 为 falsy 时从 request.tools 移除 3 个 KB 工具
      （仅影响本轮模型可见工具，checkpoint 中已存消息不受影响）
    - before_model：kb_enabled 为 truthy 且最新消息为 HumanMessage 时注入
      KB_ANSWER_PROMPT（仅用户新消息时注入一次，避免 tool 循环重复注入，
      同 IntentMiddleware 模式）

    无实例级可变状态：中间件被编译进共享 graph，并发运行互不影响。
    """

    def wrap_model_call(self, request, handler):
        if kb_enabled_from_config():
            return handler(request)
        filtered = [t for t in request.tools if _tool_name(t) not in KB_TOOLS]
        if len(filtered) == len(request.tools):
            return handler(request)
        return handler(request.override(tools=filtered))

    async def awrap_model_call(self, request, handler):
        if kb_enabled_from_config():
            return await handler(request)
        filtered = [t for t in request.tools if _tool_name(t) not in KB_TOOLS]
        if len(filtered) == len(request.tools):
            return await handler(request)
        return await handler(request.override(tools=filtered))

    def before_model(
        self, state: AgentState, runtime: Runtime
    ) -> dict[str, Any] | None:
        if not kb_enabled_from_config():
            return None

        messages = state.get("messages", [])
        if not messages:
            return None

        # 仅在用户发送新消息时注入（跳过 ToolMessage / AIMessage）
        if not isinstance(messages[-1], HumanMessage):
            return None

        logger.info("[KBGate] 知识库回答已开启，注入 KB 优先提示词")
        return {"messages": [SystemMessage(content=KB_ANSWER_PROMPT)]}
