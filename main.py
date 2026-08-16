# main.py 解析命令行参数并调度上方四个模块工作
import sys

from excel_handler import is_duplicate_record, update_excel, update_progress_sheet
from extractor import init_ocr, parse_ocr_text, recognize_screenshot
from utils import (
    find_image_files,
    interactive_input_fields,
    print_summary,
    save_screenshot,
)


def main():
    auto_mode, dry_run, batch_mode, image_path, batch_dir = (
        False,
        False,
        False,
        None,
        None,
    )

    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ("--auto", "-a"):
            auto_mode = True
        elif arg in ("--dry-run", "-d"):
            dry_run = True
        elif arg in ("--batch", "-b"):
            batch_mode = True
            if i + 1 < len(sys.argv) and not sys.argv[i + 1].startswith("-"):
                batch_dir = sys.argv[i + 1]
                i += 1
        elif not arg.startswith("-"):
            image_path = arg
        i += 1

    ocr = init_ocr()

    # 批量处理分支
    if batch_mode:
        image_files = find_image_files(batch_dir)
        if not image_files:
            return

        print(f"\n{'=' * 60}\n[BATCH] 批量处理 {len(image_files)} 张图片\n{'=' * 60}")
        success_count, skip_count, skip_all = 0, 0, False

        for idx, img_path in enumerate(image_files, 1):
            if skip_all:
                skip_count += 1
                continue

            print(
                f"\n{'─' * 60}\n[{idx}/{len(image_files)}] {img_path.name}\n{'─' * 60}"
            )
            ocr_text, raw_result = recognize_screenshot(ocr, img_path)
            if not ocr_text:
                skip_count += 1
                continue

            data = parse_ocr_text(ocr_text, raw_result)

            print("\n  解析结果:")
            for key in ["公司", "base", "行业", "投递志愿与顺序", "当前进度", "备注"]:
                if data.get(key):
                    print(f"    {key}: {data[key]}")

            if not dry_run:
                if not data.get("公司"):
                    print("\n[WARN] 未识别到公司名，自动切入手动补全模式！")
                    choice = "m"
                else:
                    choice = (
                        input("\n  [Y]确认 [m]手动修改 [n]跳过 [s]跳过剩余 [q]退出: ")
                        .strip()
                        .lower()
                    )

                if choice == "q":
                    break
                elif choice == "s":
                    skip_all = True
                    skip_count += 1
                    continue
                elif choice == "n":
                    skip_count += 1
                    continue
                elif choice == "m":
                    print("\n[INFO] 请补充缺失字段（直接回车保留原值）：")
                    for key in [
                        "公司",
                        "base",
                        "行业",
                        "投递志愿与顺序",
                        "当前进度",
                        "备注",
                    ]:
                        current_val = data.get(key, "")
                        new_val = input(f"  {key} [{current_val}]: ").strip()
                        if new_val:
                            data[key] = new_val

                if is_duplicate_record(data):
                    print(
                        f"\n[SKIP] 查重命中：记录已存在 ({data.get('公司')} - {data.get('base')} - {data.get('投递志愿与顺序')})"
                    )
                    save_screenshot(img_path, data)  # 依然移动图片，保持输入文件夹干净
                    print("  => 截图已归档，跳过 Excel 写入。")
                    skip_count += 1
                    continue

                data["jd"] = save_screenshot(img_path, data)
                update_excel(data)
                update_progress_sheet(data, is_new=True)
                success_count += 1
                print(
                    f"  [OK] 已写入: {data.get('公司', '?')} - {data.get('投递志愿与顺序', '?')}"
                )
            else:
                skip_count += 1

        print(
            f"\n{'=' * 60}\n[BATCH] 批量处理完成 (成功: {success_count} 跳过: {skip_count})\n{'=' * 60}"
        )
        return

    # 单图处理分支
    ocr_text, raw_result = recognize_screenshot(ocr, image_path)
    if auto_mode:
        data = parse_ocr_text(ocr_text, raw_result)
        print_summary(data)
        if not data.get("公司"):
            print("\n[WARN] 公司未识别到，切换到交互模式...")
            data = interactive_input_fields(ocr_text)
        elif not dry_run:
            confirm = (
                input("\n[?] 确认信息？(Y=确认 / n=取消 / m=修改): ").strip().lower()
            )
            if confirm == "n":
                sys.exit(0)
            elif confirm == "m":
                data = interactive_input_fields(ocr_text)
    else:
        data = interactive_input_fields(ocr_text)

    if not dry_run:
        data["jd"] = save_screenshot(image_path, data)
        update_excel(data)
        update_progress_sheet(data, is_new=True)
        print_summary(data)


if __name__ == "__main__":
    main()
