"""
活动水平档位换算引擎

对标「谭成义三个月减脂计划」的 4 档运动量选择引导：
- 4 档：每周 2-3h / 4-5h / 6-7h / 8-9h 训练时长，映射为 TDEE 活动系数
- 基础代谢 BMR 采用 Mifflin-St Jeor 公式
- 每日热量目标 TDEE = BMR × 活动系数，再按健身目标增减
- 宏量营养素按目标比例换算为克数（蛋白/碳水/脂肪）

纯函数实现，不依赖数据库，供饮食计划生成、前端换算预览共用。
"""
from typing import Optional


# 4 档活动水平：key 为 API 稳定标识，label 为展示文案，factor 为 TDEE 活动系数
ACTIVITY_LEVELS = {
    "light": {"label": "每周 2-3 小时", "factor": 1.375},
    "moderate": {"label": "每周 4-5 小时", "factor": 1.55},
    "active": {"label": "每周 6-7 小时", "factor": 1.725},
    "very_active": {"label": "每周 8-9 小时", "factor": 1.9},
}

DEFAULT_ACTIVITY_LEVEL = "moderate"

# 各目标的每日热量增减（kcal）：在 TDEE 基础上调整
GOAL_CALORIE_DELTA = {
    "lose_fat": -500,
    "gain_muscle": 300,
    "maintain": 0,
    "improve_health": -200,
}

# 各目标的宏量素热量占比（与饮食计划生成口径一致）
GOAL_MACRO_RATIOS = {
    "lose_fat": {"protein": 0.4, "carbs": 0.3, "fat": 0.3},
    "gain_muscle": {"protein": 0.35, "carbs": 0.45, "fat": 0.2},
    "maintain": {"protein": 0.3, "carbs": 0.4, "fat": 0.3},
    "improve_health": {"protein": 0.3, "carbs": 0.4, "fat": 0.3},
}


def calculate_bmr(
    weight_kg: Optional[float],
    height_cm: Optional[float],
    age: Optional[int],
    gender: Optional[str],
) -> Optional[float]:
    """Mifflin-St Jeor 基础代谢率（kcal/天）。

    需体重/身高/年龄齐备；性别 male/female 分别套用男/女公式，其余取中性值。
    任一关键数据缺失返回 None（调用方回退旧的 weight×factor 估算）。
    """
    if not weight_kg or not height_cm or not age:
        return None
    base = 10 * weight_kg + 6.25 * height_cm - 5 * age
    if gender == "male":
        return round(base + 5, 1)
    if gender == "female":
        return round(base - 161, 1)
    return round(base - 78, 1)


def calculate_tdee(bmr: Optional[float], activity_level: Optional[str]) -> Optional[float]:
    """TDEE = BMR × 活动系数。"""
    if bmr is None:
        return None
    level = ACTIVITY_LEVELS.get(activity_level or "", ACTIVITY_LEVELS[DEFAULT_ACTIVITY_LEVEL])
    return round(bmr * level["factor"], 1)


def calculate_target_calories(tdee: Optional[float], goal: str) -> Optional[int]:
    """在 TDEE 基础上按目标增减得到每日热量目标。"""
    if tdee is None:
        return None
    delta = GOAL_CALORIE_DELTA.get(goal, 0)
    return max(1200, round(tdee + delta))


def calculate_macros(target_calories: int, goal: str) -> dict:
    """按目标比例把每日热量换算为宏量素克数。"""
    ratios = GOAL_MACRO_RATIOS.get(goal, GOAL_MACRO_RATIOS["maintain"])
    protein_g = round(target_calories * ratios["protein"] / 4)
    carbs_g = round(target_calories * ratios["carbs"] / 4)
    fat_g = round(target_calories * ratios["fat"] / 9)
    return {"protein_g": protein_g, "carbs_g": carbs_g, "fat_g": fat_g}


def compute_daily_targets(
    *,
    weight_kg: Optional[float],
    height_cm: Optional[float],
    age: Optional[int],
    gender: Optional[str],
    activity_level: Optional[str],
    goal: str,
) -> dict:
    """一站式换算：返回每日热量目标 + 宏量素克数 + 中间量（BMR/TDEE）。

    身体数据不全时 calorie 相关字段为 None（调用方按旧逻辑兜底）。
    """
    bmr = calculate_bmr(weight_kg, height_cm, age, gender)
    tdee = calculate_tdee(bmr, activity_level)
    target_calories = calculate_target_calories(tdee, goal)
    macros = calculate_macros(target_calories, goal) if target_calories else None
    return {
        "activity_level": activity_level or DEFAULT_ACTIVITY_LEVEL,
        "activity_label": ACTIVITY_LEVELS.get(
            activity_level or "", ACTIVITY_LEVELS[DEFAULT_ACTIVITY_LEVEL]
        )["label"],
        "bmr": bmr,
        "tdee": tdee,
        "target_calories": target_calories,
        "protein_g": macros["protein_g"] if macros else None,
        "carbs_g": macros["carbs_g"] if macros else None,
        "fat_g": macros["fat_g"] if macros else None,
    }
