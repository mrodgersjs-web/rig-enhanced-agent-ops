# Live ARMS sweep — 2026-11-16 (read-only)

- db: /Users/rig128gb/Library/Application Support/Autark/workforce.db (mode=ro, zero schedule mutations)
- active schedules scored: 109
- generated: 2026-11-17T03:07:26.085923+00:00

## Expected finding

EXPECTED FINDING (not a regression): the active Autark schedules carry no pre-arm evidence fields (payload.scheduleEvidence: manual_dry_runs_passed, idempotent_writes, max_retries, token_ceiling, watched_failure_channel), so every cron/rrule schedule fails move1_arms_audit.validate_schedule and lands in blocked_armings. The sweep still completes with exit 0; the block list is the work queue for attaching pre-arm evidence before arming.

## Routines (ARMS + Gate-D axes, /10)

- sch_1m76816xcyyykzt70 Daily $30K KPI roll-up ARMS=3/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnjn3pxwjse1 Job Scout daily sourcing (ex-Rakazo) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnjrmykcscpg Daily application packet prep (ex-Rakazo) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnk8a30wc6cx Job follow-up sweep (ex-Rakazo) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnkcawt10v8d GTM signal prospecting (ex-Rakazo, $30K) ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnkea42kwf5h Outreach draft batch (ex-Rakazo, $30K) ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m768fnkkpsz6gqgn Interview readiness (ex-Rakazo) ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m79973bq854nm4gk Daily internal revenue and ideas review ARMS=3/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m799g02rgsdtjzb7 FA701427SC432 Step-1 White Paper due Fri 20 Nov 2026 12:00 P… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m79ap1dkkgx3wm0c Aside fleet health check · run steps 1–3 of Workforce/fleet… ARMS=0/10 CHAT-SHAPED schedule=allowed
- sch_1m79gx6n6esegrd30 Fleet-util hourly roll-up (Nora 2) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m79np13hqdkqz8rw Daily model optimizer (04:00 MT) ARMS=4/10 schedule=allowed
- sch_1m7a761ybrcekn1r7 Hourly revenue command cycle ARMS=3/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7a8epmd2ftwmdkq Vern nightly funnel verification 23:00 MT ARMS=6/10 CHAT-SHAPED schedule=allowed
- sch_1m7a8epmgp9n0thne Vern 07:00 MT PASS/FAIL report ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7a8qt856evknbkw 07:30 MT huddle brief (daily) ARMS=5/10 CHAT-SHAPED schedule=allowed
- sch_1m7a949303q5w2fpk Pipeline pulse, daily 08:00 MT (Card 7) ARMS=5/10 CHAT-SHAPED schedule=allowed
- sch_1m7aa0jgszw9kgt41 Ivo: daily competitor/ad diff (06:00 MT) ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7aca6czv2t4ysb3 Daily idea run: 100 ideas + top 3 with financials ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7ajt86htprt97hb Academy daily improvement cycle ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7ajt86kck6jh60c Academy weekly deeper agent/team review ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7akma3dzetrvxdv Ivo: Monday deep competitor rundown (weekly) ARMS=4/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7at7hpbkq2fcs86 Denver100: check Gmail replies/bounces on batch 1 (9 live la… ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7atp1cajktm1hn1 Clients.ai trial billing: confirm exact next-bill date + can… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7atqttnypczccew Clients.ai 2-hourly huddle line ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7av7z7m7xpf3mng Daily post-metrics line for the 15:00 huddle ARMS=5/10 CHAT-SHAPED schedule=allowed
- sch_1m7axa5bh64gcef0z Flynn huddle status every 2h (opt-ins + funnel state) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7b3f7khawngy8gm Daily EA triage digest for Mike ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7b6bgh8hcqwvs70 Clients.ai cancelled 13 Nov, access ends Nov 20. Mike wants … ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bakhk0qep529b1 Midwest trades list daily top-up (Signe) ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bd3sj8wjd24vrg Verify engineering dashboard internally ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bdd86wjk5ppzz8 Sales Genius playbook — daily run ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bdwb3pgjcq5f75 Sales Genius — 2-hourly huddle status line ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bfevsrpsyy79a0 Idea Council daily 5 ARMS=3/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7bja5hmzkn24ska Daily 17:00 approvals list to Mike ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bjavafqac7myc6 Email-time baseline: week-1 report ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7bjb60k61zzs3m6 Email-time baseline: log daily row ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bjtb0dyzhvddck SEC-5 weekly leaked-key scan (Thu 23:30 MT) ARMS=3/10 schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7bkdt011ct7yk3d Unified calendar: refresh agenda ARMS=6/10 schedule=allowed
- sch_1m7bkhfbpx8bwteaz SEC-9 fleet + cost alarm (every 30 min) ARMS=3/10 schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7bkwvpkyne8qr73 Subscriptions: weekly renewal watch ARMS=3/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7bkz0qqqk0jtghp Weekly review: prep sheet for Mike ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7bm76deqsjvv3q3 JAC: nightly scorecard refresh (21:00-06:00 MT window) ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7bm7bnwch4238ee JAC: first weekly KPI line (Sat 21 Nov) ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bq19vpd2zxhmew JAC: camp 2027 registration watch (weekly from Feb 2027) ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bqabf6cc1c1tec Weekly compliance-calendar re-read + legal KPI line ARMS=6/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7br10nchp2aqvrx Daily signal feed + morning digest (task_1m7bn5v3hvw40ckma).… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7brf4yqyy993p8n Interview #2 slot: Ideawake PRO pilot check-in is today (rev… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7brrc5a3t2j2pf7 D1 restore drill (retention policy §3) ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7brv0hf16fk3j1b D2 failover+first-aid drill planning ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7brv0hhyzf0c2ex First retention sweep (policy §1) ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7bskgr6bm0fdy4h Weekly research KPI line → huddle ch_1m7a5eygbhyevzhd4 (task… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bskgrbdszeyg2f Monthly market memo (answers/07 Q30, task task_1m7bn7mxhj7fa… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7bwpknfgb3gp9tr Nightly off-disk backup (restic → rig96gb) ARMS=4/10 schedule=allowed
- sch_1m7bwyjt2k3q0m0xs Monthly access-matrix review (SEC-7 control) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7c2cfbsy2ptqpnn Vendor quote ask went out 13 Nov 21:40 MT to Mile High, Webs… ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7c7mkthaq4wmwkb Finance daily ledger ARMS=1/10 CHAT-SHAPED schedule=allowed
- sch_1m7c7q1cpbxzasc48 Data KPI snapshot daily 07:00 ARMS=1/10 CHAT-SHAPED schedule=allowed
- sch_1m7ca4gg6x1vv7c3d Weekly check for ALARM task task_1m7bqdjg0zkpb9wc1: parse Au… ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7cg74xs7z4yqtjq Weekly secret-expiry check (ENG R7): run `python3 /Users/rig… ARMS=1/10 CHAT-SHAPED schedule=allowed
- sch_1m7chz0n6jdtm20vz ENG R8 weekly autonomy metric: run `python3 /Users/rig128gb/… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_1m7cq7rn819jjeysk ENG R4: stuck-task detector ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7dbbnve39vrmwz9 Weekly benchmark-routing refresh ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_1m7etcrn4djxycrcx Crazy Ideas weekly sheet ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1m7g0vpme24xqq8jg HOLD: Vendor follow-up held pending Mike's recorded exact-te… ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7g0xnpnfb1b2qmv HOLD: Vendor follow-up backup held pending Mike's recorded e… ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_1m7g1exkwzqgh4mka Aside inbox sweep (replaces the broken mention-wake path for… ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_31agmw0b Sage: daily Idea Council file + weekly 3 strategy angles ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_nv21hhrj Social Command metrics update (Pulse) ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_j29d7vtg JAC: weekly site traffic + mentions monitor (press lane) ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_fkkk5s4z Daily 09:00 idle-agent check ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_byy7q4ea Eng & Dev KPI edition (08:00 + 17:30 MT) ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_wss9hthq Midday inbox sweep ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_5dzww0a5 Idea Council daily file: crazy-ideas-studios ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_6b3rexgp Idea Council weekly scoring ARMS=6/10 schedule=allowed
- sch_f51kns4m Milo hourly open-work sweep ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_rzf717tp Daily ping counter (closed day) – Gov R6 ARMS=4/10 schedule=allowed
- sch_qdg0zaa8 JAC: state-final post checkpoint (task_3svzktbe) ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_19vkchhn Daily receipts status (kept agents) ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_z7datp5d Blackwell daily health receipt (e1-health.txt) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_h1bbrx3c Model-layer 5-min failure buckets ARMS=6/10 schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_0z4xrazj Model-layer 30-min lane probe ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_qaqdem35 Scout 2 daily signals + 3 scored hooks ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_6xr8vdk1 Daily glove live-readiness advance ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_v63b8nn7 Check Gmail (mrodgersjs@gmail.com via Gmail API; client id/s… ARMS=5/10 CHAT-SHAPED schedule=allowed
- sch_kevqrpa4 Scribe D1 daily draft batch ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_rqfja910 Reel R1 daily short-video draft ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_qhcmdnrg L8 after-measure (3 cases): (1) did the 17 Nov 07:30 brief c… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_0fg6btzg 06:00 chase for 17 Nov. List sources/2026-11-17/. Chase each… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_77k68yx9 Kill-date checks from decisions.md: (21 Nov) Verify Don't Cl… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_04m059d1 Fleet-util UNKNOWN row check ARMS=4/10 schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_y46zxdp6 Dax: file tomorrow's Idea Council design.md the night before ARMS=4/10 CHAT-SHAPED schedule=allowed
- sch_90vm9dtc Trial of Dax's brief layout for the 17 Nov 5 (outcomes/ag_1m… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_gqyg2qg9 Weekley SB-01: check Maya's task_1m7dxkctqx0j4hh5p for the r… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_s06ew0tw KWP after-measure: count which kwp-* skills appear in agents… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_nsfc0jv8 Daily model-client KPI ARMS=1/10 CHAT-SHAPED schedule=allowed
- sch_fzegys53 Re-pull Google Trends 'AI agents for small business' (US, py… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_xgaw9hbg task_gmp5e00d: RIG post 06f9a49d was due 08:30 MT with an in… ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_p0mmrgqr Check Vera's Agency Agents staging package due 17 Nov noon (… ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_4npjdp80 Fleet queue depth check (hold, no refill) ARMS=3/10 schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_87hcv8j8 RIG Clients cutover 4h check ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1rmv2kcq F1 daily spend line ARMS=5/10 CHAT-SHAPED schedule=allowed
- sch_ymekwp5y Jacob X P3 kill check: followers < 250 on 2026-11-20 -> kill… ARMS=3/10 CHAT-SHAPED schedule=allowed
- sch_k3vnv2q8 Interview-drill readiness check: verify Mike ran /bbb-drill … ARMS=2/10 CHAT-SHAPED schedule=allowed
- sch_zr855k1h Estate health sweep (30-min) ARMS=0/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_70febk0k Daily scorecard row (18:00 MT) ARMS=0/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_frbv9v5r Weekly OpenLIT pull (Mon 07:30 MT) ARMS=1/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_1w258qqq Dead-URL drift check (07:00 MT) ARMS=2/10 CHAT-SHAPED schedule=BLOCKED: manual_dry_runs_passed: requires manual_dry_runs_passed >= 1; idempotent_writes: requires idempotent_writes == True; max_retries: requires max_retries <= 3; token_ceiling: requires token_ceiling > 0; watched_failure_channel: requires watched_failure_channel non-empty
- sch_svaf9d4v 20:30 playable capture checkpoint: Marcus's task_tqkfysr9 (s… ARMS=2/10 CHAT-SHAPED schedule=allowed

## Blocked armings

36 blocked arming(s): sch_1m76816xcyyykzt70, sch_1m768fnjn3pxwjse1, sch_1m768fnjrmykcscpg, sch_1m768fnk8a30wc6cx, sch_1m768fnkcawt10v8d, sch_1m768fnkea42kwf5h, sch_1m768fnkkpsz6gqgn, sch_1m79973bq854nm4gk, sch_1m79gx6n6esegrd30, sch_1m7a761ybrcekn1r7, sch_1m7aca6czv2t4ysb3, sch_1m7akma3dzetrvxdv, sch_1m7atqttnypczccew, sch_1m7axa5bh64gcef0z, sch_1m7bfevsrpsyy79a0, sch_1m7bjtb0dyzhvddck, sch_1m7bkhfbpx8bwteaz, sch_1m7bkwvpkyne8qr73, sch_1m7bkz0qqqk0jtghp, sch_1m7bqabf6cc1c1tec, sch_1m7bwyjt2k3q0m0xs, sch_1m7ca4gg6x1vv7c3d, sch_1m7cq7rn819jjeysk, sch_1m7etcrn4djxycrcx, sch_1m7g1exkwzqgh4mka, sch_f51kns4m, sch_z7datp5d, sch_h1bbrx3c, sch_0z4xrazj, sch_04m059d1, sch_4npjdp80, sch_87hcv8j8, sch_zr855k1h, sch_70febk0k, sch_frbv9v5r, sch_1w258qqq

## Slot digests (consolidation)

- morning: 138 deliverable(s) from 108 routine(s)
- midday: 0 deliverable(s) from 0 routine(s)
- evening: 1 deliverable(s) from 1 routine(s)
- gate_d_yes_queue: 0 approval(s)

Exit semantics: 0 = sweep completed; blocked armings are findings, not errors.
