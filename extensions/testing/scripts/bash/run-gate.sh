#!/usr/bin/env bash
# 门禁编排脚本 run-gate（bash 版）。
#
# 与 scripts/python/run_gate.py 输出字节级等价的判定 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# 职责（v0.4 第五章 5.2 的 9 步 + v0.5 5.5 + v0.6 G/H）：
#   0. 检查 specs/<feature>/docs/impact-report.md 存在（不存在 -> FAIL）
#   0.5 降级/模块定位（v0.6 4.1）：调 python run_gate.collect_environment
#       - 无 java/mvn 或 无 root pom 且无候选模块 -> 降级（mvn SKIPPED）
#       - 唯一候选模块 -> located_module + suggestion（非 auto-locate 时 WARN）
#       - 多候选 -> stderr 打印 suggestion 后 exit 2
#   1. mvn clean test（在 mvn_dir 执行，强制 clean，杜绝 target 残留污染）
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
#       [--auto-locate] [--coverage-scope <auto|pkg,...|all>] [--baseline <file>] \
#       [--check-only] --json

set -euo pipefail

SOURCE=""
TEST_SOURCE=""
SPEC=""
PROJECT=""
FEATURE_DIR=""
CONFIG=""
AUTO_LOCATE=0
COVERAGE_SCOPE="auto"
BASELINE=""
CHECK_ONLY=0
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)         SOURCE="$2"; shift 2;;
        --test-source)    TEST_SOURCE="$2"; shift 2;;
        --spec)           SPEC="$2"; shift 2;;
        --project)        PROJECT="$2"; shift 2;;
        --feature-dir)    FEATURE_DIR="$2"; shift 2;;
        --config)         CONFIG="$2"; shift 2;;
        --auto-locate)    AUTO_LOCATE=1; shift;;
        --coverage-scope) COVERAGE_SCOPE="$2"; shift 2;;
        --baseline)       BASELINE="$2"; shift 2;;
        --check-only)     CHECK_ONLY=1; shift;;
        --json)           JSON=1; shift;;
        *) echo "用法: run-gate.sh --source ... --test-source ... --spec ... --project ... --feature-dir ... --config ... [--auto-locate] [--coverage-scope <auto|pkg,...|all>] [--baseline <file>] [--check-only] --json" >&2; exit 2;;
    esac
done

if [[ -z "$SOURCE" || -z "$TEST_SOURCE" || -z "$SPEC" || -z "$PROJECT" || -z "$FEATURE_DIR" || -z "$CONFIG" ]]; then
    echo "用法: run-gate.sh --source ... --test-source ... --spec ... --project ... --feature-dir ... --config ... [--auto-locate] [--coverage-scope <auto|pkg,...|all>] [--baseline <file>] [--check-only] --json" >&2
    exit 2
fi

# 与 python main() 一致：--baseline 与 coverage_scope=all 互斥（v0.6 6.4，
# all 已全量，无需 baseline 增量判定）
if [[ -n "$BASELINE" && "$COVERAGE_SCOPE" == "all" ]]; then
    echo "错误: --baseline 与 coverage_scope=all 互斥（文档 6.4：all 已全量，无需 baseline 增量判定）" >&2
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

# ── 步骤 0.5：降级/模块定位（v0.6 4.1，委托 python collect_environment） ──
# 输出 JSON -> 再用 python 解析为 5 行字段（每行一个，空值保留空行），
# 避免 jq 依赖。后续判定均与 python main() 结构化对齐（见下）。
PY_COLLECT=$(cat <<'PY'
import sys, json
sys.path.insert(0, sys.argv[1])
import run_gate
print(json.dumps(run_gate.collect_environment(sys.argv[2], sys.argv[3] == "1"), ensure_ascii=False))
PY
)
ENV_JSON=$("$PY_EXE" -c "$PY_COLLECT" "$PYTHON_DIR" "$PROJECT" "$AUTO_LOCATE" 2>/dev/null) || {
    echo "错误: run_gate.collect_environment 调用失败（python 核心不可用?）" >&2
    exit 3
}
ENV_FIELDS_TEXT=$("$PY_EXE" -c '
import json, sys
d = json.load(sys.stdin)
def line(k):
    v = d.get(k)
    if k == "degraded":
        return "1" if v else "0"
    return v if v else ""
print(line("degraded"))
print(line("located_module"))
print(line("degraded_reason"))
print(line("suggestion"))
print(line("mvn_dir"))
' <<< "$ENV_JSON") || {
    echo "错误: collect_environment 输出解析失败" >&2
    exit 3
}
mapfile -t ENV_FIELDS <<< "$ENV_FIELDS_TEXT"
if [[ ${#ENV_FIELDS[@]} -lt 5 ]]; then
    echo "错误: collect_environment 输出字段不足" >&2
    exit 3
fi
DEGRADED="${ENV_FIELDS[0]}"
LOCATED_MODULE="${ENV_FIELDS[1]}"
DEGRADED_REASON="${ENV_FIELDS[2]}"
SUGGESTION="${ENV_FIELDS[3]}"
MVN_DIR="${ENV_FIELDS[4]}"

# ambiguous（多候选）：与 python main() 判定完全一致（非降级 + 无 root pom +
# located_module 为空，即 collect_environment 的 ambiguous 分支），stderr 打印
# 建议后 exit 2（stdout 保持纯净 JSON，不产 gate 结果）。
if [[ "$DEGRADED" == "0" && ! -f "$PROJECT/pom.xml" && -z "$LOCATED_MODULE" ]]; then
    echo "错误: $SUGGESTION" >&2
    exit 2
fi
# 唯一候选（非 auto-locate）：WARN + 建议命令（v0.6 4.1 防误判，不自动切换）
if [[ -n "$LOCATED_MODULE" && "$AUTO_LOCATE" == "0" ]]; then
    echo "WARN: $SUGGESTION" >&2
fi

# ── 步骤 1：mvn clean test（在 mvn_dir 执行，强制 clean，仅 full 模式） ──
# run_mvn 门控与 python main() 一致：root 有 pom 或（auto-locate 且唯一候选）
# 才执行 mvn；其余非降级路径（如非 auto-locate 唯一候选）保持 SKIPPED
# （防误判：不自动切换执行目录，mvn_status 交由 run() 产出明确失败原因）。
MVN_STATUS="SKIPPED"
RUN_MVN=0
if [[ "$DEGRADED" == "0" ]]; then
    if [[ -f "$PROJECT/pom.xml" ]] || { [[ "$AUTO_LOCATE" == "1" && -n "$LOCATED_MODULE" ]]; }; then
        RUN_MVN=1
    fi
fi
if [[ "$RUN_MVN" == "1" ]]; then
    if (cd "$MVN_DIR" && mvn clean test >/dev/null 2>&1); then
        MVN_STATUS="SUCCESS"
    else
        MVN_STATUS="FAIL"
    fi
fi

# ── 步骤 2/3/4：调用子脚本收集数据（surefire/jacoco 基于 mvn_dir） ──────
STACK_JSON=""
RESULTS_JSON=""
SPEC_JSON=""
if [[ "$DEGRADED" == "0" ]]; then
    STACK_JSON=$(bash "$SCRIPT_DIR/scan-test-stack.sh" --source "$TEST_SOURCE" --json 2>/dev/null) || STACK_JSON=""
    RESULTS_JSON=$(bash "$SCRIPT_DIR/parse-test-results.sh" \
        --surefire "$MVN_DIR/target/surefire-reports" \
        --jacoco "$MVN_DIR/target/site/jacoco/jacoco.xml" --json 2>/dev/null) || RESULTS_JSON=""
fi
SPEC_JSON=$(bash "$SCRIPT_DIR/scan-spec-annotations.sh" --source "$SOURCE" --spec "$SPEC" --test-source "$TEST_SOURCE" --json 2>/dev/null) || SPEC_JSON=""

# ── JSON 序列化 + 确定性核心：python3 -c 导入 run_gate 兜底 ─────────────
# 与 Python 版字节级等价（同一 run() 实现）。
PY_CORE=$(cat <<'PY'
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
    "coverage_scope": _a(16) or "auto",
    "baseline": _a(17),
    "located_module": _a(18) or None,
    "degraded_reason": _a(19),
    "suggestion": _a(20),
    "mvn_dir": _a(21),
}
result = run_gate.run(inputs)
print(json.dumps(result, ensure_ascii=False, indent=2))
sys.exit(1 if result["status"] == "FAIL" else 0)
PY
)

"$PY_EXE" -c "$PY_CORE" "$PYTHON_DIR" "$SOURCE" "$TEST_SOURCE" "$SPEC" "$PROJECT" "$FEATURE_DIR" "$CONFIG" "$CHECK_ONLY" "$DEGRADED" "$MVN_STATUS" "$IMPACT_OK" "$STACK_JSON" "$RESULTS_JSON" "$SPEC_JSON" "$AUTO_LOCATE" "$COVERAGE_SCOPE" "$BASELINE" "$LOCATED_MODULE" "$DEGRADED_REASON" "$SUGGESTION" "$MVN_DIR"
