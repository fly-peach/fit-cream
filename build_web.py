"""构建前端并复制到后端静态目录

用法（项目根目录下）:
    python build_web.py

流程:
    [0/3] 检查/安装 node_modules
    [1/3] npm run build（Vite 构建）
    [2/3] 复制 frontend/dist → rogers/static
    [3/3] 完成，启动后端即可访问前端页面
"""
import shutil
import subprocess
import sys
from pathlib import Path


def check_deps_installed(frontend_dir: Path) -> bool:
    node_modules = frontend_dir / "node_modules"
    if node_modules.exists():
        return True
    print("\n[0/3] 安装依赖...")
    try:
        subprocess.run(["npm", "install"], cwd=frontend_dir, check=True, shell=True)
        print("  ✓ 依赖安装完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ✗ 依赖安装失败: {e}")
        return False
    except FileNotFoundError:
        print("  ✗ 未找到 npm，请先安装 Node.js")
        return False


def main():
    project_root = Path(__file__).absolute().parent
    frontend_dir = project_root / "frontend"
    static_dir = project_root / "rogers" / "static"

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 50)
    print("  FitCream - 构建前端并挂载到后端")
    print("=" * 50)

    if not frontend_dir.exists():
        print(f"错误: 前端目录不存在: {frontend_dir}")
        sys.exit(1)

    if not check_deps_installed(frontend_dir):
        sys.exit(1)

    print("\n[1/3] 构建前端项目...")
    try:
        subprocess.run(["npm", "run", "build"], cwd=frontend_dir, check=True, shell=True)
        print("  ✓ 构建完成")
    except subprocess.CalledProcessError as e:
        print(f"  ✗ 构建失败: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("  ✗ 未找到 npm，请先安装 Node.js")
        sys.exit(1)

    dist_dir = frontend_dir / "dist"
    if not dist_dir.exists():
        print(f"错误: dist 目录不存在: {dist_dir}")
        sys.exit(1)

    print("\n[2/3] 复制构建产物到 rogers/static/ ...")
    if static_dir.exists():
        shutil.rmtree(static_dir)
        print(f"  - 清理旧目录: {static_dir.name}")
    shutil.copytree(dist_dir, static_dir)
    print(f"  ✓ 已复制到: {static_dir}")

    print("\n" + "=" * 50)
    print("  ✅ 构建完成！启动后端:")
    print("     uv run python run.py --reload")
    print("  访问: http://localhost:8000")
    print("=" * 50)


if __name__ == "__main__":
    main()
