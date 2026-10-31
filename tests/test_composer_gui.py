from pathlib import Path
import sys
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import MapperApp, fill
from composer_app import ComposerApp
from mapper import dumps, loads

ROOT = Path(__file__).resolve().parents[1]


class ComposerGuiTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.errors = []
        self.root.report_callback_exception = lambda kind, error, trace: self.errors.append(error)
        self.addCleanup(self.root.destroy)
        self.app = ComposerApp(self.root)
        self.root.update()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def tearDown(self):
        self.assertEqual(self.errors, [])

    def test_load_multiple_sources_and_structure_without_mutating_sources(self):
        a, b, c = [self.folder / f"{alias}.json" for alias in "ABC"]
        a.write_text(dumps({"name": "An"}), encoding="utf-8")
        b.write_text(dumps({"profile": {"name": ""}, "keep": 5}), encoding="utf-8")
        c.write_text(dumps({"currency": "VND"}), encoding="utf-8")
        with patch("composer_app.filedialog.askopenfilenames", return_value=(str(a), str(c))), \
             patch("composer_app.simpledialog.askstring", side_effect=["A", "C"]):
            self.app.open_source()
        with patch("composer_app.filedialog.askopenfilename", return_value=str(b)), \
             patch("composer_app.simpledialog.askstring", return_value="B"):
            self.app.open_template()
        self.assertEqual(set(self.app.sources), {"A", "B", "C"})
        self.app.config["rules"] = [
            {"from": "value:A:$.name", "to": "field:B:$.profile.name"},
            {"from": "value:C:$.currency", "to": "meta.currency"}]
        self.app.refresh_rules()
        self.assertTrue(self.app.run())
        self.assertEqual(self.app.current_result, {"profile": {"name": "An"}, "keep": 5, "meta": {"currency": "VND"}})
        self.root.update()
        self.assertIsNotNone(self.app.current_result)
        self.app.template.insert("end", " ")
        self.root.update()
        self.assertIsNone(self.app.current_result)
        self.assertTrue(self.app.export_button.instate(["disabled"]))
        self.assertEqual(self.app.sources["B"]["profile"]["name"], "")

    def test_copy_field_and_value_references(self):
        self.app.sources = {"A": {"a.b": 7}}
        self.app.refresh_sources("A")
        item = next(item for item, tokens in self.app.path_tokens.items() if tokens == ("a.b",))
        self.app.paths.selection_set(item)
        self.app.copy_reference("value")
        self.assertEqual(self.root.clipboard_get(), 'value:A:$["a.b"]')
        self.app.copy_reference("field")
        self.assertEqual(self.root.clipboard_get(), 'field:A:$["a.b"]')

    def test_rule_dialog_accepts_references_and_structure_operations(self):
        self.app.sources = {"A": {"name": "An"}, "B": {"profile": {"full_name": ""}}}
        fill(self.app.template, dumps({"profile": {"full_name": "", "obsolete": True}}))
        dialog = self.app.rule_dialog()
        dialog.source.set("value:A:$.name")
        dialog.target.set("field:B:$.profile.full_name")
        dialog.accept()
        self.assertEqual(dialog.result["from"], "value:A:$.name")
        dialog = self.app.rule_dialog()
        dialog.operation.set("rename")
        dialog.kind.set("value")
        dialog.constant.set('"display_name"')
        dialog.target.set("profile.full_name")
        dialog.accept()
        self.assertEqual(dialog.result["op"], "rename")
        dialog = self.app.rule_dialog()
        dialog.operation.set("delete")
        dialog.target.set("profile.obsolete")
        fill(dialog.steps, "invalid ignored for delete")
        dialog.accept()
        self.assertEqual(dialog.result, {"op": "delete", "to": "profile.obsolete", "enabled": True})

    def test_session_save_load_resave_and_export(self):
        self.app.load_demo()
        self.assertIsNotNone(self.app.current_result)
        expected = self.app.current_result
        session_path, output_path = self.folder / "session.json", self.folder / "output.json"
        with patch("composer_app.filedialog.asksaveasfilename", return_value=str(session_path)):
            self.app.save_rules()
        self.assertEqual(set(loads(session_path.read_text(encoding="utf-8"))["sources"]), {"A", "B", "C"})
        self.app.sources = {}
        with patch("composer_app.filedialog.askopenfilename", return_value=str(session_path)):
            self.app.open_rules()
        self.assertTrue(self.app.run())
        self.assertEqual(self.app.current_result, expected)
        with patch("composer_app.filedialog.asksaveasfilename", return_value=str(session_path)):
            self.app.save_rules()  # Saving updates to a loaded session is allowed.
        with patch("composer_app.filedialog.asksaveasfilename", return_value=str(output_path)):
            self.app.export()
        self.assertEqual(loads(output_path.read_text(encoding="utf-8")), expected)
        before = session_path.read_bytes()
        with patch("composer_app.filedialog.asksaveasfilename", return_value=str(session_path)), \
             patch("composer_app.messagebox.showerror") as error:
            self.app.export()
        error.assert_called_once()
        self.assertEqual(session_path.read_bytes(), before)

    def test_export_cannot_overwrite_source_or_hardlink(self):
        self.app.load_demo()
        source_path = self.folder / "source.json"
        source_path.write_text(dumps(self.app.sources["A"]), encoding="utf-8")
        alias_path = self.folder / "alias.json"
        alias_path.hardlink_to(source_path)
        self.app.protected_sources.add(source_path.resolve())
        before = source_path.read_bytes()
        with patch("composer_app.filedialog.asksaveasfilename", return_value=str(alias_path)), \
             patch("composer_app.messagebox.showerror") as error:
            self.app.export()
        error.assert_called_once()
        self.assertEqual(source_path.read_bytes(), before)

    def test_invalid_template_or_removed_source_blocks_export(self):
        self.app.load_demo()
        fill(self.app.template, "{")
        with patch("composer_app.filedialog.asksaveasfilename") as save, \
             patch("composer_app.messagebox.showerror"):
            self.app.export()
        save.assert_not_called()
        self.assertIsNone(self.app.current_result)
        self.app.load_demo()
        self.app.refresh_sources("A")
        self.app.remove_source()
        self.assertFalse(self.app.run())
        self.assertIn("Chưa nạp nguồn", self.app.report.get("1.0", "end-1c"))

    def test_duplicate_alias_is_rejected_without_replacing_source(self):
        self.app.sources = {"A": 1}
        source_path = self.folder / "source.json"
        source_path.write_text("2", encoding="utf-8")
        with patch("composer_app.filedialog.askopenfilenames", return_value=(str(source_path),)), \
             patch("composer_app.simpledialog.askstring", return_value="A"), \
             patch("composer_app.messagebox.showerror") as error:
            self.app.open_source()
        error.assert_called_once()
        self.assertEqual(self.app.sources, {"A": 1})

    def test_multiple_rule_selection_and_main_window_integration(self):
        self.app.load_demo()
        self.app.table.selection_set("0", "1")
        self.root.update()
        self.assertTrue(self.app.rule_buttons["Sửa"].instate(["disabled"]))
        self.app.delete_rule()
        self.assertEqual(len(self.app.config["rules"]), 8)
        main_window = tk.Toplevel(self.root)
        main = MapperApp(main_window)
        main.open_composer()
        first = main.composer_app
        main.open_composer()
        self.assertIs(main.composer_app, first)
        main.composer_window.destroy()
        main.open_composer()
        self.assertIsNot(main.composer_app, first)


if __name__ == "__main__":
    unittest.main()
