"""CLI 接口回归测试：prompt / prompt_int / prompt_float / confirm /
extract_code 智能提取 / mn-mx 重试 / default 回退 / is_game_running 两路。

这些函数不依赖存档数据，只测输入解析与边界行为。
"""
import unittest
from unittest import mock
from tests.helpers import harness, sse


class TestPrompt(unittest.TestCase):
    """prompt(): 空输入回退默认值，否则返回 trim 后的输入。"""

    def test_empty_returns_default(self):
        with harness([""]):
            self.assertEqual(sse.prompt("Q", "DEF"), "DEF")

    def test_none_default(self):
        with harness([""]) as c:
            # d=None 时不拼默认值括号，仍返回 None
            self.assertIsNone(sse.prompt("Q", None))

    def test_returns_stripped_input(self):
        with harness(["  hello  "]):
            self.assertEqual(sse.prompt("Q", "DEF"), "hello")

    def test_default_used_when_blank_returned(self):
        # 空输入 → 返回 d（这里是数字字符串）
        with harness([""]):
            self.assertEqual(sse.prompt("Q", 42), 42)


class TestPromptInt(unittest.TestCase):
    """prompt_int: 解析、默认值、mn/mx 重试、extract_code。"""

    def test_basic_int(self):
        with harness(["7"]):
            self.assertEqual(sse.prompt_int("N"), 7)

    def test_default_on_blank(self):
        with harness([""]):
            self.assertEqual(sse.prompt_int("N", 5), 5)

    def test_default_param(self):
        with harness([""]):
            self.assertEqual(sse.prompt_int("N", default=9), 9)

    def test_mn_mx_retry_then_pass(self):
        # 输入 0(<1) → 重试 → 输入 5(合法)
        with harness(["0", "5"]):
            self.assertEqual(sse.prompt_int("N", mn=1, mx=10), 5)

    def test_mn_mx_all_too_low_gives_up_via_eof(self):
        # 一直越界，输入耗尽后抛 EOFError（证明确实在重试而非直接放过）
        with harness(["0", "0", "0"]):
            with self.assertRaises(EOFError):
                sse.prompt_int("N", mn=1, mx=10)

    def test_non_int_retry(self):
        with harness(["abc", "3"]):
            self.assertEqual(sse.prompt_int("N"), 3)

    def test_extract_code_x_prefix(self):
        # 智能提取：X2075 → 2075
        with harness(["X2075"]):
            self.assertEqual(sse.prompt_int("Code", extract_code=True), 2075)

    def test_extract_code_mixed(self):
        with harness(["code-20 75"]):
            self.assertEqual(sse.prompt_int("Code", extract_code=True), 2075)

    def test_extract_code_no_digits_retries(self):
        # 提取不到数字 → 重试
        with harness(["abc", "X1001"]):
            self.assertEqual(sse.prompt_int("Code", extract_code=True), 1001)


class TestPromptFloat(unittest.TestCase):
    def test_basic_float(self):
        with harness(["3.14"]):
            self.assertEqual(sse.prompt_float("F"), 3.14)

    def test_default_on_blank(self):
        with harness([""]):
            self.assertEqual(sse.prompt_float("F", 2.5), 2.5)

    def test_mn_mx_retry(self):
        with harness(["0.01", "50"]):
            self.assertEqual(sse.prompt_float("F", mn=1.0, mx=100.0), 50.0)

    def test_non_num_retry(self):
        with harness(["xx", "1.0"]):
            self.assertEqual(sse.prompt_float("F"), 1.0)


class TestConfirm(unittest.TestCase):
    """confirm: yes/no 与默认取向。"""

    def test_yes_overrides_default_no(self):
        # no=True(默认拒绝)，输入 y → True
        with harness(["y"]):
            self.assertTrue(sse.confirm("OK", no=True))

    def test_blank_with_default_no(self):
        with harness([""]):
            self.assertFalse(sse.confirm("OK", no=True))

    def test_blank_with_default_yes(self):
        # no=False → 默认同意，空输入 → True
        with harness([""]):
            self.assertTrue(sse.confirm("OK", no=False))

    def test_n_overrides_default_yes(self):
        with harness(["n"]):
            self.assertFalse(sse.confirm("OK", no=False))

    def test_yes_word(self):
        with harness(["yes"]):
            self.assertTrue(sse.confirm("OK", no=True))


class TestIsGameRunning(unittest.TestCase):
    """验证真实 is_game_running 的三条路径（不套 harness，否则会被 mock 覆盖）。"""

    def test_true_when_process_listed(self):
        result = type("R", (), {"stdout": "StocksMainForceSimulator.exe  1234"})()
        with mock.patch("sse.subprocess.run", lambda *a, **k: result):
            self.assertTrue(sse.is_game_running())

    def test_false_when_not_listed(self):
        result = type("R", (), {"stdout": "其他进程.exe  1234"})()
        with mock.patch("sse.subprocess.run", lambda *a, **k: result):
            self.assertFalse(sse.is_game_running())

    def test_false_on_exception(self):
        with mock.patch("sse.subprocess.run", side_effect=Exception("boom")):
            self.assertFalse(sse.is_game_running())


if __name__ == "__main__":
    unittest.main(verbosity=2)
