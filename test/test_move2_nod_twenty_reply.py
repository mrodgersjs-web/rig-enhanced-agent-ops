"""Tests for Move 2: schema-locked reply classifier, Twenty CRM brief, Gate-D card, trigger scorer.

Each new gate carries a planted-failure check: a known-bad variant must make the
validator/gate go red before the shipped artifact is trusted.
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from robonuggets_ops.move2_nod_twenty_reply.pipeline import (
    CLIENTS_AI_ENDPOINT,
    CONTACT_BRIEF_KEYS,
    GATE_D_CARD_KEYS,
    REPLY_CLASSES,
    REPLY_RECORD_KEYS,
    SCHEMA_VERSION,
    TRIGGER_SCORE_KEYS,
    build_contact_brief,
    build_gate_d_card,
    classify_reply,
    load_blueprint,
    score_trigger_event,
    validate_blueprint,
    validate_contact_brief,
    validate_gate_d_card,
    validate_reply_record,
    validate_trigger_score,
)

# A STOP-brake path that cannot exist on this machine: sender-lane posture in
# tests must not depend on the real ~/rig-gtm-home/gmail-sender/STOP file.
NO_STOP_FILE = "/nonexistent/rig-stop-brake-does-not-exist"

UCSF_URL = "https://ucsf.fa.us2.oraclecloud.com/hcmUI"
JPMC_URL = "https://jpmc.fa.oraclecloud.com/hcmUI"
COHERENT_URL = "https://coherent.fa.oraclecloud.com/jobs"


def _allowed_reply_record():
    return classify_reply(
        "Interested — tell me more about pricing.",
        reply_id="r-1",
        thread_id="t-1",
        sender_name="Pat Doe",
        sender_company="UCSF",
        sender_email="pat@ucsf.edu",
        url=UCSF_URL,
    )


class TestDncEnforcement(unittest.TestCase):
    """Deliverable 3: evaluate_outreach_target on every lead/reply path."""

    def test_blocked_employer_oracle_health_on_reply(self):
        record = classify_reply(
            "Tell me more.",
            sender_name="Sue",
            sender_company="Oracle Health",
            sender_email="sue@oraclehealth.com",
        )
        self.assertFalse(record["allowed"])
        self.assertEqual(record["reply_class"], "blocked")
        self.assertIn("blocked_employer", record["dnc"]["reason"])

    def test_blocked_employer_cerner_on_reply(self):
        record = classify_reply("Hi.", sender_company="Cerner")
        self.assertFalse(record["allowed"])
        self.assertIn("blocked_employer", record["dnc"]["reason"])

    def test_blocked_person_matt_colmia_blank_company(self):
        record = classify_reply("Hi.", sender_name="Matt Colmia", sender_company="")
        self.assertFalse(record["allowed"])
        self.assertEqual(record["reply_class"], "blocked")
        self.assertIn("blocked_person", record["dnc"]["reason"])

    def test_blocked_domain_oracle_com_on_reply(self):
        record = classify_reply("Hi.", sender_name="Ann", sender_email="ann@oracle.com")
        self.assertFalse(record["allowed"])
        self.assertIn("blocked_domain", record["dnc"]["reason"])

    def test_blocked_person_smuggled_into_brief(self):
        record = _allowed_reply_record()
        brief = build_contact_brief(record, name="Matt Colmia", company="", email="")
        self.assertFalse(brief["dnc"]["allowed"])
        self.assertEqual(brief["intent"], "blocked")
        self.assertEqual(brief["next_action"], "drop_contact")
        self.assertFalse(brief["write_enabled"])

    def test_blocked_record_yields_blocked_gate_d_card(self):
        record = classify_reply("Hi.", sender_name="Matt Colmia", sender_company="")
        brief = build_contact_brief(record, name="Matt Colmia", company="", email="")
        card = build_gate_d_card(record, brief, sender_stop_file=NO_STOP_FILE)
        self.assertEqual(card["stage"], "blocked")
        self.assertFalse(card["send_enabled"])
        self.assertFalse(card["clients_ai_send"])
        self.assertEqual(card["draft"]["body"], "")
        self.assertTrue(card["approval"]["exact_text"].startswith("BLOCKED_BY_DNC"))

    def test_blocked_lead_scores_zero(self):
        scored = score_trigger_event({
            "event_type": "funding",
            "domain": "oracle.com",
            "company": "Oracle",
            "age_days": 3,
            "evidence": "press release",
            "source_url": "https://oracle.com/news",
        })
        self.assertFalse(scored["allowed"])
        self.assertEqual(scored["score"], 0)
        self.assertEqual(scored["band"], "blocked")

    def test_blocked_lead_matt_colmia_blank_company_scores_zero(self):
        scored = score_trigger_event({
            "event_type": "hiring",
            "domain": "example.com",
            "company": "",
            "person_name": "Matt Colmia",
            "age_days": 3,
            "evidence": "job post",
            "source_url": "https://example.com/jobs",
        })
        self.assertEqual(scored["band"], "blocked")
        self.assertEqual(scored["score"], 0)

    def test_allowed_ats_host_carve_out(self):
        for company, url in (("UCSF", UCSF_URL), ("JPMorganChase", JPMC_URL), ("Coherent", COHERENT_URL)):
            record = classify_reply(
                "Sounds good.", sender_name="Pat", sender_company=company, url=url,
            )
            self.assertTrue(record["allowed"], company)
            self.assertTrue(record["dnc"]["atsHostCarveOut"], company)

    def test_allowed_lead_on_ats_host(self):
        scored = score_trigger_event({
            "event_type": "hiring",
            "domain": "ucsf.edu",
            "company": "UCSF",
            "age_days": 5,
            "evidence": "req posted",
            "source_url": UCSF_URL,
        })
        self.assertTrue(scored["allowed"])
        self.assertNotEqual(scored["band"], "blocked")


class TestReplyClassifierSchema(unittest.TestCase):
    def test_record_keys_are_schema_locked(self):
        record = _allowed_reply_record()
        self.assertEqual(set(record), set(REPLY_RECORD_KEYS))
        self.assertEqual(record["schema_version"], SCHEMA_VERSION)
        validate_reply_record(record)  # must not raise

    def test_deterministic_output(self):
        args = dict(
            reply_text="Please unsubscribe me from this list.",
            reply_id="r-9", thread_id="t-9",
            sender_name="Ann", sender_company="Acme", sender_email="ann@acme.com",
        )
        self.assertEqual(classify_reply(**args), classify_reply(**args))

    def test_confidence_bounds(self):
        for text in ("", "unsubscribe", "not interested, maybe next quarter"):
            record = classify_reply(text)
            self.assertGreaterEqual(record["confidence"], 0.0)
            self.assertLessEqual(record["confidence"], 1.0)

    def test_empty_text_is_other(self):
        record = classify_reply("")
        self.assertEqual(record["reply_class"], "other")
        self.assertEqual(record["confidence"], 0.0)

    def test_unsubscribe_detected(self):
        record = classify_reply("Please unsubscribe me from this list.")
        self.assertEqual(record["reply_class"], "unsubscribe")

    def test_objection_beats_interested_substring(self):
        record = classify_reply("We are not interested at this time.")
        self.assertEqual(record["reply_class"], "objection")

    def test_priority_order_breaks_score_tie(self):
        # unsubscribe (3) ties objection (3); earlier enum entry wins.
        record = classify_reply("unsubscribe now, and we are not interested")
        self.assertEqual(record["reply_class"], "unsubscribe")

    def test_classes_stay_in_locked_enum(self):
        for text in ("cease and desist", "out of office until monday", "wrong person, try my colleague",
                     "let's talk next week", "delivery failed", "circle back next quarter", "???"):
            self.assertIn(classify_reply(text)["reply_class"], REPLY_CLASSES)

    def test_validator_rejects_tampered_record(self):
        record = _allowed_reply_record()
        tampered = dict(record)
        tampered.pop("signals")
        with self.assertRaises(ValueError):
            validate_reply_record(tampered)
        tampered = dict(record)
        tampered["confidence"] = 2.0
        with self.assertRaises(ValueError):
            validate_reply_record(tampered)


class TestContactBriefBuilder(unittest.TestCase):
    def test_brief_keys_and_crm_staging(self):
        brief = build_contact_brief(
            _allowed_reply_record(), name="Pat Doe", company="UCSF",
            email="pat@ucsf.edu", url=UCSF_URL,
        )
        self.assertEqual(set(brief), set(CONTACT_BRIEF_KEYS))
        self.assertEqual(brief["crm"]["system"], "twenty")
        self.assertEqual(brief["crm"]["operation"], "upsert_contact")
        self.assertIs(brief["crm"]["staged"], True)
        self.assertIs(brief["write_enabled"], False)
        self.assertEqual(brief["intent"], "interested")
        self.assertEqual(brief["next_action"], "stage_reply_draft")
        validate_contact_brief(brief)

    def test_next_action_per_class(self):
        expectations = {
            "Please unsubscribe me now.": "suppress_contact",
            "We are not interested at this time.": "stage_objection_response",
            "Not the right person — talk to my colleague.": "stage_referral_followup",
        }
        for text, action in expectations.items():
            record = classify_reply(text)
            brief = build_contact_brief(record, name="Pat", company="Acme", email="pat@acme.com")
            self.assertEqual(brief["next_action"], action, text)

    def test_validator_rejects_enabled_write(self):
        brief = build_contact_brief(_allowed_reply_record(), name="Pat", company="Acme", email="pat@acme.com")
        tampered = dict(brief)
        tampered["write_enabled"] = True
        with self.assertRaises(ValueError):
            validate_contact_brief(tampered)


class TestGateDCardBuilder(unittest.TestCase):
    def _card(self):
        record = _allowed_reply_record()
        brief = build_contact_brief(record, name="Pat Doe", company="UCSF", email="pat@ucsf.edu", url=UCSF_URL)
        return record, brief, build_gate_d_card(record, brief, sender_stop_file=NO_STOP_FILE)

    def test_card_is_draft_only_and_never_sends(self):
        _, _, card = self._card()
        self.assertEqual(set(card), set(GATE_D_CARD_KEYS))
        self.assertIs(card["draft_only"], True)
        self.assertIs(card["send_enabled"], False)
        self.assertIs(card["clients_ai_send"], False)
        self.assertEqual(card["clients_ai_endpoint"], CLIENTS_AI_ENDPOINT)
        self.assertEqual(card["channel"], "aside-gate-d")
        self.assertEqual(card["stage"], "staged")
        validate_gate_d_card(card)

    def test_exact_text_human_approval(self):
        _, _, card = self._card()
        approval = card["approval"]
        self.assertEqual(approval["kind"], "exact-text")
        self.assertEqual(approval["approver"], "human")
        self.assertIs(approval["required"], True)
        self.assertTrue(approval["exact_text"].startswith("APPROVE SEND "))
        self.assertIn(card["draft"]["template_sha12"], approval["exact_text"])

    def test_sender_lane_never_auto_sends(self):
        _, _, card = self._card()
        self.assertIs(card["sender_lane"]["auto_send"], False)
        self.assertIs(card["sender_lane"]["ready"], False)  # no approved_sha12 yet

    def test_validator_rejects_send_enabled_card(self):
        _, _, card = self._card()
        tampered = dict(card)
        tampered["send_enabled"] = True
        with self.assertRaises(ValueError):
            validate_gate_d_card(tampered)
        tampered = dict(card)
        tampered["clients_ai_send"] = True
        with self.assertRaises(ValueError):
            validate_gate_d_card(tampered)


class TestTriggerScorer(unittest.TestCase):
    def _event(self, **overrides):
        event = {
            "event_type": "domain_registration",
            "domain": "acme.com",
            "company": "Acme",
            "age_days": 5,
            "evidence": "new marketing site with a careers page",
            "source_url": "https://www.acme.com/careers",
        }
        event.update(overrides)
        return event

    def test_score_keys_schema_locked(self):
        scored = score_trigger_event(self._event())
        self.assertEqual(set(scored), set(TRIGGER_SCORE_KEYS))
        self.assertEqual(scored["schema_version"], SCHEMA_VERSION)
        validate_trigger_score(scored)

    def test_fresh_event_beats_stale_event(self):
        fresh = score_trigger_event(self._event(age_days=5))
        stale = score_trigger_event(self._event(age_days=400))
        self.assertGreater(fresh["score"], stale["score"])
        self.assertEqual(fresh["freshness"], "fresh:30d")
        self.assertEqual(stale["freshness"], "stale")

    def test_hot_band_reachable_on_fresh_evidenced_domain(self):
        scored = score_trigger_event(self._event())
        self.assertGreaterEqual(scored["score"], 70)
        self.assertEqual(scored["band"], "hot")

    def test_band_bands(self):
        bands = {
            score_trigger_event(self._event())["band"],
            score_trigger_event(self._event(event_type="hiring", age_days=120, evidence=""))["band"],
            score_trigger_event(self._event(age_days=400))["band"],
        }
        self.assertTrue(bands <= {"hot", "warm", "cold"})

    def test_unknown_event_type_is_rejected(self):
        with self.assertRaises(ValueError):
            score_trigger_event(self._event(event_type="moon_phase"))

    def test_deterministic_output(self):
        self.assertEqual(score_trigger_event(self._event()), score_trigger_event(self._event()))


class TestBlueprint(unittest.TestCase):
    def test_shipped_blueprint_is_valid(self):
        result = validate_blueprint()
        self.assertEqual(result["errors"], [])
        self.assertTrue(result["valid"])
        self.assertEqual(result["ai_schema_locked_nodes"], 3)
        self.assertEqual(result["deterministic_nodes"], 11)

    def test_blueprint_has_cited_sources(self):
        blueprint = load_blueprint()
        self.assertEqual(len(blueprint["cited_sources"]), 4)
        for source in blueprint["cited_sources"]:
            self.assertTrue(source.startswith("src: "), source)

    def _broken(self, mutate):
        blueprint = copy.deepcopy(load_blueprint())
        mutate(blueprint)
        return validate_blueprint(blueprint)

    def test_planted_failure_send_enabled_goes_red(self):
        result = self._broken(lambda bp: bp["send_policy"].update(send_enabled=True))
        self.assertFalse(result["valid"])
        self.assertTrue(any("send_policy.send_enabled" in e for e in result["errors"]))

    def test_planted_failure_ai_node_without_output_schema_goes_red(self):
        def mutate(bp):
            for node in bp["nodes"]:
                if node["id"] == "n4_jev_reply_classification":
                    node.pop("output_schema")
        result = self._broken(mutate)
        self.assertFalse(result["valid"])
        self.assertTrue(any("output_schema" in e for e in result["errors"]))

    def test_planted_failure_ai_node_owning_pagination_goes_red(self):
        def mutate(bp):
            for node in bp["nodes"]:
                if node["id"] == "n7_draft_reply_authoring":
                    node["pagination"] = {"page_size": 10}
        result = self._broken(mutate)
        self.assertFalse(result["valid"])
        self.assertTrue(any("pagination" in e for e in result["errors"]))

    def test_planted_failure_runaway_retries_goes_red(self):
        result = self._broken(
            lambda bp: bp["deterministic_control_plane"]["retries"].update(max_retries=5)
        )
        self.assertFalse(result["valid"])
        self.assertTrue(any("max_retries" in e for e in result["errors"]))

    def test_planted_failure_missing_dnc_gate_goes_red(self):
        def mutate(bp):
            for node in bp["nodes"]:
                node.pop("calls", None)
        result = self._broken(mutate)
        self.assertFalse(result["valid"])
        self.assertTrue(any("evaluate_outreach_target" in e for e in result["errors"]))

    def test_planted_failure_empty_citations_goes_red(self):
        result = self._broken(lambda bp: bp.update(cited_sources=[]))
        self.assertFalse(result["valid"])


class TestContextArtifact(unittest.TestCase):
    REQUIRED = {"move", "status", "deliverables", "citations", "gates", "jev"}

    def test_context_json_covers_required_keys(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "src" / "robonuggets_ops" / "move2_nod_twenty_reply" / "context.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(self.REQUIRED - set(payload), set())
        self.assertTrue(payload["citations"])
        for source in payload["cited_sources"]:
            self.assertTrue(source.startswith("src: "), source)

    def test_context_json_gate_posture(self):
        path = pathlib.Path(__file__).resolve().parents[1] / "src" / "robonuggets_ops" / "move2_nod_twenty_reply" / "context.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertIs(payload["gates"]["gate_d"]["send_enabled"], False)
        self.assertIs(payload["gates"]["clients_ai_non_send"]["clients_ai_send"], False)
        self.assertIs(payload["jev"]["fail_closed"], True)


if __name__ == "__main__":
    unittest.main()
