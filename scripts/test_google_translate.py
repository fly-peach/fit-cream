"""
Google Translate 在线翻译测试脚本 (pygtrans)
=============================================
用法:
  python scripts/test_google_translate.py              # 完整测试
  python scripts/test_google_translate.py --help       # 帮助

依赖:
  pip install pygtrans

说明:
  - pygtrans 使用 Google Translate 免费 API，无需 API Key
  - 需要能访问 translate.googleapis.com
"""

import sys
import time
import argparse
from pygtrans import Translate

# 修复 Windows 终端编码问题
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def create_translator() -> Translate:
    """创建翻译器实例"""
    return Translate()


def translate_text(translator: Translate, text: str, src: str, dest: str) -> str | None:
    """执行单条翻译"""
    try:
        result = translator.translate(text, source=src, target=dest)
        return result.translatedText if result else None
    except Exception as e:
        print(f"    翻译出错: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Google Translate 测试脚本 (pygtrans)")
    args = parser.parse_args()

    print("=" * 50)
    print("Google Translate 在线翻译测试 (pygtrans)")
    print("=" * 50)

    print("\n[初始化] 创建翻译器...")
    translator = create_translator()

    # 翻译测试
    print("\n[翻译测试]")

    test_cases = [
        ("en", "zh-CN", "Hello World!"),
        ("en", "zh-CN", "Machine translation is fascinating."),
        ("en", "zh-CN", "The weather is beautiful today."),
        ("zh-CN", "en", "你好，世界！"),
        ("zh-CN", "en", "机器学习非常有趣。"),
        ("zh-CN", "en", "今天天气真好。"),
    ]

    success_count = 0
    for src, dest, source in test_cases:
        result = translate_text(translator, source, src, dest)
        if result:
            print(f"  [OK] [{src}->{dest}] {source}")
            print(f"         -> {result}")
            success_count += 1
        else:
            print(f"  [FAIL] [{src}->{dest}] {source}")

    # 性能测试
    if success_count > 0:
        print("\n[性能测试]")
        batch = [
            "I love programming.",
            "Python is a great language.",
            "Artificial intelligence is changing the world.",
        ]

        start = time.time()
        results = []
        for text in batch:
            result = translate_text(translator, text, "en", "zh-CN")
            results.append(result)
        elapsed = time.time() - start

        print(f"  英→中: {len(batch)} 条 / {elapsed:.2f}s")
        for src_text, dst_text in zip(batch, results):
            print(f"    {src_text} → {dst_text}")

    print(f"\n{'=' * 50}")
    print(f"测试完成! 成功翻译 {success_count} 条")


if __name__ == "__main__":
    main()