"""Independent desktop workspace for composing any number of JSON sources."""
from copy import deepcopy
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from app import MapperApp, RuleDialog, balance_panes, editor, fill
from composer import (ALIAS, compose, validate_composition,
                      validate_session)
from mapper import MappingError, STAR, dumps, format_path, loads, write_json

ROOT = Path(__file__).resolve().parent


class ComposerApp(MapperApp):
    def __init__(self, root):
        self.root = root
        root.title("JSON Mapper · Ghép nhiều JSON")
        root.geometry(f"{min(1500, root.winfo_screenwidth() - 60)}x{min(900, root.winfo_screenheight() - 90)}")
        root.minsize(1100, 700)
        self.sources = {}
        self.protected_sources = set()
        self.session_path = None
        self.config = {"kind": "json-composer", "version": 1, "rules": []}
        self.current_result = self.last_report = None
        self.status = tk.StringVar(value="Nạp nguồn JSON, chọn mẫu cấu trúc rồi thêm rule. Có thể sửa mẫu trực tiếp.")
        self.missing = tk.StringVar(value="error")
        self.conflict = tk.StringVar(value="error")
        self.path_tokens = {}
        self._build()
        self.template.bind("<<Modified>>", self.template_changed)
        for variable in (self.missing, self.conflict):
            variable.trace_add("write", lambda *args: self.invalidate())
        root.bind("<F5>", lambda event: self.run())
        self.refresh_rules()

    def _build(self):
        shell = ttk.Frame(self.root, padding=14)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Ghép nhiều JSON", font=("Segoe UI Semibold", 20)).pack(anchor="w")
        toolbar = ttk.Frame(shell)
        toolbar.pack(fill="x", pady=8)
        for label, command in (("Nạp nguồn JSON…", self.open_source), ("Nạp JSON cấu trúc…", self.open_template),
                               ("Nạp phiên…", self.open_rules), ("Lưu phiên…", self.save_rules),
                               ("Ví dụ 3 nguồn", self.load_demo), ("Tạo kết quả (F5)", self.run)):
            ttk.Button(toolbar, text=label, command=command).pack(side="left", padx=(0, 5))
        self.export_button = ttk.Button(toolbar, text="Xuất JSON…", command=self.export, state="disabled")
        self.export_button.pack(side="right")
        ttk.Label(shell, text="value:A:$.path = lấy giá trị · field:B:$.path = chọn field đích; ở nguồn sẽ lấy tên key.").pack(anchor="w")
        panes = ttk.Panedwindow(shell, orient="horizontal")
        panes.pack(fill="both", expand=True, pady=8)
        left, middle, right = (ttk.Frame(panes) for _ in range(3))
        for frame, weight in ((left, 3), (middle, 4), (right, 3)):
            panes.add(frame, weight=weight)
        balance_panes(panes)

        ttk.Label(left, text="1. NGUỒN JSON · bí danh phân biệt hoa/thường").pack(anchor="w")
        self.source_list = tk.Listbox(left, height=4, exportselection=False)
        self.source_list.pack(fill="x", padx=(0, 8), pady=5)
        self.source_list.bind("<<ListboxSelect>>", self.show_source)
        source_actions = ttk.Frame(left)
        source_actions.pack(fill="x")
        ttk.Button(source_actions, text="Dùng làm mẫu cấu trúc", command=self.use_template).pack(side="left")
        ttk.Button(source_actions, text="Bỏ nguồn", command=self.remove_source).pack(side="left", padx=4)
        tabs = ttk.Notebook(left)
        tabs.pack(fill="both", expand=True, padx=(0, 8), pady=6)
        paths_tab, content_tab = ttk.Frame(tabs), ttk.Frame(tabs)
        tabs.add(paths_tab, text="Field / value tham khảo")
        tabs.add(content_tab, text="JSON nguồn")
        self.source = editor(content_tab, readonly=True)
        self.source.pack(fill="both", expand=True)
        self.paths = ttk.Treeview(paths_tab, columns=("path", "value"), show="tree headings", selectmode="browse")
        self.paths.heading("#0", text="Field / cấu trúc")
        self.paths.column("#0", width=170, minwidth=100)
        self.paths.heading("path", text="Path")
        self.paths.heading("value", text="Giá trị mẫu")
        self.paths.column("path", width=170, minwidth=90)
        self.paths.column("value", width=100, minwidth=50)
        scroll = ttk.Scrollbar(paths_tab, orient="vertical", command=self.paths.yview)
        horizontal = ttk.Scrollbar(paths_tab, orient="horizontal", command=self.paths.xview)
        self.paths.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        self.paths.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        paths_tab.rowconfigure(0, weight=1)
        paths_tab.columnconfigure(0, weight=1)
        copy_actions = ttk.Frame(left)
        copy_actions.pack(fill="x")
        ttk.Button(copy_actions, text="Copy value:", command=lambda: self.copy_reference("value")).pack(side="left")
        ttk.Button(copy_actions, text="Copy field:", command=lambda: self.copy_reference("field")).pack(side="left", padx=4)
        ttk.Label(left, text="Chọn path rồi copy tham chiếu để dán vào rule.\nQuét tối đa 3.000 path / 20.000 nút; nguồn vẫn giữ đủ.",
                  wraplength=340).pack(anchor="w", pady=5)

        ttk.Label(middle, text="2. MẪU CẤU TRÚC VÀ RULE").pack(anchor="w")
        middle_tabs = ttk.Notebook(middle)
        middle_tabs.pack(fill="both", expand=True, padx=(0, 8), pady=5)
        template_tab, rules_tab = ttk.Frame(middle_tabs), ttk.Frame(middle_tabs)
        middle_tabs.add(rules_tab, text="Rule")
        middle_tabs.add(template_tab, text="Mẫu cấu trúc · sửa được")
        self.template = editor(template_tab)
        self.template.pack(fill="both", expand=True)
        fill(self.template, "{}\n")
        ttk.Label(template_tab, text="Mẫu giữ nguyên giá trị chưa được rule ghi lại. Sửa JSON để thêm, bỏ hoặc đổi cấu trúc.\n"
                  "Dùng [] cho mảng đích mới; mẫu không tự nhân bản phần tử. Parent cần object/mảng thay vì null.",
                  wraplength=250).pack(anchor="w", pady=5)
        table_frame = ttk.Frame(rules_tab)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("source", "target", "op"), show="headings", selectmode="extended")
        for key, label, width in (("source", "Nguồn / hằng số", 155), ("target", "Đích", 155), ("op", "Thao tác", 100)):
            self.table.heading(key, text=label)
            self.table.column(key, width=width, minwidth=55)
        table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        table_horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=table_scroll.set, xscrollcommand=table_horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        table_scroll.grid(row=0, column=1, sticky="ns")
        table_horizontal.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table.bind("<<TreeviewSelect>>", self.update_rule_actions)
        self.table.bind("<Double-1>", lambda event: self.edit_rule())
        actions = ttk.Frame(rules_tab)
        actions.pack(fill="x", pady=6)
        self.rule_buttons = {}
        for index, (label, command) in enumerate((("+ Thêm", self.add_rule), ("Sửa", self.edit_rule), ("Xóa", self.delete_rule),
                                                ("↑", lambda: self.move_rule(-1)), ("↓", lambda: self.move_rule(1)))):
            button = ttk.Button(actions, text=label, command=command, width=6)
            button.grid(row=index // 3, column=index % 3, sticky="ew", padx=(0, 3), pady=2)
            actions.columnconfigure(index % 3, weight=1)
            self.rule_buttons[label] = button
        self.custom_rule_actions(rules_tab)
        ttk.Button(rules_tab, text="Cấu hình JSON nâng cao…", command=self.advanced).pack(anchor="w")
        ttk.Label(rules_tab, text="set: thêm/ghi giá trị · delete: xóa field đích · rename: đổi tên field đích.\n"
                  "Ctrl/Shift + nhấp để chọn nhiều rule; Xóa sẽ xóa nhóm rule đang chọn.", wraplength=250).pack(anchor="w", pady=6)
        options = ttk.Frame(middle)
        options.pack(fill="x", pady=4)
        for row, (label, variable, choices) in enumerate((("Thiếu field", self.missing, ("error", "skip", "default")),
                                                        ("Ghi chồng", self.conflict, ("error", "overwrite")))):
            ttk.Label(options, text=label).grid(row=row, column=0, sticky="w", padx=(0, 4), pady=2)
            ttk.Combobox(options, textvariable=variable, values=choices, state="readonly", width=9).grid(row=row, column=1, sticky="w")

        ttk.Label(right, text="3. KẾT QUẢ").pack(anchor="w")
        self.report_tabs = ttk.Notebook(right)
        self.report_tabs.pack(fill="both", expand=True, pady=5)
        output_tab, report_tab = ttk.Frame(self.report_tabs), ttk.Frame(self.report_tabs)
        self.report_tabs.add(output_tab, text="JSON kết quả")
        self.report_tabs.add(report_tab, text="Báo cáo / lỗi")
        self.output = editor(output_tab, readonly=True)
        self.output.pack(fill="both", expand=True)
        self.report = editor(report_tab, readonly=True)
        self.report.pack(fill="both", expand=True)
        ttk.Label(shell, textvariable=self.status, wraplength=1400).pack(fill="x")

    def template_changed(self, event=None):
        if self.template.edit_modified():
            self.template.edit_modified(False)
            self.invalidate()

    def rule_dialog(self, rule=None):
        index = self.selected() if rule is not None else None
        return RuleDialog(self.root, rule, validator=lambda item: self.validate_rule_batch([item], index), operations=True,
                          help_text="Nguồn: value:A:$.name hoặc field:A:$.name (tên key).\n"
                          "Đích: field:B:$.profile.name hoặc profile.name.\n"
                          "rename: Đích là field cần đổi tên; Nguồn/hằng số là tên mới. delete chỉ cần Đích.")

    def check_rule_config(self, config):
        compose(self.sources, config)

    def custom_rule_help(self):
        return ('Nguồn: value:A:$.path hoặc field:A:$.path; đích: field:B:$.path hoặc path thường.\n'
                'op: set / delete / rename. Các bí danh nguồn phải đã được nạp; có thể thêm hằng số bằng value.')

    def selected_alias(self):
        selection = self.source_list.curselection()
        return self.source_list.get(selection[0]) if selection else None

    def refresh_sources(self, alias=None):
        self.source_list.delete(0, "end")
        for name in self.sources:
            self.source_list.insert("end", name)
        if self.sources:
            names = list(self.sources)
            self.source_list.selection_set(names.index(alias) if alias in self.sources else 0)
        self.show_source()

    def show_source(self, event=None):
        alias = self.selected_alias()
        fill(self.source, dumps(self.sources[alias]) if alias else "", readonly=True)
        self.paths.delete(*self.paths.get_children())
        self.path_tokens.clear()
        if alias is None:
            return
        visited = 0
        seen = set()
        items = {}

        def walk(value, tokens):
            nonlocal visited
            if visited >= 20000 or len(seen) >= 3000:
                return
            visited += 1
            path = format_path(tokens)
            if path not in seen:
                seen.add(path)
                preview = (f"object ({len(value)} keys)" if isinstance(value, dict) else
                           f"array ({len(value)})" if isinstance(value, list) else dumps(value).strip()[:90])
                label = "$" if not tokens else "[*]" if tokens[-1] is STAR else str(tokens[-1])
                item = self.paths.insert(items.get(format_path(tokens[:-1]), "") if tokens else "", "end",
                                         text=label, values=(path, preview), open=len(tokens) < 2)
                items[path] = item
                self.path_tokens[item] = tokens
            children = value.items() if isinstance(value, dict) else ((STAR, child) for child in value) if isinstance(value, list) else ()
            for key, child in children:
                if visited >= 20000 or len(seen) >= 3000:
                    break
                walk(child, tokens + (key,))

        walk(self.sources[alias], ())

    def copy_reference(self, kind):
        alias, selection = self.selected_alias(), self.paths.selection()
        if alias is None or not selection:
            return
        tokens = self.path_tokens[selection[0]]
        if kind == "field" and (not tokens or not isinstance(tokens[-1], str)):
            self.status.set("Chọn một key object để copy field:; gốc/mảng dùng value:.")
            return
        text = f"{kind}:{alias}:{format_path(tokens)}"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.status.set("Đã copy: " + text)

    def load_source_file(self, path):
        path = Path(path)
        data = loads(path.read_text(encoding="utf-8-sig"))
        suggested = re.sub(r"[^A-Za-z_0-9]", "_", path.stem)
        if not suggested or not ALIAS.fullmatch(suggested):
            suggested = "source"
        base, count = suggested, 2
        while suggested in self.sources:
            suggested = f"{base}_{count}"
            count += 1
        alias = simpledialog.askstring("Bí danh nguồn", "Đặt bí danh (ví dụ A, B, C). Dùng trong value:A:$.path / field:B:$.path.",
                                       initialvalue=suggested, parent=self.root)
        if alias is None:
            return None
        if not ALIAS.fullmatch(alias) or alias in self.sources:
            raise MappingError("Bí danh phải duy nhất, dùng chữ ASCII/số/_ và không bắt đầu bằng số.")
        self.sources[alias] = data
        self.protected_sources.add(path.resolve())
        self.refresh_sources(alias)
        self.invalidate()
        self.status.set(f"Đã nạp nguồn {alias}: {path.name}. Có {len(self.sources)} nguồn.")
        return alias

    def open_source(self):
        paths = filedialog.askopenfilenames(title="Chọn một hoặc nhiều JSON nguồn", filetypes=[("JSON", "*.json"), ("Tất cả", "*.*")], parent=self.root)
        for path in paths:
            try:
                self.load_source_file(path)
            except (ValueError, OSError, UnicodeError, RecursionError) as exc:
                messagebox.showerror("Không nạp được nguồn", f"{path}\n{exc}", parent=self.root)

    def open_template(self):
        path = filedialog.askopenfilename(title="Nạp JSON tham khảo cấu trúc", filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                alias = self.load_source_file(path)
                if alias is not None:
                    self.use_template()
            except (ValueError, OSError, UnicodeError, RecursionError) as exc:
                messagebox.showerror("Không nạp được mẫu", str(exc), parent=self.root)

    def use_template(self):
        alias = self.selected_alias()
        if alias is not None:
            fill(self.template, dumps(self.sources[alias]))
            self.invalidate()
            self.status.set(f"Đã copy {alias} làm mẫu cấu trúc. Sửa mẫu không làm đổi nguồn {alias}.")

    def remove_source(self):
        alias = self.selected_alias()
        if alias is not None:
            del self.sources[alias]
            self.refresh_sources()
            self.invalidate()
            self.status.set(f"Đã bỏ nguồn {alias}. Rule còn tham chiếu nguồn này sẽ báo lỗi khi chạy.")

    def get_config(self):
        config = deepcopy(self.config)
        config.update(template=loads(self.template.get("1.0", "end-1c")),
                      missing=self.missing.get(), on_conflict=self.conflict.get())
        return config

    def apply_config(self, config):
        validate_composition(config)
        self.config = deepcopy(config)
        self.missing.set(config.get("missing", "error"))
        self.conflict.set(config.get("on_conflict", "error"))
        fill(self.template, dumps(config.get("template", {})))
        self.refresh_rules()

    def advanced(self):
        try:
            text = dumps(self.get_config())
        except ValueError as exc:
            messagebox.showerror("Mẫu JSON không hợp lệ", str(exc), parent=self.root)
            return
        dialog = tk.Toplevel(self.root)
        dialog.title("Cấu hình ghép JSON nâng cao")
        dialog.geometry("850x680")
        area = editor(dialog)
        area.pack(fill="both", expand=True, padx=12, pady=12)
        fill(area, text)

        def apply():
            try:
                config = loads(area.get("1.0", "end-1c"))
                self.check_rule_config(config)
                self.apply_config(config)
                dialog.destroy()
            except (ValueError, TypeError, RecursionError) as exc:
                messagebox.showerror("Cấu hình không hợp lệ", str(exc), parent=dialog)

        ttk.Button(dialog, text="Áp dụng", command=apply).pack(pady=8)

    def open_rules(self):
        path = filedialog.askopenfilename(title="Nạp phiên ghép nhiều JSON", filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                session = validate_session(loads(Path(path).read_text(encoding="utf-8-sig")))
                self.sources = deepcopy(session["sources"])
                self.session_path = Path(path).resolve()
                self.apply_config(session["config"])
                self.refresh_sources()
                self.status.set("Đã nạp phiên (nguồn + mẫu + rule): " + path)
            except (ValueError, OSError, UnicodeError, RecursionError) as exc:
                messagebox.showerror("Không nạp được phiên", str(exc), parent=self.root)

    def save_rules(self):
        try:
            session = validate_session({"kind": "json-composer-session", "version": 1,
                                        "sources": self.sources, "config": self.get_config()})
            path = filedialog.asksaveasfilename(title="Lưu phiên: gồm dữ liệu nguồn, mẫu và rule", defaultextension=".json",
                                              initialfile="composition.session.json", filetypes=[("JSON", "*.json")], parent=self.root)
            if path:
                write_json(path, session, overwrite=True, protected=self.protected_sources)
                self.session_path = Path(path).resolve()
                self.status.set("Đã lưu phiên kèm toàn bộ dữ liệu nguồn: " + path)
        except (ValueError, OSError, RecursionError) as exc:
            messagebox.showerror("Không lưu được phiên", str(exc), parent=self.root)

    def load_demo(self):
        try:
            session = validate_session(loads((ROOT / "examples/composition.session.json").read_text(encoding="utf-8")))
            self.sources = deepcopy(session["sources"])
            self.apply_config(session["config"])
            self.refresh_sources()
            self.run()
        except (ValueError, OSError, RecursionError) as exc:
            messagebox.showerror("Không mở được ví dụ", str(exc), parent=self.root)

    def run(self, show_errors=False):
        self.invalidate()
        try:
            result, report = compose(self.sources, self.get_config())
            self.current_result, self.last_report = result, report
            fill(self.output, dumps(result), readonly=True)
            fill(self.report, dumps(report), readonly=True)
            self.export_button.configure(state="normal")
            self.report_tabs.select(0)
            self.status.set(f"Thành công · {report['sources']} nguồn · {report['written']} giá trị · "
                            f"{report['renamed']} đổi tên · {report['deleted']} xóa field. Bấm Xuất JSON để lưu.")
            return True
        except (ValueError, TypeError, RecursionError) as exc:
            fill(self.report, str(exc), readonly=True)
            self.report_tabs.select(1)
            self.status.set("Chưa tạo được kết quả. Xem Báo cáo / lỗi.")
            if show_errors:
                messagebox.showerror("Chưa tạo được kết quả", str(exc), parent=self.root)
            return False

    def export(self):
        if not self.run(show_errors=True):
            return
        path = filedialog.asksaveasfilename(title="Xuất JSON kết quả ghép", defaultextension=".json",
                                          initialfile="composed.json", filetypes=[("JSON", "*.json")], parent=self.root)
        if path:
            try:
                protected = list(self.protected_sources) + ([self.session_path] if self.session_path else [])
                write_json(path, self.current_result, overwrite=True, protected=protected)
                self.status.set("Đã xuất JSON: " + path)
            except (ValueError, OSError) as exc:
                messagebox.showerror("Không xuất được JSON", str(exc), parent=self.root)


if __name__ == "__main__":
    root = tk.Tk()
    ttk.Style(root).theme_use("clam")
    ComposerApp(root)
    root.mainloop()
