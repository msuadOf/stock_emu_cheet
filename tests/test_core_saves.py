"""src.core.saves 的纯函数单元测试（默认目录 / 槽列表 / 文件列表）。

这些函数是三端（CLI/TUI/GUI）选择存档的统一后端，需保证健壮：
默认目录恒定、空目录不报错、返回结构正确。
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from src.core import (
    default_save_dir,
    find_save_dirs,
    list_saves,
    list_save_slots,
    list_save_files,
)


def _make_slot(root, slot_name, sav_names):
    """在 root 下造一个含 .sav 的子目录。"""
    d = Path(root) / slot_name
    d.mkdir(parents=True)
    for n in sav_names:
        (d / n).write_text("{}", encoding="utf-8")
    return d


class TestDefaultSaveDir(unittest.TestCase):
    def test_returns_path_with_game_path(self):
        p = default_save_dir()
        self.assertIsInstance(p, Path)
        # 形态应是 .../LoneCat/StocksMainForceSimulator/Saves
        self.assertEqual(p.name, "Saves")
        self.assertIn("StocksMainForceSimulator", str(p))


class TestListSaveSlots(unittest.TestCase):
    def test_empty_dir_returns_empty(self):
        with TemporaryDirectory() as root:
            self.assertEqual(list_save_slots(root), [])

    def test_nonexistent_dir_returns_empty(self):
        self.assertEqual(list_save_slots(Path("Z:/nope/does/not/exist")), [])

    def test_lists_slots_with_file_count(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "slot_a", ["Archive-1.sav", "Archive-2.sav"])
            _make_slot(root, "slot_b", ["Game.sav"])
            (Path(root) / "not_a_slot").mkdir()  # 无 .sav，不应出现
            slots = list_save_slots(root)
            names = [s["name"] for s in slots]
            self.assertEqual(names, ["slot_a", "slot_b"])
            self.assertEqual(slots[0]["file_count"], 2)
            self.assertEqual(slots[1]["file_count"], 1)
            # path 字段是完整路径字符串
            self.assertTrue(slots[0]["path"].endswith("slot_a"))

    def test_dir_without_savs_excluded(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "slot_a", ["x.sav"])
            (Path(root) / "empty_slot").mkdir()
            slots = list_save_slots(root)
            self.assertEqual([s["name"] for s in slots], ["slot_a"])


class TestListSaveFiles(unittest.TestCase):
    def test_lists_files_with_size_and_modified(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "slot_a", ["Archive-1.sav", "Game.sav"])
            files = list_save_files(Path(root) / "slot_a")
            names = [f["name"] for f in files]
            self.assertEqual(names, ["Archive-1.sav", "Game.sav"])  # 排序
            f0 = files[0]
            self.assertIn("path", f0)
            self.assertIn("size_kb", f0)
            self.assertIn("modified", f0)
            self.assertRegex(f0["modified"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_nonexistent_dir_returns_empty(self):
        self.assertEqual(list_save_files(Path("Z:/nope")), [])

    def test_excludes_non_sav_files(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "slot_a", ["Archive-1.sav"])
            (Path(root) / "slot_a" / "Name.sav.bak.20260101").write_text("x")  # .sav.bak，应排除
            (Path(root) / "slot_a" / "readme.txt").write_text("x")
            files = list_save_files(Path(root) / "slot_a")
            self.assertEqual([f["name"] for f in files], ["Archive-1.sav"])


class TestBackwardCompat(unittest.TestCase):
    """底层 find_save_dirs / list_saves 仍被 TUI 直接使用，不能破坏。"""

    def test_find_save_dirs_returns_paths(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "s1", ["a.sav"])
            ds = find_save_dirs(root)
            self.assertEqual(len(ds), 1)
            self.assertIsInstance(ds[0], Path)

    def test_list_saves_returns_paths(self):
        with TemporaryDirectory() as root:
            _make_slot(root, "s1", ["a.sav", "b.sav"])
            ss = list_saves(Path(root) / "s1")
            self.assertEqual([p.name for p in ss], ["a.sav", "b.sav"])
            self.assertIsInstance(ss[0], Path)


if __name__ == "__main__":
    unittest.main()
