# Blob Storage

Specification and runbook for Flash's rendered-image blob storage.

This doc covers two things:

1. **Decision** — which backend Flash uses for rendered images and why.
2. **Runbook** — how to provision the chosen backend and wire it into the
   `timepoint-flash-deploy-private-feb-2026` Railway production environment.

> **Status:** decision finalized 2026-04-28 (task el-5bkwk). Provisioning is
> blocked on Sean's Cloudflare + Railway account access — see
> [Provisioning Runbook](#provisioning-runbook) for the escalation checklist.

---

## TL;DR

| Field                           | Value                                      |
| ------------------------------- | ------------------------------------------ |
| **Backend**                     | Cloudflare R2 (S3-compatible object store) |
| **Bucket name**                 | `timepoint-flash-renders`                  |
| **Region / location hint**      | `auto` (R2 is regionless; pick `WNAM`/`ENAM` if forced) |
| **Public read**                 | Enabled via R2 public bucket setting (custom domain optional) |
| **Public URL pattern**          | `https://<r2-public-host>/<key>`           |
| **Object key layout**           | `timepoints/<YYYY>/<MM>/<folder_name>/<file>` (mirrors local layout in `app/storage/naming.py`) |
| **Code path that uploads**      | `app/storage/backends/cloud.py` (currently a `NotImplementedError` stub — see [Migration Path](#migration-path)) |
| **Env var prefix**              | `FLASH_BLOB_*` (set on Railway prod env)   |

---

## Why Cloudflare R2

Flash's rendered images are read by `<img>` tags inside Belle / web-app /
public share pages, with no auth handshake. Belle generates hundreds of
images per run, so egress dominates cost. Flash already lives on
Railway-centric infra and the rest of Timepoint speaks S3 API.

### Option comparison

| Option                       | Egress cost                     | Public read                                    | S3 API     | Fits Railway infra | Verdict                                        |
| ---------------------------- | ------------------------------- | ---------------------------------------------- | ---------- | ------------------ | ---------------------------------------------- |
| **Cloudflare R2** ✅ chosen  | **$0** (free egress)            | Yes (public bucket or custom domain)           | Yes        | Yes (no Railway change) | Best fit. Free egress is the deciding factor. |
| Railway Volume + nginx       | Bandwidth on Railway egress     | Possible but requires us to run a static server in front | No (POSIX) | Native Railway     | Couples storage to compute. Volume-per-replica makes scale-out painful. Egress is Railway-billed. |
| AWS S3 + CloudFront          | $0.085/GB S3 egress, CF mitigates with caching | Yes                                            | Yes        | Cross-cloud (extra IAM, billing) | Works, but costs more than R2 and adds a second cloud to the bill. |
| Backblaze B2 + Cloudflare    | Free via Bandwidth Alliance     | Yes                                            | Yes (B2 native S3 layer) | Cross-vendor       | Viable fallback if R2 has issues, but no in-house Cloudflare account is needed for R2. |
| Supabase Storage             | Bundled with Supabase plan      | Yes                                            | Limited S3 compat | Adds a Supabase dep | Pulls in a database vendor we don't otherwise use. |

**Decision driver:** Belle's image-heavy generation pattern + public `<img>`
fetches mean egress is the dominant variable cost. R2 zeroes that line item
out and keeps the S3 API surface so we can reuse `boto3`/`aiobotocore` in
`app/storage/backends/cloud.py`.

---

## Bucket Specification

Bucket configuration to apply when provisioning:

```yaml
name: timepoint-flash-renders
location_hint: auto              # Or WNAM if forced to choose
public_read: true                # Enable "Public Bucket" or attach custom domain
default_object_acl: public-read  # Mirrors public bucket setting
versioning: disabled             # We do not need versioning; soft-delete is handled in code via .trash/ prefix
lifecycle_rules:
  - prefix: timepoints/.trash/
    expire_after_days: 30        # Hard-delete soft-deleted blobs after 30 days
cors:
  - allowed_origins:
      - https://timepointai.com
      - https://*.timepointai.com
      - https://flash.timepointai.com
      - https://belle.timepointai.com
      - http://localhost:3000      # Dev only — remove if security review objects
    allowed_methods: [GET, HEAD]
    allowed_headers: ["*"]
    max_age_seconds: 3600
```

### Object key layout

Object keys mirror the local layout produced by
[`app/storage/naming.generate_folder_path`](../app/storage/naming.py):

```
timepoints/2026/04/alan-turing-breaks-enigma_20260209_d46138/image.png
timepoints/2026/04/alan-turing-breaks-enigma_20260209_d46138/scene.json
timepoints/2026/04/alan-turing-breaks-enigma_20260209_d46138/manifest.json
timepoints/2026/04/alan-turing-breaks-enigma_20260209_d46138/index.html
...
```

The leading `timepoints/` prefix is implicit when `BLOB_STORAGE_ROOT` is
`./output/timepoints` locally; in R2 we drop the `./output/` and use
`timepoints/` as the bucket-level prefix so we have headroom for future
asset types (`avatars/`, `thumbnails/`, etc.) under the same bucket.

---

## Environment Variables

Set on the **`timepoint-flash-deploy-private-feb-2026`** service on Railway,
**production environment** only. Do **not** put real credentials in
`.env.example` — only the placeholders below.

| Variable                 | Required when           | Example                                          | Purpose                                                                |
| ------------------------ | ----------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- |
| `BLOB_STORAGE_ENABLED`   | always                  | `true`                                           | Master switch — already wired to `app.storage.config.StorageConfig`.    |
| `BLOB_STORAGE_BACKEND`   | when cloud is desired   | `cloud`                                          | New: selects `local` (default) or `cloud`. See [Migration Path](#migration-path). |
| `FLASH_BLOB_BUCKET`      | cloud backend           | `timepoint-flash-renders`                        | R2 bucket name.                                                         |
| `FLASH_BLOB_ENDPOINT`    | cloud backend           | `https://<account-id>.r2.cloudflarestorage.com`  | R2 S3-compatible endpoint. Per-account host (no region in path).        |
| `FLASH_BLOB_ACCESS_KEY`  | cloud backend           | `<32-char R2 access key id>`                     | R2 token Access Key ID. Scope: bucket-only Read+Write.                  |
| `FLASH_BLOB_SECRET`      | cloud backend           | `<64-char R2 secret>`                            | R2 token Secret. Mark as Railway "secret" so it's masked in the UI.     |
| `FLASH_BLOB_PUBLIC_BASE` | cloud backend           | `https://renders.timepointai.com` *(or)* `https://pub-<hash>.r2.dev` | Public URL prefix used to build `image_url` from object keys. Custom domain preferred for stable URLs. |
| `FLASH_BLOB_REGION`      | optional                | `auto`                                           | S3 SDK region string. R2 uses `auto`; some SDKs require a non-empty value. |

### Local dev defaults

For local dev, leave `BLOB_STORAGE_BACKEND` unset (or `local`). The
`FLASH_BLOB_*` vars are unused unless `BLOB_STORAGE_BACKEND=cloud`. If a
developer wants to test against R2 from their laptop, request a separate
`timepoint-flash-renders-dev` bucket + scoped key — never reuse prod
credentials locally.

### Add to `.env.railway.example`

Append to `timepoint-flash-deploy-private-feb-2026/.env.railway.example`
once provisioning is done (placeholder values only — do not commit live
keys):

```dotenv
# === Blob storage (cloud) ===
BLOB_STORAGE_ENABLED=true
BLOB_STORAGE_BACKEND=cloud
FLASH_BLOB_BUCKET=timepoint-flash-renders
FLASH_BLOB_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
FLASH_BLOB_ACCESS_KEY=
FLASH_BLOB_SECRET=
FLASH_BLOB_PUBLIC_BASE=https://renders.timepointai.com
FLASH_BLOB_REGION=auto
```

---

## Provisioning Runbook

These steps require Sean's Cloudflare and Railway dashboard access. The
worker (infra-ops) cannot execute them — escalate via
`sf message send --to el-2owx` referencing task el-5bkwk.

### 1. Create the R2 bucket (Cloudflare dashboard)

1. Cloudflare → **R2** → **Create bucket**.
2. Name: `timepoint-flash-renders`.
3. Location: `Automatic` (default).
4. Click **Create bucket**.

### 2. Enable public access

Pick **one** of the two options below:

**Option A — Quick (R2.dev subdomain):**

1. Bucket → **Settings** → **Public access** → **Allow Access via R2.dev subdomain**.
2. Cloudflare assigns a host like `pub-<hash>.r2.dev`. Use that as
   `FLASH_BLOB_PUBLIC_BASE`.
3. Note: r2.dev URLs are rate-limited and discouraged for high-traffic prod.
   Treat as launch-day stopgap; migrate to Option B inside the first week.

**Option B — Custom domain (recommended for prod):**

1. Bucket → **Settings** → **Custom Domains** → **Connect Domain**.
2. Use `renders.timepointai.com` (or similar). Cloudflare DNS for
   `timepointai.com` already lives in our account, so it auto-creates the
   CNAME.
3. Wait for SSL provisioning (usually <5 min).
4. Use `https://renders.timepointai.com` as `FLASH_BLOB_PUBLIC_BASE`.

### 3. Apply CORS + lifecycle config

1. Bucket → **Settings** → **CORS Policy** → paste the JSON form of the
   YAML in [Bucket Specification](#bucket-specification) (Cloudflare expects
   a JSON array — the dashboard has a "Add CORS policy" form).
2. Bucket → **Settings** → **Object lifecycle rules** → **Add rule**:
   - Prefix: `timepoints/.trash/`
   - Action: Delete objects 30 days after creation.

### 4. Create scoped API token

1. R2 → **Manage R2 API Tokens** → **Create API Token**.
2. Permissions: **Object Read & Write**.
3. Specify bucket: `timepoint-flash-renders` only.
4. TTL: no expiry (rotate manually) **or** 1 year — whichever matches
   security policy.
5. Copy the **Access Key ID** and **Secret Access Key** *immediately* — the
   secret is shown once.
6. Note the **S3 endpoint** shown on the same screen
   (`https://<account-id>.r2.cloudflarestorage.com`).

### 5. Set Railway env vars

Railway dashboard → project containing
`timepoint-flash-deploy-private-feb-2026` → **production** environment →
service → **Variables** → **Raw editor**, append:

```dotenv
BLOB_STORAGE_ENABLED=true
BLOB_STORAGE_BACKEND=cloud
FLASH_BLOB_BUCKET=timepoint-flash-renders
FLASH_BLOB_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
FLASH_BLOB_ACCESS_KEY=<paste from step 4>
FLASH_BLOB_SECRET=<paste from step 4>
FLASH_BLOB_PUBLIC_BASE=https://renders.timepointai.com
FLASH_BLOB_REGION=auto
```

Mark `FLASH_BLOB_SECRET` as **Sealed/Secret** in Railway so the value is
masked in the UI and not exposed in build logs.

Trigger a redeploy if Railway does not auto-restart on env change.

> **Important:** until the cloud backend is implemented (see [Migration
> Path](#migration-path)), setting `BLOB_STORAGE_BACKEND=cloud` will raise
> `NotImplementedError` from `CloudStorageBackend`. Either leave
> `BLOB_STORAGE_BACKEND` unset until the backend lands, or implement the
> backend first and provision second. Recommended order:
>
> 1. Provision bucket + token (steps 1–4 above).
> 2. Implement R2-backed `CloudStorageBackend` (separate task — J-2 or
>    similar).
> 3. Set Railway env vars including `BLOB_STORAGE_BACKEND=cloud`.

### 6. Verify

From a laptop with the same credentials in `~/.aws/credentials` (profile
`r2-flash`) or via env vars:

```bash
# Smoke-test: write/read/delete via S3 API
aws --profile r2-flash --endpoint-url "$FLASH_BLOB_ENDPOINT" \
    s3 cp /tmp/hello.txt "s3://timepoint-flash-renders/_smoke/hello.txt"

aws --profile r2-flash --endpoint-url "$FLASH_BLOB_ENDPOINT" \
    s3 ls "s3://timepoint-flash-renders/_smoke/"

# Public read (no auth) — only works if step 2 succeeded
curl -fsS "${FLASH_BLOB_PUBLIC_BASE}/_smoke/hello.txt"

# Cleanup
aws --profile r2-flash --endpoint-url "$FLASH_BLOB_ENDPOINT" \
    s3 rm "s3://timepoint-flash-renders/_smoke/hello.txt"
```

All four commands must succeed before declaring the bucket production-ready.

---

## Migration Path

The [`CloudStorageBackend`](../app/storage/backends/cloud.py) is currently a
stub that raises `NotImplementedError`. To go live on R2, a follow-up task
must:

1. Implement `CloudStorageBackend` using `aioboto3`/`aiobotocore` with
   endpoint, bucket, and credentials sourced from the `FLASH_BLOB_*` env
   vars.
2. Extend `StorageConfig` (in `app/storage/config.py`) with a `backend` field
   (`local` | `cloud`) and read `BLOB_STORAGE_BACKEND` from settings.
3. Update `StorageService.from_config` to dispatch to the right backend.
4. Set `Timepoint.image_url` to `f"{FLASH_BLOB_PUBLIC_BASE}/{key}"` when the
   cloud backend is active so consumers get a working URL without an extra
   indirection through the API.
5. Add an integration test that round-trips a small object through R2 in
   CI (gated on the presence of `FLASH_BLOB_ACCESS_KEY` so the public-repo
   CI skips it).

The `local` backend remains the default and the only option in the public
open-source repo unless contributors opt in by setting the env vars.

---

## Operational Notes

- **No private data in this bucket.** Public read is enabled. Anything
  written here is world-readable — do **not** put PII, prompts containing
  user data, or anything not safe for `<img src>` consumption. JSON
  sidecars (`scene.json`, `dialog.json`, etc.) are public-grade by design.
- **Soft delete uses prefix moves.** `StorageService.delete_blob(soft=True)`
  moves objects to `timepoints/.trash/<date>/<folder>/`. The lifecycle rule
  hard-deletes after 30 days. There is no R2-side versioning to roll back
  beyond that window.
- **Cost guardrails.** R2's free tier is generous (10 GB storage,
  1M Class-A ops/month, 10M Class-B ops/month). Belle traffic should fit
  inside the free tier for the foreseeable future. Monitor via Cloudflare
  → R2 → Metrics. Set a billing alert at $5/mo as an early-warning.
- **Key rotation.** Rotate `FLASH_BLOB_SECRET` annually or on suspicion of
  compromise. Procedure: create a new token, swap in Railway, redeploy,
  delete the old token from Cloudflare.

---

*Last updated: 2026-04-28 (task el-5bkwk).*
