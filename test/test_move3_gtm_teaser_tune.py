import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))
from robonuggets_ops.move3_gtm_teaser_tune.pack import (
    RETAINER_TIERS,
    annual_bleed,
    build_tune_report,
    check_kickoff_contract,
    generate_followup_sequence,
    generate_working_teaser,
    retainer_tiers,
    touch1_link_free_guard,
)


class TestWorkingTeaser(unittest.TestCase):
    def test_teaser_is_five_sentence_permission_ask_and_link_free(self):
        res = generate_working_teaser(
            company="Acme",
            finding="your intake form loses every third submission",
            evidence="three of nine test submissions never reached the CRM",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["stage"], "pre_touch_1")
        self.assertLessEqual(len(res["draft"]["sentences"]), 5)
        self.assertIn("Mind if I send", res["draft"]["body"])
        self.assertTrue(touch1_link_free_guard(res["draft"]["body"])["link_free"])

    def test_blocked_targets_produce_no_draft(self):
        oracle = generate_working_teaser(company="Oracle", finding="x")
        self.assertFalse(oracle["ok"])
        self.assertIsNone(oracle["draft"])
        self.assertFalse(oracle["blocked_by"]["allowed"])
        colmia = generate_working_teaser(
            company="Acme", finding="x", contact_name="Matt Colmia"
        )
        self.assertFalse(colmia["ok"])
        self.assertIsNone(colmia["draft"])

    def test_ats_host_carve_out_with_company_still_produces_draft(self):
        res = generate_working_teaser(
            company="JPMorganChase",
            finding="your ATS handoff drops candidates",
            url="https://jpmc.fa.oraclecloud.com/hcmUI",
        )
        self.assertTrue(res["ok"])
        self.assertTrue(res["blocked_by"]["atsHostCarveOut"])

    def test_missing_finding_refused(self):
        self.assertFalse(generate_working_teaser(company="Acme", finding="  ")["ok"])


class TestTouch1LinkFreeGuard(unittest.TestCase):
    def test_catches_urls_and_bare_domains(self):
        self.assertFalse(touch1_link_free_guard("see https://acme.com/report")["link_free"])
        self.assertFalse(touch1_link_free_guard("go to www.acme.com now")["link_free"])
        self.assertFalse(touch1_link_free_guard("full deck at acme.io/deck")["link_free"])

    def test_plain_text_passes(self):
        self.assertTrue(touch1_link_free_guard("Mind if I send what I found over?")["link_free"])


class TestFollowupSequence(unittest.TestCase):
    def test_five_touches_spaced_with_distinct_angles(self):
        res = generate_followup_sequence(company="Acme", finding="the sync job retries forever")
        self.assertTrue(res["ok"])
        touches = res["touches"]
        self.assertEqual(len(touches), 5)
        offsets = [t["day_offset"] for t in touches]
        self.assertEqual(offsets, sorted(offsets))
        self.assertEqual(len({t["angle"] for t in touches}), 5)
        self.assertTrue(all(t["link_free"] for t in touches))
        self.assertTrue(all(t["gate_d"].startswith("draft_only") for t in touches))

    def test_touch_1_is_link_free(self):
        res = generate_followup_sequence(company="Acme", finding="the sync job retries forever")
        guard = touch1_link_free_guard(res["touches"][0]["text"])
        self.assertTrue(guard["link_free"])

    def test_bad_angle_sets_and_offsets_refused(self):
        dup = generate_followup_sequence(
            company="Acme",
            finding="x",
            angles=("finding", "finding", "proof", "insight", "permission_close"),
        )
        self.assertFalse(dup["ok"])
        self.assertEqual(dup["reason"], "angles_must_be_5_distinct")
        flat = generate_followup_sequence(
            company="Acme",
            finding="x",
            day_offsets=(0, 3, 3, 12, 18),
        )
        self.assertFalse(flat["ok"])
        self.assertEqual(flat["reason"], "day_offsets_must_be_5_strictly_increasing")

    def test_blocked_target_produces_no_sequence(self):
        res = generate_followup_sequence(company="Oracle Health", finding="x")
        self.assertFalse(res["ok"])
        self.assertEqual(res["touches"], [])


class TestAnnualBleed(unittest.TestCase):
    def test_bleed_math_exact(self):
        bleed = annual_bleed(
            hours_per_week=10,
            loaded_hourly_rate=100,
            errors_per_week=2,
            cost_per_error=50,
            lost_leads_per_week=1,
            value_per_lead=2000,
        )
        self.assertEqual(bleed["annual_time_bleed"], 52000.0)
        self.assertEqual(bleed["annual_error_bleed"], 5200.0)
        self.assertEqual(bleed["annual_lead_loss_bleed"], 104000.0)
        self.assertEqual(bleed["annual_total_bleed"], 161200.0)

    def test_rejects_bad_numbers(self):
        with self.assertRaises(ValueError):
            annual_bleed(hours_per_week=-1, loaded_hourly_rate=100)
        with self.assertRaises(TypeError):
            annual_bleed(hours_per_week="10", loaded_hourly_rate=100)


class TestKickoffContract(unittest.TestCase):
    GOOD = "DFY — we keep running it\nScope: intake automation\nHypercare follows go-live."

    def test_good_contract_locks_model_on_line_1(self):
        res = check_kickoff_contract(
            kickoff_text=self.GOOD,
            hypercare_start="2026-12-01",
            hypercare_end="2026-12-22",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["integration_model"], "DFY")
        self.assertEqual(res["hypercare_days"], 21)

    def test_model_not_on_line_1_fails(self):
        res = check_kickoff_contract(
            kickoff_text="Scope: intake automation\nIntegration model: DFY",
            hypercare_start="2026-12-01",
            hypercare_end="2026-12-22",
        )
        self.assertFalse(res["ok"])
        self.assertIn("integration_model_not_locked_on_line_1", res["errors"])

    def test_hypercare_window_bounds(self):
        for start, end, ok in (
            ("2026-12-01", "2026-12-15", True),  # 14 days: 2 weeks floor
            ("2026-12-01", "2026-12-29", True),  # 28 days: 4 weeks ceiling
            ("2026-12-01", "2026-12-08", False),  # 1 week: too short
            ("2026-12-01", "2027-01-05", False),  # 5 weeks: too long
        ):
            res = check_kickoff_contract(
                kickoff_text="install_into_stack — installed into their stack",
                hypercare_start=start,
                hypercare_end=end,
            )
            self.assertEqual(res["ok"], ok, (start, end, res["errors"]))

    def test_missing_dates_fail(self):
        res = check_kickoff_contract(
            kickoff_text="build_operate_transfer — run then hand over",
            hypercare_start="",
            hypercare_end="2026-12-22",
        )
        self.assertFalse(res["ok"])
        self.assertIn("hypercare_start_missing_or_unparseable", res["errors"])


class TestTuneReport(unittest.TestCase):
    def test_five_field_dollarized_slide(self):
        res = build_tune_report(
            what_shipped="intake triage agent live in production",
            purchase_metric="hours_returned",
            metric_value=12,
            dollar_value=3600,
            paid=5000,
            received=10000,
            expansion_suggestion="extend triage to the support inbox",
        )
        self.assertTrue(res["ok"])
        self.assertEqual(res["field_count"], 5)
        self.assertEqual(len(res["slide"]["fields"]), 5)
        self.assertEqual(res["slide"]["fields"]["paid_versus_received"]["roi"], 2.0)

    def test_metric_must_match_the_purchase(self):
        res = build_tune_report(
            what_shipped="x",
            purchase_metric="impressions",
            metric_value=1,
            dollar_value=1,
            paid=1,
            received=1,
            expansion_suggestion="y",
        )
        self.assertFalse(res["ok"])
        self.assertIn("purchase_metric_must_match_what_they_bought", res["errors"])

    def test_blank_dollar_and_expansion_refused(self):
        res = build_tune_report(
            what_shipped="x",
            purchase_metric="money_moved",
            metric_value=1,
            dollar_value=0,
            paid=1,
            received=1,
            expansion_suggestion=" ",
        )
        self.assertFalse(res["ok"])
        self.assertIn("one_expansion_suggestion_required", res["errors"])


class TestRetainerTiers(unittest.TestCase):
    def test_three_recurring_tiers_tied_to_observed_gap(self):
        res = retainer_tiers(something_shipped=True, observed_gap="no monitoring on the retry queue")
        self.assertTrue(res["ok"])
        self.assertEqual([t["id"] for t in res["tiers"]], list(RETAINER_TIERS))
        self.assertTrue(all(t["cadence"] == "recurring" for t in res["tiers"]))
        self.assertTrue(all(t["tied_to_gap"] == "no monitoring on the retry queue" for t in res["tiers"]))

    def test_never_pitch_before_shipping(self):
        res = retainer_tiers(something_shipped=False, observed_gap="x")
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "never_pitch_tiers_before_something_shipped")

    def test_gap_required(self):
        res = retainer_tiers(something_shipped=True, observed_gap="")
        self.assertFalse(res["ok"])
        self.assertEqual(res["reason"], "each_tier_must_tie_to_an_observed_gap")


if __name__ == "__main__":
    unittest.main()
