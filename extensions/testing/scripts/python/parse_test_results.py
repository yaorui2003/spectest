#!/usr/bin/env python3
"""Maven Surefire + JaCoCo 测试结果解析脚本（Python 版）。

解析 surefire 目录下的 ``*.xml`` 报告与 JaCoCo 覆盖率 ``jacoco.xml``，
输出结构化测试结果 JSON（单元测试/契约测试/覆盖率）。

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

# 契约测试类名标记
CONTRACT_TEST_MARKER = "ContractTest"

# JaCoCo counter type -> 输出字段名
JACOCO_TYPE_MAP = {
    "LINE": "line_coverage",
    "BRANCH": "branch_coverage",
    "METHOD": "method_coverage",
    "INSTRUCTION": "instruction_coverage",
    "COMPLEXITY": "complexity_coverage",
}


def _parse_surefire(surefire_dir: Path) -> dict:
    """解析 surefire 目录下的所有 *.xml，返回单元/契约测试统计。"""
    unit_total = unit_passed = unit_failed = 0
    contract_total = contract_passed = contract_failed = 0
    if surefire_dir.is_dir():
        for xml in sorted(surefire_dir.glob("*.xml")):
            try:
                root = ET.parse(str(xml)).getroot()
            except ET.ParseError:
                continue
            for ts in root.iter("testsuite"):
                name = ts.attrib.get("name", "")
                tests = int(ts.attrib.get("tests", 0))
                failures = int(ts.attrib.get("failures", 0))
                errors = int(ts.attrib.get("errors", 0))
                passed = tests - failures - errors
                if CONTRACT_TEST_MARKER in name:
                    contract_total += tests
                    contract_failed += failures + errors
                    contract_passed += passed
                else:
                    unit_total += tests
                    unit_failed += failures + errors
                    unit_passed += passed
    unit_pass_rate = round(unit_passed / unit_total * 100) if unit_total > 0 else 0
    contract_pass_rate = (
        round(contract_passed / contract_total * 100) if contract_total > 0 else 0
    )
    return {
        "unit_tests": {
            "total": unit_total,
            "passed": unit_passed,
            "failed": unit_failed,
            "pass_rate": unit_pass_rate,
        },
        "contract_tests": {
            "total": contract_total,
            "passed": contract_passed,
            "failed": contract_failed,
            "pass_rate": contract_pass_rate,
        },
    }


def _parse_jacoco(jacoco_file: Path) -> tuple[dict, list[dict]]:
    """解析 JaCoCo jacoco.xml，返回 (聚合覆盖率, class 级覆盖率列表)。

    聚合覆盖率：全量 counter 汇总的各类百分比（整数，现状语义）。

    class 级覆盖率（v0.6 9.4，供 run_gate 覆盖率作用域判定）：
    按 XML 出现顺序遍历 ``<package name>`` -> ``<class name>``，收集每 class
    的 LINE/BRANCH/METHOD/INSTRUCTION/COMPLEXITY counter；百分比保留 2 位小数，
    分母为 0（missed+covered==0）的指标给 ``None``（判定时跳过该指标）。
    class 全名 = package + "." + class。
    """
    cov = {key: 0 for key in JACOCO_TYPE_MAP.values()}
    classes: list[dict] = []
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
            # class 级覆盖率（按 XML 出现顺序）
            for pkg_el in root.iter("package"):
                pkg_name = pkg_el.attrib.get("name", "")
                for cls_el in pkg_el.iter("class"):
                    cls_name = cls_el.attrib.get("name", "")
                    entry: dict = {
                        "name": f"{pkg_name}.{cls_name}" if pkg_name else cls_name,
                        "package": pkg_name,
                        "line_coverage": None,
                        "branch_coverage": None,
                        "method_coverage": None,
                        "instruction_coverage": None,
                        "complexity_coverage": None,
                    }
                    cls_sums: dict[str, list[int]] = {}
                    for c in cls_el.iter("counter"):
                        t = c.attrib.get("type")
                        if t in JACOCO_TYPE_MAP:
                            missed = int(c.attrib.get("missed", 0))
                            covered = int(c.attrib.get("covered", 0))
                            s = cls_sums.setdefault(t, [0, 0])
                            s[0] += missed
                            s[1] += covered
                    for t, (missed, covered) in cls_sums.items():
                        total = missed + covered
                        entry[JACOCO_TYPE_MAP[t]] = (
                            round(covered / total * 100, 2) if total > 0 else None
                        )
                    classes.append(entry)
    return cov, classes


def parse_results(surefire_dir: Path, jacoco_file: Path) -> dict:
    """组装测试结果 JSON 对象（含 v0.6 9.4 class 级覆盖率）。"""
    tests = _parse_surefire(surefire_dir)
    cov, classes = _parse_jacoco(jacoco_file)
    return {
        "unit_tests": tests["unit_tests"],
        "contract_tests": tests["contract_tests"],
        "coverage": cov,
        "classes": classes,
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
