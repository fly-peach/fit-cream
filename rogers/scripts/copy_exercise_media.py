"""复制 exercises-dataset 的图片/视频到后端静态目录。

source: E:\\agentme\\exercises-dataset\\{images,videos}
dest:   rogers/static/exercises/{images,videos}

媒体共 ~131MB（图片 8.5MB + 视频 122.8MB），已 gitignore（rogers/static/）。
已存在的文件跳过，幂等可重复运行。

运行：
    uv run python scripts/copy_exercise_media.py [DATASET_DIR]
"""
import shutil
import sys
from pathlib import Path

# 默认 dataset 仓库根（与 fit-cream 同级）
DEFAULT_DATASET = Path(r"E:\agentme\exercises-dataset")
STATIC_ROOT = Path(__file__).resolve().parent.parent / "static" / "exercises"

PAIRS = [("images", "images"), ("videos", "videos")]


def copy_dir(src: Path, dst: Path) -> tuple[int, int]:
    dst.mkdir(parents=True, exist_ok=True)
    copied = skipped = 0
    for f in src.iterdir():
        if not f.is_file():
            continue
        target = dst / f.name
        if target.exists() and target.stat().st_size == f.stat().st_size:
            skipped += 1
            continue
        shutil.copy2(f, target)
        copied += 1
    return copied, skipped


def main() -> None:
    dataset = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DATASET
    if not dataset.exists():
        print(f"dataset 目录不存在: {dataset}")
        sys.exit(1)

    total_copied = total_skipped = 0
    for sub, name in PAIRS:
        src = dataset / sub
        if not src.exists():
            print(f"跳过（不存在）: {src}")
            continue
        dst = STATIC_ROOT / name
        copied, skipped = copy_dir(src, dst)
        total_copied += copied
        total_skipped += skipped
        print(f"{name}: 新复制 {copied}，跳过 {skipped}")

    print(f"完成: 共复制 {total_copied}，跳过 {total_skipped} -> {STATIC_ROOT}")


if __name__ == "__main__":
    main()
