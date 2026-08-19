<#
.SYNOPSIS
  门禁编排脚本 run-gate（PowerShell 版）。

.DESCRIPTION
  与 scripts/python/run_gate.py 输出字节级等价的判定 JSON
  （spec-kit scripts: frontmatter 三语言等价契约）。

  职责（v0.4 第五章 5.2 的 9 步 + v0.5 5.5 + v0.6 G/H）：本版负责环境编排
  （降级/模块定位委托 python run_gate.collect_environment、mvn clean test、
  调用 PowerShell 版子脚本 scan-test-stack.ps1 / parse-test-results.ps1 /
  scan-spec-annotations.ps1 收集数据、文件检查）；确定性核心（@DisplayName
  对齐 + 阈值比对 + 判定 + 写 gate-result.md + JSON 序列化）由 python3 -c
  导入 run_gate.run() 完成，与 Python 版字节级等价（同一 json.dumps 格式
  ensure_ascii=False, indent=2）。若 python3 不可用回退 python。

  降级/模块定位（v0.6 4.1）：collect_environment 判定——
  - 无 java/mvn 或 无 root pom 且无候选模块 -> 降级（仅 @Spec 静态扫描）
  - 唯一候选模块 -> located_module + suggestion（非 auto-locate 时 WARN）
  - 多候选 -> stderr 打印 suggestion 后 exit 2
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

.PARAMETER AutoLocate
  唯一候选模块时自动采用（供 CI，v0.6 4.1）。

.PARAMETER CoverageScope
  覆盖率作用域：auto | <pkg,...> | all（默认 auto，v0.6 6.2）。

.PARAMETER Baseline
  baseline 快照文件路径（可选，默认空，v0.6 6.4）。

.PARAMETER CheckOnly
  只跑步骤 1-7，不写 gate-result.md。

.PARAMETER Json
  输出判定 JSON 到 stdout（固定开启）。

.EXAMPLE
  ./run-gate.ps1 -Source ./src -TestSource ./src/test -Spec ./spec.md -Project . -FeatureDir ./specs/001-bank-transfer -Config ./testing-config.yml -Json
#>

<#
DEPRECATED (beta 阶段)：本脚本已弃用，仅保留供参考，不再维护。
当前只维护 scripts/python/ 下的唯一实现；行为可能与 python 版漂移。
#>

param(
    [Parameter(Mandatory=$true)][string]$Source,
    [Parameter(Mandatory=$true)][string]$TestSource,
    [Parameter(Mandatory=$true)][string]$Spec,
    [Parameter(Mandatory=$true)][string]$Project,
    [Parameter(Mandatory=$true)][string]$FeatureDir,
    [Parameter(Mandatory=$true)][string]$Config,
    [switch]$AutoLocate,
    [string]$CoverageScope,
    [string]$Baseline,
    [switch]$CheckOnly,
    [switch]$Json
)

$ErrorActionPreference = "Stop"

# 强制 UTF-8 输出，确保中文与 Python 版字节级一致
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$pyDir = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\python"))

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

# CoverageScope/Baseline 未传保持空串，由 run() 核心回落 config 默认（6.5）
$autoLocateFlag = if ($AutoLocate) { "1" } else { "0" }

# 与 python main() 一致：-Baseline 与 CoverageScope=all 互斥（v0.6 6.4，
# all 已全量，无需 baseline 增量判定）
if ($Baseline -and $CoverageScope -eq "all") {
    [Console]::Error.WriteLine("错误: -Baseline 与 CoverageScope=all 互斥（文档 6.4：all 已全量，无需 baseline 增量判定）")
    exit 2
}

# ── 步骤 0：impact-report.md 存在性（堵 P0 #3） ─────────────────────────
$impactOk = "0"
if (Test-Path -LiteralPath (Join-Path $FeatureDir "docs\impact-report.md") -PathType Leaf) {
    $impactOk = "1"
}

# ── 步骤 0.5：降级/模块定位（v0.6 4.1，委托 python collect_environment） ──
$pyCollect = @'
import sys, json
sys.path.insert(0, sys.argv[1])
import run_gate
print(json.dumps(run_gate.collect_environment(sys.argv[2], sys.argv[3] == "1"), ensure_ascii=False))
'@
$envJson = (& $pyExe -c $pyCollect $pyDir $Project $autoLocateFlag 2>$null | Out-String).TrimEnd()
if (-not $envJson) {
    [Console]::Error.WriteLine("错误: run_gate.collect_environment 调用失败（python 核心不可用?）")
    exit 3
}
$envObj = $envJson | ConvertFrom-Json
$degraded = if ($envObj.degraded) { "1" } else { "0" }
$locatedModule = if ($envObj.located_module) { [string]$envObj.located_module } else { "" }
$degradedReason = if ($envObj.degraded_reason) { [string]$envObj.degraded_reason } else { "" }
$suggestion = if ($envObj.suggestion) { [string]$envObj.suggestion } else { "" }
$mvnDir = if ($envObj.mvn_dir) { [string]$envObj.mvn_dir } else { "" }

# ambiguous（多候选）：与 python main() 判定完全一致（非降级 + 无 root pom +
# located_module 为空，即 collect_environment 的 ambiguous 分支），stderr 打印
# 建议后 exit 2（stdout 保持纯净 JSON，不产 gate 结果）。
$rootHasPom = Test-Path -LiteralPath (Join-Path $Project "pom.xml") -PathType Leaf
if ($degraded -eq "0" -and -not $rootHasPom -and -not $locatedModule) {
    [Console]::Error.WriteLine("错误: $suggestion")
    exit 2
}
# 唯一候选（非 auto-locate）：WARN + 建议命令（v0.6 4.1 防误判，不自动切换）
if ($locatedModule -and -not $AutoLocate) {
    [Console]::Error.WriteLine("WARN: $suggestion")
}

# ── 步骤 1：mvn clean test（在 mvn_dir 执行，强制 clean，仅 full 模式） ─
# run_mvn 门控与 python main() 一致：root 有 pom 或（auto-locate 且唯一候选）
# 才执行 mvn；其余非降级路径（如非 auto-locate 唯一候选）保持 SKIPPED
# （防误判：不自动切换执行目录，mvn_status 交由 run() 产出明确失败原因）。
$mvnStatus = "SKIPPED"
$runMvn = $false
if ($degraded -eq "0" -and ($rootHasPom -or ($AutoLocate -and $locatedModule))) {
    $runMvn = $true
}
if ($runMvn) {
    Push-Location $mvnDir
    try {
        & mvn clean test *> $null
        if ($LASTEXITCODE -eq 0) { $mvnStatus = "SUCCESS" } else { $mvnStatus = "FAIL" }
    } catch {
        $mvnStatus = "FAIL"
    } finally {
        Pop-Location
    }
}

# ── 步骤 2/3/4：调用子脚本收集数据（surefire/jacoco 基于 mvn_dir） ─────
$stackJson = ""
$resultsJson = ""
$specJson = ""
if ($degraded -eq "0") {
    $stackJson = (& "$PSScriptRoot\scan-test-stack.ps1" -Source $TestSource -Json 2>$null | Out-String).TrimEnd()
    $resultsJson = (& "$PSScriptRoot\parse-test-results.ps1" `
        -Surefire (Join-Path $mvnDir "target\surefire-reports") `
        -Jacoco (Join-Path $mvnDir "target\site\jacoco\jacoco.xml") -Json 2>$null | Out-String).TrimEnd()
}
$specJson = (& "$PSScriptRoot\scan-spec-annotations.ps1" -Source $Source -Spec $Spec -TestSource $TestSource -Config $Config -Json 2>$null | Out-String).TrimEnd()

# ── JSON 序列化 + 确定性核心：python3 -c 导入 run_gate 兜底 ─────────────
$pyCore = @'
import sys, json
sys.path.insert(0, sys.argv[1])
import run_gate
args = sys.argv
def _a(i):
    return args[i] if i < len(args) else ""
def _json_or_none(s):
    import json, os
    if not s:
        return None
    try:
        if os.path.isfile(s):
            with open(s, encoding='utf-8') as f:
                return json.load(f)
        return json.loads(s)
    except Exception:
        return None
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
    "scan_stack": _json_or_none(_a(12)),
    "parse_results": _json_or_none(_a(13)),
    "scan_spec": _json_or_none(_a(14)),
    "auto_locate": _a(15) == "1",
    "coverage_scope": _a(16),
    "baseline": _a(17),
    "located_module": _a(18) or None,
    "degraded_reason": _a(19),
    "suggestion": _a(20),
    "mvn_dir": _a(21),
}
result = run_gate.run(inputs)
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if result["status"] == "FAIL" else 0)
'@

$checkOnlyFlag = if ($CheckOnly) { "1" } else { "0" }

# ── F5：多行 JSON 不直接作 argv（Win PowerShell 5.1 参数拼接脆弱） ─────
# 三个子脚本的 JSON 串各写临时文件、传路径；嵌入 python 的 _json_or_none
# 对路径读文件、对 JSON 串走 json.loads 原逻辑（bash 仍传 JSON 串，两端
# 共享同一段嵌入代码保持 parity）。try/finally 保证临时文件必清理不泄漏。
$stackFile = ""
$resultsFile = ""
$specFile = ""
try {
    if ($degraded -eq "0") {
        $stackFile = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllText($stackFile, $stackJson, [System.Text.UTF8Encoding]::new($false))
        $resultsFile = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllText($resultsFile, $resultsJson, [System.Text.UTF8Encoding]::new($false))
    }
    $specFile = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($specFile, $specJson, [System.Text.UTF8Encoding]::new($false))

    & $pyExe -c $pyCore $pyDir $Source $TestSource $Spec $Project $FeatureDir $Config `
        $checkOnlyFlag $degraded $mvnStatus $impactOk $stackFile $resultsFile $specFile `
        $autoLocateFlag $CoverageScope $Baseline $locatedModule $degradedReason $suggestion $mvnDir
    exit $LASTEXITCODE
}
finally {
    if ($stackFile) { Remove-Item -LiteralPath $stackFile -Force -ErrorAction SilentlyContinue }
    if ($resultsFile) { Remove-Item -LiteralPath $resultsFile -Force -ErrorAction SilentlyContinue }
    if ($specFile) { Remove-Item -LiteralPath $specFile -Force -ErrorAction SilentlyContinue }
}
