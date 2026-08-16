import unittest
from unittest.mock import patch

from utils import interactive_input_fields


class TestInteractiveInputFields(unittest.TestCase):

    def _make_inputs(self, **overrides):
        """构建 10 个字段的模拟输入序列，可通过 overrides 覆盖指定字段。"""
        defaults = {
            "公司": "测试公司",
            "base": "1",
            "行业": "2",
            "平台": "3",
            "批次": "4",
            "投递志愿与顺序": "后端开发",
            "当前进度": "5",
            "对应日期": "",
            "投递链接": "",
            "备注": "",
        }
        defaults.update(overrides)
        return list(defaults.values())

    def _run(self, **overrides):
        mock_inputs = self._make_inputs(**overrides)
        with patch("builtins.input", side_effect=mock_inputs):
            with patch("builtins.print"):
                return interactive_input_fields()

    # ---- 编号选择测试 ----

    def test_select_base_by_number(self):
        result = self._run(base="1")
        self.assertEqual(result["base"], "北京")

    def test_select_base_by_number_last(self):
        result = self._run(base="5")
        self.assertEqual(result["base"], "深圳")

    def test_select_industry_by_number(self):
        result = self._run(行业="2")
        self.assertEqual(result["行业"], "外企")

    def test_select_platform_by_number(self):
        result = self._run(平台="3")
        self.assertEqual(result["平台"], "内推")

    def test_select_batch_by_number(self):
        result = self._run(批次="4")
        self.assertEqual(result["批次"], "管培生")

    def test_select_progress_by_number(self):
        result = self._run(当前进度="5")
        self.assertEqual(result["当前进度"], "三面")

    # ---- 自定义文本测试 ----

    def test_custom_text_not_overwritten(self):
        result = self._run(base="成都")
        self.assertEqual(result["base"], "成都")

    def test_custom_text_chinese(self):
        result = self._run(行业="制造业")
        self.assertEqual(result["行业"], "制造业")

    # ---- 边界测试 ----

    def test_number_out_of_range_treated_as_text(self):
        result = self._run(base="99")
        self.assertEqual(result["base"], "99")

    def test_zero_treated_as_text(self):
        result = self._run(base="0")
        self.assertEqual(result["base"], "0")

    def test_negative_treated_as_text(self):
        result = self._run(base="-1")
        self.assertEqual(result["base"], "-1")

    # ---- 空输入 / 默认值测试 ----

    def test_empty_input_uses_default_for_progress(self):
        result = self._run(当前进度="")
        self.assertEqual(result["当前进度"], "投递")

    def test_empty_input_no_default_for_base(self):
        result = self._run(base="")
        self.assertEqual(result["base"], "")

    # ---- 非选项字段不受影响 ----

    def test_non_option_field_company(self):
        result = self._run(公司="字节跳动")
        self.assertEqual(result["公司"], "字节跳动")

    def test_non_option_field_link(self):
        result = self._run(投递链接="https://example.com")
        self.assertEqual(result["投递链接"], "https://example.com")

    def test_non_option_field_remark(self):
        result = self._run(备注="内推人：张三")
        self.assertEqual(result["备注"], "内推人：张三")

    # ---- 安全测试 ----

    def test_sql_injection_treated_as_text(self):
        result = self._run(base="'; DROP TABLE--")
        self.assertEqual(result["base"], "'; DROP TABLE--")

    def test_spaces_only_uses_default(self):
        result = self._run(base="   ")
        self.assertEqual(result["base"], "")


if __name__ == "__main__":
    unittest.main()