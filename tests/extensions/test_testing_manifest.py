"""T007: testing 扩展 extension.yml manifest 校验。

校验 ``extensions/testing/extension.yml`` 符合
``specs/001-speckit-testing-ext/contracts/manifest-schema.md``：

- ``schema_version == "1.0"``
- ``extension.id == "testing"``、``version == "1.0.0"``
- ``requires.speckit_version == ">=0.2.0"``
- ``hooks`` 为顶层字段（不在 ``provides`` 内）
- ``hooks.before_plan`` / ``hooks.after_implement`` 命令与 optional
- ``provides.commands`` 4 个，命名匹配 ``^speckit\\.testing\\.[a-z]+$``
- ``provides.templates`` 5 个，命名匹配 ``^[a-z-]+$``
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

# 仓库根：tests/extensions/test_testing_manifest.py -> parents[2] = spec-kit/
PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "extensions" / "testing" / "extension.yml"

CMD_NAME_RE = re.compile(r"^speckit\.testing\.[a-z]+$")
TEMPLATE_NAME_RE = re.compile(r"^[a-z-]+$")


@pytest.fixture(scope="module")
def manifest() -> dict:
    """读取并缓存 extension.yml。"""
    assert MANIFEST_PATH.exists(), f"manifest 不存在: {MANIFEST_PATH}"
    return yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_schema_version(manifest):
    assert manifest["schema_version"] == "1.0"


def test_extension_identity(manifest):
    ext = manifest["extension"]
    assert ext["id"] == "testing"
    assert ext["version"] == "1.0.0"


def test_requires_speckit_version(manifest):
    """钩子机制最低版本 >=0.2.0（见 research.md 决策 1）。"""
    assert manifest["requires"]["speckit_version"] == ">=0.2.0"


def test_hooks_is_top_level_not_in_provides(manifest):
    """hooks 必须是顶层字段，不能放进 provides（research.md 决策 3）。"""
    assert "hooks" in manifest, "hooks 必须作为顶层字段存在"
    assert "hooks" not in manifest.get("provides", {}), "hooks 不得放在 provides 内"


def test_hooks_before_plan(manifest):
    hook = manifest["hooks"]["before_plan"]
    assert hook["command"] == "speckit.testing.impact"
    assert hook["optional"] is False


def test_hooks_after_implement(manifest):
    hook = manifest["hooks"]["after_implement"]
    assert hook["command"] == "speckit.testing.gate"
    assert hook["optional"] is False


def test_provides_commands_count_and_naming(manifest):
    commands = manifest["provides"]["commands"]
    assert len(commands) == 4
    names = [c["name"] for c in commands]
    for name in names:
        assert CMD_NAME_RE.match(name), (
            f"命令名 {name!r} 不匹配 {CMD_NAME_RE.pattern}"
        )
    assert set(names) == {
        "speckit.testing.impact",
        "speckit.testing.plan",
        "speckit.testing.gate",
        "speckit.testing.report",
    }


def test_provides_templates_count_and_naming(manifest):
    templates = manifest["provides"]["templates"]
    assert len(templates) == 5
    for t in templates:
        assert TEMPLATE_NAME_RE.match(t["name"]), (
            f"模板名 {t['name']!r} 不匹配 {TEMPLATE_NAME_RE.pattern}"
        )


# ── T027: manifest 声明的文件实际存在性校验 ──────────────────────────────────
# 以下测试校验 manifest 中 provides.*[].file / .template 指向的文件以及
# hooks 声明的命令在 provides.commands 中有对应条目。manifest 中 file 路径
# 均相对扩展根目录（extensions/testing/）。

# 扩展根目录（extensions/testing/），manifest 中所有 file 路径均相对此目录
EXTENSION_DIR = PROJECT_ROOT / "extensions" / "testing"


def test_declared_command_files_exist(manifest):
    """provides.commands[].file 指向的 4 个命令 .md 文件必须实际存在。"""
    commands = manifest["provides"]["commands"]
    missing: list[str] = []
    for cmd in commands:
        # cmd["file"] 形如 "commands/speckit.testing.gate.md"，相对扩展根
        file_path = EXTENSION_DIR / cmd["file"]
        if not file_path.exists():
            missing.append(str(file_path))
    assert not missing, f"manifest 声明的命令文件缺失: {missing}"


def test_declared_template_files_exist(manifest):
    """provides.templates[].file 指向的 5 个模板文件必须实际存在。"""
    templates = manifest["provides"]["templates"]
    missing: list[str] = []
    for tpl in templates:
        # tpl["file"] 形如 "templates/java-service.template.java"
        file_path = EXTENSION_DIR / tpl["file"]
        if not file_path.exists():
            missing.append(str(file_path))
    assert not missing, f"manifest 声明的模板文件缺失: {missing}"


def test_declared_script_files_exist(manifest):
    """provides.scripts[].file 指向的 scan_spec_annotations.py 必须实际存在。"""
    scripts = manifest["provides"]["scripts"]
    missing: list[str] = []
    for scr in scripts:
        # scr["file"] 形如 "scripts/python/scan_spec_annotations.py"
        file_path = EXTENSION_DIR / scr["file"]
        if not file_path.exists():
            missing.append(str(file_path))
    assert not missing, f"manifest 声明的脚本文件缺失: {missing}"


def test_declared_config_files_exist(manifest):
    """provides.config[].template 指向的 testing-config.template.yml 必须存在。"""
    configs = manifest["provides"]["config"]
    missing: list[str] = []
    for cfg in configs:
        # cfg["template"] 形如 "config/testing-config.template.yml"
        file_path = EXTENSION_DIR / cfg["template"]
        if not file_path.exists():
            missing.append(str(file_path))
    assert not missing, f"manifest 声明的配置模板文件缺失: {missing}"


def test_hook_commands_are_provided(manifest):
    """hooks 声明的命令必须在 provides.commands 中有对应条目。

    - before_plan -> speckit.testing.impact
    - after_implement -> speckit.testing.gate

    两者都必须在 provides.commands 列表中提供，否则钩子触发时
    找不到对应命令实现。
    """
    hooks = manifest["hooks"]
    provided_names = {c["name"] for c in manifest["provides"]["commands"]}
    missing: list[str] = []
    for hook_name, hook_def in hooks.items():
        cmd = hook_def["command"]
        if cmd not in provided_names:
            missing.append(f"{hook_name} -> {cmd}")
    assert not missing, (
        f"hooks 声明的命令未在 provides.commands 中提供: {missing}"
    )
