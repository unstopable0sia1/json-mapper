from copy import deepcopy
from pathlib import Path
import sys
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import MapperApp, fill
from composer_app import ComposerApp
from custom_rules import parse_rules
from mapper import MappingError, dumps, loads


class CustomRuleParsingTests(unittest.TestCase):
    def test_object_or_array_and_single_rule_edit(self):
        rule = {"value": 1, "to": "x"}
        self.assertEqual(parse_rules(dumps(rule)), [rule])
        self.assertEqual(parse_rules(dumps([rule, rule])), [rule, rule])
        for value in ([], None, "x", 1, [rule, False]):
            with self.subTest(value=value), self.assertRaises(MappingError):
                parse_rules(dumps(value))
        with self.assertRaises(MappingError):
            parse_rules(dumps([rule, rule]), single=True)
        with self.assertRaises(MappingError):
            parse_rules('{"to":"x","to":"y","value":1}')


class CustomRuleGuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.addCleanup(self.root.destroy)
        self.app = MapperApp(self.root)
        self.root.update()

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def test_invalid_batch_is_atomic_and_keeps_preview(self):
        before = deepcopy(self.app.config)
        output = self.app.current_result
        batches = [
            [{"value": 1, "to": "extra"}, {"value": 2, "to": "a..b"}],
            [{"value": 1, "to": "extra", "unsupported": True}],
            [{"value": 1, "to": "extra", "name": 10}],
            [{"from": "customer.age", "to": "extra", "transforms": ["not_an_op"]}],
            [{"from": "orders[*].id", "to": "extra"}],
            [{"from": "customer.name", "to": "extra", "transforms": ["integer"]}],
            [{"value": 1, "to": "extra"}, {"value": 2, "to": "extra"}]]
        for rules in batches:
            with self.subTest(rules=rules), self.assertRaises((ValueError, TypeError)):
                self.app.store_rule_batch(rules)
            self.assertEqual(self.app.config, before)
            self.assertIs(self.app.current_result, output)
            self.assertEqual(len(self.app.table.get_children()), 9)

    def test_custom_dialog_rechecks_after_success_and_can_be_corrected(self):
        dialog = self.app.custom_rule_dialog()
        rules = [{"value": "VND", "to": "custom.currency"},
                 {"from": "customer.name", "to": "custom.name", "transforms": ["trim"]}]
        fill(dialog.text, dumps(rules))
        self.assertEqual(dialog.check(), rules)
        fill(dialog.text, '{"value":1,"to":"bad..path"}')
        dialog.accept()
        self.assertIsNone(dialog.result)
        self.assertTrue(dialog.winfo_exists())
        self.assertIn("Chưa hợp lệ", dialog.feedback.get())
        self.assertEqual(len(self.app.config["rules"]), 9)
        fill(dialog.text, dumps(rules))
        dialog.accept()
        self.app.store_rule_batch(dialog.result)
        self.assertEqual(self.app.config["rules"][-2:], rules)
        self.assertTrue(self.app.run())
        self.assertEqual(self.app.current_result["custom"], {"currency": "VND", "name": "Nguyễn An"})

    def test_single_json_edit_and_multi_selection_guard(self):
        self.app.table.selection_set("0", "1")
        self.root.update()
        self.assertTrue(self.app.rule_buttons["Sửa JSON"].instate(["disabled"]))
        with patch.object(self.app, "save_custom_rules") as save:
            self.app.edit_custom_rule()
        save.assert_not_called()
        self.app.table.selection_set("0")
        self.root.update()
        self.assertTrue(self.app.rule_buttons["Sửa JSON"].instate(["!disabled"]))
        rule = {"from": "a.a", "to": "hello", "name": "Tên tùy chỉnh"}
        dialog = self.app.custom_rule_dialog(0)
        fill(dialog.text, dumps([rule, rule]))
        self.assertIsNone(dialog.check())
        fill(dialog.text, dumps(rule))
        dialog.accept()
        self.app.store_rule_batch(dialog.result, 0)
        self.assertEqual(len(self.app.config["rules"]), 9)
        self.assertEqual(self.app.config["rules"][0], rule)

    def test_custom_add_callback_uses_modal_dialog(self):
        create = self.app.custom_rule_dialog
        def open_dialog(index=None):
            dialog = create(index)
            fill(dialog.text, '{"value": true, "to": "custom.flag"}')
            dialog.after(1, dialog.accept)
            return dialog
        with patch.object(self.app, "custom_rule_dialog", side_effect=open_dialog):
            self.app.add_custom_rules()
        self.assertEqual(self.app.config["rules"][-1], {"value": True, "to": "custom.flag"})

    def test_form_rejects_invalid_rule_without_closing(self):
        dialog = self.app.rule_dialog()
        dialog.source.set("customer.age")
        dialog.target.set("extra")
        fill(dialog.steps, '["not_an_op"]')
        with patch("app.messagebox.showerror") as error:
            dialog.accept()
        error.assert_called_once()
        self.assertIsNone(dialog.result)
        self.assertTrue(dialog.winfo_exists())
        self.assertEqual(len(self.app.config["rules"]), 9)
        dialog.destroy()

    def test_composer_prefixes_and_renames_checked_before_insertion(self):
        window = tk.Toplevel(self.root)
        app = ComposerApp(window)
        app.load_demo()
        snapshot = deepcopy((app.sources, app.config))
        for rule in ({"from": "value:Unknown:$.x", "to": "extra"},
                     {"value": 1, "to": "value:A:$.x"},
                     {"value": 1, "to": "field:B:$.missing"},
                     {"op": "rename", "to": "profile.full_name", "value": 2}):
            with self.subTest(rule=rule), self.assertRaises(MappingError):
                app.store_rule_batch([rule])
            self.assertEqual((app.sources, app.config), snapshot)
        app.conflict.set("overwrite")
        rules = [{"op": "rename", "to": "profile.full_name", "value": "display_name"},
                 {"value": {"nested": [1, 2]}, "to": "custom"}]
        dialog = app.custom_rule_dialog()
        fill(dialog.text, dumps(rules))
        dialog.accept()
        self.assertEqual(dialog.result, rules)
        app.store_rule_batch(dialog.result)
        self.assertTrue(app.run())
        self.assertEqual(app.current_result["profile"]["display_name"], "Nguyễn An")
        self.assertEqual(app.sources, snapshot[0])
        self.assertIn("\t\t", app.output.get("1.0", "end-1c"))


if __name__ == "__main__":
    unittest.main()
