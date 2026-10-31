"""Compose JSON from named, immutable sources and an editable output template."""
from copy import deepcopy
import re

from mapper import (EMPTY, MISSING, STAR, MappingError, dumps, format_path,
                    matches, materialize, parse_path, put, register_write,
                    substitute, transform, validate_config)

ALIAS = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")


def reference(text):
    if not isinstance(text, str):
        raise MappingError("Tham chiếu phải là chuỗi value:A:$.path hoặc field:A:$.path.")
    parts = text.split(":", 2)
    if len(parts) != 3 or parts[0] not in ("value", "field") or not ALIAS.fullmatch(parts[1]):
        raise MappingError(f"Tham chiếu không hợp lệ: {text!r}; dùng value:A:$.path hoặc field:A:$.path.")
    kind, alias, path = parts
    tokens = parse_path(path)
    if kind == "field" and (not tokens or not isinstance(tokens[-1], str)):
        raise MappingError("field: phải trỏ đến tên key object, không phải gốc hoặc index mảng.")
    return kind, alias, tokens


def target_path(text):
    if isinstance(text, str) and text.startswith("field:"):
        return reference(text)[2]
    if isinstance(text, str) and text.startswith("value:"):
        raise MappingError("Path đích dùng field:A:$.path hoặc path thường; value: dùng ở nguồn giá trị.")
    return parse_path(text)


def validate_rule(rule):
    if not isinstance(rule, dict):
        raise MappingError("Rule phải là object.")
    op = rule.get("op", "set")
    if op not in ("set", "delete", "rename"):
        raise MappingError("Thao tác phải là set, delete hoặc rename.")
    target = target_path(rule.get("to"))
    if op != "set" and (not target or not isinstance(target[-1], str)):
        raise MappingError("delete/rename chỉ áp dụng cho key object, kể cả key trong mảng [*].")
    core = {key: value for key, value in rule.items() if key != "op"}
    core["to"] = format_path(target)
    if op == "delete":
        if set(rule) - {"op", "to", "enabled", "name", "missing"} or rule.get("missing") == "default":
            raise MappingError("delete chỉ nhận to, enabled, name, missing=error/skip.")
        core["from"] = format_path(target)
    elif "from" in rule:
        _, _, tokens = reference(rule["from"])
        if op == "rename":
            if STAR in tokens:
                raise MappingError("Nguồn tên mới của rename không dùng [*]; dùng tên chung cho các field đích.")
            core["to"] = "$"
        core["from"] = format_path(tokens)
    elif op == "rename":
        core["to"] = "$"
    validate_config({"rules": [core]})
    return rule


def validate_composition(config):
    if not isinstance(config, dict) or set(config) - {"version", "kind", "template", "rules", "missing", "on_conflict"}:
        raise MappingError("Cấu hình ghép có thuộc tính không hỗ trợ.")
    if type(config.get("version", 1)) is not int or config.get("version", 1) != 1:
        raise MappingError("Chỉ hỗ trợ version=1.")
    if config.get("kind", "json-composer") != "json-composer":
        raise MappingError("Đây không phải cấu hình json-composer.")
    if config.get("missing", "error") not in ("error", "skip", "default"):
        raise MappingError("missing phải là error, skip hoặc default.")
    if config.get("on_conflict", "error") not in ("error", "overwrite"):
        raise MappingError("on_conflict phải là error hoặc overwrite.")
    if not isinstance(config.get("rules"), list):
        raise MappingError("rules phải là mảng (có thể rỗng để chỉ xuất template).")
    for index, rule in enumerate(config["rules"], 1):
        try:
            validate_rule(rule)
            if (rule.get("op", "set") != "delete" and
                    rule.get("missing", config.get("missing", "error")) == "default" and "default" not in rule):
                raise MappingError("Cần khai báo default trong rule.")
        except (ValueError, TypeError) as exc:
            raise MappingError(f"Rule {index}: {exc}") from exc
    dumps(config)
    return config


def read_reference(sources, text):
    kind, alias, tokens = reference(text)
    if alias not in sources:
        raise MappingError(f"Chưa nạp nguồn {alias!r}.")
    for value, captures, actual in matches(sources[alias], tokens):
        if kind == "field" and value is not MISSING and value is not EMPTY:
            value = tokens[-1]
        yield value, captures, actual


def compose(sources, config):
    validate_composition(config)
    if not isinstance(sources, dict) or any(not isinstance(key, str) or not ALIAS.fullmatch(key) for key in sources):
        raise MappingError("Nguồn phải là object bí danh → JSON; bí danh dùng chữ ASCII, số, dấu _ và không bắt đầu bằng số.")
    dumps(sources)
    output = deepcopy(config.get("template", {}))
    writes = {}
    report = {"sources": len(sources), "written": 0, "defaults": 0, "skipped": 0,
              "deleted": 0, "renamed": 0, "empty_arrays": 0, "events": []}
    conflict = config.get("on_conflict", "error")

    def missing(rule, path, index, allow_default=True):
        policy = rule.get("missing", config.get("missing", "error"))
        if len(report["events"]) < 1000:
            report["events"].append({"rule": index, "path": format_path(path), "action": policy})
        if policy == "skip":
            report["skipped"] += 1
            return MISSING
        if policy == "default" and allow_default and rule.get("op", "set") != "delete":
            report["defaults"] += 1
            return deepcopy(rule["default"])
        raise MappingError(f"Không tìm thấy {format_path(path)}.")

    def register(path):
        if conflict == "error":
            register_write(writes, path)

    for index, rule in enumerate(config["rules"], 1):
        if not rule.get("enabled", True):
            continue
        try:
            target = target_path(rule["to"])
            if rule["to"].startswith("field:"):
                # Validate the referenced structure against its original source, not the evolving output.
                found = False
                for value, _, _ in read_reference(sources, rule["to"]):
                    if value is MISSING:
                        raise MappingError(f"Field tham khảo không tồn tại: {rule['to']}")
                    found = True
                if not found:
                    raise MappingError(f"Field tham khảo không tồn tại: {rule['to']}")
            op = rule.get("op", "set")
            if op in ("delete", "rename"):
                new_name = None
                if op == "rename":
                    new_name = (next(read_reference(sources, rule["from"]))[0]
                                if "from" in rule else deepcopy(rule["value"]))
                    if new_name is MISSING:
                        new_name = missing(rule, reference(rule["from"])[2], index)
                        if new_name is MISSING:
                            continue
                    for step in rule.get("transforms", []):
                        new_name = transform(new_name, step)
                    if not isinstance(new_name, str):
                        raise MappingError("Tên field mới phải là chuỗi.")
                # Snapshot matches before changing keys; array positions stay unchanged.
                for value, _, actual in list(matches(output, target)):
                    if value is EMPTY:
                        continue
                    if value is MISSING:
                        missing(rule, actual, index, allow_default=False)
                        continue
                    parent = next(matches(output, actual[:-1]))[0]
                    if op == "rename" and new_name == actual[-1]:
                        continue
                    register(actual)
                    if op == "rename":
                        destination = actual[:-1] + (new_name,)
                        if new_name in parent and conflict == "error":
                            raise MappingError(f"Tên field đích đã tồn tại: {new_name!r}.")
                        register(destination)
                        parent[new_name] = value
                        report["renamed"] += 1
                    else:
                        report["deleted"] += 1
                    del parent[actual[-1]]
                continue
            stream = (read_reference(sources, rule["from"]) if "from" in rule
                      else [(deepcopy(rule["value"]), (), ())])
            for value, captures, actual in stream:
                if value is EMPTY:
                    empty_target = substitute(target, captures, partial=True)
                    previous = next(matches(output, empty_target))[0]
                    if previous is MISSING:
                        output = put(output, empty_target, [])
                    elif not isinstance(previous, list):
                        raise MappingError("Đích của mảng rỗng phải là mảng.")
                    report["empty_arrays"] += 1
                    continue
                if value is MISSING:
                    value = missing(rule, actual, index)
                    if value is MISSING:
                        continue
                    if sum(token is STAR for token in target) != len(captures):
                        raise MappingError("Không thể dùng default để đoán số phần tử mảng bị thiếu.")
                destination = substitute(target, captures)
                register(destination)
                value = deepcopy(value)
                for step in rule.get("transforms", []):
                    value = transform(value, step)
                output = put(output, destination, value)
                report["written"] += 1
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise MappingError(f"Rule {index} ({rule['to']}): {exc}") from exc
    output = materialize(output)
    dumps(output)
    return output, report


def validate_session(session):
    if not isinstance(session, dict) or set(session) != {"kind", "version", "sources", "config"}:
        raise MappingError("File phiên cần kind, version, sources và config.")
    if session["kind"] != "json-composer-session" or type(session["version"]) is not int or session["version"] != 1:
        raise MappingError("Định dạng phiên ghép không hỗ trợ.")
    sources = session["sources"]
    if not isinstance(sources, dict) or any(not isinstance(key, str) or not ALIAS.fullmatch(key) for key in sources):
        raise MappingError("Bí danh nguồn không hợp lệ.")
    validate_composition(session["config"])
    dumps(session)
    return session
