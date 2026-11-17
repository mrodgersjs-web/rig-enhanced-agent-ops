"""Phase 2 live wiring tests: mapper contract, thin bridge bundle, read-only sweep.

Unit tests run against a tiny fixture DB and a temp doctrine dir. The live
integration block (skipped when the real Autark DB is absent) proves the sweep
writes both reports, scores exactly the active schedules, leaves workforce.db
byte-identical (size + mtime_ns), and emits six thin, lint-clean bridges.
"""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sqlite3
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from robonuggets_ops.move1_arms_audit import auditor  # noqa: E402
from robonuggets_ops.move4_harness_bridges import bridges  # noqa: E402
from robonuggets_ops.phase2_live_wiring import live_wiring  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "run_live_product_phase2", REPO_ROOT / "scripts" / "run_live_product_phase2.py"
)
phase2_cli = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(phase2_cli)

CTX_PATH = REPO_ROOT / "src" / "robonuggets_ops" / "phase2_live_wiring" / "context.json"
SPEC_PATH = REPO_ROOT / "spec" / "ROBONUGGETS-6TOOL-SPEC.md"
REPORT_PATH = REPO_ROOT / "reports" / "live_arms_audit_2026-11-16.json"
SUMMARY_PATH = REPO_ROOT / "reports" / "live_arms_summary.md"
BRIDGES_DIR = REPO_ROOT / "dist" / "harness_bridges"

LIVE_DB = live_wiring.DEFAULT_DB
LIVE_DOCTRINE = pathlib.Path(live_wiring.DEFAULT_DOCTRINE_DIR)


def _row(**overrides) -> dict:
    row = {
        "id": "sch-1",
        "owner_id": "ag-1",
        "conversation_id": "ch-1",
        "task_id": "task-1",
        "kind": "routine",
        "title": "Morning sweep",
        "spec": {"cron": "0 6 * * *", "tz": "America/Denver"},
        "payload": {
            "taskTemplate": {
                "title": "Morning sweep",
                "notes": (
                    "Run: sweep.sh\n"
                    "read the ledger and log the digest to reports/sweep.md\n"
                    "gate-d approval routed through JEV"
                ),
            }
        },
    }
    row.update(overrides)
    return row


def _make_fixture_db(path: str) -> None:
    con = sqlite3.connect(path)
    con.executescript(
        """
        CREATE TABLE schedules (id TEXT, owner_id TEXT, conversation_id TEXT, task_id TEXT,
                                kind TEXT, title TEXT, spec TEXT, payload TEXT,
                                created_at TEXT, active INTEGER);
        CREATE TABLE agents (id TEXT, model_policy TEXT);
        CREATE TABLE runs (id TEXT, agent_id TEXT, task_id TEXT, model TEXT, started_at TEXT);
        CREATE TABLE feedback (id TEXT, context TEXT, status TEXT);
        INSERT INTO agents VALUES ('ag-1', '{"pin": "m-pin", "costMode": "cap"}');
        INSERT INTO runs VALUES ('run-2', 'ag-1', 'task-1', 'm-fallback', '2026-11-16T06:05:00Z');
        INSERT INTO runs VALUES ('run-1', 'ag-1', 'task-1', 'm-fallback', '2026-11-15T06:05:00Z');
        INSERT INTO feedback VALUES ('fb-1', 'sch-1 review', 'applied');
        """
    )
    con.execute(
        "INSERT INTO schedules VALUES ('sch-1', 'ag-1', 'ch-1', 'task-1', 'routine', 'Morning sweep', ?, ?, '2026-11-01T00:00:00Z', 1)",
        (json.dumps(_row()["spec"]), json.dumps(_row()["payload"])),
    )
    con.execute(
        "INSERT INTO schedules VALUES ('sch-2', 'ag-1', NULL, NULL, 'reminder', 'Noon note', ?, ?, '2026-11-02T00:00:00Z', 1)",
        (
            json.dumps({"everyMs": 3600000, "tz": "America/Denver"}),
            json.dumps({"note": "read the ledger and write the digest"}),
        ),
    )
    con.execute(
        "INSERT INTO schedules VALUES ('sch-3', 'ag-1', NULL, NULL, 'routine', 'Inactive', ?, ?, '2026-11-03T00:00:00Z', 0)",
        (json.dumps({"cron": "0 7 * * *"}), json.dumps({"taskTemplate": {"notes": "Run: x"}})),
    )
    con.commit()
    con.close()


def _make_doctrine_dir(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "attention.md").write_text("# Attention\n\nDuty: attention.\n", encoding="utf-8")
    (path / "no-oracle.md").write_text("# No Oracle\n\nRule: no-oracle.\n", encoding="utf-8")
    (path / "gate-d.md").write_text("# Gate-D\n\nRule: gate-d draft only.\n", encoding="utf-8")
    (path / "jev-before-done.md").write_text("# Jev\n\nRule: jev-before-done.\n", encoding="utf-8")


class TestScheduleRowToRoutines(unittest.TestCase):
    """Pure mapper contract: fields, slot mapping, schedule kind, pre-arm evidence."""

    def test_happy_path_maps_every_routine_field(self):
        routine = live_wiring.schedule_row_to_routine(_row(), ["run-2", "run-1"], "m-pin", "m-fallback")
        self.assertEqual(routine["id"], "sch-1")
        self.assertEqual(routine["name"], "Morning sweep")
        self.assertEqual(routine["actions"], ["sweep.sh"])
        self.assertEqual(routine["action_receipts"], ["run-2", "run-1"])
        self.assertEqual(routine["model"], "m-pin")
        self.assertEqual(routine["model_fallback"], "m-fallback")
        self.assertTrue(routine["recall_writes"])  # "Log ... to ..." scans as a write verb
        self.assertTrue(routine["deliverables"])
        self.assertIn("reports/sweep.md", routine["deliverables"])
        self.assertEqual(routine["gate_d_actions"], [])
        self.assertEqual(routine["schedule"], {"kind": "cron"})
        self.assertEqual(routine["slot"], "morning")

    def test_slot_mapping_window_hours(self):
        spec = {"window": {"from": "06:00", "to": "21:00"}}
        self.assertEqual(live_wiring.schedule_row_to_routine(_row(spec=spec), [], None, None)["slot"], "morning")
        spec = {"window": {"from": "12:00", "to": "21:00"}}
        self.assertEqual(live_wiring.schedule_row_to_routine(_row(spec=spec), [], None, None)["slot"], "midday")
        spec = {"window": {"from": "18:00", "to": "23:00"}}
        self.assertEqual(live_wiring.schedule_row_to_routine(_row(spec=spec), [], None, None)["slot"], "evening")
        self.assertEqual(live_wiring.schedule_row_to_routine(_row(spec={}), [], None, None)["slot"], "morning")
        self.assertEqual(
            live_wiring.schedule_row_to_routine(_row(spec={"window": {"from": "garbage"}}), [], None, None)["slot"],
            "morning",
        )

    def test_schedule_kind_detection(self):
        self.assertEqual(live_wiring.schedule_row_to_routine(_row(), [], None, None)["schedule"]["kind"], "cron")
        row = _row(spec={"everyMs": 900000})
        self.assertEqual(live_wiring.schedule_row_to_routine(row, [], None, None)["schedule"]["kind"], "rrule")
        row = _row(spec={"times": ["09:00"]})
        self.assertEqual(live_wiring.schedule_row_to_routine(row, [], None, None)["schedule"]["kind"], "manual")

    def test_pre_arm_evidence_lands_on_the_schedule_block(self):
        evidence = {
            "manual_dry_runs_passed": 1,
            "idempotent_writes": True,
            "max_retries": 3,
            "token_ceiling": 4000,
            "watched_failure_channel": "#failures",
        }
        row = _row(payload={"scheduleEvidence": evidence, "taskTemplate": {"notes": "Run: x"}})
        routine = live_wiring.schedule_row_to_routine(row, [], None, None)
        verdict = auditor.validate_schedule(routine)
        self.assertTrue(verdict["allowed"])
        self.assertEqual(verdict["kind"], "cron")

    def test_missing_pre_arm_evidence_blocks_cron_and_rrule(self):
        # Planted-failure check: the known-bad schedule (no scheduleEvidence) must go RED.
        for spec in ({"cron": "0 6 * * *"}, {"everyMs": 3600000}):
            routine = live_wiring.schedule_row_to_routine(_row(spec=spec), [], None, None)
            verdict = auditor.validate_schedule(routine)
            self.assertFalse(verdict["allowed"])
            self.assertTrue(any("manual_dry_runs_passed" in item for item in verdict["violations"]))
        # A manual schedule needs no pre-arm evidence.
        routine = live_wiring.schedule_row_to_routine(_row(spec={"times": ["09:00"]}), [], None, None)
        self.assertTrue(auditor.validate_schedule(routine)["allowed"])

    def test_gate_d_and_jev_keywords_scan_the_payload_corpus(self):
        row = _row(payload={"taskTemplate": {"notes": "Run: x"}, "note": "needs gate-d approval, route done to JEV"})
        routine = live_wiring.schedule_row_to_routine(row, [], None, None)
        self.assertTrue(routine["gate_d"])
        self.assertTrue(routine["jev"])

    def test_cli_module_reexports_the_documented_interfaces(self):
        self.assertIs(phase2_cli.schedule_row_to_routine, live_wiring.schedule_row_to_routine)
        self.assertIs(phase2_cli.main, live_wiring.main)


class TestRenderBridgeMd(unittest.TestCase):
    """The generated bridge file is thin: role, rule pointers, exactly 3 invariants."""

    def test_bridge_md_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            doctrine = pathlib.Path(tmp) / "doctrine"
            _make_doctrine_dir(doctrine)
            bridge = bridges.generate_bridge("aside", doctrine)
            md = bridges.render_bridge_md(bridge)
            self.assertIn("# aside harness bridge", md)
            self.assertIn("Role: operator console and logged-in browser lane", md)
            self.assertIn("attention.md", md)
            for name in ("no_oracle", "gate_d_draft_only", "jev_before_done"):
                self.assertIn(name, md)
            # exactly three enumerated invariants
            for index in ("1.", "2.", "3."):
                self.assertIn(index, md)
            self.assertNotIn("4.", md)
            self.assertIn('"ats_host_carve_out": true', md)
            self.assertIn('"mode": "draft_only"', md)
            self.assertIn('"route_on_done": "JEV"', md)

    def test_bridge_md_never_duplicates_doctrine_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            doctrine = pathlib.Path(tmp) / "doctrine"
            _make_doctrine_dir(doctrine)
            long_line = "Z" * 120
            (doctrine / "attention.md").write_text(f"# Attention\n\n{long_line}\n", encoding="utf-8")
            bridge = bridges.generate_bridge("aside", doctrine)
            self.assertNotIn(long_line, bridges.render_bridge_md(bridge))


class TestRunArmsOnFixtureDb(unittest.TestCase):
    """Sweep against a tiny fixture DB: both reports written, db untouched."""

    def test_reports_written_and_fixture_db_unmutated(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            db_path = tmp_path / "workforce.db"
            _make_fixture_db(str(db_path))
            out_dir = tmp_path / "reports"
            before = (db_path.stat().st_size, db_path.stat().st_mtime_ns)

            result = live_wiring.run_arms(str(db_path), str(out_dir), "2026-11-16")
            report_path = out_dir / "live_arms_audit_2026-11-16.json"
            summary_path = out_dir / "live_arms_summary.md"
            self.assertEqual(result["written"], [str(report_path), str(summary_path)])

            report = json.loads(report_path.read_text())
            self.assertEqual(report["metadata"]["mode"], "ro")
            self.assertEqual(report["metadata"]["active_count"], 2)
            self.assertEqual(len(report["routines"]), 2)
            for key in ("routines", "blocked_armings", "consolidation"):
                self.assertIn(key, report)
            by_id = {entry["id"]: entry for entry in report["routines"]}
            self.assertEqual(by_id["sch-1"]["arms"]["total"], 10)
            self.assertIn("sch-1", report["blocked_armings"])  # cron without pre-arm evidence
            self.assertNotIn("sch-3", by_id)  # inactive schedule is never scored

            summary = summary_path.read_text()
            self.assertIn("EXPECTED FINDING", summary)
            self.assertIn("sch-1", summary)
            self.assertIn("mode=ro", summary)

            after = (db_path.stat().st_size, db_path.stat().st_mtime_ns)
            self.assertEqual(before, after, "read-only sweep must not mutate the database")

    def test_summary_reports_the_expected_finding(self):
        report = {
            "metadata": {"db_path": "x", "mode": "ro", "active_count": 0, "generated_at": "t", "date": "d"},
            "routines": [],
            "blocked_armings": [],
            "consolidation": {"slots": {s: {"routines": [], "inbox": []} for s in auditor.SLOTS}, "gate_d_yes_queue": []},
        }
        summary = live_wiring.render_summary(report)
        self.assertIn("EXPECTED FINDING", summary)
        self.assertIn("0 = sweep completed", summary)


class TestRepoArtifactsPresent(unittest.TestCase):
    """The Phase 2 deliverables are checked on disk, like the repo-hygiene tests."""

    def test_spec_script_and_reports_exist(self):
        self.assertTrue(SPEC_PATH.is_file())
        self.assertTrue((REPO_ROOT / "scripts" / "run_live_product_phase2.py").is_file())
        report = json.loads(REPORT_PATH.read_text())
        for key in ("routines", "blocked_armings", "consolidation"):
            self.assertIn(key, report)
        self.assertEqual(report["metadata"]["mode"], "ro")
        self.assertGreater(report["metadata"]["active_count"], 0)
        self.assertIn("EXPECTED FINDING", SUMMARY_PATH.read_text())

    def test_repo_bridge_bundle_has_exactly_six_thin_files(self):
        names = sorted(p.name for p in BRIDGES_DIR.glob("*.md"))
        self.assertEqual(names, sorted(f"{tool}.md" for tool in bridges.TOOLS))
        for tool in bridges.TOOLS:
            text = (BRIDGES_DIR / f"{tool}.md").read_text()
            self.assertIn(f"# {tool} harness bridge", text)
            self.assertIn("## lint_bridge verdict", text)

    def test_context_json_cited_sources_valid(self):
        payload = json.loads(CTX_PATH.read_text())
        for key in ("move", "status", "deliverables", "citations", "gates", "jev", "cited_sources"):
            self.assertIn(key, payload)
        self.assertTrue(payload["citations"])
        for source in payload["cited_sources"]:
            self.assertTrue(source["id"].startswith("src: classroom/"))
            self.assertTrue(source["supports"])


@unittest.skipUnless(os.path.exists(LIVE_DB), "Autark workforce.db not present on this machine")
class TestPhase2LiveWiringIntegration(unittest.TestCase):
    """Sweep the real live database READ-ONLY into a temp out dir."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_path = pathlib.Path(cls._tmp.name)
        cls.out_dir = tmp_path / "reports"
        cls.bridges_dir = tmp_path / "harness_bridges"
        cls.db_stat_before = (os.stat(LIVE_DB).st_size, os.stat(LIVE_DB).st_mtime_ns)
        cls.exit_code = live_wiring.main(
            ["--db", LIVE_DB, "--out-dir", str(cls.out_dir), "--bridges-dir", str(cls.bridges_dir)]
        )
        cls.report = json.loads((cls.out_dir / "live_arms_audit_2026-11-16.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_sweep_writes_both_reports(self):
        self.assertEqual(self.exit_code, 0)
        self.assertTrue((self.out_dir / "live_arms_audit_2026-11-16.json").is_file())
        self.assertTrue((self.out_dir / "live_arms_summary.md").is_file())
        for key in ("routines", "blocked_armings", "consolidation"):
            self.assertIn(key, self.report)
        self.assertEqual(self.report["metadata"]["mode"], "ro")

    def test_every_active_schedule_is_scored(self):
        con = sqlite3.connect(f"file:{LIVE_DB}?mode=ro", uri=True)
        con.execute("PRAGMA query_only=1")
        active_count = con.execute("SELECT COUNT(*) FROM schedules WHERE active = 1").fetchone()[0]
        con.close()
        self.assertEqual(self.report["metadata"]["active_count"], active_count)
        self.assertEqual(len(self.report["routines"]), active_count)

    def test_zero_mutation_of_live_workforce_db(self):
        after = (os.stat(LIVE_DB).st_size, os.stat(LIVE_DB).st_mtime_ns)
        self.assertEqual(self.db_stat_before, after, "sweep must not mutate workforce.db")

    def test_summary_states_the_expected_finding(self):
        summary = (self.out_dir / "live_arms_summary.md").read_text()
        self.assertIn("EXPECTED FINDING", summary)
        self.assertIn("blocked_armings", summary)

    @unittest.skipUnless(LIVE_DOCTRINE.is_dir(), "canonical doctrine dir not present")
    def test_bridge_bundle_is_thin_and_cited(self):
        names = sorted(p.name for p in self.bridges_dir.glob("*.md"))
        self.assertEqual(names, sorted(f"{tool}.md" for tool in bridges.TOOLS))
        for tool in bridges.TOOLS:
            text = (self.bridges_dir / f"{tool}.md").read_text()
            lint = json.loads(text.split("```json\n", 1)[1].rsplit("\n```", 1)[0])
            self.assertTrue(lint["ok"], f"{tool} lint violations: {lint['violations']}")
            self.assertEqual(lint["violations"], [])
            # every cited rule ref must be an existing doctrine file
            refs = [
                line for line in text.splitlines()
                if line.startswith("- ") and " — " in line and line.endswith(".md")
            ]
            self.assertTrue(refs, f"{tool} bridge cites no doctrine files")
            for line in refs:
                target = pathlib.Path(line.rsplit(" — ", 1)[1])
                self.assertTrue(target.is_file(), f"{tool} cites missing doctrine file {target}")


if __name__ == "__main__":
    unittest.main()
