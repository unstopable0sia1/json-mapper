"""Shared JSON editors with visible tab indentation and explicit formatting."""
import json
import re
from tkinter import font, scrolledtext, ttk

from mapper import loads


def display_json(value):
    return json.dumps(value, ensure_ascii=False, indent="\t", allow_nan=False) + "\n"


class JsonEditor(scrolledtext.ScrolledText):
    def __init__(self, parent, *, readonly=False, height=10):
        super().__init__(parent, wrap="none", undo=True, height=height, font=("Consolas", 10),
                         background="#fafcff", foreground="#182b42", insertbackground="#182b42",
                         relief="flat", padx=10, pady=8, spacing1=1, spacing3=1)
        self.configure(tabs=(font.Font(font=self["font"]).measure("    "),))
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(side="top", fill="x", before=self._w)
        self.hint = ttk.Label(toolbar, text="Tab = 4 cột", foreground="#526d8b")
        self.hint.pack(side="left", padx=4)
        if not readonly:
            ttk.Button(toolbar, text="Định dạng JSON", command=self.format_json, padding=(4, 2)).pack(side="right")
        self.horizontal = ttk.Scrollbar(self.frame, orient="horizontal", command=self.xview)
        self.horizontal.pack(side="bottom", fill="x", before=self._w)
        self.configure(xscrollcommand=self.horizontal.set)
        self.bind("<Control-Shift-F>", self.format_json)
        self.bind("<Control-Shift-f>", self.format_json)
        self.bind("<Control-Tab>", self.move_focus)
        self.bind("<Control-Shift-Tab>", self.move_focus)
        self.bind("<Tab>", self.indent)
        self.bind("<Shift-Tab>", lambda event: self.indent(event, remove=True))
        self.bind("<ISO_Left_Tab>", lambda event: self.indent(event, remove=True))
        self.bind("<Return>", self.newline)
        if readonly:
            self.configure(state="disabled")

    def move_focus(self, event):
        command = "tk_focusPrev" if event.state & 0x1 else "tk_focusNext"
        self.tk.call("focus", self.tk.call(command, self._w))
        return "break"

    def format_json(self, event=None):
        if str(self["state"]) == "disabled":
            return "break" if event else False
        try:
            text = display_json(loads(self.get("1.0", "end-1c")))
        except (ValueError, RecursionError) as exc:
            self.hint.configure(text="JSON lỗi", foreground="#b42318")
            # Keep the detailed error accessible without changing the document.
            self.last_format_error = str(exc)
            return "break" if event else False
        self.last_format_error = None
        self.edit_separator()
        position, view = self.index("insert"), self.yview()[0]
        separators = self["autoseparators"]
        self.configure(autoseparators=False)
        try:
            self.delete("1.0", "end")
            self.insert("1.0", text)
        finally:
            self.configure(autoseparators=separators)
        self.mark_set("insert", position)
        self.yview_moveto(view)
        self.edit_separator()
        self.hint.configure(text="Tab = 4 cột", foreground="#526d8b")
        return "break" if event else True

    def indent(self, event=None, remove=False):
        if str(self["state"]) == "disabled":
            return "break"
        self.edit_separator()
        selection = self.tag_ranges("sel")
        if not selection and not remove:
            self.insert("insert", "\t")
        else:
            start = self.index(selection[0] if selection else "insert")
            end = self.index(selection[1] if selection else "insert")
            first, last = int(start.split(".")[0]), int(end.split(".")[0])
            if selection and end.endswith(".0") and last > first:
                last -= 1
            for line in range(first, last + 1):
                index = f"{line}.0"
                if remove:
                    prefix = re.match(r"\t| {1,4}", self.get(index, index + " lineend"))
                    if prefix:
                        self.delete(index, f"{index}+{len(prefix[0])}c")
                else:
                    self.insert(index, "\t")
            if selection:
                self.tag_remove("sel", "1.0", "end")
                self.tag_add("sel", f"{first}.0", f"{last}.end")
        self.edit_separator()
        return "break"

    def newline(self, event=None):
        if event is not None and event.state & 0x4:  # Let dialog Ctrl+Enter bindings run.
            return None
        if str(self["state"]) == "disabled":
            return "break"
        if self.tag_ranges("sel"):
            self.delete("sel.first", "sel.last")
        before = self.get("insert linestart", "insert")
        after = self.get("insert", "insert lineend")
        indentation = re.match(r"[\t ]*", before)[0]
        opens = before.rstrip().endswith(("{", "["))
        extra = "\t" if opens else ""
        text = "\n" + indentation + extra
        self.edit_separator()
        self.insert("insert", text)
        if opens and after.lstrip().startswith(("}", "]")):
            position = self.index("insert")
            self.insert("insert", "\n" + indentation)
            self.mark_set("insert", position)
        self.edit_separator()
        return "break"
