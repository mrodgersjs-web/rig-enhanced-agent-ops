# aside harness bridge

Role: operator console and logged-in browser lane
Canonical doctrine: /Users/rig128gb/.aside/u/0/doctrine

## Rule refs (canonical doctrine pointers)

- account-identity.md — /Users/rig128gb/.aside/u/0/doctrine/account-identity.md
- attention.md — /Users/rig128gb/.aside/u/0/doctrine/attention.md
- jake-identity.md — /Users/rig128gb/.aside/u/0/doctrine/jake-identity.md
- linkedin-safety.md — /Users/rig128gb/.aside/u/0/doctrine/linkedin-safety.md

## Invariants

1. no_oracle — {"ats_host_carve_out": true, "ats_host_domains": ["oraclecloud.com", "taleo.net"], "blocked_employers": ["oracle", "oracle health", "cerner", "oracle cerner", "oracle corp", "oracle corporation", "oracle america"], "rule": "no-oracle"}
2. gate_d_draft_only — {"approval": "mike_exact_text", "auto_send": false, "mode": "draft_only", "rule": "gate-d"}
3. jev_before_done — {"route_on_done": "JEV", "rule": "jev-before-done"}

_Thin bridge: pointers only, no doctrine prose duplicated._

## lint_bridge verdict

```json
{
  "ok": true,
  "tool": "aside",
  "violations": []
}
```
