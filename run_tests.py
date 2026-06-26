#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一键回归测试入口。

用法:
    python run_tests.py            # 跑全部测试
    python run_tests.py -v         # 详细模式（每个用例一行）
    python run_tests.py tests.test_cli          # 只跑 CLI 接口测试
    python run_tests.py tests.test_features     # 只跑 feat 点测试

测试全程在虚拟存档 / 临时文件上运行，绝不触碰真实 .sav 存档。
"""
import io
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]

    # 默认 discover tests 包下所有 test_*.py
    if not argv or all(a.startswith("-") for a in argv):
        loader = unittest.TestLoader()
        suite = loader.discover(start_dir=os.path.join(HERE, "tests"),
                                pattern="test_*.py")
    else:
        # 支持传入模块名，如 tests.test_cli
        targets = [a for a in argv if not a.startswith("-")]
        verbosity = 2 if "-v" in argv else 1
        loader = unittest.TestLoader()
        suite = unittest.TestSuite()
        for t in targets:
            suite.addTests(loader.loadTestsFromName(t))
        stream = _utf8_stdout()
        runner = unittest.TextTestRunner(verbosity=verbosity, stream=stream)
        result = runner.run(suite)
        print_summary(result, stream)
        return 0 if result.wasSuccessful() else 1

    verbosity = 2 if "-v" in argv else 1
    stream = _utf8_stdout()
    runner = unittest.TextTestRunner(verbosity=verbosity, stream=stream)
    result = runner.run(suite)
    print_summary(result, stream)
    return 0 if result.wasSuccessful() else 1


def _utf8_stdout():
    """Windows 控制台默认 GBK，测试里的中文/emoji 输出会炸；强制 UTF-8。"""
    try:
        return io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                errors="replace", line_buffering=True)
    except Exception:
        return sys.stdout


def print_summary(result, stream=None):
    stream = stream or _utf8_stdout()
    total = result.testsRun
    fails = len(result.failures)
    errs = len(result.errors)
    passed = total - fails - errs
    bar = "=" * 60
    stream.write("\n" + bar + "\n")
    if fails == 0 and errs == 0:
        stream.write(f"  全部通过 ✅  {passed}/{total} 用例\n")
    else:
        stream.write(f"  存在失败 ❌  通过 {passed}/{total}，失败 {fails}，错误 {errs}\n")
    stream.write(bar + "\n")
    stream.flush()


if __name__ == "__main__":
    sys.exit(main())
