import tempfile
import unittest
from pathlib import Path

from eda_lab.models import AdapterRunResult, JobSpec
from eda_lab.parser import parse_report
from eda_lab.service import JobService
from eda_lab.store import Store


EVIDENCE = Path(__file__).resolve().parents[1] / "docs/evidence/2026-09-24-real-sta"


class OpenStaSetupMaxTests(unittest.TestCase):
    def test_real_opensta_met_report_normalizes_against_recorded_oracle(self):
        result = parse_report(EVIDENCE / "normal.log")

        self.assertEqual(result.parse_status, "OK")
        self.assertEqual(result.check_status, "PASS")
        self.assertEqual(result.semantic_status, "VALID")
        self.assertEqual(result.provenance_status, "VALID")
        self.assertEqual(result.completeness, "complete")
        self.assertEqual(result.metrics["source_kind"], "tool_generated")
        self.assertEqual(result.metrics["tool_name"], "OpenSTA")
        self.assertEqual(result.metrics["tool_version"], "3.1.0")
        self.assertEqual(result.metrics["analysis_type"], "setup_max")
        self.assertEqual(result.metrics["startpoint"], "_3_")
        self.assertEqual(result.metrics["endpoint"], "_2_")
        self.assertEqual(result.metrics["path_group"], "clk")
        self.assertAlmostEqual(result.metrics["arrival_time_ns"], 0.423375)
        self.assertAlmostEqual(result.metrics["required_time_ns"], 9.883325)
        self.assertAlmostEqual(result.metrics["worst_slack_ns"], 9.459949)
        self.assertEqual(result.provenance["source_kind"], "tool_generated")

    def test_real_opensta_violated_report_is_parsed_but_not_promoted_to_pass(self):
        result = parse_report(EVIDENCE / "tight.log")

        self.assertEqual(result.parse_status, "OK")
        self.assertEqual(result.check_status, "FAIL")
        self.assertEqual(result.semantic_status, "VALID")
        self.assertAlmostEqual(result.metrics["worst_slack_ns"], -0.440050)

    def test_opensta_analysis_type_mismatch_is_semantic_invalid_not_a_trusted_result(self):
        raw = (EVIDENCE / "normal.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "analysis-type-mismatch.log"
            path.write_text(raw.replace("Path Type: max", "Path Type: min"), encoding="utf-8")
            result = parse_report(path)

        self.assertEqual(result.parse_status, "OK")
        self.assertEqual(result.semantic_status, "INVALID")
        self.assertEqual(result.check_status, "UNKNOWN")
        self.assertIn("OpenSTA path type min does not match setup/max profile", result.errors)

    def test_service_persists_semantic_invalid_as_failed_and_untrusted(self):
        raw = (EVIDENCE / "normal.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "analysis-type-mismatch.log"
            report.write_text(raw.replace("Path Type: max", "Path Type: min"), encoding="utf-8")
            adapter = type(
                "SemanticMismatchAdapter",
                (),
                {"run": lambda _, __: AdapterRunResult(report, process_exit_code=0)},
            )()
            service = JobService(Store(), max_workers=1, max_attempts=1, adapter=adapter)
            spec = JobSpec("opensta-semantic", "tiny", "research", "opensta_setup_max", "tt_025C_1v80", 0, "ns")

            service.submit(spec)
            service.futures[spec.job_id].result(timeout=2)
            result = service.get(spec.job_id)

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["parse_status"], "OK")
        self.assertEqual(result["semantic_status"], "INVALID")
        self.assertEqual(result["trust_status"], "INVALID")
        self.assertEqual(result["attempts"][-1]["error_type"], "semantic_invalid")

    def test_opensta_report_requires_complete_supported_profile(self):
        raw = (EVIDENCE / "normal.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "truncated.log"
            path.write_text(raw.replace("EDA_LAB_REPORT_END\n", ""), encoding="utf-8")
            result = parse_report(path)

        self.assertEqual(result.parse_status, "INVALID")
        self.assertEqual(result.check_status, "UNKNOWN")
        self.assertEqual(result.provenance["source_kind"], "tool_generated")
        self.assertIn("missing or duplicate OpenSTA completion marker", result.errors)

    def test_opensta_report_rejects_unsupported_version_and_inconsistent_summary(self):
        raw = (EVIDENCE / "normal.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            unsupported = Path(directory) / "unsupported.log"
            unsupported.write_text(raw.replace("OpenSTA 3.1.0", "OpenSTA 3.2.0"), encoding="utf-8")
            inconsistent = Path(directory) / "inconsistent.log"
            inconsistent.write_text(
                raw.replace("worst slack max 9.459949", "worst slack max 9.000000"),
                encoding="utf-8",
            )

            unsupported_result = parse_report(unsupported)
            inconsistent_result = parse_report(inconsistent)

        self.assertEqual(unsupported_result.parse_status, "INVALID")
        self.assertIn("unsupported OpenSTA version 3.2.0", unsupported_result.errors)
        self.assertEqual(inconsistent_result.parse_status, "OK")
        self.assertEqual(inconsistent_result.semantic_status, "INVALID")
        self.assertIn("reported path slack differs from worst slack", inconsistent_result.errors)

    def test_opensta_error_diagnostic_is_not_parsed_as_a_timing_pass(self):
        raw = (EVIDENCE / "normal.log").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "diagnostic.log"
            path.write_text(raw + "Error: synthetic diagnostic for regression\n", encoding="utf-8")
            result = parse_report(path)

        self.assertEqual(result.parse_status, "INVALID")
        self.assertEqual(result.check_status, "UNKNOWN")
        self.assertIn("OpenSTA error diagnostic present", result.errors)

    def test_service_preserves_execution_success_separately_from_timing_failure(self):
        report = EVIDENCE / "tight.log"
        adapter = type(
            "RecordedOpenStaAdapter",
            (),
            {"run": lambda _, __: AdapterRunResult(report, process_exit_code=0)},
        )()
        service = JobService(Store(), max_workers=1, max_attempts=1, adapter=adapter)
        spec = JobSpec("opensta-tight", "tiny", "research", "opensta_setup_max", "tt_025C_1v80", 0, "ns")

        service.submit(spec)
        service.futures[spec.job_id].result(timeout=2)
        result = service.get(spec.job_id)

        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["parse_status"], "OK")
        self.assertEqual(result["check_status"], "FAIL")
        self.assertEqual(result["semantic_status"], "VALID")
        self.assertEqual(result["provenance_status"], "VALID")
        self.assertEqual(result["trust_status"], "TRUSTED")
        self.assertEqual(result["provenance"]["source_kind"], "tool_generated")
        self.assertAlmostEqual(result["metrics"]["worst_slack_ns"], -0.440050)

    def test_nonzero_process_exit_still_fails_after_valid_opensta_parse(self):
        report = EVIDENCE / "normal.log"
        adapter = type(
            "FailedOpenStaAdapter",
            (),
            {"run": lambda _, __: AdapterRunResult(report, process_exit_code=17)},
        )()
        service = JobService(Store(), max_workers=1, max_attempts=1, adapter=adapter)
        spec = JobSpec("opensta-exit", "tiny", "research", "opensta_setup_max", "tt_025C_1v80", 0, "ns")

        service.submit(spec)
        service.futures[spec.job_id].result(timeout=2)
        result = service.get(spec.job_id)

        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["parse_status"], "OK")
        self.assertEqual(result["check_status"], "PASS")
        self.assertEqual(result["trust_status"], "INVALID")
        self.assertEqual(result["attempts"][-1]["error_type"], "tool_exit")


if __name__ == "__main__":
    unittest.main()
