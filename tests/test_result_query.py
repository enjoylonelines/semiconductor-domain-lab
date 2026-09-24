import unittest

from eda_lab.store import Store


class ResultQueryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.store.create_revision("r1", "design-a", "abc", "lib-1", "sdc-1", "OpenSTA-3.1", "parser-1")
        self.store.create_revision("r2", "design-a", "def", "lib-1", "sdc-1", "OpenSTA-3.1", "parser-1")

    def test_strong_finding_identity_keeps_different_corners_as_new_violations(self):
        self.store.save_findings("r1", [("run-1", "A/Q", "B/D", "clk", "setup", "SS", -0.1)])
        self.store.save_findings("r2", [("run-2", "A/Q", "B/D", "clk", "setup", "TT", -0.2)])

        outcome = self.store.new_violations("r1", "r2")

        self.assertEqual(outcome["comparability"], "COMPARABLE")
        self.assertEqual(len(outcome["findings"]), 1)
        self.assertEqual(outcome["findings"][0]["corner"], "TT")

    def test_condition_change_withholds_regression_comparison(self):
        self.store.create_revision("r3", "design-a", "ghi", "lib-1", "sdc-other", "OpenSTA-3.1", "parser-1")

        outcome = self.store.new_violations("r1", "r3")

        self.assertEqual(outcome, {"comparability": "CONDITION_CHANGED", "findings": []})

    def test_composite_query_index_is_created_only_as_the_single_challenger(self):
        self.store.save_findings("r2", [
            ("run-2", "A/Q", "B/D", "clk", "setup", "TT", -0.2),
            ("run-2", "A/Q", "C/D", "clk", "setup", "TT", -0.2),
        ])
        before = self.store.new_violations("r1", "r2")
        self.assertFalse(self.store.has_finding_query_index())
        self.store.create_finding_query_index()
        self.assertTrue(self.store.has_finding_query_index())
        self.assertEqual(self.store.new_violations("r1", "r2"), before)


if __name__ == "__main__":
    unittest.main()
