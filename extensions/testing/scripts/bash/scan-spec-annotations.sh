#!/usr/bin/env bash
# @Spec 注解扫描脚本（bash 版）。
#
# 与 scripts/python/scan_spec_annotations.py 输出字节级等价的 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# v0.6（9.6）：重构为薄壳 —— 全部解析/比对逻辑（含 UNSPEC_CODE 漂移检测）
# 委托给 python 核心 scripts/python/scan_spec_annotations.py，本脚本只做：
#   1. 参数解析与校验（--source/--spec/--json + v0.6 新增 --test-source/
#      --exclude-patterns 透传）
#   2. 定位同目录 ../python/scan_spec_annotations.py
#   3. 原样透传 stdout 与退出码（字节级等价由 python 核心保证）
# python 不可用时 stderr 报错 exit 3。
#
# 用法: scan-spec-annotations.sh --source <java_dir> --spec <spec.md> \
#       [--test-source <test_dir>] [--exclude-patterns <逗号分隔>] --json

set -euo pipefail

SOURCE=""
SPEC=""
TEST_SOURCE=""
EXCLUDE_PATTERNS=""
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source)           SOURCE="$2"; shift 2;;
        --spec)             SPEC="$2"; shift 2;;
        --test-source)      TEST_SOURCE="$2"; shift 2;;
        --exclude-patterns) EXCLUDE_PATTERNS="$2"; shift 2;;
        --json)             JSON=1; shift;;
        *) echo "用法: $0 --source <java_dir> --spec <spec.md> [--test-source <test_dir>] [--exclude-patterns <逗号分隔>] --json" >&2; exit 2;;
    esac
done

if [[ -z "$SOURCE" || -z "$SPEC" ]]; then
    echo "用法: $0 --source <java_dir> --spec <spec.md> [--test-source <test_dir>] [--exclude-patterns <逗号分隔>] --json" >&2
    exit 2
fi
if [[ ! -d "$SOURCE" ]]; then
    echo "错误: --source 目录不存在: $SOURCE" >&2
    exit 2
fi
if [[ ! -f "$SPEC" ]]; then
    echo "错误: --spec 文件不存在: $SPEC" >&2
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_CORE="$SCRIPT_DIR/../python/scan_spec_annotations.py"
PY_EXE=$(command -v python3 2>/dev/null || command -v python 2>/dev/null)
[[ -z "$PY_EXE" ]] && { echo "错误: 未找到 python3/python，无法执行 @Spec 扫描核心" >&2; exit 3; }

# ── 委托 python 核心：原样透传 stdout（--json 恒追加，输出固定为 JSON） ──
ARGS=(--source "$SOURCE" --spec "$SPEC")
if [[ -n "$TEST_SOURCE" ]]; then
    ARGS+=(--test-source "$TEST_SOURCE")
fi
if [[ -n "$EXCLUDE_PATTERNS" ]]; then
    ARGS+=(--exclude-patterns "$EXCLUDE_PATTERNS")
fi
ARGS+=(--json)

exec "$PY_EXE" "$PY_CORE" "${ARGS[@]}"
