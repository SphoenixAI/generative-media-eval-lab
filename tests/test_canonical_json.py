"""TEST-ONLY independent byte oracles for the approved integer JCS profile."""
from hashlib import sha256
import json
import os
import subprocess
import sys

import pytest
from eval_lab.canonical_json import canonicalize, parse_json, file_digest


@pytest.mark.parametrize("source,expected", [
    (' {"b":2, "a":1}\n', b'{"a":1,"b":2}'),
    ('{"z":[{"b":false,"a":null},[],{}],"a":true}',
     b'{"a":true,"z":[{"a":null,"b":false},[],{}]}'),
    ('[-0,9007199254740991,-9007199254740991]', b'[0,9007199254740991,-9007199254740991]'),
    ('"\\u0061\\/"', b'"a/"'),
    ('"é"', '"é"'.encode()),
    ('"e\\u0301"', '"e\u0301"'.encode()),
])
def test_independent_bytes(source, expected):
    assert canonicalize(parse_json(source)) == expected
    assert file_digest(source) == sha256(expected).hexdigest()


def test_fixed_hash_and_equivalent_forms():
    expected = "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777"
    for text in ('{"a":1,"b":2}', ' { "b" : 2, "\\u0061": 1 }\n'):
        assert file_digest(text) == expected


def test_rfc8785_section_3_2_3_non_ascii_vector():
    # TEST-ONLY wrapper; published ordering data kept verbatim.
    raw = r'''{"\u20ac":"Euro Sign","\r":"Carriage Return",
      "\ufb33":"Hebrew Letter Dalet With Dagesh","1":"One",
      "\ud83d\ude00":"Emoji: Grinning Face","\u0080":"Control",
      "\u00f6":"Latin Small Letter O With Diaeresis"}'''
    expected = ('{"\\r":"Carriage Return","1":"One","\u0080":"Control",'
        '"ö":"Latin Small Letter O With Diaeresis","€":"Euro Sign",'
        '"😀":"Emoji: Grinning Face","דּ":"Hebrew Letter Dalet With Dagesh"}').encode()
    assert canonicalize(parse_json(raw)) == expected
    assert canonicalize({"nested": [parse_json(raw)]}) == b'{"nested":[' + expected + b']}'


def test_string_escaping_without_normalization():
    assert canonicalize('\x00\x08\x09\x0a\x0c\x0d\x1f"\\/\x7f') == b'"\\u0000\\b\\t\\n\\f\\r\\u001f\\\"\\\\/\x7f"'
    assert file_digest('"é"') != file_digest('"e\\u0301"')


@pytest.mark.parametrize("mutation", [
    {"a": 2}, {"a": True}, {"a": "1"}, {"a": None}, {"a": False},
    {"a": [1]}, {"a": {}}, {"a": 0}, {"a": "TEST-ONLY "},
])
def test_value_mutations_change_digest(mutation):
    assert file_digest(json.dumps(mutation)) != file_digest('{"a":1}')


def test_array_order_and_string_whitespace_are_content():
    assert file_digest('[1,2]') != file_digest('[2,1]')
    assert file_digest('"TEST-ONLY"') != file_digest('"TEST-ONLY "')


@pytest.mark.parametrize("source", ['1.0', '1e0', '0.1', '-0.0', '9007199254740992', '-9007199254740992'])
def test_reject_numbers_with_remediation(source):
    with pytest.raises(ValueError, match="integer literal.*text field.*approved"):
        parse_json(source)


@pytest.mark.parametrize("source", [
    '{"a":1,"\\u0061":2}', '{"nested":{"a":0,"a":1}}', '{',
    'NaN', 'Infinity', '-Infinity', '"\\ud800"', '{"\\udfff":1}',
    b'"\xff"', b'\xef\xbb\xbf{}', 'true false', '[1,]',
])
def test_strict_json_rejections(source):
    with pytest.raises(ValueError):
        parse_json(source)


@pytest.mark.parametrize("value", [1.0, (1,), {1: "TEST-ONLY"}, {"a": object()}, "\ud800", 2**53])
def test_reject_unsupported_python_values(value):
    with pytest.raises(ValueError):
        canonicalize(value)


def test_determinism_in_separate_processes():
    code = 'from eval_lab.canonical_json import file_digest; print(file_digest(\'{"b":2,"a":1}\'))'
    outputs = [subprocess.check_output([sys.executable, "-c", code],
        env=os.environ | {"PYTHONHASHSEED": seed}) for seed in ("1", "97")]
    assert outputs == [b'43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777\n'] * 2


def test_very_large_integer_still_has_actionable_profile_error():
    with pytest.raises(ValueError, match="integer literal.*text field.*approved"):
        parse_json("9" * 5000)
