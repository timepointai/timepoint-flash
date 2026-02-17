# Deployment

Three ways to run TIMEPOINT Flash: local development, Railway (recommended), or Docker.

---

## Local Development

```bash
git clone https://github.com/realityinspector/timepoint-flash-deploy.git
cd timepoint-flash-deploy
pip install -e .
cp .env.example .env    # Add your API keys
alembic upgrade head     # Run database migrations
./run.sh -r              # Start with auto-reload on port 8000
```

Swagger docs at `http://localhost:8000/docs`

---

## Railway (Recommended)

Railway auto-detects the `Dockerfile` and deploys with PostgreSQL, health checks, and CI gating.

### Setup

1. **Create a Railway project** → connect your GitHub repo
2. **Add PostgreSQL plugin** (Railway dashboard → Add Plugin → PostgreSQL)
3. **Set environment variables** (see `.env.railway.example`):

   | Variable | Required | Source |
   |----------|----------|--------|
   | `DATABASE_URL` | Auto | `${{Postgres.DATABASE_URL}}` (reference from plugin) |
   | `GOOGLE_API_KEY` | Yes | [aistudio.google.com](https://aistudio.google.com) (free) |
   | `OPENROUTER_API_KEY` | No | [openrouter.ai](https://openrouter.ai) (enables hyper/gemini3 presets) |
   | `ENVIRONMENT` | No | `development` or `production` |
   | `AUTH_ENABLED` | No | `false` (default) or `true` for iOS app mode |
   | `JWT_SECRET_KEY` | If auth | `openssl rand -hex 32` |
   | `ADMIN_API_KEY` | No | Secret key for dev admin endpoints |
   | `CORS_ORIGINS` | No | Comma-separated allowed origins |
   | `SHARE_URL_BASE` | No | Base URL for share links (e.g. `https://timepointai.com/t`) |

4. **Deploy** — push to your connected branch. Railway builds the Dockerfile and deploys. Migrations run automatically at container startup (via Dockerfile CMD).

### How It Works

- `Dockerfile` — multi-stage build (builder + slim runtime)
- `railway.json` — config-as-code (builder, health check, restart policy)
- Alembic migrations run at container startup (inside Dockerfile CMD, not a pre-deploy command)
- Health check at `/health` — Railway restarts unhealthy containers
- Restart policy: ON_FAILURE with 3 retries

### Branch Mapping

| Branch | Environment | Auto-deploy |
|--------|-------------|-------------|
| `main` | Production | Yes (with "Wait for CI") |
| `develop` | Development | Yes |

### Verify

```bash
curl https://your-app.up.railway.app/health
# → {"status":"healthy","version":"2.4.0","database":true,"providers":{"google":true,"openrouter":true}}
```

### Generate a Scene

```bash
curl -X POST https://your-app.up.railway.app/api/v1/timepoints/generate/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "Alan Turing breaks Enigma at Bletchley Park Hut 8, winter 1941", "preset": "balanced", "generate_image": true}'
```

### Post-Deploy Smoke Test

Run the smoke test workflow manually from GitHub Actions:

```bash
gh workflow run smoke.yml -f target_url=https://your-app.up.railway.app
```

---

## Docker (Local or Custom Deploy)

The repo includes a production-ready multi-stage `Dockerfile`:

```bash
# Build
docker build -t timepoint-flash .

# Run with SQLite (local testing)
docker run -p 8080:8080 \
  -e DATABASE_URL=sqlite+aiosqlite:///./timepoint.db \
  -e GOOGLE_API_KEY=your-key \
  timepoint-flash

# Run with PostgreSQL (production)
docker run -p 8080:8080 \
  -e DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/timepoint \
  -e ENVIRONMENT=production \
  -e GOOGLE_API_KEY=your-key \
  timepoint-flash
```

### Environment Variables

See `.env.railway.example` for the full list. Key variables:

```bash
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/timepoint
GOOGLE_API_KEY=your-key
ENVIRONMENT=production
AUTH_ENABLED=false       # Set true for iOS app mode
BLOB_STORAGE_ENABLED=true
CORS_ORIGINS=https://your-domain.com
SHARE_URL_BASE=https://timepointai.com/t   # Optional: enables share_url in responses
```

> **Note:** `AUTH_ENABLED=false` is the default. All endpoints remain open-access. Set `AUTH_ENABLED=true` only when deploying for the iOS app.

### Manual Run (without Docker)

```bash
pip install -e .
alembic upgrade head
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

---

## Billing

The open-source app ships with `NoOpBilling` — all credit checks pass and access is unlimited. The `BillingProvider` protocol in `app/services/billing.py` provides hooks for custom billing integrations.

The deployed version (`timepoint-flash-deploy`) uses a separate billing microservice (`timepoint-billing`) that handles Apple IAP and Stripe payments as its own Railway service with its own PostgreSQL database. The main app proxies billing requests and exposes an internal credits API for the billing service to grant/spend credits after purchases.

---

## Blob Storage

When `BLOB_STORAGE_ENABLED=true`, each generation writes a self-contained folder:

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

---

*Last updated: 2026-02-17*
