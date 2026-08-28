# TDD traceability

`traceability.yml` is the executable inventory for the OpenClaw-to-Codex migration.
Every product requirement has an individual stable ID and one or more concrete test
node IDs. Ranges used in the migration plan are editorial shorthand only.

The first recorded run classifies requirements as:

- `RED_EXPECTED`: a real missing or defective behavior;
- `BASELINE_GREEN`: harness or useful legacy behavior already correct;
- `EXTERNAL_BLOCKED`: the local contract is executable but a real provider probe is
  not yet available.

A valid red baseline has no collection errors, skips, xfails, unclassified failures,
network calls, production effects, or access to `/home/openclaw`.
