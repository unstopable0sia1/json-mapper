"""Native desktop editor for mapper.py (Tkinter, no third-party dependencies)."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from json_editor import JsonEditor, display_json
from custom_rules import CustomRuleDialog

from mapper import MappingError, OPS, convert, dumps, format_path, loads, validate_config, write_json

ROOT = Path(__file__).resolve().parent


def editor(parent, *, readonly=False, height=10):
    return JsonEditor(parent, readonly=readonly, height=height)


def fill(box, value, *, readonly=False):
    try:
        value = display_json(loads(value))
    except (ValueError, RecursionError):
        pass  # Error messages and unfinished JSON remain readable verbatim.
    box.configure(state="normal")
    box.delete("1.0", "end")
    box.insert("1.0", value)
    box.edit_modified(False)
    if readonly:
        box.configure(state="disabled")


def balance_panes(panes):
    initialized = False

    def initialize(event):
        nonlocal initialized
        width = panes.winfo_width()
        if not initialized and width > 1:
            panes.sashpos(0, int(width * 0.28))
            panes.sashpos(1, int(width * 0.72))
            initialized = True

    panes.bind("<Map>", initialize)


class RuleDialog(tk.Toplevel):
    def __init__(self, parent, rule=None, *, validator=None, help_text=None, operations=False):
        super().__init__(parent)
        self.title("Chỉnh rule" if rule else "Thêm rule")
        self.transient(parent)
        self.geometry("700x640")
        self.minsize(580, 550)
        self.result = None
        self.validator = validator or (lambda item: validate_config({"rules": [item]}))
        self.operations = operations
        self.original = deepcopy(rule or {})
        self.operation = tk.StringVar(value=self.original.get("op", "set"))
        self.kind = tk.StringVar(value="value" if rule and "value" in rule else "from")
        self.source = tk.StringVar(value=self.original.get("from", ""))
        self.target = tk.StringVar(value=self.original.get("to", ""))
        self.constant = tk.StringVar(value=dumps(self.original.get("value", "")).strip())
        self.policy = tk.StringVar(value=self.original.get("missing", "inherit"))
        self.default = tk.StringVar(value=dumps(self.original.get("default", None)).strip())
        self.enabled = tk.BooleanVar(value=self.original.get("enabled", True))
        area = ttk.Frame(self, padding=18)
        area.pack(fill="both", expand=True)
        area.columnconfigure(1, weight=1)
        ttk.Label(area, text="Nguồn giá trị").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Combobox(area, textvariable=self.kind, values=("from", "value"), state="readonly", width=14).grid(row=0, column=1, sticky="w")
        for row, label, variable in ((1, "Path nguồn", self.source), (2, "Hằng số (JSON)", self.constant),
                                      (3, "Path đích", self.target)):
            ttk.Label(area, text=label).grid(row=row, column=0, sticky="w", pady=8)
            ttk.Entry(area, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=(12, 0))
        ttk.Label(area, text=help_text or 'Ví dụ: a.a → b.b | rows[*].name → items[*].title | $ = toàn bộ giá trị',
                  wraplength=620, foreground="#425e7d").grid(row=4, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Label(area, text="Khi thiếu field").grid(row=5, column=0, sticky="w", pady=8)
        ttk.Combobox(area, textvariable=self.policy, values=("inherit", "error", "skip", "default"), state="readonly").grid(row=5, column=1, sticky="ew", padx=(12, 0))
        ttk.Label(area, text="Default (JSON)").grid(row=6, column=0, sticky="w", pady=8)
        ttk.Entry(area, textvariable=self.default).grid(row=6, column=1, sticky="ew", padx=(12, 0))
        ttk.Label(area, text='Chuỗi phép biến đổi (JSON), ví dụ ["trim", "integer"]').grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 4))
        self.steps = editor(area, height=5)
        self.steps.grid(row=8, column=0, columnspan=2, sticky="nsew")
        area.rowconfigure(8, weight=1)
        fill(self.steps, dumps(self.original.get("transforms", [])))
        ttk.Label(area, text="Có sẵn: " + ", ".join(OPS) + ". Tham số split/join/replace/lookup xem README.",
                  wraplength=620, foreground="#425e7d").grid(row=9, column=0, columnspan=2, sticky="w", pady=8)
        ttk.Checkbutton(area, text="Bật rule", variable=self.enabled).grid(row=10, column=0, sticky="w")
        if operations:
            self.geometry("740x720")
            ttk.Label(area, text="Thao tác: set / delete / rename").grid(row=11, column=0, sticky="w", pady=8)
            ttk.Combobox(area, textvariable=self.operation, values=("set", "delete", "rename"),
                         state="readonly").grid(row=11, column=1, sticky="ew", padx=(12, 0))
        actions = ttk.Frame(area)
        actions.grid(row=12, column=0, columnspan=2, sticky="e", pady=(16, 0))
        ttk.Button(actions, text="Hủy", command=self.destroy).pack(side="left", padx=5)
        ttk.Button(actions, text="Lưu rule", command=self.accept).pack(side="left")
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Control-Return>", lambda e: self.accept())
        self.grab_set()

    def accept(self):
        try:
            rule = {"to": self.target.get().strip(), "enabled": self.enabled.get()}
            if "name" in self.original:
                rule["name"] = self.original["name"]
            deleting = self.operations and self.operation.get() == "delete"
            if not deleting:
                if self.kind.get() == "from":
                    rule["from"] = self.source.get().strip()
                else:
                    rule["value"] = loads(self.constant.get())
            if self.policy.get() != "inherit":
                rule["missing"] = self.policy.get()
            if not deleting and (self.policy.get() == "default" or "default" in self.original):
                rule["default"] = loads(self.default.get())
            if not deleting:
                rule["transforms"] = loads(self.steps.get("1.0", "end-1c"))
            if self.operations:
                rule["op"] = self.operation.get()
                if rule["op"] == "delete":
                    rule = {key: value for key, value in rule.items()
                            if key in ("op", "to", "enabled", "name", "missing")}
            self.validator(rule)
            self.result = rule
            self.destroy()
        except (ValueError, TypeError, RecursionError) as exc:
            messagebox.showerror("Rule chưa hợp lệ", str(exc), parent=self)


class MapperApp:
    def __init__(self, root):
        self.root = root
        root.title("JSON Mapper · Chuyển cấu trúc JSON theo rule")
        width = min(1480, root.winfo_screenwidth() - 70)
        height = min(880, root.winfo_screenheight() - 90)
        root.geometry(f"{width}x{height}")
        root.minsize(1100, 700)
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TFrame", background="#edf2f8")
        style.configure("TLabel", background="#edf2f8", foreground="#182b42", font=("Segoe UI", 10))
        style.configure("TButton", padding=(10, 7), font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 20))
        style.configure("Treeview", rowheight=29, font=("Segoe UI", 10))
        self.config = {"version": 1, "mode": "document", "missing": "error", "rules": []}
        self.protected_sources = set()
        self.rules_path = None
        self.current_result = None
        self.last_report = None
        self.mode = tk.StringVar(value="document")
        self.source_root = tk.StringVar(value="$")
        self.output_root = tk.StringVar(value="$")
        self.base = tk.StringVar(value="empty")
        self.missing = tk.StringVar(value="error")
        self.status = tk.StringVar(value="Mở JSON nguồn hoặc dán vào ô bên trái. Thêm rule để bắt đầu.")
        self._build()
        for var in (self.mode, self.source_root, self.output_root, self.base, self.missing):
            var.trace_add("write", lambda *args: self.invalidate())
        self.source.bind("<<Modified>>", self.source_changed)
        root.bind("<F5>", lambda e: self.run())
        root.bind("<Control-o>", lambda e: self.open_source())
        root.bind("<Control-s>", lambda e: self.save_rules())
        self.load_demo()

    def _build(self):
        shell = ttk.Frame(self.root, padding=18)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="JSON Mapper", style="Title.TLabel").pack(anchor="w")
        ttk.Label(shell, text="Chọn nguồn · Đặt mapping · Xem trước · Xuất JSON", foreground="#526d8b").pack(anchor="w", pady=(0, 12))
        toolbar = ttk.Frame(shell)
        toolbar.pack(fill="x", pady=(0, 10))
        for label, command in (("Mở JSON nguồn", self.open_source), ("Nạp rule", self.open_rules),
                               ("Lưu rule", self.save_rules), ("Ví dụ", self.load_demo),
                               ("Rule JSON nâng cao", self.advanced), ("Chuyển đổi (F5)", self.run),
                               ("Ghép nhiều JSON…", self.open_composer)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 7))
        self.export_button = ttk.Button(toolbar, text="Xuất JSON…", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        settings = ttk.Frame(shell)
        settings.pack(fill="x", pady=(0, 12))
        for label, var, choices, width in (("Chế độ", self.mode, ("document", "each"), 11),
                                            ("Gốc nguồn", self.source_root, None, 19),
                                            ("Gốc đích", self.output_root, None, 19),
                                            ("Nền đích", self.base, ("empty", "source"), 9),
                                            ("Thiếu field", self.missing, ("error", "skip", "default"), 9)):
            ttk.Label(settings, text=label).pack(side="left", padx=(0, 5))
            widget = ttk.Combobox(settings, textvariable=var, values=choices, state="readonly", width=width) if choices else ttk.Entry(settings, textvariable=var, width=width)
            widget.pack(side="left", padx=(0, 16))
        panes = ttk.Panedwindow(shell, orient="horizontal")
        panes.pack(fill="both", expand=True)
        left, middle, right = (ttk.Frame(panes) for _ in range(3))
        panes.add(left, weight=3)
        panes.add(middle, weight=4)
        panes.add(right, weight=3)
        balance_panes(panes)
        ttk.Label(left, text="1. JSON NGUỒN · có thể sửa / dán", font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, 7))
        source_tabs = ttk.Notebook(left)
        source_tabs.pack(fill="both", expand=True, padx=(0, 8))
        source_tab, paths_tab = ttk.Frame(source_tabs), ttk.Frame(source_tabs)
        source_tabs.add(source_tab, text="Nội dung JSON")
        source_tabs.add(paths_tab, text="Path nguồn")
        self.source = editor(source_tab)
        self.source.pack(fill="both", expand=True)
        ttk.Button(paths_tab, text="Quét path từ JSON hiện tại", command=self.scan_paths).pack(anchor="w", pady=6)
        self.paths = tk.Listbox(paths_tab, font=("Consolas", 10), background="#fafcff", activestyle="none")
        self.paths.pack(fill="both", expand=True)
        self.paths.bind("<Double-Button-1>", self.copy_path)
        ttk.Label(paths_tab, text="Nhấp đúp để copy path. Quét tối đa 3.000 path.", wraplength=290).pack(anchor="w", pady=6)
        ttk.Label(middle, text="2. RULE MAPPING · theo thứ tự từ trên xuống", font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, 7))
        table_frame = ttk.Frame(middle)
        table_frame.pack(fill="both", expand=True, padx=(0, 8))
        self.table = ttk.Treeview(table_frame, columns=("source", "target", "op"), show="headings", selectmode="extended")
        for key, title, width in (("source", "Nguồn / hằng số", 175), ("target", "Đích", 175), ("op", "Biến đổi", 100)):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, minwidth=60)
        scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.bind("<Double-1>", lambda e: self.edit_rule())
        self.table.bind("<<TreeviewSelect>>", self.update_rule_actions)
        rule_actions = ttk.Frame(middle)
        rule_actions.pack(fill="x", pady=8)
        self.rule_buttons = {}
        for index, (label, command) in enumerate((("+ Thêm", self.add_rule), ("Sửa", self.edit_rule), ("Xóa", self.delete_rule),
                                                ("↑", lambda: self.move_rule(-1)), ("↓", lambda: self.move_rule(1)))):
            button = ttk.Button(rule_actions, text=label, command=command, width=7)
            button.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 4), pady=2)
            rule_actions.columnconfigure(index % 3, weight=1)
            self.rule_buttons[label] = button
        self.custom_rule_actions(middle)
        self.update_rule_actions()
        ttk.Label(middle, text="Ctrl + nhấp: chọn nhiều rule · Shift + nhấp: chọn một dải.",
                  wraplength=420, foreground="#425e7d").pack(anchor="w")
        ttk.Label(middle, text='a.a → b.b\nitems[*].name → rows[*].title\n["key.có.dấu.chấm"] → data.value\n\neach: mỗi phần tử mảng nguồn tạo một kết quả.\ndocument: chuyển toàn bộ JSON một lần.\n\nRule nâng cao: template, lookup, chuỗi transforms, bật/tắt rule, xử lý ghi chồng.',
                  wraplength=420, justify="left", foreground="#425e7d").pack(anchor="w", pady=(8, 0))
        ttk.Label(right, text="3. JSON KẾT QUẢ · xem trước trước khi xuất", font=("Segoe UI Semibold", 10)).pack(anchor="w", pady=(0, 7))
        result_tabs = ttk.Notebook(right)
        result_tabs.pack(fill="both", expand=True)
        output_tab, report_tab = ttk.Frame(result_tabs), ttk.Frame(result_tabs)
        result_tabs.add(output_tab, text="Kết quả")
        result_tabs.add(report_tab, text="Báo cáo / lỗi")
        self.output = editor(output_tab, readonly=True)
        self.output.pack(fill="both", expand=True)
        self.report = editor(report_tab, readonly=True)
        self.report.pack(fill="both", expand=True)
        self.report_tabs = result_tabs
        ttk.Label(shell, textvariable=self.status, wraplength=1380).pack(fill="x", pady=(12, 0))

    def invalidate(self):
        self.current_result = None
        self.last_report = None
        self.export_button.configure(state="disabled")
        fill(self.output, "", readonly=True)
        fill(self.report, "", readonly=True)
        self.status.set("Nguồn hoặc rule đã thay đổi. Bấm Chuyển đổi để cập nhật kết quả.")

    def source_changed(self, event=None):
        if self.source.edit_modified():
            self.source.edit_modified(False)
            self.invalidate()

    def get_config(self):
        config = deepcopy(self.config)
        config.update({"mode": self.mode.get(), "source_root": self.source_root.get().strip(),
                       "output_root": self.output_root.get().strip(), "base": self.base.get(), "missing": self.missing.get()})
        return config

    def apply_config(self, config):
        validate_config(config)
        self.config = deepcopy(config)
        self.mode.set(config.get("mode", "document"))
        self.source_root.set(config.get("source_root", "$"))
        self.output_root.set(config.get("output_root", "$"))
        self.base.set(config.get("base", "empty"))
        self.missing.set(config.get("missing", "error"))
        self.refresh_rules()

    def refresh_rules(self, select=None):
        self.table.delete(*self.table.get_children())
        for index, rule in enumerate(self.config["rules"]):
            source = (rule["from"] if "from" in rule else
                      "= " + json.dumps(rule.get("value"), ensure_ascii=False, allow_nan=False))
            if rule.get("op") == "delete":
                source = "—"
            ops = " → ".join(step if isinstance(step, str) else step.get("op", "?") for step in rule.get("transforms", [])) or "copy"
            if rule.get("op", "set") != "set":
                ops = rule["op"] + " · " + ops
            if not rule.get("enabled", True):
                source = "[TẮT] " + source
            self.table.insert("", "end", iid=str(index), values=(source, rule["to"], ops))
        if select is not None:
            self.table.selection_set(str(select))
            self.table.see(str(select))
        self.update_rule_actions()
        self.invalidate()

    def update_rule_actions(self, event=None):
        count = len(self.table.selection())
        for label in ("Sửa", "↑", "↓", "Sửa JSON"):
            self.rule_buttons[label].configure(state="normal" if count == 1 else "disabled")
        self.rule_buttons["Xóa"].configure(state="normal" if count else "disabled")

    def selected(self):
        values = self.table.selection()
        return int(values[0]) if len(values) == 1 else None

    def rule_dialog(self, rule=None):
        index = self.selected() if rule is not None else None
        return RuleDialog(self.root, rule, validator=lambda item: self.validate_rule_batch([item], index))

    def custom_rule_actions(self, parent):
        actions = ttk.Frame(parent)
        actions.pack(fill="x", pady=4)
        for label, text, command in (("Custom JSON", "+ Custom JSON…", self.add_custom_rules),
                                     ("Sửa JSON", "Sửa JSON…", self.edit_custom_rule)):
            button = ttk.Button(actions, text=text, command=command, padding=(4, 4))
            button.pack(side="left", padx=(0, 4))
            self.rule_buttons[label] = button

    def validate_rule_batch(self, rules, replace_index=None):
        if not isinstance(rules, list) or not rules:
            raise MappingError("Cần ít nhất một rule.")
        if replace_index is not None and len(rules) != 1:
            raise MappingError("Chỉ sửa một rule mỗi lần.")
        candidate = self.get_config()
        if replace_index is None:
            candidate["rules"].extend(deepcopy(rules))
        else:
            candidate["rules"][replace_index] = deepcopy(rules[0])
        self.check_rule_config(candidate)
        return candidate

    def check_rule_config(self, config):
        # The engine validates conventions and dry-runs without changing source or preview.
        convert(loads(self.source.get("1.0", "end-1c")), config)

    def store_rule_batch(self, rules, replace_index=None):
        candidate = self.validate_rule_batch(rules, replace_index)
        select = len(self.config["rules"]) if replace_index is None else replace_index
        self.config["rules"] = deepcopy(candidate["rules"])
        self.refresh_rules(select)

    def custom_rule_dialog(self, index=None):
        return CustomRuleDialog(self.root, validator=lambda items: self.validate_rule_batch(items, index),
                                initial=self.config["rules"][index] if index is not None else None,
                                single=index is not None, help_text=self.custom_rule_help())

    def custom_rule_help(self):
        return ('Nguồn: from hoặc value (chọn một); đích: to. Path: a.b, items[*].id, ["key.có.chấm"].\n'
                'Tùy chọn: transforms, missing, default, enabled, name. Không nhận field hoặc phép biến đổi ngoài quy ước.')

    def add_custom_rules(self):
        self.save_custom_rules()

    def edit_custom_rule(self):
        index = self.selected()
        if index is not None:
            self.save_custom_rules(index)

    def save_custom_rules(self, index=None):
        dialog = self.custom_rule_dialog(index)
        self.root.wait_window(dialog)
        if dialog.result is not None:
            try:
                self.store_rule_batch(dialog.result, index)
            except (ValueError, TypeError, RecursionError) as exc:
                messagebox.showerror("Rule chưa hợp lệ — chưa lưu", str(exc), parent=self.root)

    def add_rule(self):
        dialog = self.rule_dialog()
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.store_rule_batch([dialog.result])
            except (ValueError, TypeError, RecursionError) as exc:
                messagebox.showerror("Rule chưa hợp lệ — chưa lưu", str(exc), parent=self.root)

    def edit_rule(self):
        index = self.selected()
        if index is None:
            return
        dialog = self.rule_dialog(self.config["rules"][index])
        self.root.wait_window(dialog)
        if dialog.result:
            try:
                self.store_rule_batch([dialog.result], index)
            except (ValueError, TypeError, RecursionError) as exc:
                messagebox.showerror("Rule chưa hợp lệ — chưa lưu", str(exc), parent=self.root)

    def delete_rule(self):
        indices = sorted((int(value) for value in self.table.selection()), reverse=True)
        if indices:
            for index in indices:
                del self.config["rules"][index]
            self.refresh_rules()

    def move_rule(self, offset):
        index = self.selected()
        if index is None or not 0 <= index + offset < len(self.config["rules"]):
            return
        rules = self.config["rules"]
        rules[index], rules[index + offset] = rules[index + offset], rules[index]
        self.refresh_rules(index + offset)

    def open_source(self):
        path = filedialog.askopenfilename(title="Mở JSON nguồn", filetypes=[("JSON", "*.json"), ("Tất cả", "*.*")])
        if not path:
            return
        try:
            data = loads(Path(path).read_text(encoding="utf-8-sig"))
            fill(self.source, dumps(data))
            self.protected_sources.add(Path(path).resolve())
            self.paths.delete(0, "end")
            self.invalidate()
            self.status.set("Đã nạp nguồn: " + path)
        except (ValueError, OSError, UnicodeError) as exc:
            messagebox.showerror("Không mở được JSON", str(exc), parent=self.root)

    def open_composer(self):
        from composer_app import ComposerApp
        window = getattr(self, "composer_window", None)
        if window is not None and window.winfo_exists():
            window.deiconify()
            window.lift()
            return
        self.composer_window = tk.Toplevel(self.root)
        self.composer_app = ComposerApp(self.composer_window)

    def open_rules(self):
        path = filedialog.askopenfilename(title="Nạp bộ rule", filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.apply_config(loads(Path(path).read_text(encoding="utf-8-sig")))
                self.rules_path = Path(path).resolve()
                self.status.set("Đã nạp rule: " + path)
            except (ValueError, OSError, UnicodeError) as exc:
                messagebox.showerror("Không nạp được rule", str(exc), parent=self.root)

    def save_rules(self):
        try:
            config = validate_config(self.get_config())
            path = filedialog.asksaveasfilename(title="Lưu bộ rule tái sử dụng", defaultextension=".json", initialfile="mapping.rules.json", filetypes=[("JSON", "*.json")])
            if path:
                write_json(path, config, overwrite=True, protected=self.protected_sources)
                self.rules_path = Path(path).resolve()
                self.status.set("Đã lưu rule: " + path)
        except (ValueError, OSError) as exc:
            messagebox.showerror("Không lưu được rule", str(exc), parent=self.root)

    def load_demo(self):
        try:
            self.apply_config(loads((ROOT / "examples" / "mapping.rules.json").read_text(encoding="utf-8")))
            fill(self.source, (ROOT / "examples" / "input.json").read_text(encoding="utf-8"))
            self.rules_path = None
            self.run()
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))

    def scan_paths(self):
        try:
            data = loads(self.source.get("1.0", "end-1c"))
            self.paths.delete(0, "end")
            found, visited, truncated = set(), 0, False

            def walk(value, path):
                nonlocal visited, truncated
                visited += 1
                if visited > 20000 or len(found) >= 3000:
                    truncated = True
                    return
                found.add(format_path(path))
                if isinstance(value, dict):
                    for key, child in value.items():
                        if truncated:
                            break
                        walk(child, path + (key,))
                elif isinstance(value, list):
                    from mapper import STAR
                    for child in value:
                        if truncated:
                            break
                        walk(child, path + (STAR,))

            walk(data, ())
            for path in sorted(found):
                self.paths.insert("end", path)
            self.status.set(f"Đã quét {len(found)} path" + (" (đã chạm giới hạn quét; JSON nguồn vẫn giữ đủ)." if truncated else ". Nhấp đúp để copy."))
        except (ValueError, RecursionError) as exc:
            messagebox.showerror("Không quét được path", str(exc), parent=self.root)

    def copy_path(self, event=None):
        selection = self.paths.curselection()
        if selection:
            path = self.paths.get(selection[0])
            self.root.clipboard_clear()
            self.root.clipboard_append(path)
            self.status.set("Đã copy: " + path)

    def advanced(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Bộ rule JSON nâng cao")
        dialog.geometry("900x720")
        dialog.transient(self.root)
        area = ttk.Frame(dialog, padding=16)
        area.pack(fill="both", expand=True)
        ttk.Label(area, text="Sửa toàn bộ cấu hình. Bấm Áp dụng để đồng bộ về bảng mapping.").pack(anchor="w", pady=(0, 8))
        text = editor(area)
        text.pack(fill="both", expand=True)
        fill(text, dumps(self.get_config()))

        def apply():
            try:
                config = loads(text.get("1.0", "end-1c"))
                self.check_rule_config(config)
                self.apply_config(config)
                dialog.destroy()
            except (ValueError, TypeError, RecursionError) as exc:
                messagebox.showerror("Bộ rule chưa hợp lệ", str(exc), parent=dialog)

        actions = ttk.Frame(area)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Hủy", command=dialog.destroy).pack(side="right")
        ttk.Button(actions, text="Áp dụng", command=apply).pack(side="right", padx=8)
        dialog.grab_set()

    def run(self, show_errors=False):
        self.invalidate()
        try:
            result, report = convert(loads(self.source.get("1.0", "end-1c")), self.get_config())
            self.current_result, self.last_report = result, report
            fill(self.output, dumps(result), readonly=True)
            fill(self.report, dumps(report), readonly=True)
            self.export_button.configure(state="normal")
            self.status.set(f"Thành công · {report['records']} bản ghi · {report['written']} giá trị đã map · {report['defaults']} default · {report['skipped']} bỏ qua. Chưa ghi file; bấm Xuất JSON để lưu.")
            self.report_tabs.select(0)
            return True
        except (ValueError, TypeError, RecursionError) as exc:
            fill(self.report, str(exc), readonly=True)
            self.report_tabs.select(1)
            self.status.set("Chuyển đổi chưa thành công. Xem Báo cáo / lỗi.")
            if show_errors:
                messagebox.showerror("Chuyển đổi chưa thành công", str(exc), parent=self.root)
            return False

    def export(self):
        # Recompute to guarantee that the saved file matches CURRENT input/settings.
        if not self.run(show_errors=True):
            return
        path = filedialog.asksaveasfilename(title="Xuất JSON kết quả", defaultextension=".json", initialfile="converted.json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                protected = list(self.protected_sources) + ([self.rules_path] if self.rules_path else [])
                write_json(path, self.current_result, overwrite=True, protected=protected)
                self.status.set("Đã xuất JSON: " + path)
            except (ValueError, OSError) as exc:
                messagebox.showerror("Không xuất được JSON", str(exc), parent=self.root)


def main():
    root = tk.Tk()
    MapperApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
