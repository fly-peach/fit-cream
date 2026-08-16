"""
记忆提取器 (Memory Extractor)

从对话中提取值得长期记忆的信息：
- 情景记忆：重要事件、观察、用户分享的经历
- 语义记忆：用户偏好、事实、规则（三元组形式）
- 程序性记忆：工作流程、技能方法

使用 LLM 分析对话内容，自动提取结构化记忆。

用法：
    from src.agents.harness.runtime.memory.extractor import MemoryExtractor
    
    extractor = MemoryExtractor(llm)
    extracted = await extractor.extract_from_conversation(
        user_id="user-123",
        messages=conversation_messages,
    )
"""

import json
import logging
from typing import Optional, Any
from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage
from langchain_core.language_models import BaseChatModel

from src.fitme.services.usage_service import SOURCE_MEMORY_EXTRACTION, UsageService

logger = logging.getLogger("fitcream.memory")


@dataclass
class ExtractedEpisodic:
    """提取的情景记忆"""
    content: str
    memory_type: str = "conversation"  # conversation/event/observation
    importance: float = 0.5
    emotional_valence: str = "neutral"  # positive/negative/neutral
    summary: Optional[str] = None


@dataclass
class ExtractedSemantic:
    """提取的语义记忆"""
    subject: str
    predicate: str
    object: str
    category: str = "fact"  # preference/fact/rule/status
    confidence: float = 1.0


@dataclass
class ExtractedProcedural:
    """提取的程序性记忆"""
    name: str
    steps: list[dict] = field(default_factory=list)
    description: Optional[str] = None
    trigger_conditions: Optional[dict] = None


@dataclass
class ExtractionResult:
    """提取结果"""
    episodic: list[ExtractedEpisodic] = field(default_factory=list)
    semantic: list[ExtractedSemantic] = field(default_factory=list)
    procedural: list[ExtractedProcedural] = field(default_factory=list)


EXTRACTION_PROMPT = """\
你是一个记忆提取专家。分析以下对话，提取值得长期记忆的信息。

## 对话内容
{conversation}

## 提取要求

### 1. 情景记忆 (Episodic Memory)
提取重要的事件、观察、用户分享的经历：
- 用户提到的具体事件（如"今天跑了5公里"）
- 重要的对话片段
- 用户表达的感受或状态

### 2. 语义记忆 (Semantic Memory)
提取用户偏好、事实、规则，以三元组形式表示：
- (用户, 偏好, 晨跑) - 用户喜欢晨跑
- (用户, 目标, 减脂) - 用户的目标是减脂
- (用户, 身体状况, 膝盖有旧伤) - 用户的身体状况

**禁止提取会落库到用户档案的字段**（身高/体重/年龄/性别/健身目标/昵称），
这些数据已存储在数据库 users/health_metrics/user_settings 表中，不应在记忆里重复记录。
例如"我身高175cm、体重70kg、目标是减脂"中的身高/体重/目标都不要提取为语义记忆，
只提取偏好、伤病、习惯、规则等不会落库的信息。

### 3. 程序性记忆 (Procedural Memory)
如果用户描述了某个流程或方法，可以固化为技能（较少见）。

## 输出格式
请输出 JSON 格式（不要包含 markdown 代码块标记）：
{{
    "episodic": [
        {{
            "content": "记忆内容",
            "type": "conversation|event|observation",
            "importance": 0.8,
            "emotional_valence": "positive|negative|neutral",
            "summary": "简短摘要"
        }}
    ],
    "semantic": [
        {{
            "subject": "主体",
            "predicate": "关系",
            "object": "对象",
            "category": "preference|fact|rule|status",
            "confidence": 0.9
        }}
    ],
    "procedural": []
}}

如果没有值得提取的记忆，返回空数组。
"""


class MemoryExtractor:
    """
    记忆提取器
    
    使用 LLM 分析对话，提取值得长期记忆的信息。
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        min_importance: float = 0.3,
    ):
        """
        初始化记忆提取器
        
        Args:
            llm: LLM 模型实例
            min_importance: 最小重要性阈值，低于此值的情景记忆将被过滤
        """
        self.llm = llm
        self.min_importance = min_importance
    
    async def extract_from_conversation(
        self,
        user_id: str,
        messages: list[BaseMessage],
        thread_id: Optional[str] = None,
    ) -> ExtractionResult:
        """
        从对话中提取记忆
        
        Args:
            user_id: 用户 ID
            messages: 对话消息列表
            thread_id: 对话线程 ID
            
        Returns:
            ExtractionResult 包含三类提取的记忆
        """
        # 格式化对话内容
        conversation_text = self._format_conversation(messages)
        
        # 如果对话太短，跳过提取
        if len(conversation_text) < 50:
            return ExtractionResult()
        
        # 构建提取 prompt
        prompt = EXTRACTION_PROMPT.format(conversation=conversation_text)
        
        # 调用 LLM 提取
        try:
            response = await self.llm.ainvoke([
                ("system", "你是一个记忆提取专家，请按要求输出 JSON 格式。"),
                ("human", prompt),
            ])

            usage = getattr(response, "usage_metadata", None) or {}
            if usage:
                await UsageService.record_background(
                    user_id=user_id,
                    source=SOURCE_MEMORY_EXTRACTION,
                    input_tokens=usage.get("input_tokens", 0) or 0,
                    output_tokens=usage.get("output_tokens", 0) or 0,
                    total_tokens=usage.get("total_tokens", 0) or 0,
                    llm_calls=1,
                )

            # 解析响应
            result = self._parse_response(response.content)
            
            # 过滤低重要性的情景记忆
            result.episodic = [
                ep for ep in result.episodic 
                if ep.importance >= self.min_importance
            ]
            
            return result
            
        except Exception as e:
            # 提取失败时返回空结果
            logger.error(f"Memory extraction failed: {e}")
            return ExtractionResult()
    
    def _format_conversation(self, messages: list[BaseMessage]) -> str:
        """格式化对话内容"""
        lines = []
        for msg in messages:
            role = self._get_role_name(msg)
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if content.strip():
                lines.append(f"{role}: {content}")
        return "\n".join(lines)
    
    def _get_role_name(self, message: BaseMessage) -> str:
        """获取消息角色名称"""
        role_map = {
            "human": "用户",
            "ai": "助手",
            "system": "系统",
        }
        return role_map.get(message.type, message.type)
    
    def _parse_response(self, content: str) -> ExtractionResult:
        """解析 LLM 响应，容错处理 markdown 代码块和 JSON 提取"""
        # 清理可能的 markdown 代码块标记（```json ... ```）
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 尝试用正则从混杂文本中提取 JSON 部分
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    return ExtractionResult()
            else:
                return ExtractionResult()
        
        # 解析情景记忆
        episodic = []
        for item in data.get("episodic", []):
            episodic.append(ExtractedEpisodic(
                content=item.get("content", ""),
                memory_type=item.get("type", "conversation"),
                importance=float(item.get("importance", 0.5)),
                emotional_valence=item.get("emotional_valence", "neutral"),
                summary=item.get("summary"),
            ))
        
        # 解析语义记忆
        semantic = []
        for item in data.get("semantic", []):
            semantic.append(ExtractedSemantic(
                subject=item.get("subject", ""),
                predicate=item.get("predicate", ""),
                object=item.get("object", ""),
                category=item.get("category", "fact"),
                confidence=float(item.get("confidence", 1.0)),
            ))
        
        # 解析程序性记忆
        procedural = []
        for item in data.get("procedural", []):
            procedural.append(ExtractedProcedural(
                name=item.get("name", ""),
                steps=item.get("steps", []),
                description=item.get("description"),
                trigger_conditions=item.get("trigger_conditions"),
            ))
        
        return ExtractionResult(
            episodic=episodic,
            semantic=semantic,
            procedural=procedural,
        )
    
    async def extract_preferences(
        self,
        user_id: str,
        text: str,
    ) -> list[ExtractedSemantic]:
        """
        从文本中提取用户偏好
        
        Args:
            user_id: 用户 ID
            text: 文本内容
            
        Returns:
            提取的偏好列表
        """
        prompt = f"""\
从以下文本中提取用户偏好，以三元组形式输出。

文本：{text}

输出 JSON 格式（不要包含 markdown 代码块标记）：
{{
    "preferences": [
        {{"subject": "用户", "predicate": "偏好", "object": "具体偏好"}}
    ]
}}
"""
        try:
            response = await self.llm.ainvoke([
                ("system", "你是一个偏好提取专家。"),
                ("human", prompt),
            ])
            
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]
            
            data = json.loads(content)
            
            return [
                ExtractedSemantic(
                    subject=item.get("subject", "用户"),
                    predicate=item.get("predicate", "偏好"),
                    object=item.get("object", ""),
                    category="preference",
                )
                for item in data.get("preferences", [])
            ]
            
        except Exception:
            return []
    
    async def generate_summary(
        self,
        text: str,
        max_length: int = 100,
    ) -> str:
        """
        生成文本摘要
        
        Args:
            text: 原始文本
            max_length: 最大摘要长度
            
        Returns:
            摘要文本
        """
        prompt = f"""\
请用不超过 {max_length} 个字概括以下内容：

{text}

摘要："""
        
        try:
            response = await self.llm.ainvoke([
                ("human", prompt),
            ])
            return response.content.strip()
        except Exception:
            return text[:max_length]