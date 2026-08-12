#!/usr/bin/env bash
# 测试技术栈扫描脚本（bash 版）。
#
# 与 scripts/python/scan_test_stack.py 输出字节级等价的 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# 数据提取用 bash 原生工具（find + awk）；JSON 序列化用 python3 -c 兜底，
# 以复用与 Python 版完全一致的 json.dumps 格式（ensure_ascii=False, indent=2）。
#
# 用法: scan-test-stack.sh --source <test_dir> --json

set -euo pipefail

SOURCE=""
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source) SOURCE="$2"; shift 2;;
        --json)   JSON=1; shift;;
        *) echo "用法: $0 --source <test_dir> --json" >&2; exit 2;;
    esac
done

if [[ -z "$SOURCE" ]]; then
    echo "用法: $0 --source <test_dir> --json" >&2
    exit 2
fi
if [[ ! -d "$SOURCE" ]]; then
    echo "错误: --source 目录不存在: $SOURCE" >&2
    exit 2
fi

# ── 1. 遍历 .java 文件（按路径排序），提取发现 ─────────────────────────
# 每行输出: type\tfile\tline\tdetail（detail 已去首尾空白）
FINDINGS=""
while IFS= read -r f; do
    f_tsv=$(awk '
        { gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0) }
        /org\.powermock/ { printf "powermock\t%s\t%d\t%s\n", FILENAME, FNR, $0 }
        /@SpringBootTest/ { printf "springboottest\t%s\t%d\t%s\n", FILENAME, FNR, $0 }
    ' "$f")
    if [[ -n "$f_tsv" ]]; then
        FINDINGS+="$f_tsv"$'\n'
    fi
done < <(find "$SOURCE" -name '*.java' -type f | LC_ALL=C sort)

# ── 2. JSON 序列化：python3 -c 兜底，与 Python 版字节级等价 ─────────────
PY_SERIALIZER=$(cat <<'PY'
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
PY
)

PY_EXE=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -z "$PY_EXE" ]] && { echo "错误: 未找到 python3/python，无法序列化 JSON" >&2; exit 3; }

printf '%s' "$FINDINGS" | "$PY_EXE" -c "$PY_SERIALIZER"
