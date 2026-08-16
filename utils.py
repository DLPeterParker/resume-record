# utils.py 文件搜索、图片移动存档、控制台打印输出。
import shutil
from datetime import datetime
from pathlib import Path

import config

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


# 把识别完的截图，从原始位置"搬家"到存档目录，并自动重命名
def save_screenshot(image_path, data):
    config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    company = data.get("公司", "未知公司").strip()
    base = data.get("base", "未知地点").strip()
    original_name = Path(image_path).name

    def _sanitize_filename(text):
        """替换文件名中的非法字符"""
        invalid_chars = r'\/:*?"<>|'
        for ch in invalid_chars:
            text = text.replace(ch, "_")
        return text

    name_parts = (
        [_sanitize_filename(company)] if company and company != "未知公司" else []
    )
    if name_parts:
        if base and base != "未知地点":
            name_parts.append(_sanitize_filename(base))

        new_name = "_".join(name_parts) + Path(image_path).suffix
    else:
        new_name = original_name

    dest_path = config.OUTPUT_DIR / new_name

    try:
        if Path(image_path).resolve() != dest_path.resolve():
            shutil.move(image_path, dest_path)
            print(f"[SAVE] 截图已存档: {dest_path}")
        else:
            print("[SAVE] 原文件已在存档目录中，无需重复复制。")
    except shutil.SameFileError:
        print("[SAVE] 原文件已在存档目录中，无需重复复制。")

    return new_name


def find_image_files(directory):
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        return []
    image_files = [
        f
        for f in dir_path.rglob("*")
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
    image_files.sort(key=lambda p: p.name)
    return image_files


def interactive_input_fields(ocr_text=""):
    if ocr_text:
        print(
            "\n"
            + "=" * 60
            + "\n[OCR] 识别出的文字：\n"
            + "=" * 60
            + f"\n{ocr_text[:500]}\n"
            + "=" * 60
        )

    data = {}
    prompts = [
        ("公司", "公司名称"),
        ("base", "城市"),
        ("行业", "行业"),
        ("平台", "招聘平台"),
        ("批次", "批次"),
        ("投递志愿与顺序", "志愿与顺序"),
        ("当前进度", "当前进度", "投递"),
        ("对应日期", "日期", datetime.now().strftime("%Y-%m-%d")),
        ("投递链接", "投递链接"),
        ("备注", "备注"),
    ]
    for p in prompts:
        field, hint = p[0], p[1]
        default = p[2] if len(p) > 2 else ""

        if field in config.FIELD_OPTIONS:
            options = config.FIELD_OPTIONS[field]
            print(f"[{hint}] 可选:", end="")
            for i, opt in enumerate(options, 1):
                print(f" {i}.{opt}", end="")
            prompt_text = " (输入编号或自定义): "
            value = input(prompt_text).strip()
            if value.isdigit():
                idx = int(value) - 1
                if 0 <= idx < len(options):
                    value = options[idx]
            data[field] = value if value else default
        else:
            prompt_text = f"[{hint}] (默认: {default}): " if default else f"[{hint}]: "
            value = input(prompt_text).strip()
            data[field] = value if value else default

    return data


def print_summary(data):
    print("\n" + "=" * 60 + "\n[SUMMARY] 新记录摘要：\n" + "=" * 60)
    for key, value in data.items():
        if value:
            print(f"  {key}: {value}")
    print("=" * 60)
