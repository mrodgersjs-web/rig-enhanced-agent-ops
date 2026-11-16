"""Tests for Move 1: ARMS + Gate-D 5-axis auditor, dry-run enforcer, 3-slot consolidator."""
import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from robonuggets_ops.move1_arms_audit import auditor

CTX_PATH = pathlib.Path(__file__).resolve().parents[1] / "src" / "robonuggets_ops" / "move1_arms_audit" / "context.json"


def full_routine(**overrides):
    routine = {
        "id": "r-full",
        "name": "full",
        "slot": "morning",
        "actions": ["collect", "write"],
        "action_receipts": ["r1.json", "r2.json"],
        "recall_reads": True,
        "recall_writes": True,
        "model": "qwen38",
        "model_fallback": "minimax",
        "feedback_log": "log.jsonl",
        "feedback_applied": "tune.md",
        "gate_d": True,
        "jev": True,
        "deliverables": ["brief.md"],
        "gate_d_actions": [],
        "schedule": {
            "kind": "cron",
            "manual_dry_runs_passed": 2,
            "idempotent_writes": True,
            "max_retries": 3,
            "token_ceiling": 20000,
            "watched_failure_channel": "#rig-alerts",
        },
    }
    routine.update(overrides)
    return routine


class TestArmsScore(unittest.TestCase):
    def test_max_score_is_ten(self):
        scores = auditor.score_arms(full_routine())
        self.assertEqual(scores["total"], 10)
        self.assertEqual(auditor.MAX_TOTAL, 10)
        self.assertFalse(scores["chat_shaped"])

    def test_each_axis_scores_zero_to_two(self):
        for routine in (full_routine(), {}, full_routine(actions=["a"])):
            for axis in auditor.AXES:
                self.assertIn(auditor.score_arms(routine)[axis], (0, 1, 2))

    def test_chat_shaped_when_action_zero(self):
        scores = auditor.score_arms({"actions": []})
        self.assertEqual(scores["action"], 0)
        self.assertTrue(scores["chat_shaped"])

    def test_weak_evidence_scores_one(self):
        scores = auditor.score_arms(full_routine(action_receipts=[], recall_writes=False,
                                                 model_fallback="", feedback_applied="",
                                                 jev=False))
        self.assertEqual(scores["action"], 1)
        self.assertEqual(scores["recall"], 1)
        self.assertEqual(scores["model"], 1)
        self.assertEqual(scores["self_improvement"], 1)
        self.assertEqual(scores["gate_d_jev"], 1)

    def test_gate_d_jev_needs_both_for_two(self):
        self.assertEqual(auditor.score_arms({"gate_d": True, "jev": True})["gate_d_jev"], 2)
        self.assertEqual(auditor.score_arms({"gate_d": True})["gate_d_jev"], 1)
        self.assertEqual(auditor.score_arms({})["gate_d_jev"], 0)


class TestScheduleValidator(unittest.TestCase):
    def test_compliant_cron_allowed(self):
        self.assertTrue(auditor.validate_schedule(full_routine())["allowed"])

    def test_manual_never_blocked(self):
        verdict = auditor.validate_schedule({"schedule": {"kind": "manual"}})
        self.assertTrue(verdict["allowed"])

    def test_cron_missing_every_rule_blocked(self):
        verdict = auditor.validate_schedule({"schedule": {"kind": "cron"}})
        self.assertFalse(verdict["allowed"])
        self.assertEqual(len(verdict["violations"]), 5)

    def test_each_rule_can_block_alone(self):
        for field, bad_value in (
            ("manual_dry_runs_passed", 0),
            ("idempotent_writes", False),
            ("max_retries", 4),
            ("token_ceiling", 0),
            ("watched_failure_channel", "  "),
        ):
            schedule = full_routine()["schedule"]
            schedule[field] = bad_value
            verdict = auditor.validate_schedule({"schedule": schedule})
            self.assertFalse(verdict["allowed"], field)
            self.assertEqual(len(verdict["violations"]), 1, field)
            self.assertIn(field, verdict["violations"][0])

    def test_rrule_held_to_same_rules(self):
        schedule = full_routine()["schedule"]
        schedule["kind"] = "rrule"
        self.assertTrue(auditor.validate_schedule({"schedule": schedule})["allowed"])
        schedule["token_ceiling"] = 0
        self.assertFalse(auditor.validate_schedule({"schedule": schedule})["allowed"])


class TestSlotConsolidator(unittest.TestCase):
    def test_three_slots_single_inbox_digest(self):
        routines = [
            full_routine(id="a", slot="morning", deliverables=["one.md", "two.md"]),
            full_routine(id="b", slot="midday", deliverables=["three.md"]),
            full_routine(id="c", slot="evening", deliverables=[]),
        ]
        result = auditor.consolidate_slots(routines)
        self.assertEqual(set(result["slots"]), {"morning", "midday", "evening"})
        self.assertEqual(result["slots"]["morning"]["inbox"], ["one.md", "two.md"])
        self.assertEqual(result["slots"]["morning"]["routines"], ["a"])
        self.assertEqual(result["digest_count"], 2)

    def test_gate_d_actions_batched_into_one_queue(self):
        routines = [
            full_routine(id="a", slot="morning", gate_d_actions=["send-brief"]),
            full_routine(id="b", slot="evening", gate_d_actions=["post-x", "post-li"]),
        ]
        result = auditor.consolidate_slots(routines)
        self.assertEqual(result["gate_d_yes_queue"], ["send-brief", "post-x", "post-li"])

    def test_unknown_slot_rejected(self):
        with self.assertRaises(ValueError):
            auditor.consolidate_slots([full_routine(slot="night")])


class TestAuditAndCli(unittest.TestCase):
    def test_audit_flags_blocked_armings(self):
        report = auditor.audit([full_routine(schedule={"kind": "cron"})])
        self.assertEqual(report["blocked_armings"], ["r-full"])

    def test_cli_json_output(self):
        routines = [full_routine(), full_routine(id="r-chatter", actions=[], action_receipts=[],
                                                 recall_reads=False, recall_writes=False,
                                                 feedback_log="", feedback_applied="",
                                                 gate_d=False, jev=False, deliverables=["chat.md"])]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
            json.dump(routines, handle)
            path = handle.name
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = auditor.main(["--json", path])
        report = json.loads(buffer.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertIn("routines", report)
        self.assertIn("consolidation", report)
        by_id = {entry["id"]: entry for entry in report["routines"]}
        self.assertEqual(by_id["r-full"]["arms"]["total"], 10)
        self.assertTrue(by_id["r-chatter"]["arms"]["chat_shaped"])

    def test_cli_exit_1_on_blocked_arming(self):
        routines = [full_routine(schedule={"kind": "cron"})]
        with mock.patch("sys.stdin", io.StringIO(json.dumps(routines))):
            with redirect_stdout(io.StringIO()):
                self.assertEqual(auditor.main([]), 1)

    def test_context_json_cited_sources_valid(self):
        payload = json.loads(CTX_PATH.read_text())
        for key in ("move", "status", "deliverables", "citations", "gates", "jev", "cited_sources"):
            self.assertIn(key, payload)
        self.assertTrue(payload["citations"])
        for source in payload["cited_sources"]:
            self.assertTrue(source["id"].startswith("src: classroom/"))
            self.assertTrue(source["supports"])


if __name__ == "__main__":
    unittest.main()
