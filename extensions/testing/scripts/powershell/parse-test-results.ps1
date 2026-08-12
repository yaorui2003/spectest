<#
.SYNOPSIS
  Maven Surefire + JaCoCo 测试结果解析脚本（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/parse_test_results.py 输出字节级等价的 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  XML 解析过于复杂，本版将整个解析与 JSON 序列化完全委托给
  python3 -c（传入 surefire 目录与 jacoco 文件路径作为参数），
  输出与 Python 版字节级等价。

  若 python3 不可用，回退到 python。

.PARAMETER Surefire
  surefire-reports 目录。

.PARAMETER Jacoco
  jacoco.xml 文件路径。

.PARAMETER Json
  输出 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./parse-test-results.ps1 -Surefire ./target/surefire-reports -Jacoco ./target/site/jacoco/jacoco.xml -Json
#>

param(
    [Parameter(Mandatory=$true)][string]$Surefire,
    [Parameter(Mandatory=$true)][string]$Jacoco,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pyScript = @'
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
'@

# 选择可用的 python 解释器
$pyExe = $null
foreach ($candidate in @("python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $candidate; break }
}
if (-not $pyExe) {
    [Console]::Error.WriteLine("错误: 未找到 python3/python，无法解析 XML")
    exit 3
}

& $pyExe -c $pyScript $Surefire $Jacoco
