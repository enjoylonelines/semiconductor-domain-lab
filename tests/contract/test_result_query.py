import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from eda_lab.store import Store


class ResultQueryTests(unittest.TestCase):
    def setUp(self):
        self.store = Store()
        self.store.create_revision("r1", "design-a", "abc", "lib-1", "sdc-1", "OpenSTA-3.1", "parser-1")
        self.store.create_revision("r2", "design-a", "def", "lib-1", "sdc-1", "OpenSTA-3.1", "parser-1")

    def tearDown(self):
        self.store.close()

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

    def test_findings_require_an_existing_revision(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_findings("missing", [("run", "A", "B", "clk", "setup", "TT", -0.1)])

    def test_failed_bulk_finding_insert_rolls_back_the_whole_batch(self):
        valid = ("run", "A", "B", "clk", "setup", "TT", -0.1)
        invalid = ("run", None, "C", "clk", "setup", "TT", -0.2)
        with self.assertRaises(sqlite3.IntegrityError):
            self.store.save_findings("r1", [valid, invalid])
        count = self.store.connection.execute("SELECT COUNT(*) FROM findings WHERE revision_id = 'r1'").fetchone()[0]
        self.assertEqual(count, 0)

    def test_separate_connections_allow_only_the_lease_owner_terminal_write(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runs.sqlite"
            owner = Store(database)
            owner.create_run("concurrent-terminal", "design-a", "PCIe", "timing")
            owner.record_attempt("concurrent-terminal", 1, "RUNNING")
            self.assertTrue(owner.acquire_attempt_lease("concurrent-terminal", 1, "worker-a", "owner-token", 30))
            contender = Store(database)
            gate = threading.Barrier(2)
            outcomes = []

            def transition(store, token):
                gate.wait(timeout=1)
                outcomes.append(store.transition_attempt("concurrent-terminal", 1, token, "SUCCEEDED"))

            threads = [
                threading.Thread(target=transition, args=(owner, "owner-token")),
                threading.Thread(target=transition, args=(contender, "stale-token")),
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)
            self.assertEqual(sorted(outcomes), [False, True])
            self.assertEqual(owner.get_run("concurrent-terminal")["attempts"][-1]["status"], "SUCCEEDED")
            contender.close()
            owner.close()


if __name__ == "__main__":
    unittest.main()
