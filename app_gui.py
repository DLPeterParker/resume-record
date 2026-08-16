# -*- coding: utf-8 -*-
"""简历投递记录自动归档助手 —— 图形界面版。

入口：python app_gui.py
"""
import os
import sys

# PyInstaller 无控制台打包时，stdout/stderr 为 None，先兜底，避免 print 崩溃
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import logging
import queue
import threading
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk

import config
import excel_handler
from extractor import init_ocr, recognize_screenshot, parse_ocr_text
from utils import find_image_files, save_screenshot

# 抑制 PaddleOCR 冗长的 DEBUG 日志
logging.getLogger("ppocr").setLevel(logging.ERROR)

# 需要用户核对/编辑的字段（与 config.COLUMNS 对齐，自动生成的 jd/进度记录 不在此列）
EDITABLE_FIELDS = [
    "公司",
    "base",
    "行业",
    "平台",
    "批次",
    "投递志愿与顺序",
    "当前进度",
    "对应日期",
    "投递链接",
    "备注",
]


class _QueueStream:
    """把 print/stdout 输出重定向到队列，供 GUI 日志区显示。"""

    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s and s.strip():
            self.q.put(s)

    def flush(self):
        pass


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("简历投递记录自动归档助手")
        self.root.geometry("1080x760")
        self.root.minsize(900, 640)

        self.log_queue = queue.Queue()
        self.result_queue = queue.Queue()

        self.image_files = []
        self.index = -1
        self.current_path = None
        self.busy = False
        self._token = 0
        self._photo = None

        # Excel 被占用时改为弹窗提示（而非阻塞在 input()）
        excel_handler.set_retry_prompt(self._excel_retry_prompt)

        self._build_ui()
        self._redirect_stdout()

        if config.OPENAI_API_KEY:
            self._append_log("已检测到 API Key，大模型提取可用。")
        else:
            self._append_log("[提示] 未检测到 API Key，大模型不可用，请手动填写字段。")
        self._append_log("就绪。请点击「选择截图」或「选择文件夹」开始。")
        self.root.after(100, self._poll)

    # ---------- UI 构建 ----------

    def _build_ui(self):
        toolbar = ttk.Frame(self.root, padding=8)
        toolbar.pack(side="top", fill="x")
        ttk.Button(toolbar, text="选择截图", command=self.select_file).pack(
            side="left", padx=(0, 6)
        )
        ttk.Button(toolbar, text="选择文件夹(批量)", command=self.select_folder).pack(
            side="left", padx=(0, 6)
        )
        self.path_var = tk.StringVar(value="未选择文件")
        ttk.Label(toolbar, textvariable=self.path_var, foreground="#555").pack(
            side="left", padx=6
        )

        main = ttk.Frame(self.root, padding=8)
        main.pack(side="top", fill="both", expand=True)

        left = ttk.LabelFrame(main, text="截图预览", padding=6)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        self.image_label = tk.Label(left, text="(暂无图片)", bg="#eeeeee")
        self.image_label.pack(fill="both", expand=True)

        right = ttk.LabelFrame(main, text="提取字段（可手动修改）", padding=6)
        right.pack(side="right", fill="both", expand=True)
        self.field_vars = {}
        for i, field in enumerate(EDITABLE_FIELDS):
            ttk.Label(right, text=field).grid(
                row=i, column=0, sticky="e", padx=(0, 6), pady=3
            )
            var = tk.StringVar()
            if field in config.FIELD_OPTIONS:
                combo = ttk.Combobox(
                    right,
                    textvariable=var,
                    values=config.FIELD_OPTIONS[field],
                    width=34,
                    state="normal",
                )
                combo.grid(row=i, column=1, sticky="we", pady=3)
            else:
                ttk.Entry(right, textvariable=var, width=36).grid(
                    row=i, column=1, sticky="we", pady=3
                )
            self.field_vars[field] = var
        right.columnconfigure(1, weight=1)

        log_frame = ttk.LabelFrame(self.root, text="日志", padding=6)
        log_frame.pack(side="bottom", fill="x")
        self.log_text = tk.Text(log_frame, height=9, state="disabled", wrap="word")
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        controls = ttk.Frame(self.root, padding=8)
        controls.pack(side="bottom", fill="x")
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(controls, textvariable=self.status_var, foreground="#0066cc").pack(
            side="left", padx=6
        )
        ttk.Button(controls, text="上一张", command=lambda: self.nav(-1)).pack(
            side="right", padx=4
        )
        ttk.Button(controls, text="下一张", command=lambda: self.nav(1)).pack(
            side="right", padx=4
        )
        ttk.Button(controls, text="跳过", command=self.skip).pack(side="right", padx=4)
        ttk.Button(controls, text="确认写入", command=self.confirm).pack(
            side="right", padx=4
        )
        ttk.Button(controls, text="重新识别", command=self.reprocess).pack(
            side="right", padx=4
        )

    # ---------- 文件选择 ----------

    def select_file(self):
        path = filedialog.askopenfilename(
            title="选择截图",
            filetypes=[("图片", "*.png *.jpg *.jpeg *.bmp *.webp"), ("所有文件", "*.*")],
        )
        if path:
            self.image_files = [Path(path)]
            self.index = 0
            self._load_current()

    def select_folder(self):
        path = filedialog.askdirectory(title="选择截图文件夹")
        if not path:
            return
        files = find_image_files(path)
        if not files:
            messagebox.showinfo("提示", "该文件夹下没有找到图片文件。")
            return
        self.image_files = files
        self.index = 0
        self._load_current()

    # ---------- 处理流程 ----------

    def _load_current(self):
        if self.index < 0 or self.index >= len(self.image_files):
            return
        self.current_path = self.image_files[self.index]
        self.path_var.set(
            f"[{self.index + 1}/{len(self.image_files)}] {self.current_path.name}"
        )
        self._show_image(self.current_path)
        self._clear_fields()
        self._start_processing()

    def _start_processing(self):
        if self.busy:
            return
        self.busy = True
        self._token += 1
        token = self._token
        self.status_var.set("识别中…")
        self._append_log(f"\n[OCR] 正在识别: {self.current_path.name}")
        path = self.current_path
        threading.Thread(target=self._worker, args=(path, token), daemon=True).start()

    def _worker(self, path, token):
        try:
            ocr = init_ocr()
            ocr_text, raw = recognize_screenshot(ocr, path)
            data = parse_ocr_text(ocr_text, raw)
            self.result_queue.put(("result", token, path, data))
        except Exception as e:
            self.result_queue.put(("error", token, path, str(e)))

    def _poll(self):
        try:
            while True:
                self._append_log(self.log_queue.get_nowait())
        except queue.Empty:
            pass

        try:
            msg = self.result_queue.get_nowait()
        except queue.Empty:
            msg = None
        if msg is not None:
            self._handle_result(msg)

        self.root.after(100, self._poll)

    def _handle_result(self, msg):
        kind, token, path = msg[0], msg[1], msg[2]
        if token != self._token:
            return  # 已经切到别的图了，丢弃过期结果
        self.busy = False
        if kind == "result":
            data = msg[3]
            self._set_fields(data)
            if data.get("公司"):
                self.status_var.set("识别完成，请核对字段后点击「确认写入」")
            else:
                self.status_var.set("未识别到公司，请手动补全后点击「确认写入」")
        else:
            self.status_var.set("识别出错")
            messagebox.showerror("识别失败", f"识别出错：\n{msg[3]}")

    # ---------- 写入 / 跳过 ----------

    def confirm(self):
        if self.current_path is None or self.busy:
            return
        data = self._get_fields()
        if not data.get("公司"):
            if not messagebox.askyesno("公司为空", "未填写公司名称，仍要写入吗？"):
                return
        try:
            if excel_handler.is_duplicate_record(data):
                self._append_log(
                    f"[SKIP] 查重命中：{data.get('公司')} - {data.get('base')} - {data.get('投递志愿与顺序')}"
                )
                data["jd"] = save_screenshot(self.current_path, data)
                messagebox.showinfo("查重", "该记录已存在，截图已归档，跳过写入。")
                self._advance(1)
                return

            data["jd"] = save_screenshot(self.current_path, data)
            excel_handler.update_excel(data)
            excel_handler.update_progress_sheet(data, is_new=True)
            self._append_log(
                f"[OK] 已写入: {data.get('公司')} - {data.get('投递志愿与顺序')}"
            )
            self.status_var.set("已写入")
            self._advance(1)
        except Exception as e:
            messagebox.showerror("写入失败", f"写入出错：\n{e}")

    def skip(self):
        if self.current_path is None or self.busy:
            return
        self._advance(1)

    def nav(self, delta):
        if self.current_path is None:
            return
        self._advance(delta)

    def reprocess(self):
        if self.current_path is None or self.busy:
            return
        self._start_processing()

    def _advance(self, delta):
        new_idx = self.index + delta
        if 0 <= new_idx < len(self.image_files):
            self.index = new_idx
            self._load_current()
        elif delta > 0 and self.index == len(self.image_files) - 1:
            self.status_var.set("已处理完当前批次")
            messagebox.showinfo("完成", "当前批次已处理完毕。")
        else:
            self.status_var.set("已到边界")

    # ---------- 字段与图片 ----------

    def _set_fields(self, data):
        for field in EDITABLE_FIELDS:
            self.field_vars[field].set(str(data.get(field, "") or ""))

    def _get_fields(self):
        data = {}
        for field in EDITABLE_FIELDS:
            data[field] = self.field_vars[field].get().strip()
        return data

    def _clear_fields(self):
        for field in EDITABLE_FIELDS:
            self.field_vars[field].set("")
        self.field_vars["当前进度"].set("投递")
        self.field_vars["对应日期"].set(datetime.now().strftime("%Y-%m-%d"))

    def _show_image(self, path):
        try:
            img = Image.open(path)
            max_w, max_h = 480, 500
            ratio = min(max_w / img.width, max_h / img.height, 1.0)
            if ratio < 1:
                img = img.resize(
                    (int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS
                )
            self._photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self._photo, text="")
        except Exception:
            self._photo = None
            self.image_label.config(image="", text="[无法预览图片]")

    # ---------- 日志与提示 ----------

    def _append_log(self, text):
        self.log_text.config(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _redirect_stdout(self):
        stream = _QueueStream(self.log_queue)
        sys.stdout = stream
        sys.stderr = stream

    def _excel_retry_prompt(self, message):
        messagebox.showwarning(
            "文件被占用", "Excel 文件正被占用，请关闭 WPS/Office 后点击确定重试。"
        )
        return ""


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
