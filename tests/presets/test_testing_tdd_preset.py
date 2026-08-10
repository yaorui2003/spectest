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
    assert m["preset"]["version"] == "1.0.0"
    assert m["requires"]["speckit_version"] == ">=0.14.4"


def test_preset_provides_three_overrides():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    names = {t["name"] for t in m["provides"]["templates"]}
    assert "constitution-template" in names
    assert "tasks-template" in names
    assert "speckit.implement" in names


# ---------- constitution-template（replace，预置 Principle VI）----------

def test_constitution_template_seeds_principle_vi():
    f = PRESET_DIR / "templates" / "constitution-template.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    # Principle VI 静态预置（非占位符）
    assert "VI. Spec Traceability" in content
    assert "@Spec" in content
    assert "NON-NEGOTIABLE" in content
    # 仍保留 Principles I-V 占位符供项目填充
    assert "[PRINCIPLE_1_NAME]" in content


# ---------- tasks-template（wrap，强制 TDD）----------

def test_tasks_template_uses_wrap_strategy():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    tasks_entry = next(
        t for t in m["provides"]["templates"] if t["name"] == "tasks-template"
    )
    assert tasks_entry["strategy"] == "wrap"


def test_tasks_template_wraps_core_with_override():
    f = PRESET_DIR / "templates" / "tasks-template.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    # wrap 策略必须含 {CORE_TEMPLATE} 占位符
    assert "{CORE_TEMPLATE}" in content
    # 强制 REQUIRED，覆盖核心的 OPTIONAL
    assert "REQUIRED" in content
    # 测试任务前置
    assert "测试任务" in content or "test task" in content.lower()


# ---------- implement 命令（append，强制 @Spec）----------

def test_implement_command_uses_append_strategy():
    with (PRESET_DIR / "preset.yml").open() as f:
        m = yaml.safe_load(f)
    impl_entry = next(
        t for t in m["provides"]["templates"] if t["name"] == "speckit.implement"
    )
    assert impl_entry["strategy"] == "append"


def test_implement_command_enforces_spec_annotation():
    f = PRESET_DIR / "commands" / "speckit.implement.md"
    assert f.is_file()
    content = f.read_text(encoding="utf-8")
    assert "@Spec" in content
    # 引用 java-service-template 模板
    assert "java-service-template" in content
    # 引用宪法 Principle VI
    assert "Principle VI" in content or "Spec Traceability" in content


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
