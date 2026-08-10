<#
.SYNOPSIS
  @Spec 注解扫描脚本（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/scan_spec_annotations.py 输出字节级等价的 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  数据提取用 PowerShell 原生工具（Select-String / Get-Content / -match）；
  JSON 序列化用 python3 -c 兜底，以复用与 Python 版完全一致的 json.dumps
  格式（ensure_ascii=False, indent=2, 键顺序固定）。

  若 python3 不可用，回退到 python。

.PARAMETER Source
  Java 源文件根目录。

.PARAMETER Spec
  spec.md 文件路径。

.PARAMETER Json
  输出 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./scan-spec-annotations.ps1 -Source ./src -Spec ./spec.md -Json
#>

param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Spec,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
    [Console]::Error.WriteLine("错误: -Source 目录不存在: $Source")
    exit 2
}
if (-not (Test-Path -LiteralPath $Spec -PathType Leaf)) {
    [Console]::Error.WriteLine("错误: -Spec 文件不存在: $Spec")
    exit 2
}

# 强制 UTF-8 读写，确保中文与 Python 版字节级一致
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# ── 1. 提取 spec_rules：解析 spec.md 的 business_rules 章节 ─────────────
$specLines = [System.IO.File]::ReadAllLines($Spec, $utf8)
$specRules = [System.Collections.Generic.List[string]]::new()
$seenRules = @{}
$inSection = $false
foreach ($line in $specLines) {
    if ($line -match '^\s*#') {
        $title = $line.ToLower()
        if ($title -match 'business[\t _-]rules') {
            $inSection = $true
        } elseif ($inSection) {
            $inSection = $false
        }
        continue
    }
    if (-not $inSection) { continue }
    if ($line -match '^\s*[-*]?\s*\**?(R\d+)\b') {
        $rule = $Matches[1]
        if (-not $seenRules.ContainsKey($rule)) {
            $seenRules[$rule] = $true
            $specRules.Add($rule)
        }
    }
}

# ── 2. 提取 annotations：遍历 .java 文件（按路径排序） ─────────────────
$javaFiles = Get-ChildItem -LiteralPath $Source -Recurse -Filter *.java |
    Sort-Object FullName
$annotations = [System.Collections.Generic.List[string]]::new()
foreach ($javaFile in $javaFiles) {
    $lines = [System.IO.File]::ReadAllLines($javaFile.FullName, $utf8)
    $package = ""
    $className = ""
    $pending = $false
    $pRule = ""; $pCap = ""; $pDesc = ""; $pLine = 0
    for ($i = 0; $i -lt $lines.Count; $i++) {
        $line = $lines[$i]
        $lineNo = $i + 1
        # 包名
        if ($package -eq "" -and $line -match '^\s*package\s+([\w.]+)\s*;') {
            $package = $Matches[1]
        }
        # 类名
        if ($className -eq "" -and $line -match '\b(?:class|interface|enum|record)\s+(\w+)') {
            $className = $Matches[1]
        }
        # @Spec 注解
        if ($line -match '@Spec\s*\(\s*capability\s*=\s*"([^"]+)"\s*,\s*rule\s*=\s*"(R\d+)"(?:\s*,\s*description\s*=\s*"([^"]*)")?\s*\)') {
            $pCap = $Matches[1]
            $pRule = $Matches[2]
            $pDesc = if ($Matches[3]) { $Matches[3] } else { "" }
            $pLine = $lineNo
            $pending = $true
            continue
        }
        # pending 时查找方法签名（跳过其他注解行）
        if ($pending -and $line -notmatch '^\s*@') {
            if ($line -match '(public|protected|private)' -and $line -match '\(') {
                $s = $line -replace '\(.*', ''
                if ($s -match '([A-Za-z_][A-Za-z0-9_]*)\s*$') {
                    $method = $Matches[1]
                    if ($s -match '\s$') { $method = $method.Trim() }
                    if ($package -ne "") {
                        $loc = "$package.$className.$method`:$pLine"
                    } else {
                        $loc = "$className.$method`:$pLine"
                    }
                    $annotations.Add("$pRule`t$pCap`t$pDesc`t$loc")
                    $pending = $false
                }
            }
        }
    }
}

# ── 3. JSON 序列化：python3 兜底，与 Python 版字节级等价 ─────────────
$tsv = ($specRules -join "`n") + "`n===`n" + ($annotations -join "`n")

$pyScript = @'
import json, sys
data = sys.stdin.read().split("\n")
spec_rules = []
annotations = []
mode = "rules"
for line in data:
    if line == "===":
        mode = "annotations"
        continue
    if line == "":
        continue
    if mode == "rules":
        spec_rules.append(line)
    else:
        parts = line.split("\t")
        if len(parts) == 4:
            annotations.append({"rule": parts[0], "capability": parts[1], "description": parts[2], "location": parts[3]})
annotated_rules = {}
for ann in annotations:
    annotated_rules.setdefault(ann["rule"], []).append(ann["location"])
spec_set = set(spec_rules)
annotated_set = set(annotated_rules.keys())
unimplemented = [r for r in spec_rules if r not in annotated_set]
orphan = [ann for ann in annotations if ann["rule"] not in spec_set]
if spec_rules:
    covered = sum(1 for r in spec_rules if r in annotated_set)
    coverage = round(covered / len(spec_rules) * 100)
else:
    coverage = 0
result = {
    "spec_rules": spec_rules,
    "annotations": annotations,
    "annotated_rules": annotated_rules,
    "unimplemented_rules": unimplemented,
    "orphan_annotations": orphan,
    "coverage_percent": coverage,
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
    [Console]::Error.WriteLine("错误: 未找到 python3/python，无法序列化 JSON")
    exit 3
}

$tsv | & $pyExe -c $pyScript
