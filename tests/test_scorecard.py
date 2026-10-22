import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import scorecard  # noqa: E402

EXAMPLE = ROOT / "examples" / "acme-widgets.results.json"


class ScorecardTest(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def test_failed_is_not_a_miss(self):
        s = scorecard.summarize(self.data)
        p = s["per_engine"]["perplexity"]
        self.assertEqual(p["failed"], 1)
        self.assertEqual(p["valid"], 2)
        self.assertEqual(p["mentioned"], 1)
        self.assertAlmostEqual(p["hit_rate"], 0.5)

    def test_overall_and_competitors(self):
        s = scorecard.summarize(self.data)
        self.assertAlmostEqual(s["overall_hit_rate"], 3 / 5)
        self.assertEqual(s["competitors"][0], ("supplier-one.example", 3))

    def test_render_contains_table(self):
        md = scorecard.render(self.data)
        self.assertIn("| chatgpt | 3 | 0 | 2/3 | 67% |", md)
        self.assertIn("FAILED", md)
        self.assertIn("✅ #3", md)

    def test_checked_in_scorecard_matches_renderer(self):
        expected = (ROOT / 'examples/acme-widgets.scorecard.md').read_text(encoding='utf-8')
        self.assertEqual(scorecard.render(self.data), expected)
        self.assertTrue(expected.startswith('> ' + self.data['_note']))

    def test_optional_note_is_not_invented(self):
        del self.data['_note']
        self.assertTrue(scorecard.render(self.data).startswith('# AI Visibility Scorecard'))

    def test_diff_against_previous(self):
        prev = json.loads(json.dumps(self.data))
        for r in prev["results"]:
            if r["engine"] == "chatgpt" and r["question_id"] == "Q2":
                r["mentioned"], r["rank"] = False, None
            r["competitors"] = [c for c in r.get("competitors", []) if c != "supplier-three.example"]
        md = scorecard.render(self.data, prev)
        self.assertIn("chatgpt / Q2: now mentioned", md)
        self.assertIn("New competitors: supplier-three.example", md)


if __name__ == "__main__":
    unittest.main()
