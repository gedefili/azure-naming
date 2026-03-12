"""Extended tests for core.name_generator module."""

from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.name_generator import (
    _apply_prefix,
    _get_segments,
    _require_prefix,
    _template_context,
    build_name,
)


# ---------------------------------------------------------------------------
# _get_segments
# ---------------------------------------------------------------------------

class TestGetSegments:
    def test_from_object_attr(self):
        rule = SimpleNamespace(segments=["region", "slug"])
        assert list(_get_segments(rule)) == ["region", "slug"]

    def test_from_dict(self):
        rule = {"segments": ["region", "environment"]}
        assert list(_get_segments(rule)) == ["region", "environment"]

    def test_empty_dict(self):
        assert list(_get_segments({})) == []

    def test_no_segments(self):
        assert list(_get_segments(42)) == []


# ---------------------------------------------------------------------------
# _require_prefix
# ---------------------------------------------------------------------------

class TestRequirePrefix:
    def test_from_object_true(self):
        rule = SimpleNamespace(require_sanmar_prefix=True)
        assert _require_prefix(rule) is True

    def test_from_object_false(self):
        rule = SimpleNamespace(require_sanmar_prefix=False)
        assert _require_prefix(rule) is False

    def test_from_dict(self):
        assert _require_prefix({"require_sanmar_prefix": True}) is True
        assert _require_prefix({"require_sanmar_prefix": False}) is False

    def test_default(self):
        assert _require_prefix({}) is False
        assert _require_prefix(42) is False


# ---------------------------------------------------------------------------
# _template_context
# ---------------------------------------------------------------------------

class TestTemplateContext:
    def test_basic(self):
        ctx = _template_context("wus2", "dev", "vm", {})
        assert ctx["region"] == "wus2"
        assert ctx["environment"] == "dev"
        assert ctx["slug"] == "vm"
        assert ctx["sanmar_prefix"] == ""

    def test_with_prefix(self):
        ctx = _template_context("wus2", "dev", "vm", {}, require_prefix=True)
        assert ctx["sanmar_prefix"] == "sanmar"

    def test_optional_inputs(self):
        ctx = _template_context("wus2", "dev", "vm", {"index": "01"})
        assert ctx["index"] == "01"
        assert ctx["index_segment"] == "-01"

    def test_empty_optional(self):
        ctx = _template_context("wus2", "dev", "vm", {"index": ""})
        assert ctx["index_segment"] == ""


# ---------------------------------------------------------------------------
# _apply_prefix
# ---------------------------------------------------------------------------

class TestApplyPrefix:
    def test_adds_prefix(self):
        rule = SimpleNamespace(require_sanmar_prefix=True)
        assert _apply_prefix("myname", rule) == "sanmar-myname"

    def test_no_double_prefix(self):
        rule = SimpleNamespace(require_sanmar_prefix=True)
        assert _apply_prefix("sanmar-myname", rule) == "sanmar-myname"

    def test_no_prefix_needed(self):
        rule = SimpleNamespace(require_sanmar_prefix=False)
        assert _apply_prefix("myname", rule) == "myname"


# ---------------------------------------------------------------------------
# build_name — segment path
# ---------------------------------------------------------------------------

class TestBuildNameSegments:
    def test_basic_segments(self):
        rule = SimpleNamespace(
            segments=["region", "environment", "slug"],
            name_template=None,
            require_sanmar_prefix=False,
        )
        name = build_name("wus2", "prod", "vm", rule, {})
        assert name == "wus2-prod-vm"

    def test_segments_with_optional(self):
        rule = SimpleNamespace(
            segments=["region", "slug", "index"],
            name_template=None,
            require_sanmar_prefix=False,
        )
        name = build_name("eus", "dev", "st", rule, {"index": "01"})
        assert name == "eus-st-01"

    def test_segments_with_prefix(self):
        rule = SimpleNamespace(
            segments=["slug", "region"],
            name_template=None,
            require_sanmar_prefix=True,
        )
        name = build_name("wus2", "dev", "vm", rule, {})
        assert name == "sanmar-vm-wus2"

    def test_empty_optional_excluded(self):
        rule = SimpleNamespace(
            segments=["region", "slug", "system"],
            name_template=None,
            require_sanmar_prefix=False,
        )
        name = build_name("wus2", "dev", "vm", rule, {"system": ""})
        assert name == "wus2-vm"


# ---------------------------------------------------------------------------
# build_name — template path
# ---------------------------------------------------------------------------

class TestBuildNameTemplate:
    def test_template_basic(self):
        rule = SimpleNamespace(
            segments=(),
            name_template="{region}-{environment}-{slug}",
            require_sanmar_prefix=False,
        )
        name = build_name("wus2", "dev", "vm", rule, {})
        assert name == "wus2-dev-vm"

    def test_template_with_segment_suffix(self):
        rule = SimpleNamespace(
            segments=(),
            name_template="{slug}-{region}{index_segment}",
            require_sanmar_prefix=False,
        )
        name = build_name("wus2", "dev", "st", rule, {"index": "01"})
        assert name == "st-wus2-01"

    def test_template_collapses_dashes(self):
        rule = SimpleNamespace(
            segments=(),
            name_template="{slug}-{region}{index_segment}",
            require_sanmar_prefix=False,
        )
        name = build_name("wus2", "dev", "st", rule, {"index": ""})
        assert "--" not in name

    def test_template_auto_prefix(self):
        rule = SimpleNamespace(
            segments=(),
            name_template="{slug}-{region}",
            require_sanmar_prefix=True,
        )
        name = build_name("wus2", "dev", "st", rule, {})
        assert name.startswith("sanmar-")

    def test_template_with_sanmar_prefix_placeholder(self):
        rule = SimpleNamespace(
            segments=(),
            name_template="{sanmar_prefix}{slug}-{region}",
            require_sanmar_prefix=True,
        )
        name = build_name("wus2", "dev", "st", rule, {})
        assert name.startswith("sanmar")
        # Should NOT double-prefix
        assert not name.startswith("sanmar-sanmar")
