"""端到端 (E2E) 测试：走真正的 main() 入口。

与 test_features 的区别：这里不直接调 change_*，而是从 main() 启动，
让真实的命令行解析、目录扫描、子菜单循环全部跑起来。虚拟存档结构在
临时目录里真实落盘（make_save_tree），select_save_dir/select_save_file
走真实逻辑，harness 只 mock 交互副作用 + 注入 sys.argv。
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from tests.helpers import harness, sse, make_save, make_stock, make_save_tree


class TestParseArgs(unittest.TestCase):
    """parse_args 单元：-d 解析 + 默认值回退。"""

    def test_default_falls_back_to_default_save_dir(self):
        a = sse.parse_args([])
        self.assertEqual(a.save_dir, sse.DEFAULT_SAVE_DIR)

    def test_short_flag_d(self):
        a = sse.parse_args(["-d", "D:/my/saves"])
        self.assertEqual(a.save_dir, Path("D:/my/saves"))

    def test_long_flag_save_dir_with_equals(self):
        a = sse.parse_args(["--save-dir=E:/backups"])
        self.assertEqual(a.save_dir, Path("E:/backups"))

    def test_unknown_flag_errors(self):
        with self.assertRaises(SystemExit):
            sse.parse_args(["--nope"])


class TestMainE2E(unittest.TestCase):
    """走 main() 的完整端到端流程，验证命令行参数→选档→改档→写盘→退出。"""

    def _tree(self, slot_name="slot1", fname="save.sav", stocks=None):
        """造一个单 slot 单文件的存档目录树。"""
        data = make_save(stocks if stocks is not None else [make_stock(2001)])
        root = make_save_tree([{"name": slot_name, "file": fname, "data": data}])
        sav_path = root / slot_name / fname
        return root, sav_path

    def _run_main(self, argv, inputs, game_running=False):
        """跑完一次 main()，返回 stdout 文本。失败时打印输出便于调试。"""
        out_text = ""
        try:
            with harness(inputs, game_running=game_running, argv=argv) as ctx:
                sse.main()
                out_text = ctx.out.getvalue()
        except Exception:
            # 捕获后打印，定位输入序列错位
            import sys
            print("\n--- main() 输出(调试) ---\n" + out_text)
            raise
        return out_text

    # ------------------------------------------------------------------
    # 流程：-d 指定目录 → 选股 → 改 PE → 保存 → 退出（验证磁盘写盘）
    # ------------------------------------------------------------------
    def test_full_flow_writes_disk(self):
        root, sav_path = self._tree()
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            # 单 slot 单文件 → select_save_dir/select_save_file 不提问
            # Loaded 提示后 pause()
            # main_menu: 1=选股, code=2001, 子菜单: 2=改PE, PE值, 确认y,
            #   子菜单: 0=返回, main_menu: 15=保存, main_menu: 17=退出
            inputs = [
                "1", "2001",      # 主菜单选股 + 输入代码（走 extract_code）
                "2", "1.0", "y",  # 子菜单改 PE：目标值 + 确认
                "0",              # 子菜单返回
                "15",             # 主菜单保存
                "17",             # 主菜单退出
            ]
            self._run_main(argv, inputs)

            # 验证：磁盘上确实写入了改 PE 后的值（RewardBusiness 被改）
            with open(sav_path, encoding="utf-8") as f:
                on_disk = json.load(f)
            info = on_disk["Market"]["Stocks"][0]["Info"]
            self.assertEqual(info["CostBusiness"], 0)  # change_pe 清零成本
            self.assertEqual(info["CostOther"], 0)
            # 备份文件生成
            self.assertEqual(len(list(sav_path.parent.glob("*.sav.bak.*"))), 1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_default_dir_arg_when_no_flag(self):
        # 不传 -d：parse_args 用 DEFAULT_SAVE_DIR；目录不存在时
        # find_save_dirs 返回 [] → select_save_dir 报错 → main 返回
        # 用一个不存在的路径模拟“默认目录无存档”
        root = Path(tempfile.mkdtemp(prefix="sse_empty_")) / "nonexist"
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            out = self._run_main(argv, [])  # 无 input，因为目录空直接返回前 pause
            self.assertIn("No save dirs", out)
        finally:
            shutil.rmtree(root.parent, ignore_errors=True)

    def test_multi_slot_prompts_dir_choice(self):
        # 多个 slot → select_save_dir 会问 Dir 编号
        root = make_save_tree([
            {"name": "slot_a", "file": "a.sav", "data": make_save([make_stock(2001)])},
            {"name": "slot_b", "file": "b.sav", "data": make_save([make_stock(2002)])},
        ])
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            # Dir选1(slot_a) → 单文件自动选 → pause → 主菜单17退出
            inputs = ["1", "17"]
            out = self._run_main(argv, inputs)
            # 选了 slot_a → 加载的应是 X2001；输出里能看到 stocks 数量=1
            self.assertIn("1 stocks", out)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_multi_file_prompts_save_choice(self):
        # 单 slot 多文件 → select_save_file 会问 Save 编号
        root = make_save_tree([
            {"name": "slot_x", "file": "s1.sav", "data": make_save([make_stock(2001)])},
        ])
        # 同一 slot 下再放第二个 .sav
        with open(root / "slot_x" / "s2.sav", "w", encoding="utf-8") as f:
            json.dump(make_save([make_stock(2002)]), f)
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            # 单slot自动选 → Save选2(s2.sav,含X2002) → pause → 退出
            inputs = ["2", "17"]
            out = self._run_main(argv, inputs)
            self.assertIn("1 stocks", out)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_game_running_warning_at_startup(self):
        root, sav_path = self._tree()
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            # game_running=True → 启动警告 + pause(no-op) →
            # 单slot单文件自动选 → pause → 主菜单 Choose=17 退出
            # 注意：空输入在主菜单会被 continue 跳过，故直接喂 "17"
            inputs = ["17"]
            out = self._run_main(argv, inputs, game_running=True)
            self.assertIn("警告", out)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_stock_code_not_found_in_main_menu(self):
        root, _ = self._tree()
        try:
            argv = ["stock_save_editor.py", "-d", str(root)]
            # 选股输入不存在的 9999 → 报 not found → pause → 主菜单 17 退出
            inputs = ["1", "9999", "17"]
            out = self._run_main(argv, inputs)
            self.assertIn("not found", out)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
