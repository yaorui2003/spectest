<#
.SYNOPSIS
  测试技术栈扫描脚本（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/scan_test_stack.py 输出字节级等价的 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  数据提取用 PowerShell 原生工具（Get-ChildItem / -match / .Trim()）；
  JSON 序列化用 python3 -c 兜底，以复用与 Python 版完全一致的
  json.dumps 格式（ensure_ascii=False, indent=2, 键顺序固定）。

  若 python3 不可用，回退到 python。

.PARAMETER Source
  测试源码根目录。

.PARAMETER Json
  输出 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./scan-test-stack.ps1 -Source ./src/test -Json
#>

param(
    [Parameter(Mandatory=$true)][string]$Source,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    [Console]::Error.WriteLine("错误: -Source 目录不存在: $Source")
    exit 2
}

# 强制 UTF-8 读写，确保与 Python 版字节级一致
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── 1. 遍历 .java 文件（按路径排序），提取发现 ─────────────────────────
# 每行输出: type\tfile\tline\tdetail（detail 已去首尾空白）
$findings = [System.Collections.Generic.List[string]]::new()
$javaFiles = Get-ChildItem -LiteralPath $Source -Recurse -Filter *.java |
    Sort-Object FullName
foreach ($javaFile in $javaFiles) {
    $lines = [System.IO.File]::ReadAllLines($javaFile.FullName, $utf8)
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $lineNo = $i + 1
        if ($line -match 'org\.powermock') {
            $findings.Add("powermock`t$($javaFile.FullName)`t$lineNo`t$($line.Trim())")
        }
        if ($line -match '@SpringBootTest') {
            $findings.Add("springboottest`t$($javaFile.FullName)`t$lineNo`t$($line.Trim())")
        }
    }
}
$tsv = $findings -join "`n"

# ── 2. JSON 序列化：python3 兜底，与 Python 版字节级等价 ─────────────
$pyScript = @'
import json, sys
data = sys.stdin.read().split("\n")
findings = []
for line in data:
    if line == "":
        continue
    parts = line.split("\t")
    if len(parts) == 4:
        findings.append({"type": parts[0], "file": parts[1], "line": int(parts[2]), "detail": parts[3]})
result = {"forbidden_findings": findings}
print(json.dumps(result, ensure_ascii=False, indent=2))
'@

# 选择可用的 python 解释器
$pyExe = $null
foreach ($candidate in @("python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $candidate; break }
}
if (-not $pyExe) {
    [Console]::Error.WriteLine("错误: 未找到 python3/python，无法序列化 JSON")
    exit 3
}

$tsv | & $pyExe -c $pyScript
