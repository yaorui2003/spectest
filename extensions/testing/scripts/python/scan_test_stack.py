#!/usr/bin/env python3
"""测试技术栈扫描脚本（Python 版）。

递归扫描测试源码目录中的 ``.java`` 文件，检查禁止使用的技术
（PowerMock 导入、@SpringBootTest 注解），输出发现清单 JSON。

用法::

    python scan_test_stack.py --source <test_dir> --json

三语言（py/sh/ps）等价：bash/PowerShell 版本用 grep/Select-String 提取数据，
再交由 ``python3 -c`` 做 JSON 序列化，输出字节级等价。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def scan(source_dir: Path) -> dict:
    """递归扫描测试源码目录，返回 forbidden_findings 清单。"""
    findings: list[dict] = []
    # 按 Path 字符串排序，保证三语言一致的文件遍历顺序
    for java_file in sorted(source_dir.rglob("*.java")):
        lines = java_file.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            if "org.powermock" in line:
                findings.append({
                    "type": "powermock",
                    "file": str(java_file),
                    "line": i + 1,
                    "detail": line.strip(),
                })
            if "@SpringBootTest" in line:
                findings.append({
                    "type": "springboottest",
                    "file": str(java_file),
                    "line": i + 1,
                    "detail": line.strip(),
                })
    return {"forbidden_findings": findings}


def main() -> int:
    parser = argparse.ArgumentParser(description="测试技术栈扫描脚本。")
    parser.add_argument("--source", required=True, help="测试源码根目录")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = parser.parse_args()

    result = scan(Path(args.source))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
