#!/usr/bin/env bash
# spec.md 格式验证脚本（bash 版）。
#
# 与 scripts/python/validate_spec_format.py 输出字节级等价的 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# 数据提取用 bash 原生工具（awk）；JSON 序列化用 python3 -c 兜底，
# 以复用与 Python 版完全一致的 json.dumps 格式（ensure_ascii=False, indent=2）。
#
# 用法: validate-spec-format.sh --spec <spec.md> --json

set -euo pipefail

SPEC=""
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --spec) SPEC="$2"; shift 2;;
        --json) JSON=1; shift;;
        *) echo "用法: $0 --spec <spec.md> --json" >&2; exit 2;;
    esac
done

if [[ -z "$SPEC" ]]; then
    echo "用法: $0 --spec <spec.md> --json" >&2
    exit 2
fi
if [[ ! -f "$SPEC" ]]; then
    echo "错误: --spec 文件不存在: $SPEC" >&2
    exit 2
fi

# ── 1. Business Rules 章节存在性 ────────────────────────────────────────
RULES_SECTION=0
if awk '
    /^#/ {
        title = tolower($0)
        if (title ~ /business[[:space:]_ -]+rules/) { found = 1 }
    }
    END { exit !found }
' "$SPEC"; then
    RULES_SECTION=1
fi

# ── 2. 提取规则编号（business_rules 章节内，保持出现顺序，去重） ──────
RULES_DATA=$(awk '
    /^#/ {
        title = tolower($0)
        if (title ~ /business[[:space:]_ -]+rules/) { in_section = 1 }
        else if (in_section) { in_section = 0 }
        next
    }
    in_section {
        if (match($0, /^[[:space:]]*[-*]?[[:space:]]*\**R[0-9]+/)) {
            s = substr($0, RSTART, RLENGTH)
            gsub(/^[[:space:]]*[-*]?[[:space:]]*\**/, "", s)
            if (!(s in seen)) { seen[s] = 1; print s }
        }
    }
' "$SPEC")

# ── 3. Error Code Definitions 章节存在性 ────────────────────────────────
ERROR_SECTION=0
if awk '
    /^#/ {
        title = tolower($0)
        if (title ~ /error[[:space:]_ -]+code[[:space:]_ -]+definitions/) { found = 1 }
    }
    END { exit !found }
' "$SPEC"; then
    ERROR_SECTION=1
fi

# ── 4. 提取错误码（Error Code Definitions 章节内，保持出现顺序，去重） ─
ERROR_DATA=$(awk '
    /^#/ {
        title = tolower($0)
        if (title ~ /error[[:space:]_ -]+code[[:space:]_ -]+definitions/) { in_section = 1 }
        else if (in_section) { in_section = 0 }
        next
    }
    in_section {
        while (match($0, /[A-Z][A-Z0-9_]{1,}/)) {
            s = substr($0, RSTART, RLENGTH)
            if (!(s in seen)) { seen[s] = 1; print s }
            $0 = substr($0, RSTART + RLENGTH)
        }
    }
' "$SPEC")

# ── 5. JSON 序列化：python3 -c 兜底，与 Python 版字节级等价 ─────────────
# stdin 格式：
#   第一行 rules_section 标志（1/0）
#   其后规则编号（每行一个）
#   "===" 分隔
#   下一行 err_section 标志（1/0）
#   其后错误码（每行一个）
PY_SERIALIZER=$(cat <<'PY'
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
PY
)

PY_EXE=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -z "$PY_EXE" ]] && { echo "错误: 未找到 python3/python，无法序列化 JSON" >&2; exit 3; }

{
    printf '%s\n' "$RULES_SECTION"
    printf '%s\n' "$RULES_DATA"
    printf '===\n'
    printf '%s\n' "$ERROR_SECTION"
    printf '%s\n' "$ERROR_DATA"
} | "$PY_EXE" -c "$PY_SERIALIZER"
