#!/usr/bin/env python3
"""spec.md 格式验证脚本（Python 版）。

验证 spec.md 是否包含必需的 ``## Business Rules`` 章节（带 R\\d+ 规则编号），
并可选检查 ``### Error Code Definitions`` 章节（缺失仅警告，不影响 valid）。

用法::

    python validate_spec_format.py --spec <spec.md> --json

三语言（py/sh/ps）等价：本脚本定义输出格式（``json.dumps`` +
``ensure_ascii=False`` + ``indent=2``），bash/PowerShell 版本输出字节级等价。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# spec.md 权威源段标题（与 scan_spec_annotations.py 一致）：
# ① ### Functional Requirements 段（FR 顶层锚，新项目默认/唯一必选路径，v0.63 起）
# ② ## Business Rules 段（R\d+，老项目兼容回落，v0.6 行为）
FR_HEADER_RE = re.compile(r"^#{1,6}\s+Functional Requirements", re.IGNORECASE)
BUSINESS_RULES_HEADER_RE = re.compile(r"^#{1,6}\s+.*business[\s_-]+rules", re.IGNORECASE)

# 章节内行首规则编号：- FR-001: / - **FR-001** / - R1: / - **R1** / R1: ...
RULE_LINE_RE = re.compile(r"^\s*[-*]?\s*\**?(FR-\d+|R\d+)\b")

# @DisplayName 子编号正则（可选 --test-source 校验）：@DisplayName("FR-001-R1-...")
DISPLAYNAME_SUB_RE = re.compile(r'@DisplayName\s*\(\s*"FR-(\d+)-R(\d+)-')

# ### Error Code Definitions 章节标题
ERROR_CODE_HEADER_RE = re.compile(r"^#{1,6}\s+Error Code Definitions", re.IGNORECASE)

# 错误码：全大写标识符，如 INVALID_AMOUNT / ACCOUNT_NOT_FOUND
ERROR_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9_]{1,}\b")


def _extract_section_rules(
    lines: list[str], header_re: re.Pattern
) -> tuple[bool, list[str]]:
    """在指定标题段内按出现顺序去重提取规则编号，返回 (段是否存在, 规则列表)。"""
    in_section = False
    section_found = False
    rules: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if header_re.match(stripped):
                in_section = True
                section_found = True
            else:
                if in_section:
                    break
            continue
        if not in_section:
            continue
        m = RULE_LINE_RE.match(line)
        if m:
            rule = m.group(1)
            if rule not in seen:
                rules.append(rule)
                seen.add(rule)
    return section_found, rules


def _extract_rules(text: str) -> tuple[str, list[str]]:
    """返回 ``(rule_source, 规则编号列表)``。

    rule_source（v0.63 2.3 契约，与 scan_spec_annotations 一致）：
    - ``"fr-section"``：spec.md 含 ``### Functional Requirements`` 段（FR-001）；
    - ``"business-rules"``：FR 段缺失但含 ``## Business Rules`` 段（R\\d+，老项目回落）；
    - ``"none"``：两者皆无。
    """
    lines = text.splitlines()
    found, rules = _extract_section_rules(lines, FR_HEADER_RE)
    if found:
        return "fr-section", rules
    found, rules = _extract_section_rules(lines, BUSINESS_RULES_HEADER_RE)
    if found:
        return "business-rules", rules
    return "none", []


def _collect_displayname_subscenes(test_source: str) -> list[tuple[int, int]]:
    """扫描测试源码，收集 @DisplayName("FR-xxx-Rm-...") 的 (FR 序号, R 序号)。

    仅当 rule_source == fr-section 且提供 --test-source 时启用；老 R 体系
    DisplayName 无子编号，不适用（返回空）。
    """
    src = Path(test_source)
    if not src.is_dir():
        return []
    pairs: list[tuple[int, int]] = []
    for java_file in sorted(src.rglob("*.java")):
        try:
            text = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in DISPLAYNAME_SUB_RE.finditer(text):
            pairs.append((int(m.group(1)), int(m.group(2))))
    return pairs


def _extract_error_codes(text: str) -> tuple[bool, list[str]]:
    """返回 (Error Code Definitions 章节是否存在, 按出现顺序去重的错误码列表)。

    只提取错误码表格的第一数据列（错误码列），避免混入噪音：
    - 跳过 HTML 注释行（``<!-- ... -->``，如 OPTIONAL/API 说明）；
    - 表格行只取第一个数据列（``|...|.split('|')`` 首元素为空 -> cells[1]），
      并跳过表头行（含 "error code"）与分隔行（全 -/:）；
    - 非表格行（如列表格式 ``- INVALID_AMOUNT: ...``）取行内第一个全大写标识符。
    """
    lines = text.splitlines()
    section_found = False
    in_section = False
    codes: list[str] = []
    seen: set[str] = set()

    def add(code: str) -> None:
        if code not in seen:
            codes.append(code)
            seen.add(code)

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if ERROR_CODE_HEADER_RE.match(stripped):
                in_section = True
                section_found = True
            else:
                if in_section:
                    break
            continue
        if not in_section:
            continue
        if "<!--" in line:
            continue  # 跳过 HTML 注释行
        if stripped.startswith("|"):
            cells = [c.strip() for c in line.split("|")]
            # 跳过表头行：任一单元格含 "error code"（忽略大小写）
            if any("error code" in c.lower() for c in cells):
                continue
            # 跳过分隔行：所有非空单元格均为 - 或 :
            non_empty = [c for c in cells if c]
            if non_empty and all(re.fullmatch(r"[-:]+", c) for c in non_empty):
                continue
            # 第一个数据列：|...|.split('|') 首元素为空 -> cells[1]
            if len(cells) >= 2 and re.fullmatch(r"[A-Z][A-Z0-9_]+", cells[1]):
                add(cells[1])
            continue
        # 非表格行（列表格式）：取行内第一个全大写标识符
        m = ERROR_CODE_RE.search(line)
        if m:
            add(m.group(0))
    return section_found, codes


def _build_result(
    rule_source: str,
    rules: list[str],
    err_section: bool,
    codes: list[str],
    displayname_sub_pairs: list[tuple[int, int]] | None = None,
) -> dict:
    """基于提取的原始信息组装 JSON 对象。

    v0.66（v0.63 六章 6.2）：规则源 = FR 段优先 / Business Rules 段回落 / 两者
    皆无 -> error；FR 顶层锚全局连续（FR-001, FR-002, ...），Business Rules 段
    R 全局连续；可选校验 @DisplayName 子编号 FR-xxx-Rm 在同 FR 内从 1 连续
    （WARN 不 FAIL）。
    """
    errors: list[str] = []
    warnings: list[str] = []
    if rule_source == "none":
        errors.append(
            "Missing required '### Functional Requirements' or '## Business Rules' section"
        )
    else:
        prefix = "FR-" if rule_source == "fr-section" else "R"
        nums: list[int] = []
        for r in rules:
            m = re.match(rf"{prefix}.*?(\d+)", r)
            if m:
                nums.append(int(m.group(1)))
        if nums:
            mx = max(nums)
            for n in range(1, mx + 1):
                if n not in nums:
                    label = f"FR-{n:03d}" if prefix == "FR-" else f"R{n}"
                    errors.append(f"Rule numbering gap: missing {label}")
    if not err_section:
        warnings.append("No '### Error Code Definitions' section found (optional, skipped)")
    # @DisplayName 子编号 F-xxx-Rm 同 FR 内从 1 连续（WARN，不 FAIL，6.2）
    if displayname_sub_pairs:
        by_fr: dict[int, set[int]] = {}
        for fr_no, r_no in displayname_sub_pairs:
            by_fr.setdefault(fr_no, set()).add(r_no)
        for fr_no in sorted(by_fr):
            subs = by_fr[fr_no]
            mx = max(subs)
            for n in range(1, mx + 1):
                if n not in subs:
                    warnings.append(
                        f"DisplayName 子编号断裂: FR-{fr_no:03d} 缺 R{n}"
                    )
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "rules_found": rules,
        "rule_source": rule_source,
        "error_codes_found": codes,
    }


def validate_spec(spec_path: Path, test_source: str = "") -> dict:
    """验证 spec.md，返回扫描契约 JSON 对象。

    ``test_source`` 可选：提供时额外校验 @DisplayName 子编号连续性（6.2）。
    """
    text = spec_path.read_text(encoding="utf-8")
    rule_source, rules = _extract_rules(text)
    err_section, codes = _extract_error_codes(text)
    displayname_pairs = _collect_displayname_subscenes(test_source) if test_source else []
    return _build_result(rule_source, rules, err_section, codes, displayname_pairs)


def main() -> int:
    parser = argparse.ArgumentParser(description="spec.md 格式验证脚本。")
    parser.add_argument("--spec", required=True, help="spec.md 文件路径")
    parser.add_argument(
        "--test-source",
        default="",
        help="测试源码根目录（可选，v0.66 6.2）：存在时校验 @DisplayName 子编号"
             " FR-xxx-Rm 在同 FR 内从 1 连续（WARN，不 FAIL）",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = parser.parse_args()

    result = validate_spec(Path(args.spec), args.test_source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
