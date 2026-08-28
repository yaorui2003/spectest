#!/usr/bin/env python3
"""Maven Surefire + JaCoCo 测试结果解析脚本（Python 版）。

解析 surefire 目录下的 ``*.xml`` 报告与 JaCoCo 覆盖率 ``jacoco.xml``，
输出结构化测试结果 JSON（单测统计/覆盖率/行级覆盖）。

用法::

    python parse_test_results.py --surefire <dir> --jacoco <file> --json

三语言（py/sh/ps）等价：bash/PowerShell 版本完全委托给 ``python3 -c``
（XML 解析过于复杂），与本 Python 版输出字节级等价。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

# JaCoCo counter type -> 输出字段名
JACOCO_TYPE_MAP = {
    "LINE": "line_coverage",
    "BRANCH": "branch_coverage",
    "METHOD": "method_coverage",
    "INSTRUCTION": "instruction_coverage",
    "COMPLEXITY": "complexity_coverage",
}


def _parse_surefire(surefire_dir: Path) -> dict:
    """解析 surefire 目录下的所有 *.xml，返回单测统计。"""
    unit_total = unit_passed = unit_failed = 0
    if surefire_dir.is_dir():
        for xml in sorted(surefire_dir.glob("*.xml")):
            try:
                root = ET.parse(str(xml)).getroot()
            except ET.ParseError:
                continue
            for ts in root.iter("testsuite"):
                tests = int(ts.attrib.get("tests", 0))
                failures = int(ts.attrib.get("failures", 0))
                errors = int(ts.attrib.get("errors", 0))
                unit_total += tests
                unit_failed += failures + errors
                unit_passed += tests - failures - errors
    unit_pass_rate = round(unit_passed / unit_total * 100) if unit_total > 0 else 0
    return {
        "unit_tests": {
            "total": unit_total,
            "passed": unit_passed,
            "failed": unit_failed,
            "pass_rate": unit_pass_rate,
        },
    }


def _parse_jacoco(jacoco_file: Path) -> tuple[dict, list[dict]]:
    """解析 JaCoCo jacoco.xml，返回 (聚合覆盖率, 行级覆盖率列表)。

    聚合覆盖率：全量 counter 汇总的各类百分比（整数，现状语义，fallback_all
    回退全量阈值判定与 gate-result.md 展示用）。

    行级覆盖率（diff coverage 判定用）：按 XML 出现顺序遍历
    ``<package name>`` -> ``<sourcefile name>`` -> ``<line nr mi ci mb cb>``；
    ``key`` = package 名点转斜杠（``com.example`` -> ``com/example``）+ "/" +
    sourcefile 名（如 ``com/example/AccountService.java``），与 git diff 相对
    路径匹配（见 run_gate._compute_diff_coverage）；仅当 sourcefile 下存在
    ``<line>`` 元素时输出该文件条目（无行级数据的文件不出现在 source_lines）；
    lines 按 nr 升序。sourcefile 与 class 在 XML 中是 package 下的兄弟元素，
    行级数据在 sourcefile 下，key 拼装只用 package + sourcefile 名。
    """
    cov = {key: 0 for key in JACOCO_TYPE_MAP.values()}
    source_lines: list[dict] = []
    if jacoco_file.is_file():
        try:
            root = ET.parse(str(jacoco_file)).getroot()
        except ET.ParseError:
            root = None
        if root is not None:
            sums: dict[str, list[int]] = {}
            for c in root.iter("counter"):
                t = c.attrib.get("type")
                if t in JACOCO_TYPE_MAP:
                    missed = int(c.attrib.get("missed", 0))
                    covered = int(c.attrib.get("covered", 0))
                    s = sums.setdefault(t, [0, 0])
                    s[0] += missed
                    s[1] += covered
            for t, (missed, covered) in sums.items():
                total = missed + covered
                cov[JACOCO_TYPE_MAP[t]] = (
                    round(covered / total * 100) if total > 0 else 0
                )
            # 行级数据（按 XML 出现顺序；key = package 点转斜杠 + / + sourcefile 名）
            for pkg_el in root.iter("package"):
                pkg_name = pkg_el.attrib.get("name", "") or ""
                pkg_key = pkg_name.replace(".", "/")
                for sf_el in pkg_el.iter("sourcefile"):
                    sf_name = sf_el.attrib.get("name", "") or ""
                    lines: list[dict] = []
                    for line_el in sf_el.iter("line"):
                        lines.append({
                            "nr": int(line_el.attrib.get("nr", 0)),
                            "mi": int(line_el.attrib.get("mi", 0)),
                            "ci": int(line_el.attrib.get("ci", 0)),
                        })
                    if not lines:
                        continue  # 无行级数据 -> 不出现在 source_lines
                    lines.sort(key=lambda l: l["nr"])
                    source_lines.append({
                        "key": f"{pkg_key}/{sf_name}",
                        "package": pkg_name,
                        "file": sf_name,
                        "lines": lines,
                    })
    return cov, source_lines


def parse_results(surefire_dir: Path, jacoco_file: Path) -> dict:
    """组装测试结果 JSON 对象（含行级覆盖率，diff coverage 判定用）。"""
    tests = _parse_surefire(surefire_dir)
    cov, source_lines = _parse_jacoco(jacoco_file)
    return {
        "unit_tests": tests["unit_tests"],
        "coverage": cov,
        "source_lines": source_lines,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Maven Surefire + JaCoCo 测试结果解析脚本。"
    )
    parser.add_argument("--surefire", required=True, help="surefire-reports 目录")
    parser.add_argument("--jacoco", required=True, help="jacoco.xml 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = parser.parse_args()

    result = parse_results(Path(args.surefire), Path(args.jacoco))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
