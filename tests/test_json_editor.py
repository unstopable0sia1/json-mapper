from pathlib import Path
import sys
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import MapperApp, editor, fill
from composer_app import ComposerApp
from mapper import dumps, loads


class JsonEditorTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.addCleanup(self.root.destroy)
        self.box = editor(self.root)

    def test_tabs_preserve_unicode_types_and_string_whitespace(self):
        data = {"Tiếng Việt": {"value": " a\tb\n  c ", "items": [None, False, 1.5]}}
        fill(self.box, dumps(data))
        text = self.box.get("1.0", "end-1c")
        self.assertIn('\n\t"Tiếng Việt"', text)
        self.assertIn('\n\t\t"items"', text)
        self.assertEqual(loads(text), data)

    def test_explicit_format_invalid_json_and_undo(self):
        self.box.insert("1.0", '{"a":{"b":1}}')
        self.box.edit_reset()
        self.assertTrue(self.box.format_json())
        self.assertIn('\n\t\t"b"', self.box.get("1.0", "end-1c"))
        self.box.edit_undo()
        self.assertEqual(self.box.get("1.0", "end-1c"), '{"a":{"b":1}}')
        fill(self.box, '{"a":')
        before = self.box.get("1.0", "end-1c")
        self.assertFalse(self.box.format_json())
        self.assertEqual(self.box.get("1.0", "end-1c"), before)

    def test_indent_and_unindent_only_selected_lines(self):
        fill(self.box, "one\ntwo\nthree")
        self.box.tag_add("sel", "1.0", "3.0")
        self.box.indent()
        self.assertEqual(self.box.get("1.0", "end-1c"), "\tone\n\ttwo\nthree")
        self.box.indent(remove=True)
        self.assertEqual(self.box.get("1.0", "end-1c"), "one\ntwo\nthree")

    def test_newline_indents_inside_braces_and_readonly_stays_readonly(self):
        fill(self.box, "{}")
        self.box.delete("1.0", "end")
        self.box.insert("1.0", "{}")
        self.box.mark_set("insert", "1.1")
        self.box.newline()
        self.assertEqual(self.box.get("1.0", "end-1c"), "{\n\t\n}")
        self.assertEqual(self.box.index("insert"), "2.1")
        fill(self.box, '{"a":1}', readonly=True)
        before = self.box.get("1.0", "end-1c")
        self.box.indent()
        self.box.newline()
        self.box.format_json()
        self.assertEqual(self.box.get("1.0", "end-1c"), before)

    def test_formatting_invalidates_preview_and_tree_preserves_copy_path(self):
        app = MapperApp(self.root)
        self.root.update()
        self.assertIsNotNone(app.current_result)
        app.source.format_json()
        self.root.update()
        self.assertIsNone(app.current_result)
        self.assertTrue(app.export_button.instate(["disabled"]))
        window = tk.Toplevel(self.root)
        composer = ComposerApp(window)
        composer.sources = {"A": {"customer": {"a.b": 7}}}
        composer.refresh_sources("A")
        by_path = {tokens: item for item, tokens in composer.path_tokens.items()}
        self.assertEqual(composer.paths.parent(by_path[("customer", "a.b")]), by_path[("customer",)])
        self.assertEqual(composer.paths.parent(by_path[("customer",)]), by_path[()])
        composer.paths.selection_set(by_path[("customer", "a.b")])
        composer.copy_reference("field")
        self.assertEqual(self.root.clipboard_get(), 'field:A:$.customer["a.b"]')

    def test_rule_controls_fit_narrow_windows(self):
        for app_type in (MapperApp, ComposerApp):
            with self.subTest(app=app_type.__name__):
                window = tk.Toplevel(self.root)
                app = app_type(window)
                window.geometry("1100x700")
                window.update()
                self.assertGreater(app.table.winfo_width(), 300)
                for name, button in app.rule_buttons.items():
                    self.assertTrue(button.winfo_ismapped(), name)
                    self.assertGreaterEqual(button.winfo_width(), button.winfo_reqwidth(), name)
                window.destroy()


if __name__ == "__main__":
    unittest.main()
