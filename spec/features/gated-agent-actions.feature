Feature: Gated agent actions
  As an operator running autonomous agents in production
  I want every agent action routed through a confidence-gated proof gate
  So that high-risk actions never execute unreviewed and every decision
    is sealed into a tamper-evident audit trail

  Background:
    Given a fresh audit trail
    And an action gate wired to that audit trail
    And the auto-execute threshold is 0.85
    And the validate threshold is 0.70

  # --- Scenario 1: the confidence-routing contract -------------------------

  Scenario: high-confidence auto-executes
    Given an agent action "deploy_release" with confidence 0.95
    When the action gate processes the action
    Then the action is executed
    And the gate status is "auto_executed"
    And a proof packet is sealed recording the action, input, output, confidence, and timestamp
    And the proof packet is appended to the audit trail

  Scenario Outline: confidence at or above the auto threshold always auto-executes
    Given an agent action "deploy_release" with confidence <confidence>
    When the action gate processes the action
    Then the gate status is "auto_executed"

    Examples:
      | confidence |
      | 0.85       |
      | 0.90       |
      | 1.00       |

  Scenario: mid-confidence executes and requires validation
    Given an agent action "send_customer_email" with confidence 0.75
    When the action gate processes the action
    Then the action is executed
    And the gate status is "validated"
    And a proof packet is sealed recording the outcome

  Scenario: low-confidence escalates
    Given an agent action "delete_production_database" with confidence 0.40
    When the action gate processes the action
    Then the action is NEVER executed
    And an escalation is raised
    And the gate status is "escalated"
    And a proof packet is sealed recording the escalation itself

  Scenario Outline: confidence below the validate threshold always escalates
    Given an agent action "delete_production_database" with confidence <confidence>
    When the action gate processes the action
    Then the action is NEVER executed
    And the gate status is "escalated"

    Examples:
      | confidence |
      | 0.00       |
      | 0.30       |
      | 0.69       |

  # --- Scenario 2: independent validation -----------------------------------

  Scenario: validated action fails independent review
    Given a validator that always rejects
    And an agent action "post_public_statement" with confidence 0.78
    When the action gate processes the action
    Then the action is executed
    But the validation fails
    And the gate status is "rejected"
    And the proof packet recording the rejection remains on the audit trail

  # --- Scenario 3: tamper-evident chain integrity ---------------------------

  Scenario: the audit trail chains packets like a blockchain
    Given three agent actions have been processed by the gate
    Then each proof packet's prev_hash equals the previous packet's hash
    And the first proof packet's prev_hash equals the genesis hash
    And the audit trail verifies as intact

  Scenario: tampered audit trail detected
    Given three agent actions have been processed by the gate
    And the audit trail currently verifies as intact
    When an attacker mutates the output field of the second proof packet without resealing it
    Then the audit trail no longer verifies as intact
    And the verification failure identifies the second proof packet
    And an independent verifier, given only the exported trail, also detects the tampering

  Scenario: tampered audit trail detected even with a correct downstream chain
    Given three agent actions have been processed by the gate
    When an attacker mutates the confidence field of the first proof packet without resealing it
    Then the audit trail no longer verifies as intact
    And the verification failure identifies the first proof packet
    And no other proof packet is falsely reported as broken

  Scenario: signed audit trail rejects the wrong key
    Given an audit trail signed with a secret key
    And three agent actions have been processed by the gate
    When an independent verifier checks the trail with the wrong key
    Then the verification fails with a signature mismatch
    When an independent verifier checks the trail with the correct key
    Then the verification succeeds
