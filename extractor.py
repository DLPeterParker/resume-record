# extractor.py
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from openai import OpenAI
from paddleocr import PaddleOCR

import config

ocr_global = None


def _model_dir(rel_path):
    """打包后从内置目录读取 OCR 模型，源码运行时返回 None（走默认下载路径）。"""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return str(base / "paddle_models" / rel_path)
    return None


def init_ocr():
    global ocr_global
    if ocr_global is None:
        print("[INIT] 正在初始化 OCR 引擎...")
        det_dir = _model_dir("det/ch_PP-OCRv4_det_infer")
        rec_dir = _model_dir("rec/ch_PP-OCRv4_rec_infer")
        if det_dir and rec_dir:
            ocr_global = PaddleOCR(
                text_det_box_thresh=0.3,
                det_model_dir=det_dir,
                rec_model_dir=rec_dir,
                use_angle_cls=False,
            )
        else:
            ocr_global = PaddleOCR(text_det_box_thresh=0.3)
        print("[OK] OCR 引擎初始化成功")
    return ocr_global


def recognize_screenshot(ocr, image_path):
    print(f"[OCR] 正在识别截图: {image_path}")
    result = ocr.ocr(str(image_path))
    all_text = []
    for page in result:
        if page is None:
            continue
        for line in page:
            text = line[1][0]
            if text.strip():
                all_text.append(text)
    return "\n".join(all_text), result


def call_llm_extract(ocr_text: str) -> dict:
    if not config.OPENAI_API_KEY:
        print("[WARN] API_KEY 未设置，LLM 提取已禁用")
        return {}

    client = OpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_BASE_URL)

    # 优化后的 System Prompt：严禁输出数组和字典
    system_prompt = """
你是一个专业的数据结构化提取助手。你的任务是从招聘界面/投递成功的 OCR 识别文本中提取求职记录信息。

【严格输出规范】
1. 必须且只能输出合法的 JSON 对象。
2. 绝对不能包含任何 markdown 代码块标识（如 ```json）或额外的解释文字。
3. JSON 中的所有 value 必须是纯字符串（String），绝对不能是数组（Array）或对象（Object）。如果有多个城市或岗位，请使用逗号拼接字符串（例如："武汉,北京"、"算法工程师,产品经理"）。

JSON 字段定义如下：
【简洁原则】
- 所有字段只提取最核心信息，不要冗余描述。
- 不同字段之间不要重复相同内容。
- 不要添加""或者{}等额外的标点符号。
- "公司": 公司简称（如：字节、腾讯、vivo，去掉"有限公司""科技"等后缀，只保留品牌名）。
- "base": 工作城市（如：北京、上海、远程，去除“工作地点：”等字样）。
- "行业": 所属行业（如：互联网、智能制造等，无法判断默认互联网）。
- "平台": 招聘渠道（如：BOSS直聘、官网，无法判断默认官网）。
- "批次": 招聘批次（如：秋招、提前批，无法判断默认秋招）。
- "投递志愿与顺序": 投递的岗位名称简称（多个岗位用逗号拼接，严禁使用JSON数组）。
- "备注": 仅记录其他字段未覆盖的关键信息（如：需笔试、有测评），不要重复已有字段的内容。

若某个字段在文本中完全无法找到或推理出，对应的值请设为空字符串 ""。
"""
    try:
        response = client.chat.completions.create(
            model=config.LLM_MODEL,
            temperature=0.1,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"请从以下OCR识别文本中提取招聘信息：\n\n{ocr_text}",
                },
            ],
        )
        content = response.choices[0].message.content or ""
        cleaned_content = re.sub(r"^```json\s*|\s*```$", "", content.strip())
        return json.loads(cleaned_content)
    except Exception as e:
        print(f"[WARN] LLM 提取失败: {e}")
        return {}


def parse_ocr_text(ocr_text, raw_result):
    data = {"当前进度": "投递", "对应日期": datetime.now().strftime("%Y-%m-%d")}
    llm_result = call_llm_extract(ocr_text)
    if llm_result:
        for key in ["公司", "base", "行业", "平台", "批次", "投递志愿与顺序", "备注"]:
            if key in llm_result and llm_result[key]:
                data[key] = str(llm_result[key])
    else:
        print("[WARN] LLM 提取失败，降级为交互式手动输入模式")
    return data
