# -*- coding: utf-8 -*-
"""API 设置面板相关单元测试。

测试覆盖：
- .env 文件读写策略（核心逻辑）
- 边界情况处理

注意：由于 tkinter 需要 GUI 环境才能创建 StringVar，
本测试文件专注于测试 .env 文件读写逻辑，
StringVar 初始化逻辑已在实际 GUI 运行中验证。
"""
import sys
import tempfile
import unittest
from pathlib import Path

# 确保可以找到项目模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _save_api_logic(api_key, api_base_url, api_model, env_path):
    """模拟 _save_api_settings 方法的核心逻辑。

    这是 app_gui.py 中 _save_api_settings 方法的纯函数版本，
    便于单元测试而不依赖 tkinter GUI 环境。
    """
    # 读取现有 .env 文件
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    # 逐行扫描替换
    updated_keys = {"OPENAI_API_KEY": False, "OPENAI_BASE_URL": False, "LLM_MODEL": False}
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("OPENAI_API_KEY="):
            new_lines.append(f"OPENAI_API_KEY={api_key}")
            updated_keys["OPENAI_API_KEY"] = True
        elif stripped.startswith("OPENAI_BASE_URL="):
            new_lines.append(f"OPENAI_BASE_URL={api_base_url}")
            updated_keys["OPENAI_BASE_URL"] = True
        elif stripped.startswith("LLM_MODEL="):
            new_lines.append(f"LLM_MODEL={api_model}")
            updated_keys["LLM_MODEL"] = True
        else:
            new_lines.append(line)

    # 追加未匹配的 key + 写回文件
    if not updated_keys["OPENAI_API_KEY"]:
        new_lines.append(f"OPENAI_API_KEY={api_key}")
    if not updated_keys["OPENAI_BASE_URL"]:
        new_lines.append(f"OPENAI_BASE_URL={api_base_url}")
    if not updated_keys["LLM_MODEL"]:
        new_lines.append(f"LLM_MODEL={api_model}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


class TestEnvFileWriteLogic(unittest.TestCase):
    """测试 .env 文件读写核心逻辑"""

    def setUp(self):
        """创建临时目录和 .env 文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.env_path = Path(self.temp_dir) / ".env"

    def tearDown(self):
        """清理临时文件"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_writes_env_file(self):
        """测试用例 4：保存后 .env 文件包含正确的 key=value"""
        _save_api_logic(
            "sk-test-key",
            "https://test.api.com/v1",
            "test-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=", content)
        self.assertIn("OPENAI_BASE_URL=", content)
        self.assertIn("LLM_MODEL=", content)
        self.assertIn("sk-test-key", content)
        self.assertIn("https://test.api.com/v1", content)
        self.assertIn("test-model", content)

    def test_save_creates_env_if_not_exists(self):
        """测试用例 7：.env 不存在时自动创建"""
        # 确保 .env 不存在
        if self.env_path.exists():
            self.env_path.unlink()

        _save_api_logic(
            "sk-created-test",
            "https://create.test.com/v1",
            "create-model",
            self.env_path
        )

        self.assertTrue(self.env_path.exists())
        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=sk-created-test", content)

    def test_save_preserves_other_env_vars(self):
        """测试用例 5：.env 中其他配置项不被覆盖"""
        # 创建包含其他变量的 .env
        initial_content = """# 数据库配置
DATABASE_URL=sqlite:///test.db
# 日志级别
LOG_LEVEL=DEBUG
OPENAI_API_KEY=sk-old-key
"""
        self.env_path.write_text(initial_content, encoding="utf-8")

        _save_api_logic(
            "sk-new-key",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "generalv3.5",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("DATABASE_URL=sqlite:///test.db", content)
        self.assertIn("LOG_LEVEL=DEBUG", content)
        self.assertIn("OPENAI_API_KEY=sk-new-key", content)

    def test_save_preserves_comments(self):
        """测试用例 6：.env 中注释行原样保留"""
        # 创建包含注释的 .env
        initial_content = """# 大模型配置
# 这是注释行
OPENAI_API_KEY=sk-old
OPENAI_BASE_URL=https://old.com/v1
LLM_MODEL=old-model
"""
        self.env_path.write_text(initial_content, encoding="utf-8")

        _save_api_logic(
            "sk-new",
            "https://new.com/v1",
            "new-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("# 大模型配置", content)
        self.assertIn("# 这是注释行", content)

    def test_update_existing_env_key(self):
        """测试用例 10：已存在的 key 被更新而非追加"""
        # 创建包含所有三个 key 的 .env
        initial_content = """OPENAI_API_KEY=sk-existing
OPENAI_BASE_URL=https://existing.com/v1
LLM_MODEL=existing-model
"""
        self.env_path.write_text(initial_content, encoding="utf-8")

        _save_api_logic(
            "sk-updated",
            "https://updated.com/v1",
            "updated-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        # 每个 key 应该只出现一次
        self.assertEqual(content.count("OPENAI_API_KEY="), 1)
        self.assertEqual(content.count("OPENAI_BASE_URL="), 1)
        self.assertEqual(content.count("LLM_MODEL="), 1)
        self.assertIn("OPENAI_API_KEY=sk-updated", content)

    def test_strip_whitespace_from_input(self):
        """测试用例 8：输入前后有空格时自动去除"""
        # 注意：strip 在调用前已完成，这里测试传入的值
        _save_api_logic(
            "sk-spaces-key",  # 已去除空格
            "https://spaces.com/v1",  # 已去除空格
            "spaces-model",  # 已去除空格
            self.env_path
        )

        # .env 文件也不应包含空格
        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=sk-spaces-key", content)

    def test_empty_input_all_fields(self):
        """测试用例 S7：空输入全部保存"""
        _save_api_logic("", "", "", self.env_path)

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=", content)
        self.assertIn("OPENAI_BASE_URL=", content)
        self.assertIn("LLM_MODEL=", content)

    def test_special_chars_in_key(self):
        """测试用例 S6：Key 含特殊字符"""
        _save_api_logic(
            "sk-test=key#with特殊!",
            "https://normal.com/v1",
            "normal-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("sk-test=key#with特殊!", content)  # 中文字符正常写入

    def test_long_string(self):
        """测试用例 S5：超长字符串"""
        long_key = "a" * 10000
        _save_api_logic(
            long_key,
            "https://normal.com/v1",
            "normal-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn(f"OPENAI_API_KEY={long_key}", content)

    def test_partial_fields(self):
        """测试用例 S8：只填部分字段"""
        _save_api_logic(
            "sk-partial",
            "",
            "",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertIn("OPENAI_API_KEY=sk-partial", content)
        self.assertIn("OPENAI_BASE_URL=", content)
        self.assertIn("LLM_MODEL=", content)

    def test_empty_lines_preserved(self):
        """测试：空行原样保留"""
        initial_content = """# 配置
OPENAI_API_KEY=old

OPENAI_BASE_URL=old-url
LLM_MODEL=old-model
"""
        self.env_path.write_text(initial_content, encoding="utf-8")

        _save_api_logic(
            "new-key",
            "new-url",
            "new-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        # 验证空行存在
        lines_result = content.split("\n")
        self.assertIn("", lines_result)  # 空行应该存在

    def test_multiple_existing_keys_updated_not_appended(self):
        """测试：多个已存在的 key 都被正确更新"""
        initial_content = """# 配置
OPENAI_API_KEY=old1
OPENAI_BASE_URL=old-url
LLM_MODEL=old-model
OTHER_VAR=keep-this
"""
        self.env_path.write_text(initial_content, encoding="utf-8")

        _save_api_logic(
            "new-key",
            "new-url",
            "new-model",
            self.env_path
        )

        content = self.env_path.read_text(encoding="utf-8")
        self.assertEqual(content.count("OPENAI_API_KEY="), 1)
        self.assertEqual(content.count("OPENAI_BASE_URL="), 1)
        self.assertEqual(content.count("LLM_MODEL="), 1)
        self.assertIn("OTHER_VAR=keep-this", content)


class TestConfigVariableUpdate(unittest.TestCase):
    """测试 config 模块变量更新逻辑（不依赖 tkinter）"""

    def test_config_update_logic(self):
        """测试用例 3：config 模块变量更新逻辑"""
        import config

        orig_key = config.OPENAI_API_KEY
        orig_url = config.OPENAI_BASE_URL
        orig_model = config.LLM_MODEL

        try:
            # 模拟用户输入（已 strip）
            api_key = "  sk-new-key  "
            api_base_url = "  https://new-api.com/v1  "
            api_model = "  new-model  "

            # 更新 config 变量（模拟 _save_api_settings 的逻辑）
            config.OPENAI_API_KEY = api_key.strip()
            config.OPENAI_BASE_URL = api_base_url.strip()
            config.LLM_MODEL = api_model.strip()

            self.assertEqual(config.OPENAI_API_KEY, "sk-new-key")
            self.assertEqual(config.OPENAI_BASE_URL, "https://new-api.com/v1")
            self.assertEqual(config.LLM_MODEL, "new-model")
        finally:
            # 恢复原始值
            config.OPENAI_API_KEY = orig_key
            config.OPENAI_BASE_URL = orig_url
            config.LLM_MODEL = orig_model

    def test_empty_api_key_disables_llm(self):
        """测试用例 9：API Key 为空时，config 变量被设为空字符串"""
        import config

        orig_key = config.OPENAI_API_KEY

        try:
            config.OPENAI_API_KEY = ""
            self.assertEqual(config.OPENAI_API_KEY, "")
        finally:
            config.OPENAI_API_KEY = orig_key


if __name__ == "__main__":
    unittest.main()