from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mapper import MappingError, convert, dumps, loads, parse_path, write_json

ROOT = Path(__file__).resolve().parents[1]


class MappingTests(unittest.TestCase):
    def map(self, source, rules, **options):
        return convert(source, {"rules": rules, **options})[0]

    def test_dot_mapping(self):
        self.assertEqual(self.map({"a": {"a": 42}}, [{"from": "a.a", "to": "b.b"}]), {"b": {"b": 42}})

    def test_literal_keys_and_root_array(self):
        rule = {"from": '$[0]["a.b"][""]', "to": '$[1]["x.y"]'}
        self.assertEqual(self.map([{"a.b": {"": "VI"}}], [rule]), [None, {"x.y": "VI"}])

    def test_root_copy_does_not_mutate(self):
        source = {"a": [1, 2]}
        config = {"rules": [{"from": "$", "to": "data"}]}
        original = deepcopy((source, config))
        result, _ = convert(source, config)
        result["data"]["a"].append(3)
        self.assertEqual((source, config), original)

    def test_nested_arrays_preserve_index_and_empty(self):
        source = {"groups": [{"items": [{"x": 1}, {"x": 2}]}, {"items": []}]}
        result = self.map(source, [{"from": "groups[*].items[*].x", "to": "rows[*].values[*].y"}])
        self.assertEqual(result, {"rows": [{"values": [{"y": 1}, {"y": 2}]}, {"values": []}]})

    def test_multiple_rules_empty_array(self):
        result = self.map({"rows": []}, [{"from": "rows[*].x", "to": "data[*].a"}, {"from": "rows[*].y", "to": "data[*].b"}])
        self.assertEqual(result, {"data": []})

    def test_missing_error(self):
        with self.assertRaisesRegex(MappingError, "Record 1, rule 1"):
            self.map({}, [{"from": "a.x", "to": "x"}])

    def test_skip_preserves_array_indices(self):
        result, report = convert({"rows": [{}, {"x": 7}]}, {"rules": [{"from": "rows[*].x", "to": "items[*].y", "missing": "skip"}]})
        self.assertEqual(result, {"items": [None, {"y": 7}]})
        self.assertEqual(report["skipped"], 1)

    def test_defaults_only_replace_absent(self):
        result, report = convert({"a": None, "b": False, "c": "", "d": 0}, {"missing": "default", "rules": [
            {"from": key, "to": key, "default": "fallback"} for key in ("a", "b", "c", "d", "e")]})
        self.assertEqual(result, {"a": None, "b": False, "c": "", "d": 0, "e": "fallback"})
        self.assertEqual(report["defaults"], 1)

    def test_default_unknown_array_cardinality_rejected(self):
        with self.assertRaisesRegex(MappingError, "số phần tử"):
            self.map({}, [{"from": "rows[*].x", "to": "items[*].y", "missing": "default", "default": 0}])

    def test_null_parent_is_type_error(self):
        with self.assertRaisesRegex(MappingError, "phải là object"):
            self.map({"a": None}, [{"from": "a.x", "to": "x", "missing": "default", "default": 5}])

    def test_constants_support_all_json_types(self):
        for value in (None, False, 0, "", [], {}, {"a": ["Việt Nam"]}):
            with self.subTest(value=value):
                self.assertEqual(self.map({}, [{"value": value, "to": "$"}]), value)

    def test_each_wrapper_and_empty_source(self):
        rules = [{"from": "x", "to": "a.b"}]
        self.assertEqual(self.map({"rows": [{"x": 1}, {"x": 2}]}, rules, mode="each", source_root="rows", output_root="payload.items"),
                         {"payload": {"items": [{"a": {"b": 1}}, {"a": {"b": 2}}]}})
        self.assertEqual(self.map([], rules, mode="each"), [])

    def test_each_requires_array(self):
        with self.assertRaisesRegex(MappingError, "yêu cầu source_root trỏ đến mảng"):
            self.map({}, [{"value": 1, "to": "a"}], mode="each")

    def test_base_and_template_are_copied(self):
        source = {"x": 2, "keep": True}
        self.assertEqual(self.map(source, [{"from": "x", "to": "x"}], base="source"), source)
        template = {"header": [], "data": {}}
        result = self.map(source, [{"from": "x", "to": "data.n"}], template=template)
        self.assertEqual(result, {"header": [], "data": {"n": 2}})
        self.assertEqual(template, {"header": [], "data": {}})

    def test_duplicate_and_ancestor_destinations_rejected(self):
        for a, b in (("a", "a"), ("a", "a.b"), ("a.b", "a"), ("$", "a")):
            with self.subTest(a=a, b=b), self.assertRaisesRegex(MappingError, "chồng path"):
                self.map({}, [{"value": {}, "to": a}, {"value": 2, "to": b}])

    def test_explicit_overwrite(self):
        result = self.map({}, [{"value": {"old": 1}, "to": "a"}, {"value": 2, "to": "a.new"}], on_conflict="overwrite")
        self.assertEqual(result, {"a": {"old": 1, "new": 2}})

    def test_parent_type_conflict(self):
        with self.assertRaisesRegex(MappingError, "Đích cần"):
            self.map({}, [{"value": 1, "to": "a.x"}], template={"a": None})

    def test_wildcard_counts(self):
        for source, target in (("a[*]", "b"), ("a", "b[*]")):
            with self.assertRaisesRegex(MappingError, "số \\[\\*\\]"):
                self.map({}, [{"from": source, "to": target}])

    def test_transform_chain(self):
        self.assertEqual(self.map({"x": " 42 "}, [{"from": "x", "to": "$", "transforms": ["trim", "integer"]}]), 42)

    def test_large_integer_exact(self):
        value = "9007199254740993123456789.0"
        self.assertEqual(self.map(value, [{"from": "$", "to": "$", "transforms": ["integer"]}]), 9007199254740993123456789)

    def test_transform_cases(self):
        cases = [(" false ", ["boolean"], False), ("true", ["boolean"], True),
                 ("3.5", ["number"], 3.5), ("a,b", ["split"], ["a", "b"]),
                 (["a", "b"], [{"op": "join", "separator": "/"}], "a/b"),
                 ("Nguyễn An", ["upper"], "NGUYỄN AN"), ("ABC", ["lower"], "abc"),
                 ("hello", [{"op": "replace", "old": "h", "new": "H"}], "Hello"),
                 ("x", [{"op": "lookup", "values": {"x": 7}}], 7),
                 (False, [{"op": "lookup", "values": {"false": "Không"}}], "Không"),
                 ("?", [{"op": "lookup", "values": {}, "default": None}], None),
                 ('{"a": 1}', ["parse_json"], {"a": 1}),
                 ({"a": 1}, ["json_string"], '{"a":1}'), (False, ["string"], "false")]
        for value, steps, expected in cases:
            with self.subTest(steps=steps):
                self.assertEqual(self.map(value, [{"from": "$", "to": "$", "transforms": steps}]), expected)

    def test_invalid_transforms_do_not_coerce_silently(self):
        for value, steps in ((None, ["integer"]), (False, ["number"]), ("2.3", ["integer"]),
                             ("yes", ["boolean"]), (1, ["trim"]), ([1], ["join"]),
                             ("x", [{"op": "lookup", "values": {}}])):
            with self.subTest(value=value, steps=steps), self.assertRaises(MappingError):
                self.map(value, [{"from": "$", "to": "$", "transforms": steps}])

    def test_config_typos_rejected(self):
        bad = [{"rules": [{"from": "a", "to": "b", "missng": "skip"}]},
               {"rules": [{"value": 1, "to": "a", "transforms": [{"op": "split", "separator": ""}]}]},
               {"rules": [{"value": 1, "to": "a"}], "surprise": 1},
               {"rules": [{"value": 1, "to": "a", "missing": "default"}]},
               {"rules": [{"from": "x", "value": 1, "to": "a"}]}]
        for config in bad:
            with self.subTest(config=config), self.assertRaises(MappingError):
                convert({}, config)

    def test_bad_paths_rejected(self):
        for path in ("", "a..b", "a.", "a.[0]", "a[-1]", "a[01]", "a[", "a b", "$a", "a[0]b", "a[1000001]"):
            with self.subTest(path=path), self.assertRaises(MappingError):
                parse_path(path)

    def test_disabled_rule(self):
        self.assertEqual(self.map({}, [{"from": "absent", "to": "x", "enabled": False}]), {})

    def test_strict_json(self):
        for raw in ('{"a":1,"a":2}', "NaN", "Infinity", "1e9999"):
            with self.subTest(raw=raw), self.assertRaises(MappingError):
                loads(raw)
        self.assertEqual(loads('\ufeff{"tiếng": "Việt"}'), {"tiếng": "Việt"})

    def test_examples(self):
        data = loads((ROOT / "examples/input.json").read_text(encoding="utf-8"))
        config = loads((ROOT / "examples/mapping.rules.json").read_text(encoding="utf-8"))
        result, report = convert(data, config)
        self.assertEqual(result["b"]["b"], "Xin chào")
        self.assertIs(result["profile"]["active"], False)
        self.assertEqual(result["items"][1]["total"], 98000)
        self.assertEqual(report["written"], 12)
        self.assertEqual(result, loads((ROOT / "examples/expected.json").read_text(encoding="utf-8")))

    def test_thousands_of_array_items(self):
        source = {"rows": [{"id": i, "name": str(i)} for i in range(10000)]}
        result, report = convert(source, {"rules": [{"from": "rows[*].id", "to": "items[*].id"}, {"from": "rows[*].name", "to": "items[*].name"}]})
        self.assertEqual(len(result["items"]), 10000)
        self.assertEqual(result["items"][-1], {"id": 9999, "name": "9999"})
        self.assertEqual(report["written"], 20000)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source, self.rules, self.output = [self.folder / name for name in ("input.json", "rules.json", "output.json")]
        self.source.write_bytes(b'\xef\xbb\xbf{"a":{"a":1}}')
        self.rules.write_text(dumps({"rules": [{"from": "a.a", "to": "b.b"}]}), encoding="utf-8")

    def cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "mapper.py"), str(self.source), str(self.rules), *map(str, args)],
                              capture_output=True, text=True, encoding="utf-8", timeout=15)

    def test_cli_report_and_input_integrity(self):
        before = self.source.read_bytes()
        report = self.folder / "report.json"
        result = self.cli(self.output, "--report", report)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(loads(self.output.read_text()), {"b": {"b": 1}})
        self.assertEqual(loads(report.read_text())["written"], 1)
        self.assertEqual(self.source.read_bytes(), before)

    def test_no_overwrite_by_default(self):
        self.output.write_text("original")
        result = self.cli(self.output)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.output.read_text(), "original")

    def test_overwrite_source_and_rules_forbidden(self):
        for path in (self.source, self.rules):
            before = path.read_bytes()
            result = self.cli(path, "--overwrite")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(path.read_bytes(), before)

    def test_report_collision_detected_before_output(self):
        for report in (self.output, self.source, self.rules):
            result = self.cli(self.output, "--report", report, "--overwrite")
            self.assertEqual(result.returncode, 2)
            self.assertFalse(self.output.exists())

    def test_bad_rule_writes_no_output(self):
        self.rules.write_text(dumps({"rules": [{"from": "missing", "to": "b"}]}))
        result = self.cli(self.output)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(self.output.exists())

    def test_dry_run(self):
        report = self.folder / "report.json"
        result = self.cli(self.output, "--dry-run", "--report", report)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.output.exists())
        self.assertFalse(report.exists())

    def test_hardlink_source_is_protected(self):
        alias = self.folder / "alias.json"
        try:
            alias.hardlink_to(self.source)
        except OSError:
            self.skipTest("Filesystem does not support hardlinks")
        before = self.source.read_bytes()
        result = self.cli(alias, "--overwrite")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
