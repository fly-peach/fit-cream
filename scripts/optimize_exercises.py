"""
优化动作数据集脚本
==================
将 exercises_dataset.json 优化为只包含 zh 和 en 两个语言版本

用法:
  python scripts/optimize_exercises.py

输出:
  rogers/seeds/exercises_dataset_opt.json
"""

import json
import sys
import time
from pathlib import Path

# 修复 Windows 终端编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 预定义的中文翻译映射表
CATEGORY_ZH = {
    "back": "背部",
    "cardio": "有氧",
    "chest": "胸部",
    "lower arms": "前臂",
    "lower legs": "小腿",
    "neck": "颈部",
    "shoulders": "肩部",
    "upper arms": "上臂",
    "upper legs": "大腿",
    "waist": "腰部",
}

BODY_PART_ZH = CATEGORY_ZH  # body_part 和 category 相同

EQUIPMENT_ZH = {
    "assisted": "辅助",
    "band": "弹力带",
    "barbell": "杠铃",
    "body weight": "自重",
    "bosu ball": "波速球",
    "cable": "绳索",
    "dumbbell": "哑铃",
    "elliptical machine": "椭圆机",
    "ez barbell": "曲杆杠铃",
    "hammer": "锤铃",
    "kettlebell": "壶铃",
    "leverage machine": "杠杆机",
    "medicine ball": "药球",
    "olympic barbell": "奥林匹克杠铃",
    "resistance band": "阻力带",
    "roller": "滚轮",
    "rope": "绳子",
    "skierg machine": "滑雪机",
    "sled machine": "雪橇机",
    "smith machine": "史密斯机",
    "stability ball": "稳定球",
    "stationary bike": "动感单车",
    "stepmill machine": "登山机",
    "tire": "轮胎",
    "trap bar": "六角杠铃",
    "upper body ergometer": "上肢功率计",
    "weighted": "负重",
    "wheel roller": "健腹轮",
}

MUSCLE_GROUP_ZH = {
    "abdominals": "腹直肌",
    "ankle stabilizers": "踝关节稳定肌",
    "ankles": "踝关节",
    "biceps": "肱二头肌",
    "calves": "小腿三头肌",
    "chest": "胸肌",
    "core": "核心肌群",
    "deltoids": "三角肌",
    "forearms": "前臂肌群",
    "glutes": "臀大肌",
    "hamstrings": "腘绳肌",
    "hands": "手部",
    "hip flexors": "髋屈肌",
    "latissimus dorsi": "背阔肌",
    "lats": "背阔肌",
    "lower back": "下背部",
    "obliques": "腹斜肌",
    "quadriceps": "股四头肌",
    "rhomboids": "菱形肌",
    "rotator cuff": "肩袖肌群",
    "shoulders": "肩部",
    "soleus": "比目鱼肌",
    "trapezius": "斜方肌",
    "traps": "斜方肌",
    "triceps": "肱三头肌",
    "upper back": "上背部",
    "wrist extensors": "腕伸肌",
    "wrist flexors": "腕屈肌",
    "wrists": "腕部",
}

TARGET_ZH = {
    "abductors": "外展肌",
    "abs": "腹肌",
    "adductors": "内收肌",
    "biceps": "肱二头肌",
    "calves": "小腿三头肌",
    "cardiovascular system": "心血管系统",
    "delts": "三角肌",
    "forearms": "前臂肌群",
    "glutes": "臀大肌",
    "hamstrings": "腘绳肌",
    "lats": "背阔肌",
    "levator scapulae": "肩胛提肌",
    "pectorals": "胸肌",
    "quads": "股四头肌",
    "serratus anterior": "前锯肌",
    "spine": "脊柱",
    "traps": "斜方肌",
    "triceps": "肱三头肌",
    "upper back": "上背部",
}

SECONDARY_MUSCLES_ZH = {
    "abdominals": "腹直肌",
    "ankle stabilizers": "踝关节稳定肌",
    "ankles": "踝关节",
    "back": "背部",
    "biceps": "肱二头肌",
    "brachialis": "肱肌",
    "calves": "小腿三头肌",
    "chest": "胸肌",
    "core": "核心肌群",
    "deltoids": "三角肌",
    "feet": "足部",
    "forearms": "前臂肌群",
    "glutes": "臀大肌",
    "grip muscles": "握力肌群",
    "groin": "腹股沟",
    "hamstrings": "腘绳肌",
    "hands": "手部",
    "hip flexors": "髋屈肌",
    "inner thighs": "大腿内侧",
    "latissimus dorsi": "背阔肌",
    "lats": "背阔肌",
    "lower abs": "下腹部",
    "lower back": "下背部",
    "obliques": "腹斜肌",
    "quadriceps": "股四头肌",
    "rear deltoids": "后三角肌",
    "rhomboids": "菱形肌",
    "rotator cuff": "肩袖肌群",
    "shins": "胫骨前肌",
    "shoulders": "肩部",
    "soleus": "比目鱼肌",
    "sternocleidomastoid": "胸锁乳突肌",
    "trapezius": "斜方肌",
    "traps": "斜方肌",
    "triceps": "肱三头肌",
    "upper back": "上背部",
    "upper chest": "上胸部",
    "wrist extensors": "腕伸肌",
    "wrist flexors": "腕屈肌",
    "wrists": "腕部",
}


def translate_names_batch(names: list[str]) -> dict[str, str]:
    """使用 Google Translate 批量翻译动作名称"""
    from pygtrans import Translate

    translator = Translate()
    result = {}
    batch_size = 50
    total = len(names)

    for i in range(0, total, batch_size):
        batch = names[i : i + batch_size]
        print(f"  翻译动作名称: {min(i + batch_size, total)}/{total}")

        try:
            translations = translator.translate(batch, source="en", target="zh-CN")
            for name, trans in zip(batch, translations):
                result[name] = trans.translatedText if trans else name
        except Exception as e:
            print(f"    翻译出错: {e}，使用原文")
            for name in batch:
                result[name] = name

        # 避免请求过快
        if i + batch_size < total:
            time.sleep(0.5)

    return result


def optimize_exercise(item: dict, name_zh_map: dict[str, str]) -> dict:
    """优化单个动作数据"""
    name_en = item["name"]
    category_en = item["category"]
    body_part_en = item["body_part"]
    equipment_en = item["equipment"]
    muscle_group_en = item["muscle_group"]
    target_en = item["target"]

    # 获取中文翻译
    name_zh = name_zh_map.get(name_en, name_en)
    category_zh = CATEGORY_ZH.get(category_en, category_en)
    body_part_zh = BODY_PART_ZH.get(body_part_en, body_part_en)
    equipment_zh = EQUIPMENT_ZH.get(equipment_en, equipment_en)
    muscle_group_zh = MUSCLE_GROUP_ZH.get(muscle_group_en, muscle_group_en)
    target_zh = TARGET_ZH.get(target_en, target_en)

    # 处理 instructions - 只保留 en 和 zh
    instructions_en = item.get("instructions", {}).get("en", "")
    instructions_zh = item.get("instructions", {}).get("zh", "")

    # 处理 instruction_steps - 只保留 en 和 zh
    instruction_steps_en = item.get("instruction_steps", {}).get("en", [])
    instruction_steps_zh = item.get("instruction_steps", {}).get("zh", [])

    # 处理 secondary_muscles
    secondary_en = item.get("secondary_muscles", [])
    secondary_zh = [SECONDARY_MUSCLES_ZH.get(m, m) for m in secondary_en]

    return {
        "id": item["id"],
        "name": {"en": name_en, "zh": name_zh},
        "category": {"en": category_en, "zh": category_zh},
        "body_part": {"en": body_part_en, "zh": body_part_zh},
        "equipment": {"en": equipment_en, "zh": equipment_zh},
        "instructions": {"en": instructions_en, "zh": instructions_zh},
        "instruction_steps": {"en": instruction_steps_en, "zh": instruction_steps_zh},
        "muscle_group": {"en": muscle_group_en, "zh": muscle_group_zh},
        "secondary_muscles": {"en": secondary_en, "zh": secondary_zh},
        "target": {"en": target_en, "zh": target_zh},
        "image": item.get("image", ""),
        "gif_url": item.get("gif_url", ""),
        "media_id": item.get("media_id", ""),
        "created_at": item.get("created_at", ""),
        "attribution": item.get("attribution", ""),
    }


def main():
    base_dir = Path(__file__).parent.parent
    input_file = base_dir / "rogers" / "seeds" / "exercises_dataset.json"
    output_file = base_dir / "rogers" / "seeds" / "exercises_dataset_opt.json"

    print("=" * 50)
    print("优化动作数据集")
    print("=" * 50)

    # 读取源数据
    print(f"\n[1/4] 读取源数据: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"  共 {len(data)} 条动作数据")

    # 收集所有唯一的动作名称
    print("\n[2/4] 收集动作名称...")
    unique_names = list(set(item["name"] for item in data))
    print(f"  共 {len(unique_names)} 个唯一动作名称")

    # 翻译动作名称
    print("\n[3/4] 翻译动作名称...")
    name_zh_map = translate_names_batch(unique_names)
    print(f"  翻译完成: {len(name_zh_map)} 个")

    # 优化数据
    print("\n[4/4] 优化数据结构...")
    optimized = [optimize_exercise(item, name_zh_map) for item in data]

    # 写入输出文件
    print(f"\n写入输出文件: {output_file}")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(optimized, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 50}")
    print(f"完成! 共优化 {len(optimized)} 条动作数据")
    print(f"输出文件: {output_file}")


if __name__ == "__main__":
    main()