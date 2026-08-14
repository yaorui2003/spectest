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

# spec.md business_rules 章节标题（与 scan_spec_annotations.py 一致）
BUSINESS_RULES_HEADER_RE = re.compile(r"^#{1,6}\s+.*business[\s_-]+rules", re.IGNORECASE)

# 章节内行首规则编号：- R1: / * **R1** / R1: ...
RULE_LINE_RE = re.compile(r"^\s*[-*]?\s*\**?(R\d+)\b")

# ### Error Code Definitions 章节标题
ERROR_CODE_HEADER_RE = re.compile(r"^#{1,6}\s+Error Code Definitions", re.IGNORECASE)

# 错误码：全大写标识符，如 INVALID_AMOUNT / ACCOUNT_NOT_FOUND
ERROR_CODE_RE = re.compile(r"\b[A-Z][A-Z0-9_]{1,}\b")


def _extract_spec_rules(text: str) -> tuple[bool, list[str]]:
    """返回 (business_rules 章节是否存在, 按出现顺序去重的规则编号列表)。"""
    lines = text.splitlines()
    section_found = False
    in_section = False
    rules: list[str] = []
    seen: set[str] = set()
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            if BUSINESS_RULES_HEADER_RE.match(stripped):
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
    rules_section: bool,
    rules: list[str],
    err_section: bool,
    codes: list[str],
) -> dict:
    """基于提取的原始信息组装 JSON 对象（与 bash/PowerShell 内联脚本一致）。"""
    errors: list[str] = []
    warnings: list[str] = []
    if not rules_section:
        errors.append("Missing required '## Business Rules' section")
    else:
        nums: list[int] = []
        for r in rules:
            m = re.match(r"R(\d+)", r)
            if m:
                nums.append(int(m.group(1)))
        if nums:
            mx = max(nums)
            for n in range(1, mx + 1):
                if n not in nums:
                    errors.append(f"Rule numbering gap: missing R{n}")
    if not err_section:
        warnings.append("No '### Error Code Definitions' section found (optional, skipped)")
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "rules_found": rules,
        "error_codes_found": codes,
    }


def validate_spec(spec_path: Path) -> dict:
    """验证 spec.md，返回扫描契约 JSON 对象。"""
    text = spec_path.read_text(encoding="utf-8")
    rules_section, rules = _extract_spec_rules(text)
    err_section, codes = _extract_error_codes(text)
    return _build_result(rules_section, rules, err_section, codes)


def main() -> int:
    parser = argparse.ArgumentParser(description="spec.md 格式验证脚本。")
    parser.add_argument("--spec", required=True, help="spec.md 文件路径")
    parser.add_argument("--json", action="store_true", help="输出 JSON 到 stdout")
    args = parser.parse_args()

    result = validate_spec(Path(args.spec))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
