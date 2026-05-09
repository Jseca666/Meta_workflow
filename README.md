# Meta_workflow

Meta_workflow is a meta workflow engine workspace: it is meant to build, run, check, and improve workflows for arbitrary projects.

The first extracted subsystem is `integrations/pro_bridge`, a guarded interface for using an external ChatGPT Pro project as an outside expert. Pro feedback is treated as evidence and advice only; local gates decide whether it changes workflow rules, memory, or acceptance status.

## Pro Bridge quick start

1. Copy `integrations/pro_bridge/config/pro_chat_monitor.config.example.json` to `integrations/pro_bridge/config/pro_chat_monitor.config.local.json`.
2. Fill the local browser profile, Pro project id, expected conversation id, and any one-run send nonce in the local config.
3. Prepare a prompt with a fixed GitHub `source_ref`.
4. Validate before any browser action:

```powershell
node integrations/pro_bridge/tools/pro_chat_monitor.mjs self-test --json
node integrations/pro_bridge/tools/pro_chat_monitor.mjs validate-prompt --config integrations/pro_bridge/config/pro_chat_monitor.config.local.json --json
```

Runtime captures, locks, local registries, and Pro responses stay under `integrations/pro_bridge/runtime/` and are intentionally not committed.
