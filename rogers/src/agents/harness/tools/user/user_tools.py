"""
用户相关 Tools

供 Agent 调用，查询和更新用户个人资料：
- get_user_profile_tool: 获取用户身体数据和健身目标（数据库实时数据）
- update_user_profile_tool: 部分更新用户资料（身高、体重、年龄、性别、目标）
- update_fitness_profile_tool: 部分更新用户健身画像（健康安全/体能/经历/生活方式/饮食偏好）

直接调用 UserService（同进程融合，不走 HTTP）。
"""

from datetime import date
from typing import Optional

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from pydantic import BaseModel, Field

from src.agents.harness.tools._common import error_response, extract_user_id, session_scope
from src.fitme.schemas.user import UserFitnessProfileUpdate
from src.fitme.services.user_service import UserService


@tool
async def get_user_profile_tool(config: RunnableConfig) -> dict:
    """
    获取当前用户的个人资料和身体数据。

    当需要了解用户信息以提供个性化建议时调用。

    Returns:
        用户基本信息、身体数据、健身目标
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息（未登录或会话无效）"}

    try:
        async with session_scope() as db:
            profile = await UserService.get_profile_summary(db, user_id)
            return {"success": True, "profile": profile}
    except Exception as e:
        return error_response(e)


class UpdateUserProfileInput(BaseModel):
    """更新用户资料的输入参数"""

    name: Optional[str] = Field(default=None, description="昵称")
    height_cm: Optional[float] = Field(default=None, description="身高（厘米）")
    weight_kg: Optional[float] = Field(default=None, description="体重（公斤）")
    birth_date: Optional[date] = Field(default=None, description="出生日期（YYYY-MM-DD）")
    gender: Optional[str] = Field(
        default=None, description="性别：male(男)、female(女)、other(其他)"
    )
    goal: Optional[str] = Field(
        default=None,
        description=(
            "健身目标：lose_fat(减脂)、gain_muscle(增肌)、"
            "maintain(保持健康)、improve_health(改善体质)"
        ),
    )


@tool(args_schema=UpdateUserProfileInput)
async def update_user_profile_tool(
    name: Optional[str] = None,
    height_cm: Optional[float] = None,
    weight_kg: Optional[float] = None,
    birth_date: Optional[date] = None,
    gender: Optional[str] = None,
    goal: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    更新当前用户的个人资料和身体数据。

    使用场景：
    - 用户说"我身高175，体重70公斤"→ height_cm=175, weight_kg=70
    - 用户说"我出生日期是2000年1月1日，男"→ birth_date="2000-01-01", gender="male"
    - 用户说"我的目标是减脂"→ goal="lose_fat"
    - 用户说"帮我改一下体重为68"→ weight_kg=68

    只更新传入的字段，未传入的字段保持不变。

    Returns:
        更新后的用户资料
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息（未登录或会话无效）"}

    try:
        async with session_scope() as db:
            await UserService.update_profile_consolidated(
                db,
                user_id,
                name=name,
                birth_date=birth_date,
                gender=gender,
                height_cm=height_cm,
                weight_kg=weight_kg,
                goal=goal,
            )

            profile = await UserService.get_profile_summary(db, user_id)
            return {
                "success": True,
                "profile": profile,
                "message": "用户资料已更新。",
            }
    except Exception as e:
        return error_response(e)


class UpdateFitnessProfileInput(BaseModel):
    """更新用户健身画像的输入参数（健康安全/体能/经历/生活方式/饮食偏好）"""

    # health_safety 健康与安全基线
    medical_history: Optional[str] = Field(
        default=None,
        description="既往病史与当前健康状况（如高血压、糖尿病等，无则填「无」）",
    )
    injuries: Optional[str] = Field(
        default=None,
        description="伤病与身体限制（如膝盖旧伤、腰背不适，无则填「无」）",
    )
    allergies: Optional[str] = Field(
        default=None, description="过敏史与食物不耐（如海鲜过敏、乳糖不耐受）"
    )
    pregnancy: Optional[str] = Field(
        default=None, description="孕期/产后状态（女性是否处于孕期、备孕或产后阶段）"
    )
    medication: Optional[str] = Field(
        default=None,
        description="正在服用的药物（可能影响运动生理反应，无则填「无」）",
    )
    parq_result: Optional[str] = Field(
        default=None,
        description=(
            "PAR-Q 运动风险自查结果：low(无上述情况/低风险)、"
            "uncertain(不确定)、high(有上述情况/建议先咨询医生)"
        ),
    )
    doctor_advice: Optional[str] = Field(
        default=None, description="医生建议（运动的许可或限制说明）"
    )

    # fitness_level 当前体能水平
    training_experience: Optional[str] = Field(
        default=None,
        description=(
            "系统训练经验：never(从未系统训练)、beginner(初学者/不足1年)、"
            "intermediate(进阶/1-3年)、advanced(资深/3年以上)"
        ),
    )
    cardio_level: Optional[str] = Field(
        default=None,
        description="心肺耐力：beginner(吃力)、intermediate(可以完成但较累)、advanced(轻松完成)",
    )
    strength_level: Optional[str] = Field(
        default=None,
        description="力量水平：beginner(入门)、intermediate(中等)、advanced(良好)",
    )
    flexibility: Optional[str] = Field(
        default=None,
        description="柔韧性：limited(较受限)、normal(正常)、good(良好)",
    )
    body_fat_pct: Optional[float] = Field(
        default=None, ge=0, le=100, description="自估体脂率（百分比数值）"
    )

    # exercise_history 运动经历与习惯
    weekly_frequency: Optional[str] = Field(
        default=None,
        description="当前每周运动次数：0(几乎不运动)、1-2、3-4、5+(5次以上)",
    )
    session_duration: Optional[str] = Field(
        default=None,
        description="每次运动时长：<30(30分钟以内)、30-60、>60(1小时以上)",
    )
    preferred_types: Optional[str] = Field(
        default=None, description="常做/喜欢的运动（如跑步、撸铁、游泳）"
    )
    past_results: Optional[str] = Field(
        default=None, description="过往训练成果"
    )

    # lifestyle 生活方式与客观环境
    occupation_schedule: Optional[str] = Field(
        default=None, description="职业与作息（如久坐办公、晚上有空）"
    )
    diet_habits: Optional[str] = Field(
        default=None, description="饮食习惯（如外卖为主、口味偏咸）"
    )
    sleep_quality: Optional[str] = Field(
        default=None,
        description="睡眠质量：poor(较差)、normal(一般)、good(良好)",
    )
    stress_level: Optional[str] = Field(
        default=None,
        description="压力水平：low(较低)、medium(中等)、high(较高)",
    )
    equipment: Optional[str] = Field(
        default=None, description="可用训练设备/场地（如健身房、家用哑铃、无器械）"
    )
    preferred_time: Optional[str] = Field(
        default=None,
        description=(
            "偏好训练时段：morning(早晨)、noon(中午)、evening(晚上)、flexible(灵活)"
        ),
    )

    # diet_profile 饮食偏好与结构
    diet_preferences: Optional[str] = Field(
        default=None, description="饮食偏好（如少油清淡、爱吃肉、素食为主）"
    )
    food_allergies: Optional[str] = Field(
        default=None, description="忌口/过敏（如海鲜过敏、不吃辣）"
    )
    cooking_condition: Optional[str] = Field(
        default=None, description="烹饪条件/时间（如早餐外食、晚餐可自炊）"
    )
    meals_per_day: Optional[str] = Field(
        default=None, description="每日餐次：2、3、4、5+(5餐以上)"
    )
    eating_out_ratio: Optional[str] = Field(
        default=None,
        description=(
            "外食vs自炊比例：mostly_out(基本外食)、half(各一半)、mostly_home(基本自炊)"
        ),
    )
    budget: Optional[str] = Field(
        default=None, description="每日饮食预算（如 50 元/天）"
    )


@tool(args_schema=UpdateFitnessProfileInput)
async def update_fitness_profile_tool(
    medical_history: Optional[str] = None,
    injuries: Optional[str] = None,
    allergies: Optional[str] = None,
    pregnancy: Optional[str] = None,
    medication: Optional[str] = None,
    parq_result: Optional[str] = None,
    doctor_advice: Optional[str] = None,
    training_experience: Optional[str] = None,
    cardio_level: Optional[str] = None,
    strength_level: Optional[str] = None,
    flexibility: Optional[str] = None,
    body_fat_pct: Optional[float] = None,
    weekly_frequency: Optional[str] = None,
    session_duration: Optional[str] = None,
    preferred_types: Optional[str] = None,
    past_results: Optional[str] = None,
    occupation_schedule: Optional[str] = None,
    diet_habits: Optional[str] = None,
    sleep_quality: Optional[str] = None,
    stress_level: Optional[str] = None,
    equipment: Optional[str] = None,
    preferred_time: Optional[str] = None,
    diet_preferences: Optional[str] = None,
    food_allergies: Optional[str] = None,
    cooking_condition: Optional[str] = None,
    meals_per_day: Optional[str] = None,
    eating_out_ratio: Optional[str] = None,
    budget: Optional[str] = None,
    config: "RunnableConfig" = None,  # type: ignore[assignment]
) -> dict:
    """
    更新当前用户的健身画像（健康与安全 / 体能水平 / 运动经历 / 生活方式 / 饮食偏好）。

    使用场景：
    - 用户提交 health_safety/fitness_level/exercise_history/lifestyle/diet_profile
      表单后，读取「[表单提交: <form_id>]」消息中的新补充字段调用本工具落库
    - 用户闲聊中主动告知健康/体能/生活方式变化时，直接更新对应字段
    - 个人中心健身画像页保存时由前端直连 REST 接口，不经过本工具

    只更新传入的字段，未传入的字段保持不变；不触发审批中断（非破坏性写入）。

    Returns:
        更新后的健身画像
    """
    user_id = extract_user_id(config)
    if not user_id:
        return {"success": False, "error": "无法获取用户信息（未登录或会话无效）"}

    try:
        update = UserFitnessProfileUpdate(
            medical_history=medical_history,
            injuries=injuries,
            allergies=allergies,
            pregnancy=pregnancy,
            medication=medication,
            parq_result=parq_result,
            doctor_advice=doctor_advice,
            training_experience=training_experience,
            cardio_level=cardio_level,
            strength_level=strength_level,
            flexibility=flexibility,
            body_fat_pct=body_fat_pct,
            weekly_frequency=weekly_frequency,
            session_duration=session_duration,
            preferred_types=preferred_types,
            past_results=past_results,
            occupation_schedule=occupation_schedule,
            diet_habits=diet_habits,
            sleep_quality=sleep_quality,
            stress_level=stress_level,
            equipment=equipment,
            preferred_time=preferred_time,
            diet_preferences=diet_preferences,
            food_allergies=food_allergies,
            cooking_condition=cooking_condition,
            meals_per_day=meals_per_day,
            eating_out_ratio=eating_out_ratio,
            budget=budget,
        )
        async with session_scope() as db:
            await UserService.update_fitness_profile(db, user_id, update)
            return {
                "success": True,
                "intake": update.model_dump(exclude_unset=True),
                "message": "健身画像已更新。",
            }
    except Exception as e:
        return error_response(e)
