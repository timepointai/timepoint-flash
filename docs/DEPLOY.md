# Deployment

Two ways to run the open-source TIMEPOINT Flash: **local development** or **your own Railway/PaaS deployment via NIXPACKS** (Python detected from `pyproject.toml`).

> **Note on the live `flash.timepointai.com` service.** The production deployment runs from a private fork (`timepoint-flash-deploy-private-feb-2026`) that adds the billing microservice, Cloudflare R2 blob storage backend, and request-signing checks. This open-source repo is the upstream reference implementation — it ships with `NoOpBilling` (unlimited access) and the `local` blob backend (writes to disk). Provisioning steps for the private deployment live in [STORAGE.md](./STORAGE.md) and the private deploy repo's own runbook.

---

## Local Development

```bash
git clone https://github.com/timepointai/timepoint-flash.git
cd timepoint-flash
pip install -e .
cp .env.example .env    # Add your API keys
alembic upgrade head     # Run database migrations
./run.sh -r              # Start with auto-reload on port 8000
```

Swagger docs at `http://localhost:8000/docs`

---

## Railway via NIXPACKS

Railway will detect `pyproject.toml` and build with NIXPACKS automatically — no `Dockerfile` or `railway.json` is required in this repo.

### Setup

1. **Create a Railway project** → connect your GitHub fork
2. **Add a PostgreSQL plugin** (Railway dashboard → Add Plugin → PostgreSQL)
3. **Set environment variables**:

   | Variable | Required | Source |
   |----------|----------|--------|
   | `DATABASE_URL` | Auto | `${{Postgres.DATABASE_URL}}` (reference from plugin) |
   | `GOOGLE_API_KEY` | Yes | [aistudio.google.com](https://aistudio.google.com) (free) |
   | `OPENROUTER_API_KEY` | No | [openrouter.ai](https://openrouter.ai) (enables hyper/gemini3 presets) |
   | `ENVIRONMENT` | No | `development` or `production` |
   | `AUTH_ENABLED` | No | `false` (default) or `true` for iOS app mode |
   | `JWT_SECRET_KEY` | If auth | `openssl rand -hex 32` |
   | `ADMIN_API_KEY` | No | Secret key for dev admin endpoints |
   | `FLASH_SERVICE_KEY` | No | Shared secret for service-to-service auth via `X-Service-Key` header. Required when Flash is called by billing or clockchain. Empty = service-key auth disabled. |
   | `CORS_ENABLED` | No | `true` (default) or `false` — disable CORS when Flash is internal-only (no browser callers) |
   | `CORS_ORIGINS` | No | Comma-separated allowed origins |
   | `SHARE_URL_BASE` | No | Base URL for share links (e.g. `https://timepointai.com/t`) |

4. **Set the start command** in Railway → service → Settings → Deploy:

   ```bash
   alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
   ```

5. **Deploy** — push to your connected branch. Railway builds via NIXPACKS and deploys.

### How It Works

- NIXPACKS reads `pyproject.toml` and provisions a Python 3.11+ environment
- The Railway start command runs Alembic migrations, then `uvicorn`
- Health check at `/health` — Railway restarts unhealthy containers
- Recommended restart policy: ON_FAILURE with 3 retries

### Verify

```bash
curl https://your-domain.example.com/health
# → {"status":"healthy","version":"2.4.0","database":true,"providers":{"google":true,"openrouter":true}}
```

### Generate a Scene

```bash
curl -X POST https://your-domain.example.com/api/v1/timepoints/generate/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "Alan Turing breaks Enigma at Bletchley Park Hut 8, winter 1941", "preset": "balanced", "generate_image": true}'
```

---

## Manual Run (any host)

```bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

### Environment Variables

See `.env.example` for the full list. Key variables:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/timepoint
GOOGLE_API_KEY=your-key
ENVIRONMENT=production
AUTH_ENABLED=false       # Set true for iOS app mode
BLOB_STORAGE_ENABLED=true
CORS_ORIGINS=https://your-domain.com
SHARE_URL_BASE=https://timepointai.com/t   # Optional: enables share_url in responses
```

> **Note:** `AUTH_ENABLED=false` is the default. All endpoints remain open-access. Set `AUTH_ENABLED=true` only when deploying for the iOS app or other authenticated client.

---

## Service-to-Service Auth

When Flash is deployed as an internal service (behind billing or clockchain), set `FLASH_SERVICE_KEY` to a shared secret. Other services include this in the `X-Service-Key` header when calling Flash.

For the production gateway path, also set `GATEWAY_SIGNING_SECRET` so the API Gateway can HMAC-sign requests. See [API.md → Service-to-Service Auth](./API.md#service-to-service-auth) for the full signature scheme.

Three auth paths are evaluated in order:
1. **Signed Gateway request** (`X-Gateway-Signature` + optional `X-User-Id`) — preferred path for the production deployment
2. **Legacy service key** (`X-Service-Key` only) — system calls without user context
3. **Bearer JWT** — direct user auth (iOS app)

Set `CORS_ENABLED=false` when Flash is internal-only and never called from browsers.

---

## Billing

The open-source app ships with `NoOpBilling` — all credit checks pass and access is unlimited. The `BillingProvider` protocol in `app/services/billing.py` provides hooks for custom billing integrations.

The deployed version uses a separate billing microservice that handles Apple IAP and Stripe payments as its own service with its own PostgreSQL database. The main app proxies billing requests and exposes an internal credits API for the billing service to grant/spend credits after purchases.

---

## Blob Storage

> For the production cloud-storage decision (Cloudflare R2), env-var spec, and provisioning runbook, see [STORAGE.md](./STORAGE.md).

When `BLOB_STORAGE_ENABLED=true` and `BLOB_STORAGE_BACKEND=local` (default in this repo), each generation writes a self-contained folder:

```
output/timepoints/2026/02/
└── alan-turing-breaks-enigma_20260209_d46138/
    ├── image.png              # Generated image
    ├── metadata.json          # Scene, characters, dialog
    ├── generation_log.json    # Step timings, models used
    ├── manifest.json          # File inventory with SHA256 hashes
    └── index.html             # Self-contained viewer (dark theme)
```

Each folder is portable — copy it anywhere and open `index.html` to view the complete scene.

The `cloud` backend (Cloudflare R2 via S3 API) is implemented in the private deploy repo. The open-source `CloudStorageBackend` stub raises `NotImplementedError` by design — contributors who want R2 must implement the backend per the steps in [STORAGE.md → Migration Path](./STORAGE.md#migration-path).

---

*Last updated: 2026-05-18*
