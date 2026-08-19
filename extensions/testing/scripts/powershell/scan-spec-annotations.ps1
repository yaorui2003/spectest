<#
.SYNOPSIS
  @Spec 注解扫描脚本（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/scan_spec_annotations.py 输出字节级等价的 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  v0.6（9.6）：重构为薄壳 —— 全部解析/比对逻辑（含 UNSPEC_CODE 漂移检测）
  委托给 python 核心 scripts/python/scan_spec_annotations.py，本脚本只做：
    1. 参数解析与校验（-Source/-Spec/-Json + v0.6 新增 -TestSource/
       -ExcludePatterns 透传）
    2. 定位 ..\python\scan_spec_annotations.py
    3. 原样透传 stdout 与退出码（字节级等价由 python 核心保证）
  python 不可用时 stderr 报错 exit 3。

.PARAMETER Source
  Java 源文件根目录。

.PARAMETER Spec
  spec.md 文件路径。

.PARAMETER TestSource
  测试源码根目录（可选，供 UNSPEC_CODE 漂移检测判定"无测试引用"）。

.PARAMETER ExcludePatterns
  排除模式（逗号分隔，可选，供 UNSPEC_CODE 排除表）。

.PARAMETER Config
  testing-config.yml 路径（可选）：读 scan.unspec_exclude_patterns 作为排除
  模式默认；-ExcludePatterns 显式提供时以 CLI 为准。

.PARAMETER Json
  输出 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./scan-spec-annotations.ps1 -Source ./src -Spec ./spec.md -Json
#>

<#
DEPRECATED (beta 阶段)：本脚本已弃用，仅保留供参考，不再维护。
当前只维护 scripts/python/ 下的唯一实现；行为可能与 python 版漂移。
#>

param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$Spec,
    [string]$TestSource,
    [string]$ExcludePatterns,
    [string]$Config,
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

# 强制 UTF-8 输出，确保中文与 Python 版字节级一致
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$corePath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\python\scan_spec_annotations.py"))

$pyExe = $null
foreach ($candidate in @("python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $candidate; break }
}
if (-not $pyExe) {
    [Console]::Error.WriteLine("错误: 未找到 python3/python，无法执行 @Spec 扫描核心")
    exit 3
}

# ── 委托 python 核心：原样透传 stdout（--json 恒追加，输出固定为 JSON） ──
$pyArgs = @("--source", $Source, "--spec", $Spec)
if ($TestSource) { $pyArgs += @("--test-source", $TestSource) }
if ($ExcludePatterns) { $pyArgs += @("--exclude-patterns", $ExcludePatterns) }
if ($Config) { $pyArgs += @("--config", $Config) }
$pyArgs += "--json"

& $pyExe $corePath @pyArgs
exit $LASTEXITCODE
