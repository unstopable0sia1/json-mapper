"""Exercise actual Tk widgets and application callbacks without manual dialogs."""
from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import MapperApp, RuleDialog, fill
from mapper import dumps, loads


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.addCleanup(self.root.destroy)
        self.app = MapperApp(self.root)
        self.root.update()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.assertEqual(self.errors, [], str(self.errors))

    def test_initial_demo_and_path_browser(self):
        self.assertEqual(self.app.current_result["profile"]["age"], 27)
        self.assertEqual(str(self.app.export_button["state"]), "normal")
        self.app.scan_paths()
        paths = self.app.paths.get(0, "end")
        self.assertIn("$.orders[*].id", paths)
        self.assertEqual(len(self.app.table.get_children()), 9)

    def test_editing_input_invalidates_preview(self):
        self.app.source.insert("end", " ")
        self.root.update()
        self.assertIsNone(self.app.current_result)
        self.assertEqual(str(self.app.export_button["state"]), "disabled")
        self.assertEqual(self.app.output.get("1.0", "end-1c"), "")

    def test_reorder_and_delete_rule(self):
        self.app.table.selection_set("0")
        self.app.move_rule(1)
        self.assertEqual(self.app.config["rules"][1]["from"], "a.a")
        self.app.delete_rule()
        self.assertEqual(len(self.app.config["rules"]), 8)
        self.assertTrue(self.app.run())

    def test_rule_editor_builds_array_mapping(self):
        dialog = RuleDialog(self.root)
        dialog.source.set("rows[*].name")
        dialog.target.set("items[*].title")
        fill(dialog.steps, '["trim", "upper"]')
        dialog.accept()
        self.assertEqual(dialog.result["from"], "rows[*].name")
        self.assertEqual(dialog.result["transforms"], ["trim", "upper"])

    def test_rule_editor_constant_default_and_enabled(self):
        dialog = RuleDialog(self.root)
        dialog.kind.set("value")
        dialog.target.set("settings.enabled")
        dialog.constant.set("false")
        dialog.enabled.set(False)
        dialog.accept()
        self.assertIs(dialog.result["value"], False)
        self.assertIs(dialog.result["enabled"], False)

    def test_load_save_rules_and_export_roundtrip(self):
        source = self.folder / "source.json"
        rules = self.folder / "rules.json"
        saved_rules = self.folder / "saved-rules.json"
        output = self.folder / "converted.json"
        source.write_text('{"a":{"a":"Việt Nam"}}', encoding="utf-8")
        rules.write_text(dumps({"rules": [{"from": "a.a", "to": "b.b"}]}), encoding="utf-8")
        source_bytes = source.read_bytes()
        with patch("app.filedialog.askopenfilename", return_value=str(source)):
            self.app.open_source()
        with patch("app.filedialog.askopenfilename", return_value=str(rules)):
            self.app.open_rules()
        self.root.update()
        with patch("app.filedialog.asksaveasfilename", return_value=str(saved_rules)):
            self.app.save_rules()
        self.assertEqual(loads(saved_rules.read_text(encoding="utf-8"))["rules"][0]["to"], "b.b")
        with patch("app.filedialog.asksaveasfilename", return_value=str(output)):
            self.app.export()
        self.assertEqual(loads(output.read_text(encoding="utf-8")), {"b": {"b": "Việt Nam"}})
        self.assertEqual(source.read_bytes(), source_bytes)

    def test_gui_export_refuses_original_source(self):
        source = self.folder / "source.json"
        source.write_text("{}", encoding="utf-8")
        self.app.protected_sources.add(source.resolve())
        with patch("app.filedialog.asksaveasfilename", return_value=str(source)), patch("app.messagebox.showerror") as error:
            self.app.export()
        error.assert_called_once()
        self.assertEqual(source.read_text(), "{}")

    def test_invalid_data_does_not_leave_stale_export(self):
        fill(self.app.source, "{ broken JSON")
        self.assertFalse(self.app.run())
        self.assertIsNone(self.app.current_result)
        self.assertEqual(str(self.app.export_button["state"]), "disabled")
        self.assertIn("JSON không hợp lệ", self.app.report.get("1.0", "end-1c"))


if __name__ == "__main__":
    unittest.main()
