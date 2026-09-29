# CLS Palo Alto Cortex XDR v1.0.0 Plugin Guide

## Description

This plugin pushes Netskope Alerts and Events, as raw JSON, to a Palo Alto
Cortex XDR HTTP Log Collector. It does not perform field-level
transformation/remapping and does not support sending WebTx logs.

### Prerequisites

* A Netskope Cloud Exchange (CE) tenant with the Log Shipper (CLS) module,
  configured with a Netskope source plugin.
* A Palo Alto Cortex XDR tenant with the **Data Collection add-on** license
  (required to create HTTP Log Collectors).
* Permission to create an HTTP Log Collector and generate its API token in
  Cortex XDR (Settings > Data Sources & Integrations).

### Connectivity to the following hosts

* The Cortex XDR HTTP Log Collector endpoint configured for your tenant,
  e.g. `https://api-<tenant external URL>/logs/v1/event`

## CE Version Compatibility

Netskope CE version 6.1.0 and above. (Built and validated against a live
CE 6.1.0 instance; the plugin's abstract method signatures were confirmed
against that version's `netskope.integrations.cls.plugin_base` source.)

## Plugin Scope

Ingest Netskope Alerts and Events into Cortex XDR via its HTTP Log
Collector (HEC-style) endpoint, in raw JSON.

### Type of data supported

<table>
  <tr>
   <td>Data types shared</td>
   <td>Alerts (DLP, Malware, Policy, Compromised Credential, Malsite,
   Quarantine, Remediation, Security Assessment, Watchlist, UBA, CTEP)
   and Events (Page, Application, Audit, Infrastructure, Network,
   Incident, Endpoint)</td>
  </tr>
  <tr>
   <td>Data types NOT supported</td>
   <td>WebTx logs</td>
  </tr>
</table>

### Mappings

This plugin only supports sharing raw JSON logs — the "Transform the raw
logs" toggle must be disabled in the plugin's Basic configuration. No
field-level renaming or severity remapping is applied: every field in the
Netskope alert/event, including severity, is passed through to Cortex XDR
using Netskope's own native field names and values. The bundled
`mappings.json` exists only to declare the supported alert/event subtypes
to Cloud Exchange, as required by the CLS plugin framework — it does not
define any field transformations.

## Permissions

* Cortex XDR: permission to create/view HTTP Log Collectors and generate
  their API tokens (Settings > Data Sources & Integrations).
* Netskope CE: permission to add/configure CLS plugins, Business Rules,
  and SIEM Mappings under the Log Shipper module.

## API Details

### List of APIs used

<table>
  <tr>
   <td><strong>API Endpoint</strong></td>
   <td><strong>Method</strong></td>
   <td><strong>Use case</strong></td>
  </tr>
  <tr>
   <td><code>https://api-&lt;tenant external URL&gt;/logs/v1/event</code></td>
   <td>POST</td>
   <td>Ingest a batch of alert/event records (used for both
   configuration validation and regular pushes)</td>
  </tr>
</table>

### HTTP Log Collector endpoint

**Method:** POST

**Headers:**

```
Authorization: <API Key>          (no "Bearer" prefix)
Content-Type: application/json
Content-Encoding: gzip            (only when Compression = gzip)
```

**Body:** newline-delimited JSON objects, one per record, with no
envelope/wrapper — e.g.:

```
{"timestamp": 1700000000, "alert_name": "DLP violation", ...}
{"timestamp": 1700000001, "alert_name": "Malware detected", ...}
```

**Response codes** (per Cortex XDR's HTTP Log Collector documentation):

<table>
  <tr>
   <td><strong>Code</strong></td>
   <td><strong>Meaning</strong></td>
  </tr>
  <tr>
   <td>200</td>
   <td>Success</td>
  </tr>
  <tr>
   <td>401</td>
   <td>Unauthorized — invalid API Key, or the collector is deleted/disabled</td>
  </tr>
  <tr>
   <td>404</td>
   <td>Not Found — wrong URL</td>
  </tr>
  <tr>
   <td>413</td>
   <td>Payload Too Large — request exceeded 10 MB</td>
  </tr>
  <tr>
   <td>429</td>
   <td>Rate limit exceeded (400 requests/sec/customer/endpoint) — the plugin
   retries automatically</td>
  </tr>
  <tr>
   <td>500</td>
   <td>Request could not be processed — almost always means the plugin's
   <strong>Compression</strong> setting does not match the collector's
   configured Compression, or the collector's Log Format isn't set to
   JSON</td>
  </tr>
</table>

## User Agent

The user-agent added by this plugin follows the format
`netskope-ce-<module>-<plugin_name>-<plugin_version>`.

## Workflow

1. Create an HTTP Log Collector in Cortex XDR and generate its API token.
2. Configure this plugin in Netskope CE with the collector's URL, API
   Key, matching Compression setting, and a Log Source Identifier.
3. Create a Business Rule in CE to select the Alerts/Events to share.
4. Create a SIEM Mapping binding your Netskope source, the Business
   Rule, and this plugin's configuration.
5. Confirm data lands in Cortex XDR via its Data Sources & Integrations
   page and XQL Search.

## Configuration on Netskope Tenant

Follow Netskope's standard guide for configuring a Netskope Tenant and
its source plugin in Cloud Exchange before configuring this plugin;
refer to your CE deployment's Log Shipper documentation for the exact
steps, as they depend on which Netskope source plugin (e.g. Netskope
Log Shipper) is in use.

## Configuration on Palo Alto Cortex XDR

### Obtaining configuration parameters

1. In Cortex XDR, navigate to **Settings → Data Sources & Integrations**.
2. Click **+ Add New**, search for **HTTP**, and click **Add**.
3. Give the collector a descriptive name.
4. Set **Compression** to either `Uncompressed` or `Gzip` — this exact
   choice must be mirrored in this plugin's **Compression** configuration
   parameter.
5. Set **Log Format** to `JSON`.
6. Set **Vendor** and **Product** (these determine the resulting XQL
   dataset name: `<Vendor>_<Product>_raw`).
7. Click **Save & Generate Token**, and record the token immediately —
   it cannot be retrieved again later, only regenerated.
8. Copy the collector's URL (e.g.
   `https://api-<tenant external URL>/logs/v1/event`).

## Configuration on Netskope CE

### Palo Alto Cortex XDR plugin configuration

1. Go to **Settings → Plugins → Add New Plugin**, upload
   `palo_alto_cortex_xdr.zip`.
2. Create a new configuration for "Palo Alto Cortex XDR" and fill in:

   <table>
     <tr>
      <td><strong>Parameter</strong></td>
      <td><strong>Description</strong></td>
     </tr>
     <tr>
      <td>HTTP Log Collector URL</td>
      <td>The collector's POST URL from Cortex XDR</td>
     </tr>
     <tr>
      <td>API Key</td>
      <td>The token generated for the collector</td>
     </tr>
     <tr>
      <td>Compression</td>
      <td>Must exactly match the collector's own Compression setting
      (Uncompressed or Gzip)</td>
     </tr>
     <tr>
      <td>Log Source Identifier</td>
      <td>Tag value added to every record sent, to help identify the
      source in XQL Search</td>
     </tr>
   </table>

3. In the plugin's Basic configuration, disable **"Transform the raw
   logs"** — this plugin only supports raw JSON and will fail validation
   otherwise.
4. Save. This triggers a live validation call against the Cortex XDR
   endpoint.

### Adding Business Rule

* Create a Business Rule selecting the Alert/Event subtypes you want to
  share (start with a small subset for initial testing).

### Adding SIEM Mapping

* Bind your Netskope source, the Business Rule, and this plugin's
  configuration under Log Shipper > SIEM Mappings.

## Validation

### Validate the Push

* In Cortex XDR, go to **Settings → Data Sources & Integrations** and
  check the collector's "logs received" counters (last hour/day/week).
* Run an XQL Search query against the `<Vendor>_<Product>_raw` dataset
  to confirm records are landing with the expected fields.
* See `DEPLOYMENT_RUNBOOK.md` in this folder for a full step-by-step
  test checklist.

## Troubleshooting

* **HTTP 500 on push/validate** — almost always a Compression mismatch
  between this plugin's configuration and the specific collector/token
  in use, or the collector's Log Format isn't JSON.
* **HTTP 401** — API Key is wrong/expired, or the collector was deleted
  or disabled in Cortex XDR.
* **HTTP 404** — the HTTP Log Collector URL is incorrect.
* **CE reports success but no records appear in XQL Search** — confirm
  the Vendor/Product used in your search matches the collector's
  configuration, and allow a few minutes for indexing.
* See `DEPLOYMENT_RUNBOOK.md` for the full symptom-to-cause
  troubleshooting table.

## Limitations

* WebTx logs are not supported.
* No field-level transformation or severity remapping — data is shared
  exactly as Netskope reports it ("Transform the raw logs" must stay
  disabled).
* Compression is fixed per Cortex XDR collector instance; a single
  plugin configuration cannot switch between gzip and uncompressed
  without also switching to a differently-configured collector.
