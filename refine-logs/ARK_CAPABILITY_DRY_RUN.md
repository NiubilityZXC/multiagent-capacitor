# Ark AgentPlan Capability Probe — Client Preview

**Time:** 2026-08-24 15:22:23 +08:00  
**Status:** `PASS_CLIENT_PREVIEW_ONLY`  
**Network:** blocked by `arkcli --dry-run`  
**Credential:** non-secret placeholder; no user credential was read, sent, or stored

## Frozen inputs

- CLI: `arkcli 1.0.14` (`1.0.20` was reported available; formal Gate must pin one version).
- Base URL: `https://ark.cn-beijing.volces.com/api/plan/v3`.
- Provisional model: `kimi-k3`.
- Response contract: `configs/ark_capability_probe_schema.json`.
- `caching=disabled`, `store=false` by omission, `max_output_tokens=96`.
- Strict client validation: `text-format=json_schema`, `text-strict=true`.

## Reproducible safe command

The placeholder is intentionally not a usable credential.

```bash
ARKCLI_CALLER_TYPE=ai_agent \
ARKCLI_CALLER_NAME=codex \
ARKCLI_SKILL_NAME=arkcli-chat \
arkcli +chat --dry-run \
  --api-key PLACEHOLDER_NOT_A_SECRET \
  --base-url https://ark.cn-beijing.volces.com/api/plan/v3 \
  --model kimi-k3 \
  --caching disabled \
  --thinking auto \
  --max-output-tokens 96 \
  --text-format json_schema \
  --text-schema configs/ark_capability_probe_schema.json \
  --text-strict --format json \
  'Return exactly the schema values.'
```

## Observed preview contract

The CLI returned `schema_version=preview.v1`, `dry_run=true`, `mode=client_preview`, and:

```json
{
  "network": "blocked",
  "filesystem": "read_only",
  "subprocess": "blocked",
  "data_plane": "agent_plan",
  "credential_kind": "agent_plan",
  "base_url": "https://ark.cn-beijing.volces.com/api/plan/v3",
  "resource_id": "kimi-k3",
  "resource_kind": "model",
  "validated": true
}
```

## Claim boundary

This proves only that the local CLI accepts the stateless AgentPlan execution context and strict-schema request shape without network access. It does not prove authentication, model existence, Responses support, schema compliance, token accounting, or forecast quality. Those require the human-approved authenticated capability Gate with a rotated credential supplied outside tracked files.
