# Palo Alto Cortex XDR Plugin — Customer Test Window Runbook

Goal: everything below should be **known and rehearsed before** the
customer window opens. The window itself is for steps that can only
happen on the customer's real CE + Cortex XDR tenants.

## Pre-flight (do this before the window, not during it)

- [ ] `pytest` suite passes locally (`PYTHONPATH=. pytest palo_alto_cortex_xdr/tests -v`)
- [ ] `flake8 --max-line-length=80 palo_alto_cortex_xdr --exclude=palo_alto_cortex_xdr/tests/sdk_stub` is clean
- [ ] `icon.png` added to the plugin folder (128x128 or 300x50 — confirm with Netskope which applies)
- [ ] Zip built **excluding** `tests/` and `DEPLOYMENT_RUNBOOK.md`:
      `cd palo_alto_cortex_xdr && zip -r ../palo_alto_cortex_xdr.zip . -x "tests/*"`
- [ ] Have ready: Cortex XDR HTTP Log Collector URL + API Key, for both
      the gzip-configured collector and the uncompressed-configured
      collector (you already validated both independently via curl)
- [ ] Know which Compression mode you'll test first in CE (pick the
      one matching whichever collector/token you paste into the plugin config)

## In the customer window

1. **Upload the plugin**
   - Settings → Plugins → Add New Plugin → Browse → select the zip → Upload
   - Confirm it appears in the Plugin Store under module "CLS"

2. **Create a plugin configuration**
   - Log Shipper → Plugins → configure "Palo Alto Cortex XDR"
   - Fill in: HTTP Log Collector URL, API Key, Compression (must match the collector), Log Source Identifier
   - **Disable "Transform the raw logs"** toggle (mandatory — plugin rejects raw-JSON-off configs by design)
   - Save → this triggers `validate()`. Expected: green success. If it fails, see Troubleshooting below.

3. **Configure the pipeline**
   - Log Shipper → Business Rules: create/select a rule for a small, easy-to-verify subset (e.g. one alert subtype) to keep the first test low-volume
   - Log Shipper → SIEM Mappings: bind Source (Netskope tenant) → Business Rule → this plugin's configuration

4. **Trigger and confirm delivery**
   - Wait for the next scheduled run (or trigger manually if CE supports it)
   - In Cortex XDR: Settings → Data Sources & Integrations → your HTTP collector → check "logs received" count (last hour)
   - Run an XQL Search query against the `<Vendor>_<Product>_raw` dataset (Vendor/Product as configured when the collector was created) to see actual records land

5. **Sign-off**
   - Confirm record count roughly matches what CE reports as pushed
   - Spot-check 1-2 records in XQL Search for field completeness (nothing truncated/mangled)

## Troubleshooting quick reference (map the symptom, don't re-diagnose from scratch)

| Symptom | Likely cause | Fix |
|---|---|---|
| `validate()` fails immediately, no HTTP call visible in logs | Missing/malformed config field (URL, API Key, Compression) | Check CE plugin logs for the exact field flagged |
| HTTP 401 | Wrong/expired API Key, or collector deleted/disabled in Cortex XDR | Regenerate the collector's token, update plugin config |
| HTTP 404 | Wrong HTTP Log Collector URL | Re-copy the URL from Cortex XDR's collector page |
| HTTP 413 | Batch too large (shouldn't happen — plugin targets ~1 MiB, hard cap 10 MiB) | Check CE logs for actual payload size; report if this triggers, it'd indicate a bug in our batching |
| **HTTP 500** | **Compression mismatch** between plugin config and the specific collector/token being used, OR collector's Log Format isn't set to JSON | Double check: does this API Key belong to the gzip collector or the uncompressed one? Does the plugin's Compression setting match? |
| HTTP 429 | Rate limit (>400 req/sec/customer/endpoint) — unlikely at normal CE volumes | Plugin retries automatically; if persistent, check for a runaway business rule pushing unexpectedly high volume |
| CE shows push success, but no records in XQL Search | Wrong Vendor/Product on the collector vs. what you're searching, or data delayed | Confirm dataset name `<Vendor>_<Product>_raw` matches the collector's configured Vendor/Product; wait a few minutes, XQL indexing isn't instant |

## What NOT to debug live

If something fails in a way not covered above, don't improvise fixes against
the customer's tenant. Capture: CE plugin logs (full `details` traceback if
shown), the exact HTTP status code, and the Cortex XDR collector's
"logs received" counters — then step back to fix and re-test locally
against the sandbox collectors first.
