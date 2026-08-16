import os
from pathlib import Path

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 大模型配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv(
    "OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1"
)
LLM_MODEL = os.getenv("LLM_MODEL", "generalv3.5")  # 已适配讯飞星火默认名

# 路径配置
SCRIPT_DIR = Path(__file__).resolve().parent
EXCEL_PATH = SCRIPT_DIR / "简历投递记录.xlsx"

OUTPUT_DIR = SCRIPT_DIR / "已归档截图"

# Excel 表头配置
COLUMNS = [
    "公司",
    "base",
    "行业",
    "平台",
    "批次",
    "投递志愿与顺序",
    "jd",
    "当前进度",
    "进度记录",
    "对应日期",
    "投递链接",
    "备注",
]
PROGRESS_SHEET_NAME = "【附表】进度更新"
PROGRESS_COLUMNS = ["事件标题", "投递记录", "公司", "岗位名称", "阶段", "日期", "备注"]

# 交互式输入时的可选字段选项（控制台和 GUI 共用）
FIELD_OPTIONS = {
    "base": ["北京", "上海", "杭州", "广州", "深圳"],
    "行业": ["互联网", "外企", "国央企科技平台"],
    "平台": ["官网", "Boss", "内推", "微信"],
    "当前进度": ["投递", "测评", "初筛", "群面", "三面", "hr面", "offer"],
    "批次": ["提前批", "正式批", "人才计划", "管培生", "秋招"],
}
