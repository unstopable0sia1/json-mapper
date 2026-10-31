from copy import deepcopy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from composer import compose, reference, validate_composition, validate_session
from mapper import MappingError, loads

ROOT = Path(__file__).resolve().parents[1]


class ComposerTests(unittest.TestCase):
    def test_three_source_example_and_immutability(self):
        session = validate_session(loads((ROOT / "examples/composition.session.json").read_text(encoding="utf-8")))
        before = deepcopy(session)
        result, report = compose(session["sources"], session["config"])
        self.assertEqual(result, loads((ROOT / "examples/composition.expected.json").read_text(encoding="utf-8")))
        self.assertEqual((report["sources"], report["written"], report["renamed"], report["deleted"], report["defaults"]), (3, 10, 1, 1, 1))
        result["items"][0]["code"] = "modified"
        self.assertEqual(session, before)

    def test_arbitrary_number_of_sources(self):
        sources = {f"S{i}": {"x": i} for i in range(30)}
        rules = [{"from": f"value:S{i}:$.x", "to": f"items[{i}]"} for i in range(30)]
        self.assertEqual(compose(sources, {"rules": rules})[0], {"items": list(range(30))})

    def test_field_value_and_literal_key_are_distinct(self):
        sources = {"A": {"a.b:中文": {"": 7}}}
        path = '$["a.b:中文"][""]'
        result, _ = compose(sources, {"rules": [
            {"from": "value:A:" + path, "to": "data"},
            {"from": "field:A:" + path, "to": "key"},
            {"value": "value:A:$.literal", "to": "literal"}]})
        self.assertEqual(result, {"data": 7, "key": "", "literal": "value:A:$.literal"})

    def test_field_destination_preserves_full_structure(self):
        sources = {"B": {"profile": {"a.b": "sample"}}}
        result, _ = compose(sources, {"template": {"keep": True}, "rules": [
            {"value": "new", "to": 'field:B:$.profile["a.b"]'}]})
        self.assertEqual(result, {"keep": True, "profile": {"a.b": "new"}})

    def test_wildcard_nested_arrays_and_empty_arrays(self):
        sources = {"A": {"groups": [{"items": [{"x": 1}, {"x": 2}]}, {"items": []}]},
                   "B": {"rows": []}}
        result, _ = compose(sources, {"rules": [
            {"from": "value:A:$.groups[*].items[*].x", "to": "field:B:$.rows[*].values[*].y"}]})
        self.assertEqual(result, {"rows": [{"values": [{"y": 1}, {"y": 2}]}, {"values": []}]})

    def test_defaults_skip_and_explicit_null(self):
        result, report = compose({"A": {"x": None}}, {"rules": [
            {"from": "value:A:$.x", "to": "x", "missing": "default", "default": 5},
            {"from": "value:A:$.absent", "to": "y", "missing": "default", "default": 6},
            {"from": "value:A:$.other", "to": "z", "missing": "skip"}]})
        self.assertEqual(result, {"x": None, "y": 6})
        self.assertEqual((report["defaults"], report["skipped"]), (1, 1))

    def test_global_default_and_no_fabricated_array_cardinality(self):
        self.assertEqual(compose({"A": {}}, {"missing": "default", "rules": [
            {"from": "value:A:$.x", "to": "x", "default": 4}]})[0], {"x": 4})
        with self.assertRaises(MappingError):
            compose({"A": {}}, {"rules": [{"from": "value:A:$.rows[*].x", "to": "items[*].y", "missing": "default", "default": 0}]})

    def test_template_only_scalars_arrays_and_root_copy(self):
        for template in (None, False, 0, "", [], {"x": 1}):
            self.assertEqual(compose({}, {"template": template, "rules": []})[0], template)
        self.assertEqual(compose({"A": [1, 2]}, {"rules": [{"from": "value:A:$", "to": "$"}]})[0], [1, 2])

    def test_rename_delete_in_arrays_and_dynamic_name(self):
        result, report = compose({"C": {"name": "new.key"}}, {"template": {"rows": [{"old": 1, "drop": 2}, {"old": 3, "drop": 4}]}, "rules": [
            {"op": "rename", "to": "rows[*].old", "from": "value:C:$.name"},
            {"op": "delete", "to": "rows[*].drop"}]})
        self.assertEqual(result, {"rows": [{"new.key": 1}, {"new.key": 3}]})
        self.assertEqual((report["renamed"], report["deleted"]), (2, 2))

    def test_missing_rename_name_skip_and_default(self):
        config = {"template": {"old": 2}, "rules": [
            {"op": "rename", "to": "old", "from": "value:A:$.absent", "missing": "skip"}]}
        self.assertEqual(compose({"A": {}}, config)[0], {"old": 2})
        config["rules"][0].update(missing="default", default="new")
        self.assertEqual(compose({"A": {}}, config)[0], {"new": 2})
        # A fallback name cannot fabricate a field that does not exist in the output.
        config["template"] = {}
        with self.assertRaises(MappingError):
            compose({"A": {}}, config)

    def test_conflicts_and_explicit_overwrite(self):
        configs = [
            {"rules": [{"value": 1, "to": "x"}, {"value": 2, "to": "x"}]},
            {"template": {"old": 1, "new": 2}, "rules": [{"op": "rename", "to": "old", "value": "new"}]},
            {"template": {"x": 0}, "rules": [{"value": 1, "to": "x"}, {"op": "delete", "to": "x"}]}]
        for config in configs:
            with self.subTest(config=config), self.assertRaises(MappingError):
                compose({}, config)
        self.assertEqual(compose({}, {**configs[1], "on_conflict": "overwrite"})[0], {"new": 1})

    def test_disabled_rule_does_not_require_loaded_source(self):
        self.assertEqual(compose({}, {"rules": [{"from": "value:A:$.x", "to": "x", "enabled": False}]})[0], {})

    def test_bad_references_aliases_and_missing_sources(self):
        for text in ("A.x", "value:1A:$.x", "other:A:$.x", "field:A:$", "field:A:$.rows[0]"):
            with self.subTest(text=text), self.assertRaises(MappingError):
                reference(text)
        for rules in ([{"from": "value:Unknown:$.x", "to": "x", "missing": "skip"}],
                      [{"value": 1, "to": "field:A:$.missing"}],
                      [{"value": 1, "to": "value:A:$.x"}],
                      [{"from": "value:A:$.rows[*]", "to": "x"}]):
            with self.subTest(rules=rules), self.assertRaises(MappingError):
                compose({"A": {}}, {"rules": rules})

    def test_invalid_structure_operations(self):
        for rule in ({"op": "delete", "to": "$"}, {"op": "delete", "to": "rows[0]"},
                     {"op": "rename", "to": "x", "value": 42},
                     {"op": "delete", "to": "x", "missing": "default", "default": 0},
                     {"op": "rename", "to": "x", "from": "value:A:$.rows[*].name"}):
            with self.subTest(rule=rule), self.assertRaises(MappingError):
                compose({}, {"template": {"x": 1}, "rules": [rule]})

    def test_parent_null_and_missing_target_errors(self):
        for config in ({"template": {"x": None}, "rules": [{"value": 1, "to": "x.y"}]},
                       {"rules": [{"op": "delete", "to": "missing"}]}):
            with self.subTest(config=config), self.assertRaises(MappingError):
                compose({}, config)
        self.assertEqual(compose({}, {"rules": [{"op": "delete", "to": "missing", "missing": "skip"}]})[0], {})

    def test_invalid_session_and_config_are_rejected(self):
        for config in ({"rules": [], "typo": True}, {"rules": [], "version": True},
                       {"rules": [{"value": 1, "to": "x", "typo": True}]}):
            with self.subTest(config=config), self.assertRaises(MappingError):
                validate_composition(config)
        for session in ({}, {"kind": "json-composer-session", "version": 1, "sources": {"1A": {}}, "config": {"rules": []}}):
            with self.subTest(session=session), self.assertRaises(MappingError):
                validate_session(session)


if __name__ == "__main__":
    unittest.main()
