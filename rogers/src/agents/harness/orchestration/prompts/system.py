"""
FitCream Agent System Prompt（渐进式提示词架构）

采用"渐进式披露"(Progressive Disclosure) 设计：
- BASE_SYSTEM_PROMPT: 从 agent.md 加载的 L0 静态层（身份、规则、操作边界、user-summary 段）
- INTENT_PROMPTS: 按意图动态注入的专项提示词（由 IntentMiddleware 触发），
  内容存放于 injection_prompt/<intent>.md，文件名即意图键，启动时扫描加载
- build_system_prompt(): 组装 base + intent + 用户上下文

架构：
    ┌────────────────────────────────────────────┐
    │  Base Layer（agent.md，始终存在）            │
    │  - 身份、核心规则、输出格式、操作边界         │
    │  - 用户画像摘要段（get_user_summary_tool）   │
    ├────────────────────────────────────────────┤
    │  Intent Layer（由 Middleware 动态注入）       │
    │  - injection_prompt/*.md 按意图键加载        │
    │  - plan_creation / checkin / image_analysis │
    │  - meal_image_analysis / stats_analysis ... │
    ├────────────────────────────────────────────┤
    │  Context Layer（动态用户上下文）              │
    │  - 用户名、目标、统计数据、记忆上下文         │
    └────────────────────────────────────────────┘

提示词编排（agent.md / injection_prompt/*.md）与 Python 逻辑（加载 + INTENT injection）分离。
改提示词改 markdown 文件，不读本文件。
"""

from datetime import date
from pathlib import Path
from typing import Optional


# ============================================================
# 基础系统提示词（从 agent.md 加载，L0 静态层唯一入口）
# ============================================================

_AGENT_MD = Path(__file__).parent / "agent.md"
BASE_SYSTEM_PROMPT = _AGENT_MD.read_text(encoding="utf-8")

# 向后兼容：SYSTEM_PROMPT 等于基础提示词
SYSTEM_PROMPT = BASE_SYSTEM_PROMPT


# ============================================================
# 意图专项提示词（由 IntentMiddleware 渐进式注入）
# ============================================================

_INJECTION_DIR = Path(__file__).parent / "injection_prompt"


def _load_intent_prompts() -> dict[str, str]:
    """扫描 injection_prompt/ 目录加载意图专项提示词。

    文件名（不含 .md 后缀）即意图键，与 INTENT_KEYWORDS 的键对齐。
    新增意图只需添加 <intent>.md 文件，无需改代码。
    """
    prompts: dict[str, str] = {}
    if not _INJECTION_DIR.is_dir():
        return prompts
    for md in sorted(_INJECTION_DIR.glob("*.md")):
        prompts[md.stem] = md.read_text(encoding="utf-8").strip()
    return prompts


INTENT_PROMPTS: dict[str, str] = _load_intent_prompts()


# ============================================================
# 编排 / 门控类提示词（非意图注入，由对应中间件按需读取）
# ============================================================

_CONTEXT_DIR = Path(__file__).parent / "context_prompt"


def _load_context_prompts() -> dict[str, str]:
    """扫描 context_prompt/ 目录加载编排 / 门控类提示词。

    文件名（不含 .md 后缀）即键，与 injection_prompt/ 平级但互不干扰：
    ``_load_intent_prompts`` 只扫 injection_prompt/，避免门控提示词被误当意图注入。
    """
    prompts: dict[str, str] = {}
    if not _CONTEXT_DIR.is_dir():
        return prompts
    for md in sorted(_CONTEXT_DIR.glob("*.md")):
        prompts[md.stem] = md.read_text(encoding="utf-8").strip()
    return prompts


CONTEXT_PROMPTS: dict[str, str] = _load_context_prompts()


# ============================================================
# 意图列表（供 Middleware 使用）
# ============================================================

INTENT_KEYWORDS: dict[str, list[str]] = {
    "plan_creation": ["制定计划", "创建计划", "设计计划", "新计划", "减脂计划", "增肌计划", "训练计划", "饮食计划", "健身计划", "做一份计划", "做个计划", "出一份计划", "出个计划", "弄个计划", "安排训练", "安排一下训练", "帮我规划", "调整计划", "计划一下", "定制计划"],
    "checkin": ["打卡", "训练了", "做完了", "今天练了", "完成了", "练了", "刚才做了", "刚练完", "练完", "今天训练"],
    "stats_analysis": ["统计", "数据", "趋势", "分析", "多少次", "练了多少", "报告", "进展"],
    "exercise_query": ["动作", "推荐动作", "怎么练", "锻炼", "练什么", "肌群", "怎么做", "正确姿势", "动作要领"],
    "memory_operation": ["记得", "上次", "之前", "偏好", "习惯", "我喜欢", "我不喜欢", "保存", "还记得", "记住"],
    "profile_update": ["更新", "修改", "身高", "体重", "年龄", "改成", "变了"],
    "knowledge_query": ["什么是", "原理", "为什么", "知识", "解释", "区别", "蛋白质", "碳水", "肌肥大", "超负荷", "代谢"],
    "diet_record": ["吃了", "记录饮食", "今天吃了", "摄入", "热量", "营养", "记一下", "刚吃", "早餐吃了", "午餐", "晚餐", "饮食记录", "记一笔"],
}

# 负向关键词：命中任一关键词时，即使正向关键词匹配也**跳过**该意图（优先级更高）。
# 用于消解歧义——如 plan_creation 的「计划」与 diet_record 的「饮食计划」、
# stats_analysis 的「记录」与 diet_record 等。
INTENT_NEGATIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "plan_creation": ("取消计划", "删除计划", "我的计划", "现有计划", "查一下计划", "查看计划"),
    "stats_analysis": ("记录吃了", "记录饮食", "记一下吃了", "记一笔"),
    "profile_update": ("目标是什么", "目标怎么"),
}

# 饮食图片关键词：图片消息的伴随文本命中任一关键词时，走"饮食热量识别"专项流程
MEAL_IMAGE_KEYWORDS: list[str] = [
    "热量", "卡路里", "营养", "减脂餐", "增肌餐", "健身餐", "吃了",
    "餐", "饭", "面", "沙拉", "早餐", "午餐", "晚餐", "加餐", "夜宵",
]

# LLM 意图兜底提示词（仅当 configurable.intent_classify_llm 开启且关键词无命中时使用）
INTENT_CLASSIFY_PROMPT = """你是健身教练助手。判断用户最新消息属于以下哪个意图，只输出意图名本身，不要解释、不要前后缀。

可选意图：
- plan_creation：创建/设计新的训练或饮食计划
- checkin：训练打卡
- stats_analysis：查询统计/进度/趋势
- exercise_query：查询动作/训练方法/肌群知识
- memory_operation：记忆存取（记住/回想偏好）
- profile_update：更新个人资料（身高/体重/年龄/目标）
- knowledge_query：健身知识问答
- diet_record：记录饮食/热量摄入
- general_chat：以上都不属于的普通聊天

消息：{text}
意图："""


# ============================================================
# 动态构建函数
# ============================================================

def build_system_prompt(
    intent: Optional[str] = None,
    user_name: Optional[str] = None,
    user_goal: Optional[str] = None,
    user_stats: Optional[dict] = None,
    current_date: Optional[str] = None,
    extra_context: Optional[str] = None,
    memory_context: Optional[str] = None,
) -> str:
    """
    动态构建系统提示词（渐进式披露）。

    组装三层：
    1. Base Layer：身份、能力概览、核心规则（始终存在）
    2. Intent Layer：意图专项规则（当 intent 匹配时注入）
    3. Context Layer：用户名、目标、统计数据、记忆上下文

    Args:
        intent: 用户意图（plan_creation/checkin/image_analysis/meal_image_analysis/...）
        user_name: 用户名称
        user_goal: 用户健身目标 (lose_fat/gain_muscle/maintain/improve_health)
        user_stats: 用户统计信息 {"current_streak": 7, "total_workouts": 50, ...}
        current_date: 当前日期字符串 (YYYY-MM-DD)，默认今天
        extra_context: 额外的上下文信息
        memory_context: 记忆上下文（由 MemoryPipeline.get_memory_context() 生成）

    Returns:
        完整的系统提示词字符串

    Example:
        # 基础用法（无意图）
        prompt = build_system_prompt()

        # 带意图和用户上下文
        prompt = build_system_prompt(
            intent="plan_creation",
            user_name="张三",
            user_goal="lose_fat",
            user_stats={"current_streak": 7, "total_workouts": 30},
        )
    """
    # 1. Base Layer（始终存在）
    parts = [BASE_SYSTEM_PROMPT]

    # 2. Intent Layer（渐进式注入）
    if intent and intent in INTENT_PROMPTS:
        parts.append(INTENT_PROMPTS[intent])

    # 3. Context Layer（动态用户上下文）
    context_lines = ["\n# 当前对话上下文\n"]

    if current_date is None:
        current_date = date.today().isoformat()
    context_lines.append(f"- 当前日期：{current_date}")

    if user_name:
        context_lines.append(f"- 用户称呼：{user_name}")

    goal_map = {
        "lose_fat": "减脂",
        "gain_muscle": "增肌",
        "maintain": "维持体型",
        "improve_health": "改善健康",
    }
    if user_goal:
        goal_text = goal_map.get(user_goal, user_goal)
        context_lines.append(f"- 用户目标：{goal_text}")

    if user_stats:
        streak = user_stats.get("current_streak")
        total = user_stats.get("total_workouts")
        if streak is not None:
            context_lines.append(f"- 当前连续打卡：{streak} 天")
        if total is not None:
            context_lines.append(f"- 累计训练次数：{total} 次")

    if extra_context:
        context_lines.append(f"\n{extra_context}")

    parts.append("\n".join(context_lines))

    # 记忆上下文（由记忆系统动态注入）
    if memory_context:
        parts.append(f"\n{memory_context}")

    return "\n".join(parts)
