"""Deterministic JSON mapping engine. Standard library only; no eval/network."""
from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path
import re
import sys

VERSION = "1.0.0"
MISSING = object()
EMPTY = object()
STAR = object()
TERMINAL = object()
IDENT = re.compile(r"[^.\[\]\s]+")
OPS = ("copy", "string", "integer", "number", "boolean", "trim", "lower",
       "upper", "split", "join", "replace", "lookup", "parse_json", "json_string")


class MappingError(ValueError):
    pass


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise MappingError(f"Key JSON bị lặp: {key!r}")
        result[key] = value
    return result


def loads(text):
    def invalid(value):
        raise MappingError(f"Giá trị không thuộc JSON chuẩn: {value}")
    try:
        result = json.loads(text.lstrip("\ufeff"), object_pairs_hook=_pairs, parse_constant=invalid)
        dumps(result)  # Reject numbers overflowing to infinity, e.g. 1e9999.
        return result
    except (ValueError, RecursionError) as exc:
        raise MappingError(f"JSON không hợp lệ: {exc}") from exc


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def parse_path(path):
    """Dot keys, [index], [*], [\"literal.key\"], optional $ root."""
    if not isinstance(path, str) or not path:
        raise MappingError("Path phải là chuỗi; dùng $ cho gốc JSON.")
    if path == "$":
        return ()
    i = 0
    if path.startswith("$"):
        i = 1
        if i < len(path) and path[i] == ".":
            i += 1
        elif i < len(path) and path[i] != "[":
            raise MappingError(f"Path không hợp lệ: {path}")
    tokens = []
    need_key = True
    while i < len(path):
        if path[i] == "[":
            if not need_key and not tokens:
                raise MappingError(f"Path không hợp lệ: {path}")
            if i + 1 < len(path) and path[i + 1] == '"':
                try:
                    key, length = json.JSONDecoder().raw_decode(path[i + 1:])
                except ValueError as exc:
                    raise MappingError(f"Key trong path không hợp lệ: {path}") from exc
                end = i + 1 + length
                if end >= len(path) or path[end] != "]" or not isinstance(key, str):
                    raise MappingError(f"Thiếu ] trong path: {path}")
                tokens.append(key)
                i = end + 1
            else:
                end = path.find("]", i)
                if end < 0:
                    raise MappingError(f"Thiếu ] trong path: {path}")
                value = path[i + 1:end]
                if value == "*":
                    tokens.append(STAR)
                elif re.fullmatch(r"0|[1-9][0-9]*", value):
                    number = int(value)
                    if number > 1000000:
                        raise MappingError("Chỉ số mảng tối đa là 1.000.000.")
                    tokens.append(number)
                else:
                    raise MappingError(f"Index phải là số không âm hoặc *: {path}")
                i = end + 1
            need_key = False
        else:
            if not need_key:
                raise MappingError(f"Thiếu dấu . trong path: {path}")
            match = IDENT.match(path, i)
            if not match:
                raise MappingError(f"Key không hợp lệ trong path: {path}")
            tokens.append(match.group())
            i = match.end()
            need_key = False
        if i < len(path):
            if path[i] == ".":
                i += 1
                if i == len(path) or path[i] in ".[":
                    raise MappingError(f"Path không hợp lệ: {path}")
                need_key = True
            elif path[i] != "[":
                raise MappingError(f"Path không hợp lệ: {path}")
    if not tokens or need_key:
        raise MappingError(f"Path không hợp lệ: {path}")
    return tuple(tokens)


def format_path(tokens):
    text = "$"
    for token in tokens:
        if token is STAR:
            text += "[*]"
        elif isinstance(token, int):
            text += f"[{token}]"
        elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", token):
            text += "." + token
        else:
            text += "[" + json.dumps(token, ensure_ascii=False) + "]"
    return text


def matches(value, tokens, captures=(), actual=()):
    if not tokens:
        yield value, captures, actual
        return
    token, rest = tokens[0], tokens[1:]
    if value is MISSING:
        yield MISSING, captures, actual + tokens
    elif token is STAR:
        if not isinstance(value, list):
            raise MappingError(f"{format_path(actual)} phải là mảng để dùng [*].")
        if not value:
            yield EMPTY, captures, actual
        for index, child in enumerate(value):
            yield from matches(child, rest, captures + (index,), actual + (index,))
    elif isinstance(token, int):
        if not isinstance(value, list):
            raise MappingError(f"{format_path(actual)} phải là mảng.")
        child = value[token] if token < len(value) else MISSING
        yield from matches(child, rest, captures, actual + (token,))
    else:
        if not isinstance(value, dict):
            raise MappingError(f"{format_path(actual)} phải là object (không tự thay null).")
        yield from matches(value.get(token, MISSING), rest, captures, actual + (token,))


def substitute(tokens, captures, partial=False):
    result, index = [], 0
    for token in tokens:
        if token is STAR:
            if index == len(captures):
                if partial:
                    return tuple(result)
                raise MappingError("Thiếu index mảng nguồn để gán [*] đích.")
            result.append(captures[index])
            index += 1
        else:
            result.append(token)
    return tuple(result)


def put(value, tokens, new):
    """Create containers only for absent destinations; never replace a scalar parent."""
    if not tokens:
        return deepcopy(new)
    token, rest = tokens[0], tokens[1:]
    if value is MISSING:
        value = [] if isinstance(token, int) else {}
    if isinstance(token, int):
        if not isinstance(value, list):
            raise MappingError(f"Đích cần mảng tại index [{token}].")
        while len(value) <= token:
            value.append(MISSING)
        value[token] = put(value[token], rest, new)
    else:
        if not isinstance(value, dict):
            raise MappingError(f"Đích cần object tại key {token!r}.")
        value[token] = put(value.get(token, MISSING), rest, new)
    return value


def materialize(value):
    if value is MISSING:
        return None
    if isinstance(value, list):
        return [materialize(item) for item in value]
    if isinstance(value, dict):
        return {key: materialize(item) for key, item in value.items()}
    return value


def transform(value, step):
    if isinstance(step, str):
        step = {"op": step}
    op = step["op"]
    if op == "copy":
        return value
    if op == "string":
        return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
    if op in ("integer", "number"):
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise MappingError(f"Không thể đổi {value!r} thành {op}.")
        if op == "integer":
            if isinstance(value, int):
                return value
            try:
                number = Decimal(str(value).strip())
            except InvalidOperation as exc:
                raise MappingError(f"Không thể đổi {value!r} thành integer.") from exc
            if not number.is_finite() or number != number.to_integral_value():
                raise MappingError(f"Không thể đổi {value!r} thành integer mà không mất phần thập phân.")
            return int(number)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+", value.strip()):
            return int(value)
        number = float(value)
        if not math.isfinite(number):
            raise MappingError(f"Không thể đổi {value!r} thành number hữu hạn.")
        return number
    if op == "boolean":
        if isinstance(value, bool):
            return value
        if type(value) in (int, float) and value in (0, 1):
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in ("true", "false", "1", "0"):
            return value.strip().lower() in ("true", "1")
        raise MappingError("Boolean chỉ nhận true/false, 1/0 hoặc chuỗi tương ứng.")
    if op in ("trim", "lower", "upper", "split", "replace", "parse_json"):
        if not isinstance(value, str):
            raise MappingError(f"{op} cần giá trị string.")
        if op in ("trim", "lower", "upper"):
            return getattr(value, {"trim": "strip"}.get(op, op))()
        if op == "split":
            return value.split(step.get("separator", ","))
        if op == "replace":
            return value.replace(step["old"], step["new"])
        return loads(value)
    if op == "join":
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise MappingError("join cần mảng các string.")
        return step.get("separator", ",").join(value)
    if op == "json_string":
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if op == "lookup":
        key = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
        if key in step["values"]:
            return deepcopy(step["values"][key])
        if "default" in step:
            return deepcopy(step["default"])
        raise MappingError(f"lookup không có giá trị cho {key!r}.")
    raise MappingError(f"Phép biến đổi chưa hỗ trợ: {op}")


def validate_config(config):
    if not isinstance(config, dict):
        raise MappingError("Bộ rule phải là object JSON.")
    allowed = {"version", "name", "mode", "source_root", "output_root", "base", "template", "missing", "on_conflict", "rules"}
    if set(config) - allowed:
        raise MappingError(f"Thuộc tính cấu hình không hỗ trợ: {sorted(set(config) - allowed)}")
    if "name" in config and not isinstance(config["name"], str):
        raise MappingError("name phải là chuỗi.")
    if type(config.get("version", 1)) is not int or config.get("version", 1) != 1:
        raise MappingError("Chỉ hỗ trợ version=1.")
    for key, default, choices in (("mode", "document", ("document", "each")),
                                  ("base", "empty", ("empty", "source")),
                                  ("missing", "error", ("error", "skip", "default")),
                                  ("on_conflict", "error", ("error", "overwrite"))):
        if config.get(key, default) not in choices:
            raise MappingError(f"{key} phải thuộc {choices}.")
    for key in ("source_root", "output_root"):
        if STAR in parse_path(config.get(key, "$")):
            raise MappingError(f"{key} không hỗ trợ [*]; dùng mode=each hoặc rule [*].")
    if "template" in config and config.get("base", "empty") != "empty":
        raise MappingError("Không dùng template cùng base=source.")
    rules = config.get("rules")
    if not isinstance(rules, list) or not rules:
        raise MappingError("Cần ít nhất một rule trong rules.")
    for index, rule in enumerate(rules, 1):
        prefix = f"Rule {index}"
        if not isinstance(rule, dict) or set(rule) - {"from", "to", "value", "missing", "default", "transforms", "enabled", "name"}:
            raise MappingError(prefix + ": rule có thuộc tính không hỗ trợ.")
        if type(rule.get("enabled", True)) is not bool:
            raise MappingError(prefix + ": enabled phải là boolean.")
        if "name" in rule and not isinstance(rule["name"], str):
            raise MappingError(prefix + ": name phải là chuỗi.")
        if ("from" in rule) == ("value" in rule):
            raise MappingError(prefix + ": chọn đúng một trong from hoặc value.")
        target = parse_path(rule.get("to"))
        source = parse_path(rule["from"]) if "from" in rule else ()
        if sum(t is STAR for t in source) != sum(t is STAR for t in target):
            raise MappingError(prefix + ": số [*] ở from/to phải bằng nhau; gộp mảng bằng cách copy cả mảng.")
        policy = rule.get("missing", config.get("missing", "error"))
        if policy not in ("error", "skip", "default"):
            raise MappingError(prefix + ": missing không hợp lệ.")
        if policy == "default" and "default" not in rule:
            raise MappingError(prefix + ": cần khai báo default (có thể là null).")
        steps = rule.get("transforms", [])
        if not isinstance(steps, list):
            raise MappingError(prefix + ": transforms phải là mảng.")
        for step in steps:
            if isinstance(step, str):
                step = {"op": step}
            if not isinstance(step, dict) or step.get("op") not in OPS:
                raise MappingError(prefix + ": phép biến đổi không hợp lệ.")
            op = step["op"]
            params = {"split": {"separator"}, "join": {"separator"}, "replace": {"old", "new"}, "lookup": {"values", "default"}}.get(op, set())
            if set(step) - {"op"} - params:
                raise MappingError(prefix + ": tham số transform không hỗ trợ.")
            if op in ("split", "join") and (not isinstance(step.get("separator", ","), str) or (op == "split" and step.get("separator", ",") == "")):
                raise MappingError(prefix + ": separator không hợp lệ.")
            if op == "replace" and any(not isinstance(step.get(k), str) for k in ("old", "new")):
                raise MappingError(prefix + ": replace cần old/new dạng string.")
            if op == "lookup" and not isinstance(step.get("values"), dict):
                raise MappingError(prefix + ": lookup cần object values.")
    dumps(config)
    return config


@dataclass
class Report:
    records: int = 0
    written: int = 0
    skipped: int = 0
    defaults: int = 0
    empty_arrays: int = 0
    events: list = field(default_factory=list)

    def event(self, **event):
        if len(self.events) < 1000:
            self.events.append(event)

    def to_dict(self):
        return {"tool_version": VERSION, "level": "structural_mapping_only", "records": self.records,
                "written": self.written, "skipped": self.skipped, "defaults": self.defaults,
                "empty_arrays": self.empty_arrays, "events": self.events, "event_limit": 1000}


def register_write(trie, path):
    """Reject duplicate / ancestor writes in O(path depth), including large arrays."""
    node = trie
    for token in path:
        if TERMINAL in node:
            raise MappingError(f"Hai rule ghi đè hoặc chồng path {format_path(path)}; dùng on_conflict=overwrite nếu có chủ đích.")
        node = node.setdefault(token, {})
    if node:
        raise MappingError(f"Hai rule ghi đè hoặc chồng path {format_path(path)}; dùng on_conflict=overwrite nếu có chủ đích.")
    node[TERMINAL] = True


def convert(data, config):
    validate_config(config)
    source_tokens = parse_path(config.get("source_root", "$"))
    selected = next(matches(data, source_tokens))[0]
    if selected is MISSING:
        raise MappingError("Không tìm thấy source_root.")
    each = config.get("mode", "document") == "each"
    if each and not isinstance(selected, list):
        raise MappingError("mode=each yêu cầu source_root trỏ đến mảng.")
    inputs = selected if each else [selected]
    report, outputs = Report(), []
    for record_index, source in enumerate(inputs):
        output = (deepcopy(source) if config.get("base", "empty") == "source" else
                  deepcopy(config["template"]) if "template" in config else MISSING)
        writes = {}
        report.records += 1
        for rule_index, rule in enumerate(config["rules"], 1):
            if not rule.get("enabled", True):
                continue
            target = parse_path(rule["to"])
            stream = matches(source, parse_path(rule["from"])) if "from" in rule else [(rule["value"], (), ())]
            try:
                for value, captures, actual in stream:
                    if value is EMPTY:
                        empty_target = substitute(target, captures, partial=True)
                        previous = next(matches(output, empty_target))[0] if output is not MISSING else MISSING
                        if previous is MISSING:
                            output = put(output, empty_target, [])
                        elif not isinstance(previous, list):
                            raise MappingError("Đích của mảng rỗng đã tồn tại với kiểu khác mảng.")
                        report.empty_arrays += 1
                        continue
                    if value is MISSING:
                        policy = rule.get("missing", config.get("missing", "error"))
                        report.event(record=record_index, rule=rule_index, path=format_path(actual), action=policy)
                        if policy == "error":
                            raise MappingError(f"Thiếu nguồn {format_path(actual)}.")
                        if policy == "skip":
                            report.skipped += 1
                            continue
                        # Never fabricate array cardinality when its source container is absent.
                        if sum(t is STAR for t in target) != len(captures):
                            raise MappingError("Không thể dùng default để đoán số phần tử của mảng bị thiếu.")
                        value = deepcopy(rule["default"])
                        report.defaults += 1
                    concrete = substitute(target, captures)
                    if config.get("on_conflict", "error") == "error":
                        register_write(writes, concrete)
                    for step in rule.get("transforms", []):
                        value = transform(value, step)
                    output = put(output, concrete, value)
                    report.written += 1
            except (ValueError, TypeError, KeyError, OverflowError) as exc:
                raise MappingError(f"Record {record_index + 1}, rule {rule_index} ({rule['to']}): {exc}") from exc
        outputs.append(materialize(output) if output is not MISSING else {})
    result = outputs if each else outputs[0]
    root_tokens = parse_path(config.get("output_root", "$"))
    result = materialize(put(MISSING, root_tokens, result))
    dumps(result)
    return result, report.to_dict()


def write_json(path, value, *, overwrite=False, protected=()):
    path = Path(path).resolve()
    for source in protected:
        source = Path(source).resolve()
        if path == source or (path.exists() and source.exists() and path.samefile(source)):
            raise MappingError("File đầu ra không được trùng file nguồn hoặc file rule.")
    # Serialize completely before opening any destination.
    payload = dumps(value)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Chuyển cấu trúc JSON bằng rule JSON; hoàn toàn offline.")
    parser.add_argument("input", type=Path)
    parser.add_argument("rules", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in báo cáo, không ghi file")
    parser.add_argument("--report", type=Path, help="Báo cáo mapping + SHA-256 input/rules/output")
    parser.add_argument("--overwrite", action="store_true", help="Cho phép ghi lại output cũ; vẫn cấm ghi lên input/rules")
    args = parser.parse_args(argv)
    try:
        if not args.dry_run and not args.output:
            raise MappingError("Cần đường dẫn output hoặc --dry-run.")
        protected = [args.input, args.rules]
        destinations = [p for p in (args.output if not args.dry_run else None, args.report if not args.dry_run else None) if p]
        for path in destinations:
            for original in protected:
                if path.resolve() == original.resolve() or (path.exists() and original.exists() and path.samefile(original)):
                    raise MappingError("Output/report không được trùng input/rules.")
            if path.exists() and not args.overwrite:
                raise MappingError(f"File đã tồn tại: {path}; chọn tên mới hoặc --overwrite.")
            if not path.parent.exists():
                raise MappingError(f"Thư mục output chưa tồn tại: {path.parent}")
        if len(destinations) == 2 and (destinations[0].resolve() == destinations[1].resolve() or (all(p.exists() for p in destinations) and destinations[0].samefile(destinations[1]))):
            raise MappingError("Output và report phải khác file.")
        raw_input, raw_rules = args.input.read_bytes(), args.rules.read_bytes()
        result, report = convert(loads(raw_input.decode("utf-8-sig")), loads(raw_rules.decode("utf-8-sig")))
        report.update({"input_sha256": hashlib.sha256(raw_input).hexdigest(), "rules_sha256": hashlib.sha256(raw_rules).hexdigest(),
                       "output_sha256": hashlib.sha256(dumps(result).encode("utf-8")).hexdigest()})
        if not args.dry_run:
            write_json(args.output, result, overwrite=args.overwrite, protected=protected)
            if args.report:
                write_json(args.report, report, overwrite=args.overwrite, protected=protected + [args.output])
        print(dumps(report), end="")
        return 0
    except (ValueError, OSError, UnicodeError, RecursionError) as exc:
        print(f"Lỗi: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
