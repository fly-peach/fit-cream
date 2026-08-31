"""
身材原型图生成脚本
==================
读取 rogers/seeds/goal_knowledge.json（v2 扁平行），按 key/name/tagline/description/
gender + 体脂区间拼出提示词模板，调用阿里云百炼 CLI（bl image generate，token-plan
profile）为每个 (key, gender) 生成一张身材展示图，并统一压缩为 720px 宽的 WebP
（原图 1728px PNG 约 5MB/张，压缩后约 40KB/张，供前端卡片渲染）。

用法:
  python scripts/generate_goal_images.py            # 只补缺失的图
  python scripts/generate_goal_images.py --force    # 全部重新生成
  python scripts/generate_goal_images.py --only lean_aesthetic_male v_taper_female
  python scripts/generate_goal_images.py --compress # 仅压缩存量 PNG 为 WebP（不调模型）

输出:
  rogers/static/goals/<key>_<gender>.webp
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = Path(__file__).resolve().parent.parent
SEED_PATH = BASE_DIR / "rogers" / "seeds" / "goal_knowledge.json"
OUT_DIR = BASE_DIR / "rogers" / "static" / "goals"

# 卡片展示宽约 350px，2x DPR 取 720；WebP 质量 82 视觉无损
TARGET_WIDTH = 720
WEBP_QUALITY = 82

# 原型视觉关键词（由 name/tagline/description 提炼，与体脂区间共同决定画面）
ARCHETYPE_VISUAL = {
    "lean_aesthetic": (
        "lean light-weight build with subtle thin muscle definition, visible "
        "abdominal outline, slim waist, healthy toned look, not bulky"
    ),
    "v_taper": (
        "very broad shoulders and wide lats tapering to a narrow waist, "
        "pronounced V-taper silhouette, lean upper body"
    ),
    "strength_power": (
        "strong thick powerful build, dense muscle, barrel chest, thick waist, "
        "solid frame, moderate body fat, powerlifter physique"
    ),
    "muscular_mass": (
        "highly muscular bulky physique, large muscle mass, thick arms chest "
        "and legs, bodybuilder off-season look"
    ),
    "healthy_balanced": (
        "healthy balanced athletic physique, moderate muscle, normal body fat, "
        "proportionate natural look"
    ),
    "toned_curves": (
        "toned hourglass figure with shapely firm glutes and legs, slim waist, "
        "light upper-body muscle, feminine athletic curves"
    ),
}

NEGATIVE_PROMPT = (
    "cartoon, illustration, 3d render, watermark, text, logo, deformed, "
    "extra limbs, mutated hands, oiled skin, exaggerated muscles, "
    "frontal nudity, nude"
)


def _body_fat(arch: dict):
    for m in arch.get("target_metrics") or []:
        if m.get("metric") == "body_fat_pct":
            return m.get("min"), m.get("max")
    return None, None


def build_prompt(arch: dict) -> str:
    key = arch["key"]
    gender = arch["gender"]
    visual = ARCHETYPE_VISUAL.get(key, arch.get("tagline", ""))
    bmin, bmax = _body_fat(arch)
    fat_part = ""
    if bmin is not None and bmax is not None:
        fat_part = f", body fat around {bmin}-{bmax} percent"
    elif bmax is not None:
        fat_part = f", body fat around {bmax} percent"

    if gender == "female":
        subject = (
            "Professional fitness studio photography of a young athletic woman "
            "wearing a black sports bra and shorts, full body standing relaxed pose "
            "facing camera"
        )
    else:
        subject = (
            "Professional fitness studio photography of a shirtless young athletic man "
            "wearing dark grey athletic shorts and sneakers, full body standing relaxed "
            "pose facing camera"
        )
    return (
        f"{subject}, {visual}{fat_part}, "
        "clean light grey seamless studio background, soft even lighting, "
        "realistic photo, high detail"
    )


def bl_bin() -> str:
    for name in ("bl.cmd", "bl"):
        p = shutil.which(name)
        if p:
            return p
    raise SystemExit("未找到 bl CLI，请先安装 bailian-cli 并 bl auth login --config token-plan")


def compress_to_webp(src: Path, dst: Path) -> None:
    """缩放到 TARGET_WIDTH 并转 WebP（等比，LANCZOS）。"""
    with Image.open(src) as im:
        im = im.convert("RGB")
        w, h = im.size
        if w > TARGET_WIDTH:
            im = im.resize((TARGET_WIDTH, round(h * TARGET_WIDTH / w)), Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, "WEBP", quality=WEBP_QUALITY, method=6)


def generate(arch: dict, out_path: Path, bl: str) -> bool:
    prompt = build_prompt(arch)
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [
            bl, "image", "generate",
            "--config", "token-plan",
            "--prompt", prompt,
            "--size", "3:4",
            "--watermark", "false",
            "--negative-prompt", NEGATIVE_PROMPT,
            "--out-dir", tmp,
            "--out-prefix", f"{arch['key']}_{arch['gender']}",
            "--timeout", "590",
        ]
        print(f"  prompt: {prompt[:110]}...")
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode != 0:
            print(f"  失败: {res.stdout}\n{res.stderr}")
            return False
        produced = sorted(Path(tmp).glob("*.png"))
        if not produced:
            print(f"  失败: 未产出图片\n{res.stdout}")
            return False
        compress_to_webp(produced[0], out_path)
    print(f"  -> {out_path.relative_to(BASE_DIR)} ({out_path.stat().st_size // 1024}KB)")
    return True


def compress_existing(data: dict) -> None:
    """存量 PNG -> WebP 并删除原图（一次性迁移用）。"""
    for arch in data["archetypes"]:
        tag = f"{arch['key']}_{arch['gender']}"
        png = OUT_DIR / f"{tag}.png"
        webp = OUT_DIR / f"{tag}.webp"
        if not png.exists():
            continue
        before = png.stat().st_size
        compress_to_webp(png, webp)
        png.unlink()
        print(f"[webp] {tag}: {before // 1024}KB -> {webp.stat().st_size // 1024}KB")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="已存在的图也重新生成")
    parser.add_argument("--only", nargs="*", help="仅生成指定 <key>_<gender>")
    parser.add_argument("--compress", action="store_true", help="仅把存量 PNG 压缩为 WebP")
    args = parser.parse_args()

    data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    if args.compress:
        compress_existing(data)
        return

    bl = bl_bin()
    ok = fail = skip = 0
    for arch in data["archetypes"]:
        tag = f"{arch['key']}_{arch['gender']}"
        if args.only and tag not in args.only:
            continue
        out_path = OUT_DIR / f"{tag}.webp"
        if out_path.exists() and not args.force:
            print(f"[skip] {tag}（已存在，--force 重生成）")
            skip += 1
            continue
        print(f"[gen ] {tag}")
        if generate(arch, out_path, bl):
            ok += 1
        else:
            fail += 1
    print(f"\n完成：成功 {ok}，跳过 {skip}，失败 {fail}")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
