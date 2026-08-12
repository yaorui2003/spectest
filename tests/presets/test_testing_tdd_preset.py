"""testing-tdd preset 结构校验测试。"""

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PRESET_DIR = REPO_ROOT / "presets" / "testing-tdd"
BUNDLE_DIR = REPO_ROOT / "examples" / "bundles" / "speckit-testing"


# ---------- preset.yml ----------

def test_preset_manifest_exists():
    assert (PRESET_DIR / "preset.yml").is_file()


def test_preset_manifest_valid():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    assert m["schema_version"] == "1.0"
    assert m["preset"]["id"] == "testing-tdd"
    assert m["preset"]["version"] == "1.1.0"
    assert m["requires"]["speckit_version"] == ">=0.14.4"


def test_preset_provides_four_overrides():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    names = {t["name"] for t in m["provides"]["templates"]}
    assert "constitution-template" in names
    assert "spec-template" in names
    assert "tasks-template" in names
    assert "speckit.implement" in names


# ---------- constitution-template（replace，预置 Principle I 置首）----------

def test_constitution_template_seeds_principle_i():
    f = PRESET_DIR / "templates" / "constitution-template.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    # Principle I 静态预置（非占位符，置首）
    assert "I. Spec Traceability" in content
    assert "@Spec" in content
    assert "NON-NEGOTIABLE" in content
    # Principle II 中文文档要求（v0.3 新增）
    assert "II. 中文文档要求" in content or "中文文档" in content
    # 仍保留可选占位符供项目填充（Principle III 起）
    assert "[PRINCIPLE_3_NAME]" in content


# ---------- tasks-template（wrap，强制 TDD）----------

def test_tasks_template_uses_replace_strategy():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    tasks_entry = next(
        t for t in m["provides"]["templates"] if t["name"] == "tasks-template"
    )
    assert tasks_entry["strategy"] == "replace"


def test_tasks_template_enforces_required_no_optional():
    f = PRESET_DIR / "templates" / "tasks-template.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    # 强制 REQUIRED
    assert "REQUIRED" in content
    # 矛盾已消灭：不含 OPTIONAL 表述
    assert "OPTIONAL" not in content
    # 测试任务前置（TDD）
    assert "TDD" in content or "test task" in content.lower()
    # replace 不需要 wrap 的 {CORE_TEMPLATE} 占位符
    assert "{CORE_TEMPLATE}" not in content


# ---------- implement 命令（append，强制 @Spec）----------

def test_implement_command_uses_append_strategy():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    impl_entry = next(
        t for t in m["provides"]["templates"] if t["name"] == "speckit.implement"
    )
    assert impl_entry["strategy"] == "append"


def test_replace_strategy_templates():
    """constitution-template 和 spec-template 均用 replace 策略。"""
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    for name in ("constitution-template", "spec-template", "tasks-template"):
        entry = next(
            t for t in m["provides"]["templates"] if t["name"] == name
        )
        assert entry["strategy"] == "replace", (
            f"{name} 应使用 replace 策略，实际 {entry['strategy']}"
        )


def test_implement_command_enforces_spec_annotation():
    f = PRESET_DIR / "commands" / "speckit.implement.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    assert "@Spec" in content
    # 引用 java-service-template 模板
    assert "java-service-template" in content
    # 引用宪法 Principle I（v0.3: Spec Traceability 置首）
    assert "Principle I" in content or "Spec Traceability" in content


# ---------- catalog 注册 ----------

def test_preset_registered_in_catalog():
    with (REPO_ROOT / "presets" / "catalog.json").open() as f:
        import json
        cat = json.load(f)
    assert "testing-tdd" in cat["presets"]
    assert cat["presets"]["testing-tdd"]["bundled"] is True


# ---------- bundle ----------

def test_bundle_manifest_exists():
    assert (BUNDLE_DIR / "bundle.yml").is_file()


def test_bundle_references_extension_and_preset():
    with (BUNDLE_DIR / "bundle.yml").open() as f:
        b = yaml.safe_load(f)
    assert b["bundle"]["id"] == "speckit-testing"
    ext_ids = {e["id"] for e in b["provides"]["extensions"]}
    preset_ids = {p["id"] for p in b["provides"]["presets"]}
    assert "testing" in ext_ids
    assert "testing-tdd" in preset_ids
