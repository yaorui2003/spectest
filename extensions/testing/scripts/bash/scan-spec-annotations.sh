#!/usr/bin/env bash
# @Spec 注解扫描脚本（bash 版）。
#
# 与 scripts/python/scan_spec_annotations.py 输出字节级等价的 JSON
# （spec-kit scripts: frontmatter 三语言等价契约）。
#
# 数据提取用 bash 原生工具（grep/awk/sed/find）；JSON 序列化用
# python3 -c 兜底，以复用与 Python 版完全一致的 json.dumps 格式
# （ensure_ascii=False, indent=2, 键顺序固定）。
#
# 用法: scan-spec-annotations.sh --source <java_dir> --spec <spec.md> --json

set -euo pipefail

SOURCE=""
SPEC=""
JSON=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --source) SOURCE="$2"; shift 2;;
        --spec)   SPEC="$2"; shift 2;;
        --json)   JSON=1; shift;;
        *) echo "用法: $0 --source <java_dir> --spec <spec.md> --json" >&2; exit 2;;
    esac
done

if [[ -z "$SOURCE" || -z "$SPEC" ]]; then
    echo "用法: $0 --source <java_dir> --spec <spec.md> --json" >&2
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

# ── 1. 提取 spec_rules：解析 spec.md 的 business_rules 章节 ─────────────
# 输出：每行一个规则编号（保持出现顺序，去重）。
SPEC_RULES=$(awk '
    /^[[:space:]]*#/ {
        title = tolower($0)
        if (title ~ /business[\t _-]rules/) {
            in_section = 1
        } else if (in_section) {
            in_section = 0
        }
        next
    }
    in_section {
        if (match($0, /^[[:space:]]*[-*]?[[:space:]]*\**R[0-9]+/)) {
            s = substr($0, RSTART, RLENGTH)
            gsub(/^[[:space:]]*[-*]?[[:space:]]*\**/, "", s)
            if (!(s in seen)) {
                seen[s] = 1
                print s
            }
        }
    }
' "$SPEC")

# ── 2. 提取 annotations：遍历 .java 文件（按路径排序） ─────────────────
# 每行输出: rule\tcapability\tdescription\tlocation
# location = 包名.类名.方法名:@Spec行号
JAVA_FILES=()
while IFS= read -r f; do
    JAVA_FILES+=("$f")
done < <(find "$SOURCE" -name '*.java' -type f | LC_ALL=C sort)
ANNOTATIONS=""
if [[ ${#JAVA_FILES[@]} -gt 0 ]]; then
    ANNOTATIONS=$(awk '
        # 输出函数（awk 函数内变量需在参数列表尾部声明为局部变量）
        function flush_method(method,    i, loc) {
            for (i = 1; i <= pn; i++) {
                if (package != "") {
                    loc = package "." class_name "." method ":" p_line[i]
                } else {
                    loc = class_name "." method ":" p_line[i]
                }
                printf "%s\t%s\t%s\t%s\n", p_rule[i], p_cap[i], p_desc[i], loc
            }
            pn = 0
        }
        # 类级 @Spec 兜底：pending 始终未遇方法签名时，用类名作为方法名（与 Python 一致）
        function flush_class_fallback(    i, loc) {
            for (i = 1; i <= pn; i++) {
                if (package != "") {
                    loc = package "." class_name "." class_name ":" p_line[i]
                } else {
                    loc = class_name "." class_name ":" p_line[i]
                }
                printf "%s\t%s\t%s\t%s\n", p_rule[i], p_cap[i], p_desc[i], loc
            }
            pn = 0
        }

        FNR == 1 {
            # 新文件开始：先刷出上一文件残留 pending（类级 @Spec），再重置本文件状态
            if (pn > 0) {
                flush_class_fallback()
            }
            package = ""; class_name = ""; pn = 0
        }

        # 包名
        /^[[:space:]]*package[[:space:]]+/ {
            if (package == "") {
                s = $0
                sub(/^[[:space:]]*package[[:space:]]+/, "", s)
                sub(/[[:space:]]*;.*/, "", s)
                package = s
            }
        }

        # 类名
        /(class|interface|enum|record)[[:space:]]+[A-Za-z_]/ {
            if (class_name == "") {
                if (match($0, /(class|interface|enum|record)[[:space:]]+[A-Za-z_][A-Za-z0-9_]*/)) {
                    s = substr($0, RSTART, RLENGTH)
                    sub(/(class|interface|enum|record)[[:space:]]+/, "", s)
                    class_name = s
                }
            }
        }

        # @Spec 注解（支持 @Repeatable 多注解堆叠：逐条追加到 pending 列表）
        /@Spec[[:space:]]*\(/ {
            rule = ""; cap = ""; desc = ""
            if (match($0, /rule[[:space:]]*=[[:space:]]*"R[0-9]+"/)) {
                s = substr($0, RSTART, RLENGTH)
                sub(/^rule[[:space:]]*=[[:space:]]*"/, "", s); sub(/"$/, "", s); rule = s
            }
            if (match($0, /capability[[:space:]]*=[[:space:]]*"[^"]*"/)) {
                s = substr($0, RSTART, RLENGTH)
                sub(/^capability[[:space:]]*=[[:space:]]*"/, "", s); sub(/"$/, "", s); cap = s
            }
            if (match($0, /description[[:space:]]*=[[:space:]]*"[^"]*"/)) {
                s = substr($0, RSTART, RLENGTH)
                sub(/^description[[:space:]]*=[[:space:]]*"/, "", s); sub(/"$/, "", s); desc = s
            }
            if (rule != "") {
                # 同一行方法签名（如 @Spec(...) public void foo()）：
                # 立即刷出（含先前 pending），不入 pending，与 Python 逐条解析一致
                if ($0 ~ /(public|protected|private)/ && $0 ~ /\(/) {
                    s = $0
                    if (match(s, /(public|protected|private)/)) {
                        s = substr(s, RSTART)
                    }
                    sub(/\(.*/, "", s)
                    if (match(s, /[A-Za-z_][A-Za-z0-9_]*[[:space:]]*$/)) {
                        method = substr(s, RSTART, RLENGTH); sub(/[[:space:]]+$/, "", method)
                        if (pn > 0) {
                            flush_method(method)
                        }
                        if (package != "") {
                            loc = package "." class_name "." method ":" FNR
                        } else {
                            loc = class_name "." method ":" FNR
                        }
                        printf "%s\t%s\t%s\t%s\n", rule, cap, desc, loc
                        next
                    }
                }
                pn++
                p_rule[pn] = rule; p_cap[pn] = cap; p_desc[pn] = desc; p_line[pn] = FNR
            }
        }

        # pending 时查找方法签名（跳过其他注解行），一次性刷出全部 pending
        pn > 0 && $0 !~ /^[[:space:]]*@/ {
            if ($0 ~ /(public|protected|private)/ && $0 ~ /\(/) {
                s = $0; sub(/\(.*/, "", s)
                if (match(s, /[A-Za-z_][A-Za-z0-9_]*[[:space:]]*$/)) {
                    method = substr(s, RSTART, RLENGTH); sub(/[[:space:]]+$/, "", method)
                    flush_method(method)
                }
            }
        }

        # 文件末尾残留 pending（类级 @Spec 未遇方法签名）：类名兜底刷出
        END {
            if (pn > 0) {
                flush_class_fallback()
            }
        }
    ' "${JAVA_FILES[@]}")
fi

# ── 3. JSON 序列化：python3 -c 兜底，与 Python 版字节级等价 ─────────────
# stdin 格式：spec_rules（每行一个）+ "===" + annotations（每行 TSV）。
{
    printf '%s\n' "$SPEC_RULES"
    printf '===\n'
    printf '%s\n' "$ANNOTATIONS"
} | python3 -c '
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
'
