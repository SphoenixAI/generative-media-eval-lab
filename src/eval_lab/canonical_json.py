"""RFC 8785 canonical bytes for the application's safe-integer-token profile."""
from hashlib import sha256
import json

MAX_INTEGER = 9007199254740991


def reject_number(value):
    raise ValueError(f"Unsupported number {value!r}; use an integer literal within "
        f"[-{MAX_INTEGER}, {MAX_INTEGER}] for an exact integer, otherwise a human-authored "
        "representation in a schema-permitted text field or a separately approved numeric extension")


def integer(token):
    if len(token.lstrip("-")) > 16:
        reject_number(token)
    value = int(token)
    if abs(value) > MAX_INTEGER:
        reject_number(token)
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def parse_json(source: bytes | str):
    """Strict UTF-8 JSON; validate before any default decoder information loss."""
    try:
        if isinstance(source, bytes):
            source = source.decode("utf-8")
        value = json.loads(source, object_pairs_hook=unique_object, parse_int=integer,
            parse_float=reject_number, parse_constant=reject_number)
        canonicalize(value)  # Also reject lone surrogates in keys and values.
        return value
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc


def canonicalize(value) -> bytes:
    """Sort recursively by unsigned UTF-16 units; preserve arrays and Unicode."""
    def emit(item):
        if item is None:
            return "null"
        if type(item) is bool:
            return "true" if item else "false"
        if type(item) is int:
            if abs(item) > MAX_INTEGER:
                reject_number(item)
            return str(item)
        if type(item) is str:
            item.encode("utf-8", errors="strict")
            return json.dumps(item, ensure_ascii=False)
        if type(item) is list:
            return "[" + ",".join(emit(x) for x in item) + "]"
        if type(item) is dict:
            if any(type(key) is not str for key in item):
                raise ValueError("JSON object keys must be strings")
            keys = sorted(item, key=lambda key: key.encode("utf-16-be", errors="strict"))
            return "{" + ",".join(emit(key) + ":" + emit(item[key]) for key in keys) + "}"
        raise ValueError(f"unsupported JSON type: {type(item).__name__}")
    try:
        return emit(value).encode("utf-8")
    except RecursionError as exc:
        raise ValueError("JSON nesting exceeds the supported depth") from exc


def file_digest(source: bytes | str) -> str:
    return sha256(canonicalize(parse_json(source))).hexdigest()
