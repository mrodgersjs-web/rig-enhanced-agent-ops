"""Tests for Move 4 — 6-harness thin bridges + session-end edit-delta calibrator."""

import contextlib
import io
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from robonuggets_ops import dnc_guard
from robonuggets_ops.move4_harness_bridges.bridges import (
    TOOLS,
    bridge_invariants,
    calibrate_edit_deltas,
    diff_draft_to_approved,
    generate_bridge,
    generate_bridges,
    lint_bridge,
    lint_patch_proposal,
    main,
    taste_cart_update,
)


def make_doctrine_dir(root: pathlib.Path, lines: dict | None = None) -> pathlib.Path:
    doctrine = root / "doctrine"
    doctrine.mkdir(parents=True, exist_ok=True)
    files = lines or {
        "jake-identity.md": "# Jake identity\n",
        "jake-direction.md": "# Jake direction\n",
        "code-and-context.md": "# Code and context\n",
        "harnesses-and-testing.md": "# Harnesses and testing\n",
        "jev-and-verification.md": "# Jev and verification\n",
        "eight-types-gates.md": "# Eight types gates\n",
        "earned-leg-gates.md": "# Earned leg gates\n",
        "linkedin-safety.md": "# LinkedIn safety\n",
        "attention.md": "# Attention\n",
        "identity-and-account.md": "# Identity and account\n",
        "build-vs-buy.md": "# Build vs buy\n",
        "effort-ledger.md": "# Effort ledger\n",
        "gates-index.md": "# Gates index\n",
    }
    for name, body in files.items():
        (doctrine / name).write_text(body, encoding="utf-8")
    return doctrine


class BridgeGeneratorTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.doctrine = make_doctrine_dir(pathlib.Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_generate_bridges_all_six_tools(self):
        report = generate_bridges(self.doctrine)
        self.assertTrue(report["ok"], report["lint"])
        self.assertEqual([b["tool"] for b in report["bridges"]], list(TOOLS))
        for bridge in report["bridges"]:
            self.assertTrue(bridge["rule_refs"], bridge["tool"])
            for ref in bridge["rule_refs"]:
                self.assertTrue(pathlib.Path(ref["path"]).is_file())

    def test_bridge_preserves_three_invariants(self):
        for tool in TOOLS:
            bridge = generate_bridge(tool, self.doctrine)
            invariants = bridge["invariants"]
            self.assertIn("no_oracle", invariants)
            self.assertTrue(invariants["no_oracle"]["ats_host_carve_out"])
            self.assertEqual(
                list(invariants["no_oracle"]["ats_host_domains"]), list(dnc_guard.ATS_HOST_DOMAINS)
            )
            self.assertIn("gate_d_draft_only", invariants)
            self.assertEqual(invariants["gate_d_draft_only"]["mode"], "draft_only")
            self.assertFalse(invariants["gate_d_draft_only"]["auto_send"])
            self.assertIn("jev_before_done", invariants)
            self.assertEqual(invariants["jev_before_done"]["route_on_done"], "JEV")

    def test_bridge_invariants_match_dnc_guard_source(self):
        invariants = bridge_invariants()
        self.assertEqual(
            list(invariants["no_oracle"]["blocked_employers"]), list(dnc_guard.BLOCKED_EMPLOYERS)
        )

    def test_lint_bridge_flags_unresolved_ref(self):
        bridge = generate_bridge("aside", self.doctrine)
        bridge["rule_refs"].append({"ref": "missing-rule.md", "path": str(self.doctrine / "missing-rule.md")})
        result = lint_bridge(bridge, self.doctrine)
        self.assertFalse(result["ok"])
        self.assertIn("unresolved_rule_ref:missing-rule.md", result["violations"])

    def test_lint_bridge_flags_missing_invariant(self):
        bridge = generate_bridge("nod", self.doctrine)
        bridge["invariants"].pop("jev_before_done")
        result = lint_bridge(bridge, self.doctrine)
        self.assertFalse(result["ok"])
        self.assertIn("missing_invariant:jev_before_done", result["violations"])

    def test_lint_bridge_flags_duplicated_l1_prose(self):
        long_line = "- " + "canonical doctrine prose " * 8  # > 100 chars
        doctrine = make_doctrine_dir(
            pathlib.Path(self._tmp.name) / "with_prose", {"code-and-context.md": long_line + "\n"}
        )
        bridge = generate_bridge("omp", doctrine)
        bridge["note"] = long_line  # verbatim copy of the L1 line
        result = lint_bridge(bridge, doctrine)
        self.assertFalse(result["ok"])
        self.assertIn("duplicated_l1_prose", result["violations"])

    def test_lint_bridge_flags_gate_d_relaxation(self):
        bridge = generate_bridge("autark", self.doctrine)
        bridge["invariants"]["gate_d_draft_only"]["mode"] = "auto"
        result = lint_bridge(bridge, self.doctrine)
        self.assertFalse(result["ok"])
        self.assertIn("gate_d_draft_only_dropped", result["violations"])

    def test_unknown_tool_raises(self):
        with self.assertRaises(ValueError):
            generate_bridge("chatgpt", self.doctrine)


class EditDeltaCalibratorTests(unittest.TestCase):
    def test_diff_draft_to_approved_known_case(self):
        diff = diff_draft_to_approved("Send the email now", "Draft the email for review")
        self.assertTrue(diff["changed"])
        self.assertEqual(diff["edit_ops"], 2)
        self.assertEqual(diff["removed"], ["Send", "now"])
        self.assertEqual(diff["added"], ["Draft", "for review"])
        self.assertEqual(diff["similarity"], 0.4444)

    def test_calibrate_edited_draft_makes_add_check_proposal(self):
        drafts = [{"draft_id": "d1", "rule_id": "outreach-tone", "draft_text": "Send the email now"}]
        decisions = [
            {
                "draft_id": "d1",
                "decision": "approved_with_edits",
                "approved_text": "Draft the email for review",
            }
        ]
        result = calibrate_edit_deltas(drafts, decisions)
        self.assertTrue(result["ok"], result["errors"])
        self.assertEqual(result["rule_stats"]["outreach-tone"]["edited"], 1)
        ops = [p["op"] for p in result["patch_proposals"]]
        self.assertIn("add_check", ops)
        proposal = next(p for p in result["patch_proposals"] if p["op"] == "add_check")
        self.assertIn("Send", proposal["detail"])
        self.assertIn("now", proposal["detail"])
        self.assertEqual(proposal["evidence"], ["d1"])
        self.assertTrue(all(lint["ok"] for lint in result["proposal_lint"]))

    def test_calibrate_rejections_drive_tighten_rule(self):
        drafts = [
            {"draft_id": "d1", "rule_id": "gate-d", "draft_text": "a"},
            {"draft_id": "d2", "rule_id": "gate-d", "draft_text": "b"},
        ]
        decisions = [
            {"draft_id": "d1", "decision": "rejected"},
            {"draft_id": "d2", "decision": "rejected"},
        ]
        result = calibrate_edit_deltas(drafts, decisions)
        self.assertEqual(result["rule_stats"]["gate-d"]["rejection_rate"], 1.0)
        proposal = next(p for p in result["patch_proposals"] if p["op"] == "tighten_rule")
        self.assertEqual(proposal["rule_id"], "gate-d")
        self.assertEqual(sorted(proposal["evidence"]), ["d1", "d2"])

    def test_calibrate_decision_without_draft_is_error(self):
        result = calibrate_edit_deltas([], [{"draft_id": "ghost", "decision": "approved"}])
        self.assertFalse(result["ok"])
        self.assertIn("decision_without_draft:ghost", result["errors"])

    def test_calibrate_unknown_decision_value_is_error(self):
        drafts = [{"draft_id": "d1", "rule_id": "r", "draft_text": "x"}]
        result = calibrate_edit_deltas(drafts, [{"draft_id": "d1", "decision": "shrug"}])
        self.assertFalse(result["ok"])
        self.assertIn("unknown_decision:'shrug'", result["errors"])

    def test_patch_proposal_lint_rejects_raw_l1_append(self):
        raw = {"op": "raw_l1_append", "rule_id": "r", "detail": "append this line to CLAUDE.md", "evidence": ["d1"]}
        result = lint_patch_proposal(raw)
        self.assertFalse(result["ok"])
        self.assertIn("op_not_allowed:'raw_l1_append'", result["violations"])

    def test_patch_proposal_lint_rejects_missing_evidence(self):
        proposal = {"op": "add_check", "rule_id": "r", "detail": "check x", "evidence": []}
        result = lint_patch_proposal(proposal)
        self.assertFalse(result["ok"])
        self.assertIn("missing_evidence", result["violations"])

    def test_patch_proposal_lint_rejects_oversized_detail(self):
        proposal = {"op": "add_check", "rule_id": "r", "detail": "x" * 300, "evidence": ["d1"]}
        result = lint_patch_proposal(proposal)
        self.assertFalse(result["ok"])
        self.assertIn("detail_too_long", result["violations"])


class TasteCartTests(unittest.TestCase):
    def test_outlier_multiplier_math(self):
        records = [
            {"id": "a", "views": 100},
            {"id": "b", "views": 100},
            {"id": "c", "views": 400},
        ]
        result = taste_cart_update(records)
        self.assertTrue(result["ok"])
        self.assertEqual(result["account_median_views"], 100)
        by_id = {r["id"]: r for r in result["records"]}
        self.assertEqual(by_id["c"]["outlier_multiplier"], 4.0)
        self.assertEqual(by_id["c"]["tag"], "outlier")
        self.assertEqual(by_id["a"]["outlier_multiplier"], 1.0)
        self.assertEqual(by_id["a"]["tag"], "baseline")
        self.assertEqual([u["id"] for u in result["taste_cart_updates"]], ["c"])
        self.assertEqual(result["taste_cart_updates"][0]["update"], "pin_to_taste_cart")

    def test_non_positive_median_guard(self):
        result = taste_cart_update([{"id": "a", "views": 0}, {"id": "b", "views": 0}])
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "non_positive_account_median")

    def test_empty_records_guard(self):
        result = taste_cart_update([])
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "no_content_records")


class CliAndContextTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.doctrine = make_doctrine_dir(pathlib.Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self, argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_cli_json_bridges(self):
        code, out = self._run(["bridges", "--tool", "aside", "--doctrine-dir", str(self.doctrine), "--json"])
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertTrue(report["ok"])
        self.assertEqual(report["bridges"]["bridges"][0]["tool"], "aside")

    def test_cli_json_all_and_calibrate_and_taste(self):
        drafts_path = pathlib.Path(self._tmp.name) / "drafts.json"
        decisions_path = pathlib.Path(self._tmp.name) / "decisions.json"
        content_path = pathlib.Path(self._tmp.name) / "content.json"
        drafts_path.write_text(
            json.dumps([{"draft_id": "d1", "rule_id": "r", "draft_text": "Send the email now"}])
        )
        decisions_path.write_text(
            json.dumps([{"draft_id": "d1", "decision": "approved_with_edits", "approved_text": "Draft only"}])
        )
        content_path.write_text(json.dumps([{"id": "a", "views": 10}, {"id": "b", "views": 90}]))
        code, out = self._run(
            [
                "all",
                "--doctrine-dir", str(self.doctrine),
                "--drafts", str(drafts_path),
                "--decisions", str(decisions_path),
                "--content", str(content_path),
                "--json",
            ]
        )
        self.assertEqual(code, 0)
        report = json.loads(out)
        self.assertTrue(report["ok"])
        self.assertIn("calibration", report)
        self.assertIn("taste_cart", report)
        self.assertEqual(report["taste_cart"]["account_median_views"], 50)

    def test_context_json_passes_verify_gates_schema(self):
        ctx_path = (
            pathlib.Path(__file__).resolve().parents[1]
            / "src"
            / "robonuggets_ops"
            / "move4_harness_bridges"
            / "context.json"
        )
        payload = json.loads(ctx_path.read_text(encoding="utf-8"))
        required = {"move", "status", "deliverables", "citations", "gates", "jev"}
        self.assertTrue(required.issubset(payload.keys()))
        self.assertTrue(payload["citations"])
        self.assertEqual(payload["move"], "move4")
        for source in payload["cited_sources"]:
            self.assertTrue(source.startswith("src: "), source)
        self.assertIn("1-dnc", payload["gates"])
        self.assertIn("gate-d", payload["gates"])
        self.assertEqual(payload["jev"]["route"], "CODE")

    def test_context_json_deliverable_modules_resolve(self):
        ctx_path = (
            pathlib.Path(__file__).resolve().parents[1]
            / "src"
            / "robonuggets_ops"
            / "move4_harness_bridges"
            / "context.json"
        )
        payload = json.loads(ctx_path.read_text(encoding="utf-8"))
        import importlib

        for deliverable in payload["deliverables"]:
            module_name, attr = deliverable["module"].rsplit(".", 1)
            module = importlib.import_module(f"robonuggets_ops.{module_name}")
            self.assertTrue(callable(getattr(module, attr)), deliverable["module"])


if __name__ == "__main__":
    unittest.main()
