<#
.SYNOPSIS
  门禁编排脚本 run-gate（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/run_gate.py 输出字节级等价的判定 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  职责（v0.4 第五章 5.2 的 9 步）：本版负责环境编排（java/mvn/pom.xml 检测
  判定降级、mvn clean test、调用 PowerShell 版子脚本 scan-test-stack.ps1 /
  parse-test-results.ps1 / scan-spec-annotations.ps1 收集数据、文件检查）；
  确定性核心（@DisplayName 对齐 + 阈值比对 + 判定 + 写 gate-result.md +
  JSON 序列化）由 python3 -c 导入 run_gate.run() 完成，与 Python 版字节级等价
  （同一 json.dumps 格式 ensure_ascii=False, indent=2）。若 python3 不可用回退 python。

  降级模式（v0.4 5.5）：无 java/mvn 可执行，或项目非 Maven（根目录无 pom.xml）
  -> 仅 @Spec 静态扫描，gate-result.md 明确标注"降级模式（无 Java 环境）"。
  Java 项目缺 JaCoCo/surefire 报告不降级，直接 FAIL。

  --check-only 子模式：只跑步骤 1-7 不写 gate-result.md（对抗测试覆盖率自检）。

.PARAMETER Source
  Java 业务源码根目录。

.PARAMETER TestSource
  测试源码根目录。

.PARAMETER Spec
  spec.md 路径。

.PARAMETER Project
  项目根目录（执行 mvn / 找 target 报告）。

.PARAMETER FeatureDir
  feature 目录（如 specs/001-bank-transfer）。

.PARAMETER Config
  testing-config.yml 路径。

.PARAMETER CheckOnly
  只跑步骤 1-7，不写 gate-result.md。

.PARAMETER Json
  输出判定 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./run-gate.ps1 -Source ./src -TestSource ./src/test -Spec ./spec.md -Project . -FeatureDir ./specs/001-bank-transfer -Config ./testing-config.yml -Json
#>

param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$TestSource,
    [Parameter(Mandatory=$true)][string]$Spec,
    [Parameter(Mandatory=$true)][string]$Project,
    [Parameter(Mandatory=$true)][string]$FeatureDir,
    [Parameter(Mandatory=$true)][string]$Config,
    [switch]$CheckOnly,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

# 强制 UTF-8 读写，确保中文与 Python 版字节级一致
$utf8 = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pyDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\python"))

# ── 步骤 0：impact-report.md 存在性（堵 P0 #3） ─────────────────────────
$impactOk = "0"
if (Test-Path -LiteralPath (Join-Path $FeatureDir "docs\impact-report.md") -PathType Leaf) {
    $impactOk = "1"
}

# ── 降级检测：无 java/mvn 或项目非 Maven（根目录无 pom.xml） ────────────
$degraded = "1"
if ((Get-Command java -ErrorAction SilentlyContinue) -and
    (Get-Command mvn -ErrorAction SilentlyContinue) -and
    (Test-Path -LiteralPath (Join-Path $Project "pom.xml") -PathType Leaf)) {
    $degraded = "0"
}

# ── 步骤 1：mvn clean test（强制 clean，仅 full 模式） ─────────────────
$mvnStatus = "SKIPPED"
if ($degraded -eq "0") {
    Push-Location $Project
    try {
        & mvn clean test *> $null
        if ($LASTEXITCODE -eq 0) { $mvnStatus = "SUCCESS" } else { $mvnStatus = "FAIL" }
    } catch {
        $mvnStatus = "FAIL"
    } finally {
        Pop-Location
    }
}

# ── 步骤 2/3/4：调用子脚本收集数据 ─────────────────────────────────────
$stackJson = ""
$resultsJson = ""
$specJson = ""
if ($degraded -eq "0") {
    $stackJson = (& "$PSScriptRoot\scan-test-stack.ps1" -Source $TestSource -Json 2>$null | Out-String).TrimEnd()
    $resultsJson = (& "$PSScriptRoot\parse-test-results.ps1" `
        -Surefire (Join-Path $Project "target\surefire-reports") `
        -Jacoco (Join-Path $Project "target\site\jacoco\jacoco.xml") -Json 2>$null | Out-String).TrimEnd()
}
$specJson = (& "$PSScriptRoot\scan-spec-annotations.ps1" -Source $Source -Spec $Spec -Json 2>$null | Out-String).TrimEnd()

# ── JSON 序列化 + 确定性核心：python3 -c 导入 run_gate 兜底 ─────────────
$pyCore = @'
import sys, json
sys.path.insert(0, sys.argv[1])
import run_gate
args = sys.argv
def _a(i):
    return args[i] if i < len(args) else ""
def _json_or_none(i):
    s = _a(i)
    return json.loads(s) if s else None
inputs = {
    "source": _a(2),
    "test_source": _a(3),
    "spec": _a(4),
    "project": _a(5),
    "feature_dir": _a(6),
    "config": _a(7),
    "check_only": _a(8) == "1",
    "degraded": _a(9) == "1",
    "mvn_status": _a(10),
    "impact_ok": _a(11) == "1",
    "scan_stack": _json_or_none(12),
    "parse_results": _json_or_none(13),
    "scan_spec": _json_or_none(14),
}
result = run_gate.run(inputs)
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if result["status"] == "FAIL" else 0)
'@

# 选择可用的 python 解释器
$pyExe = $null
foreach ($candidate in @("python3", "python")) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $candidate; break }
}
if (-not $pyExe) {
    [Console]::Error.WriteLine("错误: 未找到 python3/python，无法执行门禁核心")
    exit 3
}

$checkOnlyFlag = if ($CheckOnly) { "1" } else { "0" }

& $pyExe -c $pyCore $pyDir $Source $TestSource $Spec $Project $FeatureDir $Config `
    $checkOnlyFlag $degraded $mvnStatus $impactOk $stackJson $resultsJson $specJson

exit $LASTEXITCODE
