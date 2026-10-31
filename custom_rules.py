"""Modal JSON rule editing; failed validation never publishes a result."""
from copy import deepcopy
import tkinter as tk
from tkinter import ttk

from json_editor import JsonEditor, display_json
from mapper import MappingError, loads


def parse_rules(text, *, single=False):
    value = loads(text)
    rules = [value] if isinstance(value, dict) else value
    if not isinstance(rules, list) or not rules or any(not isinstance(rule, dict) for rule in rules):
        raise MappingError("Nhập một object rule hoặc mảng các object rule không rỗng.")
    if single and len(rules) != 1:
        raise MappingError("Khi sửa, chỉ nhập đúng một rule.")
    return rules


class CustomRuleDialog(tk.Toplevel):
    def __init__(self, parent, *, validator, initial=None, help_text="", single=False):
        super().__init__(parent)
        self.title("Sửa rule bằng JSON" if single else "Thêm rule custom bằng JSON")
        self.geometry("820x680")
        self.minsize(580, 450)
        self.transient(parent)
        self.result = None
        self.validator = validator
        self.single = single
        area = ttk.Frame(self, padding=14)
        area.pack(fill="both", expand=True)
        ttk.Label(area, text="Nhập một rule JSON hoặc mảng rule. Tất cả phải hợp lệ mới được lưu.\n" + help_text,
                  wraplength=740, justify="left").pack(anchor="w", pady=(0, 8))
        self.text = JsonEditor(area)
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", display_json(initial if initial is not None else
                                            {"value": "Giá trị mới", "to": "custom.value"}))
        self.text.edit_modified(False)
        self.feedback = tk.StringVar(value="Chưa kiểm tra. Việc lưu sẽ kiểm tra lại toàn bộ rule với dữ liệu hiện tại.")
        self.feedback_label = ttk.Label(area, textvariable=self.feedback, wraplength=740, justify="left")
        self.feedback_label.pack(fill="x", pady=8)
        actions = ttk.Frame(area)
        actions.pack(fill="x")
        ttk.Button(actions, text="Kiểm tra", command=self.check).pack(side="left")
        ttk.Button(actions, text="Hủy", command=self.destroy).pack(side="right")
        ttk.Button(actions, text="Lưu rule" if single else "Thêm rule", command=self.accept).pack(side="right", padx=6)
        self.bind("<Escape>", lambda event: self.destroy())
        self.bind("<Control-Return>", lambda event: self.accept())
        self.grab_set()

    def check(self):
        try:
            rules = parse_rules(self.text.get("1.0", "end-1c"), single=self.single)
            self.validator(rules)
        except (ValueError, TypeError, RecursionError) as exc:
            self.feedback.set(f"Chưa hợp lệ — chưa lưu rule:\n{exc}")
            self.feedback_label.configure(foreground="#b42318")
            return None
        self.feedback.set(f"Hợp lệ: {len(rules)} rule. Chạy thử thành công với JSON hiện tại; chưa ghi vào bảng.")
        self.feedback_label.configure(foreground="#18734a")
        return rules

    def accept(self):
        rules = self.check()
        if rules is not None:
            self.result = deepcopy(rules)
            self.destroy()
