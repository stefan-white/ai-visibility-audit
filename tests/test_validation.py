import contextlib
import copy
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import scorecard


class ValidationTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((ROOT / 'examples/acme-widgets.results.json').read_text())

    def test_valid_fixture(self):
        scorecard.validate(self.data)
        self.assertIn('AI Visibility Scorecard', scorecard.render(self.data))

    def test_required_fields(self):
        for field in ('brand', 'date', 'market', 'questions', 'results'):
            with self.subTest(field=field):
                data = copy.deepcopy(self.data)
                del data[field]
                with self.assertRaisesRegex(scorecard.ValidationError, rf'\$\.{field}: required'):
                    scorecard.validate(data)

    def test_types_and_values_identify_field(self):
        cases = [
            ('mentioned', 'false'), ('mentioned', 0),
            ('rank', True), ('rank', 0), ('rank', 1.5),
            ('cited_urls', 'https://acme-widgets.example'),
            ('competitors', [123]), ('status', 'unknown'), ('engine', ''),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = copy.deepcopy(self.data)
                data['results'][0][field] = value
                with self.assertRaisesRegex(scorecard.ValidationError, rf'\$\.results\[0\]\.{field}'):
                    scorecard.validate(data)

    def test_top_level_and_nested_container_types(self):
        for value in (None, [], 'text', 42):
            with self.subTest(value=value), self.assertRaisesRegex(scorecard.ValidationError, 'expected object'):
                scorecard.validate(value)
        for field, value in [('questions', {}), ('results', {}), ('questions', [None]), ('results', [None])]:
            data = copy.deepcopy(self.data)
            data[field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(scorecard.ValidationError, field):
                scorecard.validate(data)

    def test_success_requires_mentioned(self):
        del self.data['results'][0]['mentioned']
        with self.assertRaisesRegex(scorecard.ValidationError, r'results\[0\]\.mentioned: required'):
            scorecard.validate(self.data)

    def test_failed_requires_error(self):
        del self.data['results'][4]['error']
        with self.assertRaisesRegex(scorecard.ValidationError, r'results\[4\]\.error: required'):
            scorecard.validate(self.data)

    def test_unmentioned_cannot_have_rank(self):
        self.data['results'][0]['rank'] = 1
        with self.assertRaisesRegex(scorecard.ValidationError, r'results\[0\]\.rank: expected null'):
            scorecard.validate(self.data)

    def test_unique_ids_and_references(self):
        cases = []
        data = copy.deepcopy(self.data)
        data['questions'][1]['id'] = 'Q1'
        cases.append((data, r'questions\[1\]\.id: duplicate'))
        data = copy.deepcopy(self.data)
        data['results'][0]['question_id'] = 'unknown'
        cases.append((data, r'results\[0\]\.question_id: unknown'))
        data = copy.deepcopy(self.data)
        data['results'].append(copy.deepcopy(data['results'][0]))
        cases.append((data, r'results\[6\]: duplicate'))
        for data, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(scorecard.ValidationError, message):
                scorecard.validate(data)

    def test_calendar_dates(self):
        for value in ('2026-02-30', '20260115', '2026-1-15', 'unknown'):
            self.data['date'] = value
            with self.subTest(value=value), self.assertRaisesRegex(scorecard.ValidationError, r'\$\.date:'):
                scorecard.validate(self.data)

    def test_empty_and_failed_results_are_not_misses(self):
        self.data['results'] = []
        self.assertIn('valid answers only): n/a', scorecard.render(self.data))
        self.data['results'] = [{'engine': 'gemini', 'question_id': 'Q1', 'status': 'failed', 'error': 'synthetic failure'}]
        self.assertIn('valid answers only): n/a', scorecard.render(self.data))
        self.assertIsNone(scorecard.summarize(self.data)['per_engine']['gemini']['hit_rate'])

    def test_extensions_and_other_engine_allowed(self):
        self.data['provenance'] = {'method': 'manual'}
        self.data['results'][0]['engine'] = 'another_engine'
        scorecard.validate(self.data)

    def test_render_validates_previous_input(self):
        previous = copy.deepcopy(self.data)
        del previous['brand']
        with self.assertRaisesRegex(scorecard.ValidationError, r'\$\.brand: required'):
            scorecard.render(self.data, previous)

    def test_cli_invalid_current_and_previous_no_partial_output(self):
        with tempfile.TemporaryDirectory() as directory:
            valid = pathlib.Path(directory) / 'valid.json'
            invalid = pathlib.Path(directory) / 'invalid.json'
            valid.write_text(json.dumps(self.data))
            del self.data['results'][0]['mentioned']
            invalid.write_text(json.dumps(self.data))
            for args in ([invalid], [valid, invalid]):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/scorecard.py'), *map(str, args)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertIn('$.results[0].mentioned', result.stderr)
                self.assertNotIn('Traceback', result.stderr)
                self.assertNotIn(directory, result.stderr)

    def test_cli_malformed_json_and_nonfinite_number(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / 'invalid.json'
            for content, error in [('{', 'Invalid JSON'), ('{"rank": NaN}', 'non-finite')]:
                path.write_text(content)
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    status = scorecard.main(['scorecard.py', str(path)])
                self.assertEqual(status, 2)
                self.assertEqual(out.getvalue(), '')
                self.assertIn(error, err.getvalue())

    def test_cli_invalid_utf8_current_and_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            valid = pathlib.Path(directory) / 'valid.json'
            invalid = pathlib.Path(directory) / 'invalid.json'
            valid.write_text(json.dumps(self.data), encoding='utf-8')
            invalid.write_bytes(b'{"brand": "\xff"}')
            for args in ([invalid], [valid, invalid]):
                result = subprocess.run([sys.executable, str(ROOT / 'scripts/scorecard.py'), *map(str, args)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, '')
                self.assertEqual(result.stderr, 'Invalid JSON encoding: expected UTF-8.\n')

    def test_missing_file_is_clean_error(self):
        with tempfile.TemporaryDirectory() as directory:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = scorecard.main(['scorecard.py', str(pathlib.Path(directory) / 'absent.json')])
            self.assertEqual(status, 2)
            self.assertEqual(out.getvalue(), '')
            self.assertIn('Cannot read', err.getvalue())
            self.assertNotIn(directory, err.getvalue())

    def test_schema_dialect(self):
        schema = json.loads((ROOT / 'schema/results.schema.json').read_text())
        self.assertEqual(schema['$schema'], 'https://json-schema.org/draft/2020-12/schema')


if __name__ == '__main__':
    unittest.main()
