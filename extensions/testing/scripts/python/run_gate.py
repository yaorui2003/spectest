#!/usr/bin/env python3
"""门禁编排脚本 run_gate（Python 版）。

v0.4 核心改造：把 ``speckit.testing.gate`` 门禁的全部确定性逻辑下沉到脚本，
AI 仅读 stdout 判定 JSON，**不能改判、不能补写 gate-result.md、不能跳过步骤**
（直击试点 P0 #1：Agent 伪造覆盖率）。

职责（v0.4 第五章 5.2 的 9 步 + v0.5 步骤 5.5 关键路径对抗校验 + v0.6 改进项）:

0. 检查 ``specs/<feature>/docs/impact-report.md`` 存在（不存在 -> FAIL，堵 P0 #3）
1. ``mvn clean test``（强制 clean，杜绝 target 残留污染，堵 P0 #2；在
   ``--project`` 目录执行，AI 负责传对含 pom.xml 的模块目录）
2. 调 ``scan_test_stack``（forbidden_findings 非空 -> FAIL）
3. 调 ``parse_test_results``（jacoco.xml/surefire-reports 缺失 -> FAIL，不降级；
   消费其 ``source_lines`` 行级数据做 diff coverage 判定）
4. 调 ``scan_spec_annotations``（unimplemented_rules/orphan_annotations 非空 -> FAIL；
   读取其 ``unspec_codes`` 漂移告警，MEDIUM 不阻断）
5. 内联解析 test 源码 ``@DisplayName("Rn-...")`` 算对齐数
5.5. 关键路径对抗校验（v0.5 新增）：读 impact-report 逐规则 risk + 检测
    ``@DisplayName("Rn-对抗-...")``；``critical_path_required=true`` 且 high
    风险规则 0 对抗用例 -> FAIL（configurable，false 降级跳过）
6. 读 ``impact-report.md`` 的 ``risk_level`` + 读 ``testing-config.yml`` 套风险档阈值
7. 逐项比对覆盖率/通过率/Spec 覆盖率与阈值（**diff coverage**：只判 MR/工作区
   变更行覆盖率，``git diff --unified=0`` 提取变更行、JaCoCo 行级数据判覆盖；
   git 不可用回退全量聚合阈值；无变更行跳过不判）
8. **脚本直接写 ``specs/<feature>/docs/gate-result.md``** + stdout 输出判定 JSON
   （写前只读正则检查 SOFT 段标题，缺失 WARN + soft_missing=true 不改判；旧文件
   中 AI 手写的 SOFT 段追加保留，避免覆盖后 WARN 复现）

降级模式：``collect_environment`` 判定——无 ``java``/``mvn`` 可执行，**或
``--project`` 目录无 ``pom.xml``**（AI 应先 ``find . -name pom.xml`` 定位模块
目录再传对 ``--project``；传错即降级并提示）时，降级为仅做 ``@Spec`` 静态扫描
（步骤 4 + 6 的 Spec 覆盖率阈值判定），跳过步骤 1-3/5。这是唯一降级场景；
Java 项目缺 JaCoCo/surefire 报告**不降级，直接 FAIL**。

``--check-only`` 子模式：供 implement 第 4.5 阶段（对抗测试）调用，只跑步骤 1-8
（含 5.5 对抗校验）不写 gate-result.md，输出当前覆盖率与阈值差距 JSON，
供 AI 决定补测方向。

用法::

    python run_gate.py --source <java_dir> --test-source <test_dir> --spec <spec.md> \
        --project <module_dir> --feature-dir <specs/<feature>> --config <testing-config.yml> \
        [--check-only] [--diff-threshold <pct>] [--diff-base <branch>] --json

三语言（py/sh/ps）等价：本脚本的 ``run()`` 是**唯一确定性核心**（阈值比对 + 判定
+ 写 gate-result.md + JSON 序列化）；``collect_environment()`` 是环境收集的唯一
实现（java/mvn 检测）；bash/PowerShell 版本负责调用/透传；通过 ``python3 -c``
导入本模块调用 ``run()``，输出与 Python 版字节级等价（复用
``json.dumps(result, ensure_ascii=False, indent=2)`` 格式）。
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

# @DisplayName 内联解析正则：@DisplayName("Rn-<描述>")，提取规则编号
DISPLAYNAME_RE = re.compile(r'@DisplayName\s*\(\s*"R(\d+)-')

# 对抗用例识别：@DisplayName("Rn-对抗-...")，提取规则编号（v0.5 步骤 5.5）
ADVERSARIAL_RE = re.compile(r'@DisplayName\s*\(\s*"R(\d+)-对抗')

# diff coverage：git diff hunk 头解析（U0 时新文件变更行 = c..c+d-1）
# @@ -a,b +c,d @@；b/d 缺省为 1（单行）。MULTILINE：hunk 行在 diff 输出中间
_DIFF_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)

# diff coverage：java 文件 package 声明（完整包名，非顶层包）
_PACKAGE_DECL_RE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)

# AI 交叉验证段标题（v0.6 5.1/9.3 只读检查 + 写 gate-result.md 保留 AI
# 手写段共用）。行首锚定 MULTILINE：只认独立标题行，杜绝脚本 WARN 文案自命中
# （脚本写出的文本不含完整标题行 -> 同 fixture 二次运行 soft_missing 稳定）。
_SOFT_HEADER_RE = re.compile(r"^##\s+AI 交叉验证（SOFT，不影响判定）\s*$", re.MULTILINE)


def collect_environment(project: str) -> dict:
    """环境收集（v0.6 降级判定，三语言共享的唯一实现）。

    返回 ``{"degraded": bool, "degraded_reason": str}``。

    语义：
    - 无 java/mvn（shutil.which）：degraded=True，degraded_reason="no java/mvn on PATH"；
    - 有 java+mvn 但 ``--project`` 目录无 ``pom.xml``：degraded=True，
      degraded_reason="pom.xml not found at <path>（AI 应先 find . -name pom.xml
      定位模块目录再传对 --project）"；
    - 有 java+mvn 且 ``--project`` 有 ``pom.xml``：degraded=False。
    """
    has_java = shutil.which("java") is not None
    has_mvn = shutil.which("mvn") is not None
    if not (has_java and has_mvn):
        return {"degraded": True, "degraded_reason": "no java/mvn on PATH"}
    if not (Path(project) / "pom.xml").is_file():
        return {
            "degraded": True,
            "degraded_reason": (
                f"pom.xml not found at {project}"
                "（AI 应先 find . -name pom.xml 定位模块目录再传对 --project）"
            ),
        }
    return {"degraded": False, "degraded_reason": ""}


def _compute_diff_coverage(mvn_dir: str, diff_base: str, source_lines: list) -> dict:
    """计算 MR/工作区变更行覆盖率（diff coverage，替代 v0.6 9.4 作用域方案）。

    git diff 行号提取：
    - 无 ``diff_base``：``git diff --unified=0 HEAD``（工作区 vs HEAD）；
    - 有 ``diff_base <branch>``：先 ``git merge-base <branch> HEAD`` 得 base，再
      ``git diff --unified=0 <base>``（MR 场景）。
    解析 hunk 头 ``@@ -a,b +c,d @@``：U0 时新文件变更行 = c..c+d-1（d=0 为纯删除
    行不算）。

    **多模块工程（修复 1）**：git diff 输出路径始终相对**仓库根**（如
    ``backend/src/main/java/...``），而 ``--project`` 可能指向模块子目录
    （``backend/``）。因此用 ``git rev-parse --show-toplevel``（cwd=mvn_dir）定位
    ``repo_root``；git diff / git ls-files 在 cwd=mvn_dir 执行但**不带 pathspec
    过滤**，收集全部变更 java 文件相对 repo_root 的路径；文件读取（解析 package
    声明）用 ``repo_root / rel``。修复前 pathspec 相对 cwd 解析为
    ``backend/backend/...`` 不匹配 -> 空 diff -> percent=None 静默跳过（P0）。

    **只统计生产代码（修复 2）**：过滤掉路径含 ``/src/test/`` 的 java 文件
    （jacoco 默认不插桩测试类，测试文件无行数据会被"声明即承诺"误判未覆盖 ->
    纯补测试提交被 gate 阻断）。过滤后无生产代码变更 -> ``mode="no_changes"``。

    **未跟踪新文件（修复 3）**：``git diff --name-only`` 不含工作区未跟踪文件；
    用 ``git ls-files --others --exclude-standard`` 合并。未跟踪 java 文件无 HEAD
    版本可 diff，其所有行（1..N，读文件行数）视为变更行——新文件全量计入。

    **diff 提取失败（修复 5）**：java_files 非空但提取后 changed 为空（pathspec
    全不匹配等）-> 返回 ``mode="fallback_all"``（保守，宁严勿松），而非静默
    ``mode="diff"``+percent=None。

    文件映射：对每个变更 java 文件解析 package 声明（``^\s*package\s+([\w.]+)\s*;``）
    + 文件名构造 key（``package.replace('.','/') + "/" + basename``，如
    ``com/example/AccountService.java``），与 source_lines 的 key 匹配；找不到
    （未编译/无 jacoco 数据）-> 该文件所有变更行计为未覆盖（声明即承诺，保守方向）。

    返回：
    - ``{"mode": "diff", "base": <base 描述>, "total_lines": n, "covered_lines": m,
       "percent": x|None}``；
    - ``{"mode": "fallback_all", ...}``：git 不可用/非 git 仓库/超时/失败/提取失败；
    - ``{"mode": "no_changes", ...}``：git 正常但无生产代码 java 变更行。
    """
    empty = {"mode": "fallback_all", "base": "", "total_lines": 0, "covered_lines": 0, "percent": None}

    # 0. 定位仓库根（修复 1）：git 命令 cwd 可保持 mvn_dir，但 pathspec 与文件
    #    读取必须用相对 repo_root 的路径。非 git 仓库 -> fallback_all。
    try:
        tr = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=mvn_dir, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return empty
    if tr.returncode != 0:
        return empty
    repo_root = tr.stdout.strip()
    if not repo_root:
        return empty

    # 1. 定位 base（无 diff_base 用 HEAD）
    if diff_base:
        try:
            mb = subprocess.run(
                ["git", "merge-base", diff_base, "HEAD"],
                cwd=mvn_dir, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return empty
        if mb.returncode != 0:
            return empty
        base = (mb.stdout.strip() or diff_base)[:12]
    else:
        base = "HEAD"

    # 2. 变更 java 文件列表（相对 repo_root；不带 pathspec 过滤，修复 1）
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", base],
            cwd=mvn_dir, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return empty
    if proc.returncode != 0:
        return empty
    java_files = [line.strip() for line in proc.stdout.splitlines() if line.strip().endswith(".java")]

    # 3. 未跟踪 java 文件（修复 3）：git ls-files --others --exclude-standard
    #    在 cwd=repo_root 执行（输出相对 repo_root，与 diff 路径基准一致；
    #    cwd=mvn_dir 时输出相对 cwd，会与 diff 的 repo_root 相对路径错位）
    try:
        ut = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repo_root, capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return empty
    if ut.returncode != 0:
        return empty
    untracked = [line.strip() for line in ut.stdout.splitlines() if line.strip().endswith(".java")]
    java_files = list(dict.fromkeys(java_files + untracked))

    # 只统计生产代码（修复 2）：过滤 src/test/ 路径
    prod_files = [rel for rel in java_files if "/src/test/" not in "/" + rel]
    if not prod_files:
        return {"mode": "no_changes", "base": base, "total_lines": 0, "covered_lines": 0, "percent": None}

    # 4. 逐文件提取变更行号：{相对 repo_root 路径: set(行号)}
    changed: dict[str, set[int]] = {}
    for rel in prod_files:
        if rel in untracked:
            # 未跟踪新文件：所有行视为变更（1..N）
            n = len(_safe_read(Path(repo_root) / rel).splitlines())
            if n > 0:
                changed[rel] = set(range(1, n + 1))
            continue
        try:
            dp = subprocess.run(
                ["git", "diff", "--unified=0", base, "--", rel],
                cwd=repo_root, capture_output=True, text=True, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return empty
        if dp.returncode != 0:
            return empty
        lines: set[int] = set()
        for hunk in _DIFF_HUNK_RE.finditer(dp.stdout):
            start = int(hunk.group(2))
            count = int(hunk.group(3)) if hunk.group(3) else 1
            if count > 0:
                lines.update(range(start, start + count))
        if lines:
            changed[rel] = lines

    # 5. 提取失败（修复 5）：java_files 非空但 changed 为空 -> fallback_all
    if not changed:
        return empty

    # 6. source_lines 索引：key -> {nr: ci}
    line_index: dict[str, dict[int, int]] = {}
    for entry in source_lines:
        if not isinstance(entry, dict):
            continue
        key = entry.get("key")
        if not key:
            continue
        per_line = line_index.setdefault(key, {})
        for ln in entry.get("lines") or []:
            nr = ln.get("nr")
            if isinstance(nr, int):
                per_line[nr] = int(ln.get("ci", 0))

    # 7. 汇总：变更行覆盖 = 行存在且 ci>0；缺失（未编译/无数据）视为未覆盖
    total_lines = 0
    covered_lines = 0
    for rel, linenos in changed.items():
        total_lines += len(linenos)
        pkg_m = _PACKAGE_DECL_RE.search(_safe_read(Path(repo_root) / rel))
        if pkg_m is None:
            continue  # 无 package 声明：全部变更行视为未覆盖
        key = pkg_m.group(1).replace(".", "/") + "/" + Path(rel).name
        per_line = line_index.get(key, {})
        for nr in linenos:
            if per_line.get(nr, 0) > 0:
                covered_lines += 1
    percent = round(covered_lines / total_lines * 100) if total_lines > 0 else None
    return {
        "mode": "diff",
        "base": base,
        "total_lines": total_lines,
        "covered_lines": covered_lines,
        "percent": percent,
    }


def _safe_read(path: Path) -> str:
    """读取文件内容，失败返回空串（diff 文件可能已被删除/不可读）。"""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_affected_rules(impact_path: Path) -> dict[str, str]:
    """从 impact-report.md 解析逐规则 risk（rule -> high/medium/low）。

    容错：解析失败返回空 dict（不致 gate FAIL，仅跳过对抗硬判）。
    逐行扫描 "- rule: Rn" 与后续 "risk: level" 配对。
    """
    try:
        text = impact_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    rules: dict[str, str] = {}
    current_rule = None
    for line in text.splitlines():
        m = re.match(r'\s*-\s*rule:\s*(R\d+)', line)
        if m:
            current_rule = m.group(1)
            continue
        if current_rule:
            m = re.match(r'\s*risk:\s*(high|medium|low)', line)
            if m:
                rules[current_rule] = m.group(1)
                current_rule = None
    return rules


def _count_adversarial_tests(test_source: str) -> dict[str, int]:
    """扫描测试源码，统计每规则的对抗用例数（@DisplayName("Rn-对抗-...")）。"""
    counts: dict[str, int] = {}
    src = Path(test_source)
    if not src.is_dir():
        return counts
    for java_file in sorted(src.rglob("*.java")):
        try:
            text = java_file.read_text(encoding="utf-8")
        except OSError:
            continue
        for m in ADVERSARIAL_RE.finditer(text):
            rule = "R" + m.group(1)
            counts[rule] = counts.get(rule, 0) + 1
    return counts

# 默认阈值（与 config/testing-config.template.yml 的 gate 段一致，配置缺失时兜底）
_DEFAULT_UNIT = {
    "line_coverage_min": 80,
    "branch_coverage_min": 70,
    "method_coverage_min": 80,
    "instruction_coverage_min": 85,
    "complexity_coverage_min": 70,
    "pass_rate_min": 100,
}
_DEFAULT_CONTRACT_PASS_RATE = 95
_DEFAULT_SPEC_RULE_COVERAGE_MIN = 100
_DEFAULT_REQUIRE_DISPLAYNAME_MATCH = True


# ── 配置与风险等级解析 ───────────────────────────────────────────────────────


def _load_config(path: Path) -> dict:
    """最小 YAML 子集解析（嵌套 map + 标量 int/bool/str）。

    只解析 testing-config.yml 用到的结构：两空格缩进的嵌套键值对 + 注释（#）。
    不依赖 PyYAML，保证 py/sh/ps 三语言执行环境一致。
    """
    cfg: dict = {}
    stack: list[tuple[int, dict]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return cfg
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        m = re.match(r"^(\S+?):\s*(.*)$", line.strip())
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if val == "":
            node: dict = {}
            parent = stack[-1][1] if stack else None
            if parent is not None:
                parent[key] = node
            else:
                cfg[key] = node
            stack.append((indent, node))
        else:
            low = val.lower()
            if low == "true":
                v = True
            elif low == "false":
                v = False
            elif re.fullmatch(r"-?\d+", val):
                v = int(val)
            elif re.fullmatch(r"-?\d+\.\d+", val):
                v = float(val)
            else:
                v = val.strip('"\'')
            parent = stack[-1][1] if stack else None
            if parent is not None:
                parent[key] = v
            else:
                cfg[key] = v
    return cfg


def _parse_risk_level(impact_path: Path) -> str:
    """从 impact-report.md 提取整体 risk_level（high/medium/low），缺省 default。"""
    try:
        text = impact_path.read_text(encoding="utf-8")
    except OSError:
        return "default"
    m = re.search(r"risk_level\s*[:=]\s*(high|medium|low)", text)
    return m.group(1) if m else "default"


def _resolve_thresholds(cfg: dict, risk_level: str) -> dict:
    """合并 gate 默认阈值与 risk_overrides.<risk> 覆盖（覆盖值优先），返回生效阈值。"""
    gate = cfg.get("gate", {}) if isinstance(cfg.get("gate"), dict) else {}
    unit = gate.get("unit_test", {}) if isinstance(gate.get("unit_test"), dict) else {}
    contract = (
        gate.get("contract_test", {}) if isinstance(gate.get("contract_test"), dict) else {}
    )
    trace = (
        gate.get("spec_traceability", {})
        if isinstance(gate.get("spec_traceability"), dict)
        else {}
    )
    thr = {
        "line_coverage_min": unit.get("line_coverage_min", _DEFAULT_UNIT["line_coverage_min"]),
        "branch_coverage_min": unit.get("branch_coverage_min", _DEFAULT_UNIT["branch_coverage_min"]),
        "method_coverage_min": unit.get("method_coverage_min", _DEFAULT_UNIT["method_coverage_min"]),
        "instruction_coverage_min": unit.get(
            "instruction_coverage_min", _DEFAULT_UNIT["instruction_coverage_min"]
        ),
        "complexity_coverage_min": unit.get(
            "complexity_coverage_min", _DEFAULT_UNIT["complexity_coverage_min"]
        ),
        "unit_pass_rate_min": unit.get("pass_rate_min", _DEFAULT_UNIT["pass_rate_min"]),
        "contract_pass_rate_min": contract.get(
            "pass_rate_min", _DEFAULT_CONTRACT_PASS_RATE
        ),
        "spec_rule_coverage_min": trace.get(
            "spec_rule_coverage_min", _DEFAULT_SPEC_RULE_COVERAGE_MIN
        ),
        "require_displayname_match": trace.get(
            "require_displayname_match", _DEFAULT_REQUIRE_DISPLAYNAME_MATCH
        ),
    }
    overrides = cfg.get("risk_overrides", {})
    if isinstance(overrides, dict) and risk_level in overrides:
        ov = overrides[risk_level]
        if isinstance(ov, dict):
            ov_unit = ov.get("unit_test", {}) if isinstance(ov.get("unit_test"), dict) else {}
            ov_contract = (
                ov.get("contract_test", {}) if isinstance(ov.get("contract_test"), dict) else {}
            )
            key_map = {
                "line_coverage_min": "line_coverage_min",
                "branch_coverage_min": "branch_coverage_min",
                "method_coverage_min": "method_coverage_min",
                "instruction_coverage_min": "instruction_coverage_min",
                "complexity_coverage_min": "complexity_coverage_min",
                "pass_rate_min": "unit_pass_rate_min",
            }
            for k, dk in key_map.items():
                if k in ov_unit:
                    thr[dk] = ov_unit[k]
            if "pass_rate_min" in ov_contract:
                thr["contract_pass_rate_min"] = ov_contract["pass_rate_min"]
    return thr


def _parse_displayname_match(test_source: str, spec_coverage: dict) -> dict:
    """内联解析 test 源码 @DisplayName("Rn-...")，与 @Spec 已注解规则交叉对齐（双向）。

    正向（DisplayName->@Spec）：total = @DisplayName 中带规则编号的条数；
    aligned = 其中规则已出现在 @Spec annotated_rules 的条数；
    mismatch_count = total - aligned（测试指向不存在的 @Spec 规则）。
    反向（@Spec->DisplayName）：untested_spec_rules = 有 @Spec 注解但无任何
    @DisplayName 测试的规则（按 spec_rules 顺序，保证输出确定性）。
    """
    annotated = set((spec_coverage.get("annotated_rules") or {}).keys())
    spec_rules = spec_coverage.get("spec_rules") or []
    total = 0
    aligned = 0
    displayname_rules: set[str] = set()
    src = Path(test_source)
    if src.is_dir():
        for java_file in sorted(src.rglob("*.java")):
            try:
                text = java_file.read_text(encoding="utf-8")
            except OSError:
                continue
            for m in DISPLAYNAME_RE.finditer(text):
                rule = "R" + m.group(1)
                total += 1
                displayname_rules.add(rule)
                if rule in annotated:
                    aligned += 1
    untested_spec_rules = [
        r for r in spec_rules if r in annotated and r not in displayname_rules
    ]
    return {
        "aligned": aligned,
        "total": total,
        "mismatch_count": total - aligned,
        "untested_spec_rules": untested_spec_rules,
    }


# ── gate-result.md 渲染 ──────────────────────────────────────────────────────


def _format_gate_result_md(result: dict) -> str:
    """按 v0.4 5.4 格式生成 gate-result.md 内容（脚本直接写，AI 不能改判）。

    v0.6 调整：执行环境段展示降级原因（degraded_reason），单测明细段以
    diff coverage 行为主（diff / no_changes / fallback_all / 降级 N/A 四态），
    末尾保留漂移告警段（MEDIUM 不阻断）与 SOFT 状态行（5.1/9.3）。
    """
    status = result["status"]
    mode = result["mode"]
    mvn = result["mvn_clean_test"]
    risk = result["risk_level"]
    unit = result["unit_tests"]
    contract = result["contract_tests"]
    cov = result["coverage"]
    spec = result["spec_coverage"]
    disp = result["displayname_match"]
    thr = {t["metric"]: t["threshold"] for t in result["threshold_results"]}

    lines: list[str] = []
    lines.append(f"## Gate Result: {status}")
    lines.append("")
    lines.append("### 执行环境")
    lines.append(f"- mvn clean test: {mvn}")
    if mode == "degraded":
        lines.append("- 降级模式: 降级模式（无 java/mvn 或 --project 目录无 pom.xml）")
        lines.append("- 说明: 无 java/mvn 或 --project 无 pom.xml，跳过单测/契约测试执行，仅做 @Spec 静态扫描")
        lines.append(f"- 降级原因: {result.get('degraded_reason', '')}")
    else:
        lines.append("- target 清理: 已清理（杜绝残留污染）")
    lines.append("")
    lines.append("### 单测明细")
    lines.append(f"- 总数: {unit['total']} | 通过: {unit['passed']} | 失败: {unit['failed']}")
    # diff coverage 行（替代行覆盖率行；四态：diff / no_changes / fallback_all / N/A）
    diff = result.get("diff_coverage")
    diff = diff if isinstance(diff, dict) else {}
    diff_mode = diff.get("mode", "N/A")
    diff_thr = thr.get("diff_coverage", 0)
    if diff_mode == "diff":
        pct = diff.get("percent")
        lines.append(
            f"- diff coverage: {pct}% (变更行 {diff.get('covered_lines', 0)}/{diff.get('total_lines', 0)},"
            f" base: {diff.get('base', '')}) | 阈值 >= {diff_thr}%"
        )
    elif diff_mode == "no_changes":
        lines.append("- diff coverage: 无 Java 变更行，跳过（无承诺）")
    elif diff_mode == "fallback_all":
        lines.append("- diff coverage: 无 git，回退全量阈值判定")
    else:
        lines.append("- diff coverage: N/A（降级模式）")
    lines.append(f"- 通过率: {unit['pass_rate']}% (阈值 >= {thr.get('unit_pass_rate', 0)}%)")
    lines.append("")
    lines.append("### 契约测试明细")
    lines.append(
        f"- 总数: {contract['total']} | 通过: {contract['passed']}"
        f" | 失败: {contract['failed']} | 通过率: {contract['pass_rate']}%"
    )
    lines.append("")
    lines.append("### Spec 规则覆盖矩阵")
    lines.append(
        f"- 规则总数: {len(spec.get('spec_rules', []))}"
        f" | 已注解数: {len(spec.get('annotated_rules', {}))}"
        f" | 未实现规则: {spec.get('unimplemented_rules', [])}"
        f" | 孤儿注解: {spec.get('orphan_annotations', [])}"
    )
    lines.append(f"- DisplayName 对齐数: {disp['aligned']} / {disp['total']}")
    if disp.get("untested_spec_rules"):
        lines.append(f"- 有 @Spec 无 @DisplayName 测试的规则: {disp['untested_spec_rules']}")
    lines.append("")
    lines.append("### 关键路径对抗覆盖")
    if result.get("mode") == "degraded":
        lines.append("- 未启用（降级模式，无 Java 环境跳过对抗校验）")
    else:
        adv = result["adversarial_coverage"]
        lines.append(f"- critical_path_required: {adv['critical_path_required']}")
        lines.append(f"- high 风险规则: {adv['high_risk_rules']}")
        lines.append(f"- 对抗用例分布: {adv['adversarial_counts']}")
        if adv["missing"]:
            lines.append(f"- 缺对抗用例的 high 风险规则: {adv['missing']}")
    lines.append("")
    # 漂移告警段（v0.6 9.6：UNSPEC_CODE，MEDIUM 不阻断）
    spec_cov = result.get("spec_coverage")
    spec_cov = spec_cov if isinstance(spec_cov, dict) else {}
    unspec = spec_cov.get("unspec_codes")
    if isinstance(unspec, list) and unspec:
        lines.append("### 漂移告警（MEDIUM，不阻断）")
        for item in unspec:
            lines.append(f"- {item}")
        lines.append("")
    # SOFT 状态行（v0.6 5.1/9.3：只读检查，缺段 WARN 不改判）
    # 注意：WARN 文案禁止包含完整 SOFT 标题行，避免脚本写出的文本被
    # 自身 re.search 命中（自满足 bug -> soft_missing 二次运行翻转）。
    if result.get("soft_missing"):
        lines.append("### SOFT 检查")
        lines.append(
            "- WARN: SOFT 交叉验证标题缺失（现有 gate-result.md 无 AI 手写"
            " 步骤 3 交叉验证段；不影响判定，请 AI 补段后重跑，仅补段不重跑 mvn）"
        )
        lines.append("")
    lines.append("### 判定依据")
    lines.append(f"- risk_level: {risk}")
    if risk in ("high", "medium", "low"):
        lines.append(f"- 套用阈值来源: testing-config.yml risk_overrides.{risk}")
    else:
        lines.append("- 套用阈值来源: testing-config.yml gate 默认阈值")
    if result["fail_reasons"]:
        lines.append("")
        lines.append("### 失败原因与修复建议（仅 FAIL 时）")
        for reason in result["fail_reasons"]:
            lines.append(f"- [FAIL] {reason}")
    lines.append("")
    return "\n".join(lines)


# ── 确定性核心（唯一实现，三语言共享） ─────────────────────────────────────


def run(inputs: dict) -> dict:
    """确定性核心：输入已收集的环境数据，返回完整判定 JSON，并按需写 gate-result.md。

    inputs 键：
      source / test_source / spec / project / feature_dir / config：路径
      check_only：bool，为 True 时不写 gate-result.md
      degraded：bool（环境收集时已判定）
      mvn_status：'SUCCESS' | 'FAIL' | 'SKIPPED'
      impact_ok：bool
      scan_stack / parse_results / scan_spec：子脚本输出 dict（或 None）
      diff_threshold：变更行覆盖率阈值（%）；空/None 回落 config
        gate.diff_coverage_threshold，仍无则 80
      diff_base：MR 对比分支；空/None 回落 config gate.diff_base，仍无则 ""
        （工作区 vs HEAD）
    """
    source = inputs.get("source", "")
    test_source = inputs.get("test_source", "")
    project = inputs.get("project", "")
    feature_dir = inputs.get("feature_dir", "")
    config_path = inputs.get("config", "")
    check_only = bool(inputs.get("check_only", False))
    degraded = bool(inputs.get("degraded", False))
    mvn_status = inputs.get("mvn_status", "SKIPPED")
    impact_ok = bool(inputs.get("impact_ok", False))
    scan_stack = inputs.get("scan_stack")
    parse_results = inputs.get("parse_results")
    scan_spec = inputs.get("scan_spec")
    diff_threshold = inputs.get("diff_threshold")
    diff_base = str(inputs.get("diff_base") or "")
    degraded_reason = str(inputs.get("degraded_reason") or "")

    # diff coverage 默认值（degraded 模式 N/A；非降级时在步骤 7 计算覆盖）
    diff_coverage = {"mode": "N/A", "base": "", "total_lines": 0, "covered_lines": 0, "percent": None}

    fail_reasons: list[str] = []

    # 步骤 0：impact-report.md 存在性（堵 P0 #3：钩子链断裂）
    if not impact_ok:
        fail_reasons.append(
            "impact 未执行，请先运行 speckit.testing.impact"
            "（缺少 specs/<feature>/docs/impact-report.md）"
        )

    impact_path = Path(feature_dir) / "docs" / "impact-report.md"
    risk_level = _parse_risk_level(impact_path)
    cfg = _load_config(Path(config_path))
    thr = _resolve_thresholds(cfg, risk_level)

    # config 可写默认、CLI 可覆盖：CLI 非空用 CLI，空则回落 config
    # gate.diff_coverage_threshold / gate.diff_base，仍无则 80 / ""。
    # bash/ps 透传空字符串即触发回落，三语言行为一致。
    gate_cfg = cfg.get("gate", {}) if isinstance(cfg.get("gate"), dict) else {}
    if diff_threshold is None or diff_threshold == "":
        diff_threshold = gate_cfg.get("diff_coverage_threshold", 80)
    try:
        diff_threshold = int(diff_threshold)
    except (TypeError, ValueError):
        diff_threshold = 80  # config 非法值兜底默认
    if not diff_base:
        diff_base = str(gate_cfg.get("diff_base") or "")

    # 步骤 4：@Spec 扫描（full 与 degraded 都执行）
    spec_coverage = scan_spec if isinstance(scan_spec, dict) else {}
    for rule in spec_coverage.get("unimplemented_rules", []):
        fail_reasons.append(f'unimplemented_rules: {rule} -> 在实现方法上补 @Spec(rule="{rule}")')
    for ann in spec_coverage.get("orphan_annotations", []):
        fail_reasons.append(
            f"orphan_annotations: {ann.get('rule', '?')} @ {ann.get('location', '?')}"
            " -> 修正规则编号或删除该注解"
        )

    # 空数据默认值（degraded 模式全为 0）
    unit_tests = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    contract_tests = {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0}
    coverage = {"line": 0, "branch": 0, "method": 0, "instruction": 0, "complexity": 0}
    displayname_match = {"aligned": 0, "total": 0, "mismatch_count": 0, "untested_spec_rules": []}

    if not degraded:
        # 步骤 1：mvn clean test
        if mvn_status == "FAIL":
            fail_reasons.append("mvn clean test 失败 -> 修复编译/测试错误后重新运行门禁")
        elif mvn_status == "SKIPPED":
            fail_reasons.append(
                "mvn clean test 未执行（SKIPPED）-> 请确认 --project 指向含 pom.xml"
                " 的模块目录（AI 应先 find . -name pom.xml 定位）后重跑"
            )

        # 步骤 3：报告存在性（不降级；缺失即 FAIL；基于 --project 的 target/）
        surefire_dir = Path(project) / "target" / "surefire-reports"
        jacoco_file = Path(project) / "target" / "site" / "jacoco" / "jacoco.xml"
        if not (surefire_dir.is_dir() and any(surefire_dir.glob("*.xml"))):
            fail_reasons.append(
                "surefire-reports 缺失（未配置 maven-surefire-plugin?）"
                " -> 在 pom.xml 的 <plugins> 添加 maven-surefire-plugin 后重跑"
            )
        if not jacoco_file.is_file():
            fail_reasons.append(
                "jacoco.xml 缺失（未配置 jacoco-maven-plugin?）"
                " -> 在 pom.xml 的 <plugins> 添加 jacoco-maven-plugin"
                "（prepare-agent + report）后重跑"
            )

        # 步骤 2：技术栈硬校验
        if isinstance(scan_stack, dict):
            findings = scan_stack.get("forbidden_findings", [])
            if findings:
                detail = "; ".join(
                    f"{f.get('file', '?')}:{f.get('line', '?')} {f.get('type', '?')}"
                    for f in findings
                )
                fail_reasons.append(f"forbidden_findings: {len(findings)} 项 -> {detail}")

        # 填充 parse_test_results 数据
        if isinstance(parse_results, dict):
            unit_tests = parse_results.get("unit_tests") or unit_tests
            contract_tests = parse_results.get("contract_tests") or contract_tests
            pr_cov = parse_results.get("coverage") or {}
            coverage = {
                "line": pr_cov.get("line_coverage", 0),
                "branch": pr_cov.get("branch_coverage", 0),
                "method": pr_cov.get("method_coverage", 0),
                "instruction": pr_cov.get("instruction_coverage", 0),
                "complexity": pr_cov.get("complexity_coverage", 0),
            }

        # 步骤 5：@DisplayName 对齐（degraded 无单测可读，跳过）
        displayname_match = _parse_displayname_match(test_source, spec_coverage)
        if thr["require_displayname_match"]:
            if displayname_match["mismatch_count"] > 0:
                fail_reasons.append(
                    f"displayname_mismatch: {displayname_match['mismatch_count']}"
                    " 个 @DisplayName 未与 @Spec 规则对齐"
                )
            untested = displayname_match.get("untested_spec_rules", [])
            if untested:
                fail_reasons.append(
                    f"spec_rules_without_test: {len(untested)} 条规则有 @Spec"
                    f" 但无 @DisplayName 测试 -> {untested}"
                )

    # 步骤 5.5：关键路径对抗校验（v0.5 新增，configurable）
    adversarial_cfg = cfg.get("adversarial", {}) if isinstance(cfg.get("adversarial"), dict) else {}
    critical_path_required = bool(adversarial_cfg.get("critical_path_required", True))
    affected_rules = _parse_affected_rules(impact_path) if not degraded else {}
    adversarial_counts = _count_adversarial_tests(test_source) if not degraded else {}
    high_risk_rules = [r for r, risk in affected_rules.items() if risk == "high"]
    missing_adversarial = [r for r in high_risk_rules if adversarial_counts.get(r, 0) == 0]

    adversarial_coverage = {
        "critical_path_required": critical_path_required,
        "high_risk_rules": high_risk_rules,
        "adversarial_counts": adversarial_counts,
        "missing": missing_adversarial,
    }

    if critical_path_required and not degraded and missing_adversarial:
        fail_reasons.append(
            f"critical_path_adversarial: high 风险规则 {missing_adversarial}"
            " 无对抗用例（@DisplayName(\"Rn-对抗-...\")) -> 补对抗用例"
            " 或设 critical_path_required: false 降级"
        )

    # 步骤 7：阈值逐项比对
    threshold_results: list[dict] = []
    if degraded:
        # 降级模式仅校验 Spec 覆盖率阈值（v0.4 5.5）
        spec_actual = spec_coverage.get("coverage_percent", 0)
        spec_pass = spec_actual >= thr["spec_rule_coverage_min"]
        threshold_results.append({
            "metric": "spec_coverage",
            "actual": spec_actual,
            "threshold": thr["spec_rule_coverage_min"],
            "pass": spec_pass,
        })
        if not spec_pass:
            fail_reasons.append(
                f"spec_coverage {spec_actual}% < {thr['spec_rule_coverage_min']}%"
                " -> 补齐 @Spec 注解"
            )
    else:
        # ── diff coverage 判定（替代 v0.6 9.4 作用域方案）──
        # 只判 MR/工作区变更行覆盖率（git diff --unified=0 提取变更行 + JaCoCo
        # 行级数据判覆盖）；git 不可用回退全量聚合阈值；无变更行跳过不判。
        source_lines = parse_results.get("source_lines") if isinstance(parse_results, dict) else []
        if not isinstance(source_lines, list):
            source_lines = []
        diff_coverage = _compute_diff_coverage(project, diff_base, source_lines)
        diff_mode = diff_coverage.get("mode", "fallback_all")
        if diff_mode == "diff":
            percent = diff_coverage.get("percent")
            if percent is not None:
                ok = percent >= diff_threshold
                threshold_results.append({
                    "metric": "diff_coverage",
                    "actual": percent,
                    "threshold": diff_threshold,
                    "pass": ok,
                })
                if not ok:
                    fail_reasons.append(
                        f"diff coverage {percent}% < {diff_threshold}%"
                        f" (变更行 {diff_coverage.get('covered_lines', 0)}/{diff_coverage.get('total_lines', 0)})"
                    )
            # percent None（total=0 防御）：不判
        elif diff_mode == "no_changes":
            # diff 维度 PASS（INFO 行，无承诺）
            threshold_results.append({
                "metric": "diff_coverage",
                "actual": None,
                "threshold": diff_threshold,
                "pass": True,
            })
        else:  # fallback_all：回退全量聚合阈值判定（保留原全量逻辑）
            metrics = [
                ("line_coverage", coverage["line"], thr["line_coverage_min"]),
                ("branch_coverage", coverage["branch"], thr["branch_coverage_min"]),
                ("method_coverage", coverage["method"], thr["method_coverage_min"]),
                ("instruction_coverage", coverage["instruction"], thr["instruction_coverage_min"]),
                ("complexity_coverage", coverage["complexity"], thr["complexity_coverage_min"]),
                ("unit_pass_rate", unit_tests["pass_rate"], thr["unit_pass_rate_min"]),
                ("contract_pass_rate", contract_tests["pass_rate"], thr["contract_pass_rate_min"]),
            ]
            for metric, actual, threshold in metrics:
                ok = actual >= threshold
                threshold_results.append({
                    "metric": metric, "actual": actual, "threshold": threshold, "pass": ok,
                })
                if not ok:
                    fail_reasons.append(f"{metric} {actual}% < {threshold}% ({risk_level})")
        # diff/no_changes 模式下通过率仍判（fallback_all 已含）
        if diff_mode in ("diff", "no_changes"):
            for metric, actual, threshold in [
                ("unit_pass_rate", unit_tests["pass_rate"], thr["unit_pass_rate_min"]),
                ("contract_pass_rate", contract_tests["pass_rate"], thr["contract_pass_rate_min"]),
            ]:
                ok = actual >= threshold
                threshold_results.append({
                    "metric": metric, "actual": actual, "threshold": threshold, "pass": ok,
                })
                if not ok:
                    fail_reasons.append(f"{metric} {actual}% < {threshold}% ({risk_level})")
        # spec 覆盖率判定（full 模式共用）
        spec_actual = spec_coverage.get("coverage_percent", 0)
        spec_pass = spec_actual >= thr["spec_rule_coverage_min"]
        threshold_results.append({
            "metric": "spec_coverage",
            "actual": spec_actual,
            "threshold": thr["spec_rule_coverage_min"],
            "pass": spec_pass,
        })
        if not spec_pass:
            fail_reasons.append(
                f"spec_coverage {spec_actual}% < {thr['spec_rule_coverage_min']}%"
                " -> 补齐 @Spec 注解"
            )

    status = "FAIL" if fail_reasons else "PASS"

    # v0.6 9.6：UNSPEC_CODE 漂移告警（scan_spec 的 MEDIUM 告警，不参与判定）
    unspec_codes: list = []
    if isinstance(scan_spec, dict):
        raw = scan_spec.get("unspec_codes")
        if isinstance(raw, list):
            unspec_codes = raw

    # ── v0.6 5.1/9.3：SOFT 段只读检查（判定完成后、写 gate-result.md 前）──
    # 只读正则检查现有 gate-result.md 是否含 AI 交叉验证标题；缺失 -> WARN +
    # soft_missing=true（不加入 fail_reasons，不改判——脚本不代写 SOFT 段）。
    # 正则锚定行首（MULTILINE）：只认独立标题行，杜绝脚本 WARN 文案自命中
    # （脚本写出的文本不含完整标题行 -> 同 fixture 二次运行 soft_missing 稳定）。
    soft_missing = True
    gate_result_path = Path(feature_dir) / "docs" / "gate-result.md"
    try:
        existing_md = gate_result_path.read_text(encoding="utf-8")
    except OSError:
        existing_md = ""
    if _SOFT_HEADER_RE.search(existing_md):
        soft_missing = False
    if soft_missing:
        print(
            "WARN: gate-result.md 缺少 AI 手写 SOFT 交叉验证段"
            "（soft_missing=true，不参与判定）",
            file=sys.stderr,
        )

    result = {
        "status": status,
        "mode": "degraded" if degraded else "full",
        "gate_result_path": str(gate_result_path),
        "risk_level": risk_level,
        "mvn_clean_test": mvn_status,
        "unit_tests": unit_tests,
        "contract_tests": contract_tests,
        "coverage": coverage,
        "spec_coverage": spec_coverage,
        "displayname_match": displayname_match,
        "adversarial_coverage": adversarial_coverage,
        "threshold_results": threshold_results,
        "fail_reasons": fail_reasons,
        # v0.6 字段
        "degraded_reason": degraded_reason,
        "soft_missing": soft_missing,
        "unspec_codes_count": len(unspec_codes),
        "diff_coverage": diff_coverage,
        "diff_threshold": diff_threshold,
    }

    # 步骤 8：脚本直接写 gate-result.md（--check-only 不写）
    # v0.6 5.2 流程闭环：写前保留旧文件中 AI 手写的 SOFT 交叉验证段——把标题行
    # 及其后全部旧内容追加到新生成内容末尾（前面补空行分隔）。脚本自身永不写该
    # 标题，故追加段以标题行开头，重跑时只读判定仍能识别（soft_missing=False
    # 稳定，AI 补段后重跑即消 WARN，且 AI 段不被全量覆盖抹掉）。无旧 SOFT 段不追加。
    if not check_only:
        out_dir = Path(feature_dir) / "docs"
        out_dir.mkdir(parents=True, exist_ok=True)
        new_md = _format_gate_result_md(result)
        try:
            old_md = (out_dir / "gate-result.md").read_text(encoding="utf-8")
        except OSError:
            old_md = ""
        soft_tail_match = _SOFT_HEADER_RE.search(old_md)
        if soft_tail_match:
            soft_tail = old_md[soft_tail_match.start():].rstrip()
            if soft_tail:
                new_md = new_md.rstrip() + "\n\n" + soft_tail + "\n"
        (out_dir / "gate-result.md").write_text(new_md, encoding="utf-8")

    return result


# ── 子脚本调用 ───────────────────────────────────────────────────────────────


def _call_script(script: Path, args: list[str]) -> dict | None:
    """调用子脚本（复用其解析逻辑，避免契约漂移），返回解析后的 JSON dict。"""
    try:
        proc = subprocess.run(
            [sys.executable, str(script)] + args,
            capture_output=True, text=True, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="门禁编排脚本 run_gate：全确定性逻辑下沉脚本，AI 仅读判定 JSON。"
    )
    parser.add_argument("--source", required=True, help="Java 业务源码根目录")
    parser.add_argument("--test-source", required=True, help="测试源码根目录")
    parser.add_argument("--spec", required=True, help="spec.md 路径")
    parser.add_argument("--project", required=True, help="项目根目录（执行 mvn / 找 target 报告）")
    parser.add_argument("--feature-dir", required=True, help="feature 目录（如 specs/001-bank-transfer）")
    parser.add_argument("--config", required=True, help="testing-config.yml 路径")
    parser.add_argument("--check-only", action="store_true", help="只跑步骤 1-7，不写 gate-result.md")
    parser.add_argument(
        "--diff-threshold",
        default=None,
        type=int,
        help="变更行覆盖率阈值（%%），默认取 config gate.diff_coverage_threshold（缺省 80）；范围 0-100",
    )
    parser.add_argument(
        "--diff-base",
        default=None,
        help="MR 对比分支（git merge-base 定位 base）；默认取 config gate.diff_base，空=工作区 vs HEAD",
    )
    parser.add_argument("--json", action="store_true", help="输出判定 JSON 到 stdout（固定开启）")
    args = parser.parse_args()

    # 修复 4：--diff-threshold 范围校验（0-100），越界 stderr 报错 exit 2
    if args.diff_threshold is not None and not (0 <= args.diff_threshold <= 100):
        print(
            f"错误: --diff-threshold 必须在 0-100 之间（收到 {args.diff_threshold}）",
            file=sys.stderr,
        )
        return 2

    feature_dir = Path(args.feature_dir)
    impact_ok = (feature_dir / "docs" / "impact-report.md").is_file()

    # 环境收集（v0.6 降级判定）：AI 负责传对 --project（含 pom.xml 的模块目录）
    env = collect_environment(args.project)
    degraded = env["degraded"]

    mvn_status = "SKIPPED"
    scan_stack = None
    parse_results = None
    scripts_dir = Path(__file__).resolve().parent

    # 步骤 1：mvn clean test（强制 clean；非降级即在 --project 目录执行）
    if not degraded:
        try:
            proc = subprocess.run(
                ["mvn", "clean", "test"],
                cwd=args.project,
                capture_output=True, text=True, timeout=1800,
            )
            mvn_status = "SUCCESS" if proc.returncode == 0 else "FAIL"
        except (OSError, subprocess.TimeoutExpired):
            mvn_status = "FAIL"

    # 步骤 2/3：技术栈 + 测试结果（报告路径基于 --project 的 target/）
    if not degraded:
        scan_stack = _call_script(
            scripts_dir / "scan_test_stack.py",
            ["--source", args.test_source, "--json"],
        )
        surefire = str(Path(args.project) / "target" / "surefire-reports")
        jacoco = str(Path(args.project) / "target" / "site" / "jacoco" / "jacoco.xml")
        parse_results = _call_script(
            scripts_dir / "parse_test_results.py",
            ["--surefire", surefire, "--jacoco", jacoco, "--json"],
        )

    # 步骤 4：@Spec 扫描（full 与 degraded 都执行；v0.6 9.6 透传 test-source；
    # scan.unspec_exclude_patterns 排除模式由 scan 自己读 config——--config 透传，
    # 消除重复解析，三语言行为一致）
    scan_spec_args = [
        "--source", args.source,
        "--spec", args.spec,
        "--test-source", args.test_source,
        "--config", args.config,
        "--json",
    ]
    scan_spec = _call_script(scripts_dir / "scan_spec_annotations.py", scan_spec_args)

    inputs = {
        "source": args.source,
        "test_source": args.test_source,
        "spec": args.spec,
        "project": args.project,
        "feature_dir": args.feature_dir,
        "config": args.config,
        "check_only": args.check_only,
        "degraded": degraded,
        "mvn_status": mvn_status,
        "impact_ok": impact_ok,
        "scan_stack": scan_stack,
        "parse_results": parse_results,
        "scan_spec": scan_spec,
        # v0.6 diff coverage（CLI 可覆盖，run() 内回落 config）
        "diff_threshold": args.diff_threshold,
        "diff_base": args.diff_base,
        "degraded_reason": env["degraded_reason"],
    }
    result = run(inputs)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
