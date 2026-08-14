<#
.SYNOPSIS
  spec.md 格式验证脚本（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/validate_spec_format.py 输出字节级等价的 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  数据提取用 PowerShell 原生工具（-match / [regex]::Matches）；
  JSON 序列化用 python3 -c 兜底，以复用与 Python 版完全一致的
  json.dumps 格式（ensure_ascii=False, indent=2, 键顺序固定）。

  若 python3 不可用，回退到 python。

.PARAMETER Spec
  spec.md 文件路径。

.PARAMETER Json
  输出 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./validate-spec-format.ps1 -Spec ./spec.md -Json
#>

param(
    [Parameter(Mandatory=$true)][string]$Spec,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Spec -PathType Leaf)) {
    [Console]::Error.WriteLine("错误: -Spec 文件不存在: $Spec")
    exit 2
}

# 强制 UTF-8 读写，确保与 Python 版字节级一致
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$specLines = [System.IO.File]::ReadAllLines($Spec, $utf8)

# ── 1. Business Rules 章节存在性 + 规则编号 ─────────────────────────────
$rulesSection = $false
$rules = [System.Collections.Generic.List[string]]::new()
$seenRules = @{}
$inSection = $false
foreach ($line in $specLines) {
    if ($line -match '^\s*#') {
        $title = $line.ToLower()
        if ($title -match 'business[\t _-]+rules') {
            $inSection = $true
            $rulesSection = $true
        } elseif ($inSection) { $inSection = $false }
        continue
    }
    if (-not $inSection) { continue }
    if ($line -match '^\s*[-*]?\s*\**?(R\d+)\b') {
        $rule = $Matches[1]
        if (-not $seenRules.ContainsKey($rule)) {
            $seenRules[$rule] = $true
            $rules.Add($rule)
        }
    }
}

# ── 2. Error Code Definitions 章节存在性 + 错误码 ──────────────────────
$errSection = $false
$codes = [System.Collections.Generic.List[string]]::new()
$seenCodes = @{}
$inErr = $false
foreach ($line in $specLines) {
    if ($line -match '^\s*#') {
        $title = $line.ToLower()
        if ($title -match 'error[\t _-]+code[\t _-]+definitions') {
            $inErr = $true
            $errSection = $true
        } elseif ($inErr) { $inErr = $false }
        continue
    }
    if (-not $inErr) { continue }
    # 跳过 HTML 注释行（如 <!-- OPTIONAL API errors -->）
    if ($line.Contains('<!--')) { continue }
    $stripped = $line.Trim()
    if ($stripped.StartsWith('|')) {
        # 按 | 拆分为单元格（|...|.Split('|') 首元素为空）
        $cells = @($stripped.Split('|') | ForEach-Object { $_.Trim() })
        # 跳过表头行：任一单元格含 "error code"（忽略大小写）
        $isHeader = $false
        foreach ($c in $cells) {
            if ($c.ToLower().Contains('error code')) { $isHeader = $true; break }
        }
        if ($isHeader) { continue }
        # 跳过分隔行：所有非空单元格均为 - 或 :
        $nonEmpty = @($cells | Where-Object { $_ -ne '' })
        if ($nonEmpty.Count -gt 0) {
            $isSep = $true
            foreach ($c in $nonEmpty) {
                if ($c -notmatch '^[-:]+$') { $isSep = $false; break }
            }
            if ($isSep) { continue }
        }
        # 第一个数据列：只提取错误码列，避免混入 HTTP Status / Related Rule
        if ($cells.Count -ge 2) {
            $first = $cells[1]
            if ($first -match '^[A-Z][A-Z0-9_]+$') {
                if (-not $seenCodes.ContainsKey($first)) {
                    $seenCodes[$first] = $true
                    $codes.Add($first)
                }
            }
        }
        continue
    }
    # 非表格行（列表格式）：取行内第一个全大写标识符
    $m = [regex]::Match($line, '[A-Z][A-Z0-9_]{1,}')
    if ($m.Success) {
        $code = $m.Value
        if (-not $seenCodes.ContainsKey($code)) {
            $seenCodes[$code] = $true
            $codes.Add($code)
        }
    }
}

$rulesFlag = if ($rulesSection) { "1" } else { "0" }
$errFlag = if ($errSection) { "1" } else { "0" }
$tsv = "$rulesFlag`n" + ($rules -join "`n") + "`n===`n" + $errFlag + "`n" + ($codes -join "`n")

# ── 3. JSON 序列化：python3 兜底，与 Python 版字节级等价 ─────────────
$pyScript = @'
import json, sys, re
data = sys.stdin.read().split("\n")
rules_section = None
rules = []
err_section = None
codes = []
mode = "rules"
for line in data:
    if line == "===":
        mode = "codes"
        continue
    if mode == "rules":
        if rules_section is None:
            rules_section = (line == "1")
        elif line != "":
            rules.append(line)
    else:
        if err_section is None:
            err_section = (line == "1")
        elif line != "":
            codes.append(line)
errors = []
warnings = []
if not rules_section:
    errors.append("Missing required '## Business Rules' section")
else:
    nums = []
    for r in rules:
        m = re.match(r"R(\d+)", r)
        if m:
            nums.append(int(m.group(1)))
    if nums:
        mx = max(nums)
        for n in range(1, mx + 1):
            if n not in nums:
                errors.append("Rule numbering gap: missing R%d" % n)
if not err_section:
    warnings.append("No '### Error Code Definitions' section found (optional, skipped)")
result = {
    "valid": len(errors) == 0,
    "errors": errors,
    "warnings": warnings,
    "rules_found": rules,
    "error_codes_found": codes,
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
