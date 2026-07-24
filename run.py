"""
FitCream 后端启动脚本

Windows 上 psycopg (langgraph-checkpoint-postgres) 需要 SelectorEventLoop，
必须在 uvicorn 创建事件循环之前设置策略。

用法:
    uv run python run.py
    uv run python run.py --reload
    uv run python run.py --port 8000
"""
import asyncio
import sys
from pathlib import Path

# 将 rogers 目录加入 sys.path（使 app 包可导入）
rogers_dir = str(Path(__file__).resolve().parent / "rogers")
if rogers_dir not in sys.path:
    sys.path.insert(0, rogers_dir)

# Windows: 设置 SelectorEventLoop（必须在 uvicorn 之前）
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn


def main():
    reload = "--reload" in sys.argv
    port = 8000
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    config = uvicorn.Config(
        "app.main:app",
        host="127.0.0.1",
        port=port,
        reload=reload,
        loop="none",  # 我们自己管理事件循环
    )
    server = uvicorn.Server(config)

    # 显式创建 SelectorEventLoop 并运行
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


if __name__ == "__main__":
    main()