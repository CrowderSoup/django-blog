# Deployment Guide (Docker + GHCR)

This guide covers deploying Webstead with the published GHCR image and a Docker Compose stack that includes Postgres and MinIO. It also calls out gaps discovered while writing this guide so we can harden the deployment story.

> Webstead is alpha software. Expect breaking changes and data loss risks.

---

## Prerequisites

- Docker + Docker Compose
- A domain name (if deploying publicly)
- A reverse proxy with TLS (Caddy, Nginx, Traefik, etc.)

---

## 1) Create a deployment directory

Create a fresh folder (not this repo) for your deployment assets:

```
webstead-deploy/
  docker-compose.yml
  .env
```

---

## 2) Create a `.env` file

Use this as a starting point. Update passwords and hostnames.

```env
# Core
DEBUG=False
SECRET_KEY="change-me-to-a-long-random-string"

# Hosts (required when DEBUG=False)
ALLOWED_HOSTS=example.com,.example.com
CSRF_TRUSTED_ORIGINS=https://example.com

# Database (points at the compose service name)
DB_NAME=webstead
DB_USER=webstead
DB_PASS=webstead
DB_HOST=postgres
DB_PORT=5432

# S3/MinIO storage
AWS_ACCESS_KEY_ID=minio
AWS_SECRET_ACCESS_KEY=minio12345
AWS_STORAGE_BUCKET_NAME=webstead
# For public deployments, set this to the public URL for your S3/MinIO endpoint.
AWS_S3_ENDPOINT_URL=http://minio:9000
AWS_S3_REGION_NAME=us-east-1
# Optional (use a CDN or public domain for bucket access)
# AWS_S3_CUSTOM_DOMAIN=cdn.example.com

# Optional services
AKISMET_API_KEY=
TURNSTILE_SITE_KEY=
TURNSTILE_SECRET_KEY=
```

Notes:

- `SECRET_KEY` must be unique and kept private.
- `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` are required when `DEBUG=False`.
- The MinIO bucket must exist before `collectstatic` runs.
- `AWS_S3_ENDPOINT_URL` is also used in public media URLs; set it to a public domain if you expect users to load assets from the internet.

---

## 3) Create `docker-compose.yml`

This compose file runs Postgres, MinIO, and Webstead (from GHCR).

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: webstead
      POSTGRES_USER: webstead
      POSTGRES_PASSWORD: webstead
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB"]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  minio:
    image: quay.io/minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minio
      MINIO_ROOT_PASSWORD: minio12345
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000" # S3 API (optional)
      - "9001:9001" # MinIO console (optional)
    healthcheck:
      test:
        [
          "CMD-SHELL",
          "wget -qO- http://localhost:9000/minio/health/ready || exit 1"
        ]
      interval: 5s
      timeout: 3s
      retries: 20
    restart: unless-stopped

  webstead:
    image: ghcr.io/crowdersoup/webstead:latest
    env_file:
      - .env
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      minio:
        condition: service_healthy
    restart: unless-stopped

volumes:
  db_data:
  minio_data:
```

Image tags:

- `ghcr.io/crowdersoup/webstead:latest` (main branch)
- `ghcr.io/crowdersoup/webstead:main` or `:dev` (branch tags)
- `ghcr.io/crowdersoup/webstead:<short-sha>` (pinned builds)

---

## 4) Start the stack

From your deployment directory:

```
docker compose up -d
```

Health checks:

- The container now binds to `PORT` (falling back to `8000`), which is required by many PaaS providers.
- Use `/healthz` as the HTTP health check path for a lightweight readiness probe.

---

## 5) Automatic bucket creation + collectstatic

On container startup, Webstead will:

- wait for the database
- run migrations
- create the S3/MinIO bucket (if missing)
- apply a public-read bucket policy (optional)
- run `collectstatic`

You can tune this behavior via environment variables:

```env
# Startup behavior (defaults shown)
DB_WAIT=true
DB_WAIT_TIMEOUT=60
DB_WAIT_INTERVAL=2
COLLECTSTATIC=true
STORAGE_BOOTSTRAP=true
STORAGE_BOOTSTRAP_BUCKET=true
STORAGE_BOOTSTRAP_POLICY=true
STORAGE_BUCKET_PUBLIC_READ=true
```

---

## 7) Create a Django superuser

```
docker compose exec webstead uv run manage.py createsuperuser
```

Log in at `http://<your-host>/admin`.

---

## Reverse proxy + TLS example

Webstead expects `X-Forwarded-Proto` and `X-Forwarded-Host` to be set correctly by your proxy.
Below are minimal examples you can adapt.

### Caddy (recommended)

```
example.com {
  encode gzip zstd
  reverse_proxy webstead:8000
}
```

### Nginx

```
server {
  listen 80;
  server_name example.com;

  location / {
    proxy_pass http://webstead:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
  }
}
```

When running behind a proxy, set:

- `ALLOWED_HOSTS=example.com,.example.com`
- `CSRF_TRUSTED_ORIGINS=https://example.com`

---

## Configuration reference

Required in production:

- `DEBUG=False`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_NAME`, `DB_USER`, `DB_PASS`, `DB_HOST`, `DB_PORT`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_ENDPOINT_URL`, `AWS_S3_REGION_NAME`

Optional:

- `AWS_S3_CUSTOM_DOMAIN`
- `AKISMET_API_KEY`
- `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY`

---

## Deployment readiness notes

As of this guide, the container startup flow handles DB wait, migrations,
bucket bootstrap, and `collectstatic`. If you need to disable any of those,
use the startup environment variables in step 5.
