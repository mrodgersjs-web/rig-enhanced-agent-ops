"""Phase 2 live GTM dry-run tests: DNC matrix, quarantine, terminal states, non-send bounds.

Every new gate carries a planted-failure check: a known-bad mutation must make
the check go RED before the shipped artifact is trusted (see
TestPlantedFailures). No test depends on the real
~/rig-gtm-home/gmail-sender/STOP file (NO_STOP_FILE pattern) or on network.
"""

from __future__ import annotations

import builtins
import copy
import importlib.util
import json
import pathlib
import socket
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from robonuggets_ops import dnc_guard  # noqa: E402
from robonuggets_ops.move2_nod_twenty_reply import pipeline  # noqa: E402
from robonuggets_ops.move3_gtm_teaser_tune import pack  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "run_live_gtm_phase2", REPO_ROOT / "scripts" / "run_live_gtm_phase2.py"
)
phase2 = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(phase2)

# A STOP-brake path that cannot exist on this machine: sender-lane posture in
# tests must not depend on the real ~/rig-gtm-home/gmail-sender/STOP file.
NO_STOP_FILE = "/nonexistent/rig-stop-brake-does-not-exist"

FIXTURE_DNC = {
    "updated": "2026-11-16",
    "people": ["Matt Colmia", "Someone Else"],
    "companies": ["Accenture"],
    "blocked_companies": {"companies": ["Oracle", "Oracle Health"]},
}


def _walk_dicts(payload):
    """Yield every nested dict inside a JSON payload."""
    if isinstance(payload, dict):
        yield payload
        for value in payload.values():
            yield from _walk_dicts(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_dicts(item)


class TestDncMatrix(unittest.TestCase):
    """Dry-run rows 1-5: employer block, person block, ATS carve-outs."""

    @classmethod
    def setUpClass(cls):
        cls.rows = {row["name"]: row for row in phase2.run_dry_run_matrix(dnc=FIXTURE_DNC)}

    def test_matrix_is_seven_passing_rows(self):
        all_rows = list(self.rows.values())
        self.assertEqual(len(all_rows), 7)
        for row in all_rows:
            self.assertTrue(row["pass"], f"row {row['name']} failed: {row}")

    def test_oracle_blocked(self):
        row = self.rows["oracle_blocked"]
        self.assertTrue(row["pass"])
        self.assertFalse(row["expected"]["allowed"])
        self.assertEqual(
            row["expected"]["reason"],
            "blocked: employer 'Oracle' is on the do-not-contact employer list",
        )
        verdict = dnc_guard.evaluate_outreach_target(
            company="Oracle", person_name="Jane Recruiter", url="", recipient_domain=""
        )
        self.assertFalse(verdict["allowed"])
        self.assertTrue(verdict["reason"].startswith("blocked_employer:"))

    def test_mattcolmia_blank_company(self):
        row = self.rows["mattcolmia_blank_company"]
        self.assertTrue(row["pass"])
        self.assertFalse(row["expected"]["allowed"])
        self.assertEqual(
            row["expected"]["reason"],
            "blocked: person 'Matt Colmia' is on the do-not-contact person list",
        )
        verdict = dnc_guard.evaluate_outreach_target(
            company="", person_name="Matt Colmia", url="", recipient_domain=""
        )
        self.assertFalse(verdict["allowed"])
        self.assertTrue(verdict["reason"].startswith("blocked_person:"))

    def test_ucsf_ats_carve_out(self):
        row = self.rows["ucsf_ats"]
        self.assertTrue(row["pass"])
        self.assertTrue(row["expected"]["allowed"])
        self.assertTrue(row["expected"]["atsHostCarveOut"])
        verdict = dnc_guard.evaluate_outreach_target(
            company="UCSF", person_name="Jordan Lee",
            url="https://ucsf.fa.us2.oraclecloud.com/hcmUI", recipient_domain="",
        )
        self.assertTrue(verdict["allowed"])
        self.assertTrue(verdict["atsHostCarveOut"])

    def test_jpmc_ats_carve_out(self):
        row = self.rows["jpmc_ats"]
        self.assertTrue(row["pass"])
        self.assertTrue(row["expected"]["allowed"])
        self.assertTrue(row["expected"]["atsHostCarveOut"])
        verdict = dnc_guard.evaluate_outreach_target(
            company="JPMorganChase", person_name="Jordan Lee",
            url="https://jpmc.fa.oraclecloud.com/hcmUI", recipient_domain="",
        )
        self.assertTrue(verdict["allowed"])
        self.assertTrue(verdict["atsHostCarveOut"])

    def test_ats_missing_employer_refused(self):
        row = self.rows["ats_missing_employer"]
        self.assertTrue(row["pass"])
        self.assertFalse(row["expected"]["allowed"])
        self.assertEqual(row["expected"]["reason"], "ats_host_missing_employer")
        verdict = dnc_guard.evaluate_outreach_target(
            company="", person_name="Jordan Lee",
            url="https://x.fa.oraclecloud.com/hcmUI", recipient_domain="",
        )
        self.assertFalse(verdict["allowed"])


class TestVendorPitchQuarantine(unittest.TestCase):
    """Dry-run row 6: a vendor pitch hitting no reply keywords is quarantined."""

    @classmethod
    def setUpClass(cls):
        cls.record = pipeline.classify_reply(
            phase2.VENDOR_PITCH_TEXT,
            reply_id="dryrun-vendor-pitch",
            thread_id="dryrun-thread",
            sender_name="Pat Vendor",
            sender_company="VendorCo",
            sender_email="pat@vendorco.example",
            url="",
        )
        cls.brief = pipeline.build_contact_brief(
            cls.record, name="Pat Vendor", company="VendorCo",
            email="pat@vendorco.example", url="",
        )
        cls.card = pipeline.build_gate_d_card(cls.record, cls.brief, sender_stop_file=NO_STOP_FILE)

    def test_vendor_pitch_classified_other_and_quarantined(self):
        self.assertEqual(self.record["reply_class"], "other")
        self.assertEqual(self.record["signals"], ["no_keyword_signal"])
        self.assertEqual(self.brief["next_action"], "manual_review")

    def test_vendor_pitch_never_sends_and_crm_stays_staged(self):
        self.assertFalse(self.card["send_enabled"])
        self.assertTrue(self.card["draft_only"])
        self.assertFalse(self.card["clients_ai_send"])
        self.assertTrue(self.brief["crm"]["staged"])
        self.assertEqual(self.brief["crm"]["operation"], "upsert_contact")
        self.assertFalse(self.brief["write_enabled"])

    def test_matrix_row_quarantine_passes(self):
        row = next(r for r in phase2.run_dry_run_matrix(dnc=FIXTURE_DNC) if r["name"] == "vendor_pitch_quarantined")
        self.assertTrue(row["pass"], row)


class TestTerminalStates(unittest.TestCase):
    """Dry-run row 7: Twenty terminal states are preserved (task_eae7zr9j)."""

    def test_terminal_states_never_mutate(self):
        for state in ("won", "lost", "do_not_contact", "do-not-contact"):
            self.assertEqual(
                phase2.twenty_stage_action(state),
                {"mutate": False, "reason": "terminal_state_preserved"},
                f"terminal state {state!r} must not be mutated",
            )

    def test_non_terminal_stages_write_disabled_upsert(self):
        self.assertEqual(
            phase2.twenty_stage_action("new"),
            {"mutate": True, "operation": "upsert_contact", "staged": True, "write_enabled": False},
        )

    def test_export_carries_preserve_terminal_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = phase2.export_workflow(pathlib.Path(tmp) / "wf.json")
        self.assertEqual(payload["twenty"]["preserve_terminal_states"], ["won", "lost", "do_not_contact"])
        self.assertTrue(phase2.validate_export(payload)["valid"])

    def test_matrix_row_terminal_passes(self):
        row = next(r for r in phase2.run_dry_run_matrix(dnc=FIXTURE_DNC) if r["name"] == "terminal_state_preserved")
        self.assertTrue(row["pass"], row)


class TestNonSendBounds(unittest.TestCase):
    """Every artifact stays draft-only; clients.ai :3211 is a non-send surface."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = pathlib.Path(cls.tmp.name)
        cls.export_payload = phase2.export_workflow(tmp / "nod_twenty_reply_v1.workflow.json")
        cls.moves = phase2.run_move3_sample_bundle(tmp / "gtm_pack_sample")
        cls.report = phase2.write_report(
            phase2.run_dry_run_matrix(dnc=FIXTURE_DNC),
            phase2.sender_lane_state(stop_file_path=NO_STOP_FILE),
            cls.moves,
            dest=tmp / "live_gtm_dryrun_2026-11-16.json",
        )
        cls.files = sorted(p for p in tmp.rglob("*.json"))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_every_artifact_is_non_send(self):
        self.assertEqual(len(self.files), 7)
        for path in self.files:
            payload = json.loads(path.read_text())
            for node in _walk_dicts(payload):
                for key in ("send_enabled", "clients_ai_send", "auto_send", "write_enabled"):
                    if key in node:
                        self.assertIs(node[key], False, f"{path.name}: {key} must be False")

    def test_clients_ai_endpoint_exact_and_never_called(self):
        self.assertEqual(self.export_payload["clients_ai"]["endpoint"], "http://127.0.0.1:3211")
        self.assertIs(self.export_payload["clients_ai"]["send"], False)
        self.assertEqual(
            self.report["gates"]["clients_ai_non_send"],
            {"endpoint": "http://127.0.0.1:3211", "clients_ai_send": False},
        )
        self.assertEqual(self.report["clients_ai_calls"], 0)

    def test_report_counters_are_zero(self):
        self.assertTrue(self.report["dry_run"])
        self.assertEqual(self.report["sends"], 0)
        self.assertEqual(self.report["twenty_writes"], 0)
        self.assertEqual(self.report["clients_ai_calls"], 0)

    def test_blueprint_stays_valid_and_export_verbatim(self):
        verdict = pipeline.validate_blueprint()
        self.assertTrue(verdict["valid"], verdict["errors"])
        blueprint = pipeline.load_blueprint()
        for key in ("nodes", "edges", "deterministic_control_plane", "cited_sources"):
            self.assertEqual(self.export_payload[key], blueprint[key], f"{key} must be blueprint verbatim")

    def test_gate_d_approval_is_human_exact_text(self):
        self.assertEqual(self.export_payload["gate_d"]["channel"], "aside-gate-d")
        self.assertEqual(
            self.export_payload["gate_d"]["approval"],
            {"kind": "exact-text", "approver": "human", "command": "APPROVE SEND <sha12>"},
        )


class TestSenderStopBrake(unittest.TestCase):
    """STOP brake + sha12 guard delegate to dnc_guard.check_sender_lane_ready only."""

    def test_stop_file_blocks_lane(self):
        with tempfile.TemporaryDirectory() as tmp:
            stop = pathlib.Path(tmp) / "STOP"
            stop.write_text("hold\n")
            state = phase2.sender_lane_state(stop_file_path=str(stop))
        self.assertFalse(state["ready"])
        self.assertTrue(state["reason"].startswith("blocked: sender STOP brake active"))
        self.assertFalse(state["auto_send"])

    def test_empty_sha12_blocked(self):
        state = phase2.sender_lane_state(stop_file_path=NO_STOP_FILE)
        self.assertFalse(state["ready"])
        self.assertEqual(state["reason"], "blocked: approved_sha12 must be non-empty and equal template_sha12")

    def test_mismatched_sha12_blocked(self):
        state = phase2.sender_lane_state(
            template_sha12="abc123abc123", approved_sha12="different1234", stop_file_path=NO_STOP_FILE
        )
        self.assertFalse(state["ready"])

    def test_matching_sha12_is_sender_queue_only(self):
        state = phase2.sender_lane_state(
            template_sha12="abc123abc123", approved_sha12="abc123abc123", stop_file_path=NO_STOP_FILE
        )
        self.assertTrue(state["ready"])
        self.assertEqual(state["reason"], "eligible_for_sender_queue_only_never_room_autosend")
        self.assertFalse(state["auto_send"])

    def test_sender_lane_state_asserts_auto_send_false(self):
        with mock.patch.object(
            dnc_guard, "check_sender_lane_ready",
            return_value={"ready": True, "auto_send": True, "reason": "drifted", "log_channel": "jake-owen"},
        ):
            with self.assertRaises(AssertionError):
                phase2.sender_lane_state(stop_file_path=NO_STOP_FILE)


class TestMove3Sample(unittest.TestCase):
    """Move 3 sample bundle: teaser gate, inputs_verified bleed, 5-angle drafts, 5-field tune report."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.tmp.name) / "gtm_pack_sample"
        cls.moves = phase2.run_move3_sample_bundle(cls.out)
        cls.teaser = json.loads((cls.out / "working_teaser.json").read_text())
        cls.bleed = json.loads((cls.out / "bleed_report.json").read_text())
        cls.followups = json.loads((cls.out / "followups.json").read_text())
        cls.tune = json.loads((cls.out / "tune_report.json").read_text())
        cls.manifest = json.loads((cls.out / "manifest.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_five_artifacts_written(self):
        self.assertEqual(
            sorted(p.name for p in self.out.glob("*.json")),
            ["bleed_report.json", "followups.json", "manifest.json", "tune_report.json", "working_teaser.json"],
        )
        self.assertEqual(len(self.moves["files"]), 5)

    def test_working_teaser_gate(self):
        result = self.teaser["result"]
        self.assertTrue(result["ok"])
        self.assertTrue(result["blocked_by"]["atsHostCarveOut"], "sample must ride the ATS carve-out")
        self.assertTrue(self.teaser["touch1_link_free_guard"]["link_free"])
        self.assertTrue(pack.touch1_link_free_guard(result["draft"]["body"])["link_free"])
        self.assertEqual(self.teaser["gate_d"], pack.GATE_D)

    def test_bleed_inputs_verified_and_arithmetic(self):
        self.assertIs(self.bleed["inputs_verified"], True)
        self.assertEqual(self.bleed["inputs"], phase2.BLEED_INPUTS)
        result = self.bleed["result"]
        inputs = phase2.BLEED_INPUTS
        time_bleed = inputs["hours_per_week"] * inputs["loaded_hourly_rate"] * 52
        error_bleed = inputs["errors_per_week"] * inputs["cost_per_error"] * 52
        lead_bleed = inputs["lost_leads_per_week"] * inputs["value_per_lead"] * 52
        self.assertEqual(result["annual_time_bleed"], round(time_bleed, 2))
        self.assertEqual(result["annual_error_bleed"], round(error_bleed, 2))
        self.assertEqual(result["annual_lead_loss_bleed"], round(lead_bleed, 2))
        self.assertEqual(result["annual_total_bleed"], round(time_bleed + error_bleed + lead_bleed, 2))

    def test_followups_five_distinct_angles_with_opt_out(self):
        touches = self.followups["touches"]
        self.assertEqual(len(touches), 5)
        self.assertEqual({t["angle"] for t in touches}, set(pack.TOUCH_ANGLES))
        self.assertEqual([t["day_offset"] for t in touches], list(pack.TOUCH_DAY_OFFSETS))
        opt_out = "If this isn't relevant, reply STOP and I won't follow up."
        self.assertEqual(self.followups["opt_out_line"], opt_out)
        for touch in touches:
            self.assertEqual(touch["opt_out_line"], opt_out)
            self.assertEqual(touch["draft_text"], f"{touch['text']} {opt_out}")
        self.assertTrue(touches[0]["link_free"], "touch 1 must be link-free")
        # module text stays untouched by the wrapper
        module_touches = self.followups["result"]["touches"]
        self.assertEqual([t["text"] for t in module_touches], [t["text"] for t in touches])
        self.assertTrue(all("opt_out_line" not in t for t in module_touches))

    def test_tune_report_five_fields(self):
        result = self.tune["result"]
        self.assertTrue(result["ok"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["field_count"], 5)
        fields = result["slide"]["fields"]
        self.assertEqual(
            set(fields),
            {"what_delivered", "metric", "dollar_value", "paid_versus_received", "expansion_suggestion"},
        )
        self.assertIn(fields["metric"]["type"], pack.PURCHASE_METRICS)
        self.assertGreater(fields["paid_versus_received"]["paid"], 0)

    def test_manifest_citations_verbatim(self):
        context = json.loads(
            (REPO_ROOT / "src" / "robonuggets_ops" / "move3_gtm_teaser_tune" / "context.json").read_text()
        )
        self.assertEqual(self.manifest["cited_sources"], context["cited_sources"])
        self.assertTrue(all(s.startswith("src: ") for s in self.manifest["cited_sources"]))
        self.assertEqual(len(self.manifest["artifacts"]), 5)


class TestNoNetworkNoWrites(unittest.TestCase):
    """The dry-run pack performs no network I/O and writes only where directed."""

    def test_script_source_imports_no_network_stack(self):
        source = (REPO_ROOT / "scripts" / "run_live_gtm_phase2.py").read_text()
        for banned in ("import socket", "import urllib", "urllib.request", "http.client", "import requests", "import httpx"):
            self.assertNotIn(banned, source)

    def test_writers_run_with_socket_blocked_and_stay_in_tmp(self):
        def _no_network(*args, **kwargs):
            raise AssertionError("network access attempted")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            with mock.patch.object(socket, "socket", _no_network), mock.patch.object(
                socket, "create_connection", _no_network
            ):
                phase2.export_workflow(tmp_path / "nod_twenty_reply_v1.workflow.json")
                phase2.run_move3_sample_bundle(tmp_path / "gtm_pack_sample")
                phase2.write_report(
                    phase2.run_dry_run_matrix(dnc=FIXTURE_DNC),
                    phase2.sender_lane_state(stop_file_path=NO_STOP_FILE),
                    {"files": [], "cited_sources": []},
                    dest=tmp_path / "live_gtm_dryrun_2026-11-16.json",
                )
            written = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*") if p.is_file())
            self.assertEqual(
                written,
                [
                    "gtm_pack_sample/bleed_report.json",
                    "gtm_pack_sample/followups.json",
                    "gtm_pack_sample/manifest.json",
                    "gtm_pack_sample/tune_report.json",
                    "gtm_pack_sample/working_teaser.json",
                    "live_gtm_dryrun_2026-11-16.json",
                    "nod_twenty_reply_v1.workflow.json",
                ],
            )

    def test_do_not_contact_file_opened_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            rule = pathlib.Path(tmp) / "do-not-contact.json"
            rule.write_text(json.dumps(FIXTURE_DNC))
            modes = []
            real_open = builtins.open

            def _recording_open(file, mode="r", *args, **kwargs):
                modes.append(mode)
                return real_open(file, mode, *args, **kwargs)

            with mock.patch.object(builtins, "open", _recording_open):
                loaded = phase2.load_do_not_contact(str(rule))
        self.assertEqual(loaded["people"], FIXTURE_DNC["people"])
        self.assertTrue(modes, "load_do_not_contact must open the file")
        self.assertTrue(all(m == "r" for m in modes), f"rule file must be opened read-only, saw modes {modes}")

    def test_matrix_rows_are_pure_data(self):
        rows = phase2.run_dry_run_matrix(dnc=FIXTURE_DNC)
        self.assertEqual(len(rows), 7)
        for row in rows:
            self.assertEqual(set(row), {"name", "input", "expected", "actual", "pass"})
            json.dumps(row)  # JSON-serializable, no live handles


class TestPlantedFailures(unittest.TestCase):
    """Each new gate must go RED on a known-bad mutation and GREEN on the shipped artifact."""

    def test_mattcolmia_person_check_is_load_bearing(self):
        # RED without the person check: blank company leaves no other block.
        with mock.patch.object(dnc_guard, "BLOCKED_PEOPLE", ()):
            mutated = {r["name"]: r for r in phase2.run_dry_run_matrix(dnc=FIXTURE_DNC)}
        red_row = mutated["mattcolmia_blank_company"]
        self.assertFalse(red_row["pass"], "the matrix must go red when the person check is removed")
        self.assertTrue(red_row["actual"]["allowed"], "without the person check the blocked person slips through")
        # GREEN with the shipped person check.
        shipped = {r["name"]: r for r in phase2.run_dry_run_matrix(dnc=FIXTURE_DNC)}
        self.assertTrue(shipped["mattcolmia_blank_company"]["pass"])

    def test_export_dropping_preserve_terminal_states_goes_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = phase2.export_workflow(pathlib.Path(tmp) / "wf.json")
        self.assertTrue(phase2.validate_export(payload)["valid"])
        # RED: a copied export that drops preserve_terminal_states must fail.
        mutated = copy.deepcopy(payload)
        mutated["twenty"].pop("preserve_terminal_states")
        verdict = phase2.validate_export(mutated)
        self.assertFalse(verdict["valid"])
        self.assertTrue(
            any("preserve_terminal_states" in error for error in verdict["errors"]),
            verdict["errors"],
        )


if __name__ == "__main__":
    unittest.main()
