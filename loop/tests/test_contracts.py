"""Contract checks that also run inside a frozen harness snapshot."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HARNESS = Path(__file__).resolve().parents[1]


def load_module(name):
    spec = importlib.util.spec_from_file_location('contract_' + name, HARNESS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RoleContracts(unittest.TestCase):
    def setUp(self):
        self.validators = [load_module('loopctl').validate, load_module('run').validate]
        self.evaluation = self.read('tests/fixtures/eval_r1.json')
        self.schema = self.read('schemas/evaluation.schema.json')

    def read(self, name):
        return json.loads((HARNESS / name).read_text())

    def rejects(self, value, schema=None):
        for validate in self.validators:
            with self.subTest(validator=validate.__module__):
                with self.assertRaises(ValueError):
                    validate(value, schema or self.schema)

    def test_every_schema_object_is_closed_and_all_fields_required(self):
        def visit(value):
            if isinstance(value, dict):
                if value.get('type') == 'object':
                    self.assertIs(value.get('additionalProperties'), False)
                    self.assertEqual(set(value['required']), set(value['properties']))
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)
        for name in ('evaluation', 'research', 'enhancement'):
            with self.subTest(schema=name):
                visit(self.read('schemas/' + name + '.schema.json'))

    def test_all_canned_roles_satisfy_actual_contracts(self):
        for filename, kind in [('self_eval', 'evaluation'), ('eval_r1', 'evaluation'),
                               ('eval_r2', 'evaluation'), ('research', 'research'),
                               ('enhancement', 'enhancement')]:
            for validate in self.validators:
                with self.subTest(fixture=filename, validator=validate.__module__):
                    validate(self.read('tests/fixtures/' + filename + '.json'),
                             self.read('schemas/' + kind + '.schema.json'))

    def test_missing_dimensions_and_extra_nested_fields_are_rejected(self):
        value = copy.deepcopy(self.evaluation)
        del value['scores']['accuracy']
        self.rejects(value)
        value = copy.deepcopy(self.evaluation)
        value['scores']['accuracy']['approved'] = True
        self.rejects(value)

    def test_unknown_root_fields_and_missing_audit_are_rejected(self):
        value = copy.deepcopy(self.evaluation)
        value['secret_override'] = 'PASS'
        self.rejects(value)
        value = copy.deepcopy(self.evaluation)
        del value['loophole_audit']
        self.rejects(value)

    def test_scores_reject_boolean_fraction_and_out_of_range(self):
        for invalid in (True, 3.5, -1, 5, '4', None):
            with self.subTest(value=invalid):
                value = copy.deepcopy(self.evaluation)
                value['scores']['accuracy']['score'] = invalid
                self.rejects(value)

    def test_invariant_is_nullable_but_unknown_invariant_is_rejected(self):
        value = copy.deepcopy(self.evaluation)
        finding = dict(id='F1', dimension='accuracy', severity='MATERIAL', invariant=None,
                       location='TEST-ONLY', description='Synthetic finding', required_fix='Synthetic fix')
        value['blocking_findings'] = [finding]
        for valid in (None, 'I1', 'I16'):
            finding['invariant'] = valid
            for validate in self.validators:
                validate(value, self.schema)
        finding['invariant'] = 'I17'
        self.rejects(value)

    def test_research_source_requires_attribution_and_verdict(self):
        value = self.read('tests/fixtures/research.json')
        value['claims'] = [dict(id='C1', claim='TEST-ONLY assertion', origin='plan', verdict='CONFIRMED',
            sources=[dict(url='https://example.invalid', title='TEST-ONLY', accessed='2026-10-08', quote='TEST-ONLY')],
            newer_practice=None, affects_this_step=False, action_required=False, recommended_action='None')]
        schema = self.read('schemas/research.schema.json')
        for validate in self.validators:
            validate(value, schema)
        del value['claims'][0]['sources'][0]['accessed']
        self.rejects(value, schema)
        value['claims'][0]['sources'][0]['accessed'] = '2026-10-08'
        value['claims'][0]['verdict'] = 'PROBABLY'
        self.rejects(value, schema)

    def test_enhancement_rejects_unsupported_resolution_and_missing_ref(self):
        schema = self.read('schemas/enhancement.schema.json')
        value = dict(resolutions=[dict(ref='F1', action='IGNORE', evidence='TEST-ONLY')], amendments=[])
        self.rejects(value, schema)
        value['resolutions'][0]['action'] = 'FIXED'
        del value['resolutions'][0]['ref']
        self.rejects(value, schema)


if __name__ == '__main__':
    unittest.main()
