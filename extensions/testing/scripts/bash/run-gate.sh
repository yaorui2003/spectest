#!/usr/bin/env bash
# 门禁编排脚本 run-gate（bash 版）。
#
# 与 scripts/python/run_gate.py 输出字节级等价的判定 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# 职责（v0.4 第五章 5.2 的 9 步）：
#   0. 检查 specs/<feature>/docs/impact-report.md 存在（不存在 -> FAIL）
#   1. mvn clean test（强制 clean，杜绝 target 残留污染）
#   2. 调 scan-test-stack.sh（forbidden_findings 非空 -> FAIL）
#   3. 调 parse-test-results.sh（jacoco.xml/surefire 缺失 -> FAIL，不降级）
#   4. 调 scan-spec-annotations.sh（unimplemented/orphan 非空 -> FAIL）
#   5. @DisplayName 内联对齐（确定性核心内完成）
#   6. risk_level + testing-config.yml 套阈值（确定性核心内完成）
#   7. 逐项比对判定（确定性核心内完成）
#   8. 写 specs/<feature>/docs/gate-result.md + stdout 判定 JSON（确定性核心内完成）
#
# 数据提取用 bash 原生工具（mvn 调用 / 子脚本调用 / 文件检查 / 数据收集）；
# 确定性核心（阈值比对 + 判定 + 写 gate-result.md + JSON 序列化）由
# python3 -c 导入 run_gate.run() 兜底，以复用与 Python 版完全一致的
# json.dumps 格式（ensure_ascii=False, indent=2, 键顺序固定），字节级等价。
#
# 用法: run-gate.sh --source <java_dir> --test-source <test_dir> --spec <spec.md> \
#       --project <root> --feature-dir <specs/<feature>> --config <testing-config.yml> \
#       [--check-only] --json

set -euo pipefail

SOURCE=""
TEST_SOURCE=""
SPEC=""
PROJECT=""
FEATURE_DIR=""
CONFIG=""
CHECK_ONLY=0
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)      SOURCE="$2"; shift 2;;
        --test-source) TEST_SOURCE="$2"; shift 2;;
        --spec)        SPEC="$2"; shift 2;;
        --project)     PROJECT="$2"; shift 2;;
        --feature-dir) FEATURE_DIR="$2"; shift 2;;
        --config)      CONFIG="$2"; shift 2;;
        --check-only)  CHECK_ONLY=1; shift;;
        --json)        JSON=1; shift;;
        *) echo "用法: run-gate.sh --source ... --test-source ... --spec ... --project ... --feature-dir ... --config ... [--check-only] --json" >&2; exit 2;;
    esac
done

if [[ -z "$SOURCE" || -z "$TEST_SOURCE" || -z "$SPEC" || -z "$PROJECT" || -z "$FEATURE_DIR" || -z "$CONFIG" ]]; then
    echo "用法: run-gate.sh --source ... --test-source ... --spec ... --project ... --feature-dir ... --config ... [--check-only] --json" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_DIR="$(cd "$SCRIPT_DIR/../python" && pwd)"
PY_EXE=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -z "$PY_EXE" ]] && { echo "错误: 未找到 python3/python，无法执行门禁核心" >&2; exit 3; }

# ── 步骤 0：impact-report.md 存在性（堵 P0 #3） ──────────────────────────
IMPACT_OK=0
if [[ -f "$FEATURE_DIR/docs/impact-report.md" ]]; then
    IMPACT_OK=1
fi

# ── 降级检测：无 java/mvn 或项目非 Maven（根目录无 pom.xml） ────────────
DEGRADED=1
if command -v java >/dev/null 2>&1 && command -v mvn >/dev/null 2>&1 && [[ -f "$PROJECT/pom.xml" ]]; then
    DEGRADED=0
fi

# ── 步骤 1：mvn clean test（强制 clean，仅 full 模式） ──────────────────
MVN_STATUS="SKIPPED"
if [[ "$DEGRADED" == "0" ]]; then
    if (cd "$PROJECT" && mvn clean test >/dev/null 2>&1); then
        MVN_STATUS="SUCCESS"
    else
        MVN_STATUS="FAIL"
    fi
fi

# ── 步骤 2/3/4：调用子脚本收集数据 ─────────────────────────────────────
STACK_JSON=""
RESULTS_JSON=""
SPEC_JSON=""
if [[ "$DEGRADED" == "0" ]]; then
    STACK_JSON=$(bash "$SCRIPT_DIR/scan-test-stack.sh" --source "$TEST_SOURCE" --json 2>/dev/null) || STACK_JSON=""
    RESULTS_JSON=$(bash "$SCRIPT_DIR/parse-test-results.sh" \
        --surefire "$PROJECT/target/surefire-reports" \
        --jacoco "$PROJECT/target/site/jacoco/jacoco.xml" --json 2>/dev/null) || RESULTS_JSON=""
fi
SPEC_JSON=$(bash "$SCRIPT_DIR/scan-spec-annotations.sh" --source "$SOURCE" --spec "$SPEC" --json 2>/dev/null) || SPEC_JSON=""

# ── JSON 序列化 + 确定性核心：python3 -c 导入 run_gate 兜底 ─────────────
# 与 Python 版字节级等价（同一 run() 实现）。
PY_CORE=$(cat <<'PY'
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
PY
)

"$PY_EXE" -c "$PY_CORE" "$PYTHON_DIR" "$SOURCE" "$TEST_SOURCE" "$SPEC" "$PROJECT" "$FEATURE_DIR" "$CONFIG" "$CHECK_ONLY" "$DEGRADED" "$MVN_STATUS" "$IMPACT_OK" "$STACK_JSON" "$RESULTS_JSON" "$SPEC_JSON"
