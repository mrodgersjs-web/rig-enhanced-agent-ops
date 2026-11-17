# RoboNuggets 6-Tool Spec — ARMS-audited agent stack (Nod, Autark, Aside, Orca, OMP, Prime-Agent)

Design record for the RoboNuggets agent stack and its harness bridges.
Materialized 2026-11-16 (Phase 2 Live Wiring); this file was missing from the
repo before this change and is now the spec of record for ticket #9.

## 1. The stack

Six tools, one duty lane each (role mapping of record:
`src/robonuggets_ops/move4_harness_bridges/bridges.py:ROLE_MAP`):

| Tool | Lane | Duty keywords (select the canonical doctrine rules) |
| --- | --- | --- |
| aside | operator console and logged-in browser lane | linkedin, attention, identity, safety |
| autark | autonomous desk worker (computer control lane) | gates, effort, attention |
| nod | automation pipeline lane (Nod/n8n workflows) | eight-types, earned-leg, gates |
| orca | terminal crew execution lanes | code-and-context, harnesses-and-testing, jev-and-verification |
| omp | coding agent CLI runtime | code-and-context, harnesses-and-testing, jev-and-verification, build-vs-buy |
| prime-agent | fleet execution runtime for Jake | jake-identity, jake-direction, jev-and-verification, earned-leg-gates |

## 2. ARMS + Gate-D 5-axis contract (Move 1)

Every armed routine is scored 0-2 per axis, total 0-10
(`src/robonuggets_ops/move1_arms_audit/auditor.py`):

- **action** — the routine acts (actions + run receipts); action == 0 is flagged
  `chat_shaped` ("read-only chatter");
- **recall** — it reads and writes memory (reads/writes evidence);
- **model** — pinned model + fallback are declared (agents.model_policy + runs.model);
- **self_improvement** — feedback is logged and applied;
- **gate_d_jev** — Gate-D **and** Jev are wired (2 only when both hold).

Pre-arm rules for cron/RRULE schedules (`auditor._ARM_RULES`): the schedule must
carry `manual_dry_runs_passed >= 1`, `idempotent_writes is True`,
`max_retries <= 3`, `token_ceiling > 0`, `watched_failure_channel` non-empty.
A cron/RRULE schedule failing any rule is **blocked from arming**. Deliverables
consolidate into one inbox digest per Mike-time slot (morning/midday/evening) and
one batched Gate-D yes-queue.

## 3. Thin harness bridges (Move 4)

One bridge file per tool (`dist/harness_bridges/<tool>.md`), generated from the
canonical `~/.aside/u/0/doctrine/` rules by
`src/robonuggets_ops/move4_harness_bridges/bridges.py`:

- **thin = pointers, not copies**: a role line, the canonical rule refs matched
  by duty keywords, and the invariant triplet — never doctrine prose
  (`lint_bridge` rejects any verbatim long prose line);
- **no_oracle** — rule `no-oracle`, with the ATS-host carve-out
  (`dnc_guard.ATS_HOST_DOMAINS` = oraclecloud.com, taleo.net) and the blocked
  employer list (`dnc_guard.BLOCKED_EMPLOYERS`);
- **gate_d_draft_only** — rule `gate-d`, mode `draft_only`, auto_send False,
  approval `mike_exact_text`;
- **jev_before_done** — rule `jev-before-done`, `route_on_done: JEV`.

## 4. Phase 2 live wiring (this ticket)

- `scripts/run_live_product_phase2.py` (thin CLI over
  `src/robonuggets_ops/phase2_live_wiring/live_wiring.py`) sweeps the live Autark
  workforce DB **read-only** (`mode=ro` + `PRAGMA query_only=1`, zero schedule
  mutations; never touch live cron/launchd): every active schedule is mapped by
  `schedule_row_to_routine(row, receipts, model, model_fallback)` into the Move-1
  routine shape and scored via `auditor.audit`;
- outputs: `reports/live_arms_audit_<date>.json`
  (`{metadata, routines, blocked_armings, consolidation}`, `metadata.mode == "ro"`)
  and `reports/live_arms_summary.md` (per-routine lines + blocked armings + slot
  digests, stating the expected finding below);
- the six bridge files are materialized into `dist/harness_bridges/`, each
  carrying its `lint_bridge` verdict;
- exit semantics: **0 = sweep completed**; blocked armings are findings (the
  arming work queue), not errors.

Expected finding of the 2026-11-16 sweep: the active schedules carry no
`payload.scheduleEvidence`, so cron/RRULE rows fail the pre-arm rules and are
reported under `blocked_armings`. That is the fleet predating the pre-arm
contract, not a regression.

## 5. Sources

- `src: classroom/hermes-agent-os/m3-the-arms-framework-audit-any-ai-tool` — ARMS + Gate-D audit framework
- `src: classroom/claude-code-mastery/4-scheduled-tasks` — schedule pre-arm discipline
- `src: classroom/hermes-agent-os/m5-your-morning-briefing-first-scheduled-task` — slot digests / morning briefing
- `src: classroom/community-vault/j8-codex-agents-md` — thin agents.md/bridge pattern
- `src: classroom/claude-code-mastery/2-context-control` — context/rule pointers
- `src: classroom/claude-code-mastery/1-skills` — skill/role mapping
- `src: classroom/ai-content-accelerator/module-12-finding-outliers` — outlier baselines (Move 4 calibrator)
- `src: classroom/ai-content-accelerator/module-11-idea-sources` — idea-source corpus lanes
