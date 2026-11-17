# nod harness bridge

Role: automation pipeline lane (Nod/n8n workflows)
Canonical doctrine: /Users/rig128gb/.aside/u/0/doctrine

## Rule refs (canonical doctrine pointers)

- earned-leg-gates.md — /Users/rig128gb/.aside/u/0/doctrine/earned-leg-gates.md
- eight-types-gates.md — /Users/rig128gb/.aside/u/0/doctrine/eight-types-gates.md

## Invariants

1. no_oracle — {"ats_host_carve_out": true, "ats_host_domains": ["oraclecloud.com", "taleo.net"], "blocked_employers": ["oracle", "oracle health", "cerner", "oracle cerner", "oracle corp", "oracle corporation", "oracle america"], "rule": "no-oracle"}
2. gate_d_draft_only — {"approval": "mike_exact_text", "auto_send": false, "mode": "draft_only", "rule": "gate-d"}
3. jev_before_done — {"route_on_done": "JEV", "rule": "jev-before-done"}

_Thin bridge: pointers only, no doctrine prose duplicated._

## lint_bridge verdict

```json
{
  "ok": true,
  "tool": "nod",
  "violations": []
}
```
