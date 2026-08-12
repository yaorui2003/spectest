#!/usr/bin/env bash
# Maven Surefire + JaCoCo 测试结果解析脚本（bash 版）。
#
# 与 scripts/python/parse_test_results.py 输出字节级等价的 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# XML 解析过于复杂，本版将整个解析与 JSON 序列化完全委托给
# python3 -c（传入 surefire 目录与 jacoco 文件路径作为参数），
# 输出与 Python 版字节级等价。
#
# 用法: parse-test-results.sh --surefire <dir> --jacoco <file> --json

set -euo pipefail

SUREFIRE=""
JACOCO=""
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --surefire) SUREFIRE="$2"; shift 2;;
        --jacoco)   JACOCO="$2"; shift 2;;
        --json)     JSON=1; shift;;
        *) echo "用法: $0 --surefire <dir> --jacoco <file> --json" >&2; exit 2;;
    esac
done

if [[ -z "$SUREFIRE" || -z "$JACOCO" ]]; then
    echo "用法: $0 --surefire <dir> --jacoco <file> --json" >&2
    exit 2
fi

PY_SERIALIZER=$(cat <<'PY'
import json, sys, os, glob
from xml.etree import ElementTree as ET
surefire_dir = sys.argv[1]
jacoco_file = sys.argv[2]
unit_total = unit_passed = unit_failed = 0
contract_total = contract_passed = contract_failed = 0
if os.path.isdir(surefire_dir):
    for xml in sorted(glob.glob(os.path.join(surefire_dir, "*.xml"))):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        for ts in root.iter("testsuite"):
            name = ts.attrib.get("name", "")
            tests = int(ts.attrib.get("tests", 0))
            failures = int(ts.attrib.get("failures", 0))
            errors = int(ts.attrib.get("errors", 0))
            passed = tests - failures - errors
            if "ContractTest" in name:
                contract_total += tests
                contract_failed += failures + errors
                contract_passed += passed
            else:
                unit_total += tests
                unit_failed += failures + errors
                unit_passed += passed
unit_pass_rate = round(unit_passed / unit_total * 100) if unit_total > 0 else 0
contract_pass_rate = round(contract_passed / contract_total * 100) if contract_total > 0 else 0
cov = {"LINE": 0, "BRANCH": 0, "METHOD": 0, "INSTRUCTION": 0, "COMPLEXITY": 0}
if os.path.isfile(jacoco_file):
    try:
        root = ET.parse(jacoco_file).getroot()
    except ET.ParseError:
        root = None
    if root is not None:
        sums = {}
        for c in root.iter("counter"):
            t = c.attrib.get("type")
            if t in ("LINE", "BRANCH", "METHOD", "INSTRUCTION", "COMPLEXITY"):
                missed = int(c.attrib.get("missed", 0))
                covered = int(c.attrib.get("covered", 0))
                s = sums.setdefault(t, [0, 0])
                s[0] += missed
                s[1] += covered
        for t, (missed, covered) in sums.items():
            total = missed + covered
            cov[t] = round(covered / total * 100) if total > 0 else 0
result = {
    "unit_tests": {"total": unit_total, "passed": unit_passed, "failed": unit_failed, "pass_rate": unit_pass_rate},
    "contract_tests": {"total": contract_total, "passed": contract_passed, "failed": contract_failed, "pass_rate": contract_pass_rate},
    "coverage": {
        "line_coverage": cov["LINE"],
        "branch_coverage": cov["BRANCH"],
        "method_coverage": cov["METHOD"],
        "instruction_coverage": cov["INSTRUCTION"],
        "complexity_coverage": cov["COMPLEXITY"],
    },
}
print(json.dumps(result, ensure_ascii=False, indent=2))
PY
)

PY_EXE=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -z "$PY_EXE" ]] && { echo "错误: 未找到 python3/python，无法序列化 JSON" >&2; exit 3; }

"$PY_EXE" -c "$PY_SERIALIZER" "$SUREFIRE" "$JACOCO"
