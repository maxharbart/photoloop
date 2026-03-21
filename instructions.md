# Photo Service — Coding Agent Instructions

## Project overview

Build a self-hosted web service that provides browser-based access to photos stored on a Samba share. The service supports multiple independent projects (each backed by a different source folder), per-project authentication, photo browsing in chronological order, album management, and EXIF metadata editing (date, GPS location).

---

## Constraints and non-negotiables

- All services run in Docker Compose. No host-level dependencies beyond Docker and cifs-utils.
- Samba share is mounted on the host via cifs-utils and passed into containers as a bind volume.
- No external cloud services. Everything runs locally.
- Python 3.12+ for all backend code.
- Use async SQLAlchemy with asyncpg driver throughout.
- All API endpoints must be covered by pytest tests (at minimum happy-path + auth failure).

---

## Project structure

```
photo-service/
├── docker-compose.yml
├── docker-compose.override.yml          # dev overrides (hot-reload, exposed ports)
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models/
│   │   │   ├── user.py
│   │   │   ├── project.py
│   │   │   ├── photo.py
│   │   │   └── album.py
│   │   ├── routers/
│   │   │   ├── auth.py
│   │   │   ├── projects.py
│   │   │   ├── photos.py
│   │   │   ├── albums.py
│   │   │   └── metadata.py
│   │   ├── services/
│   │   │   ├── scanner.py
│   │   │   ├── thumbnailer.py
│   │   │   └── exif.py
│   │   ├── tasks/
│   │   │   └── celery_app.py
│   │   └── schemas/
│   │       ├── auth.py
│   │       ├── project.py
│   │       ├── photo.py
│   │       └── album.py
│   └── tests/
│       ├── conftest.py
│       └── test_*.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
└── nginx/
    └── nginx.conf
```

---

## docker-compose.yml

```yaml
version: "3.9"

services:

  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-photos}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?required}
      POSTGRES_DB: ${POSTGRES_DB:-photos}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-photos}"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-photos}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB:-photos}
      REDIS_URL: redis://redis:6379/0
      MEDIA_ROOT: /media
      THUMBS_ROOT: /thumbs
      SECRET_KEY: ${SECRET_KEY:?required}
    volumes:
      - ${SAMBA_MOUNT_PATH:?required}:/media:ro
      - thumbs_data:/thumbs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-photos}:${POSTGRES_PASSWORD}@postgres/${POSTGRES_DB:-photos}
      REDIS_URL: redis://redis:6379/0
      MEDIA_ROOT: /media
      THUMBS_ROOT: /thumbs
      SECRET_KEY: ${SECRET_KEY:?required}
    volumes:
      - ${SAMBA_MOUNT_PATH:?required}:/media:ro
      - thumbs_data:/thumbs
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    command: celery -A app.tasks.celery_app worker --loglevel=info --concurrency=2

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    environment:
      NEXT_PUBLIC_API_URL: /api

  nginx:
    image: nginx:1.25-alpine
    restart: unless-stopped
    ports:
      - "${HTTP_PORT:-80}:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - thumbs_data:/thumbs:ro
    depends_on:
      - backend
      - frontend

volumes:
  postgres_data:
  redis_data:
  thumbs_data:
```

### .env.example

```
POSTGRES_PASSWORD=changeme
SECRET_KEY=generate-with-openssl-rand-hex-32
SAMBA_MOUNT_PATH=/mnt/photos        # host path where samba share is already mounted
HTTP_PORT=80
```

### Samba mount (host, one-time setup)

```bash
sudo apt install cifs-utils
sudo mkdir -p /mnt/photos
# Add to /etc/fstab:
# //NAS_IP/share /mnt/photos cifs credentials=/etc/samba/creds,uid=1000,gid=1000,iocharset=utf8 0 0
sudo mount -a
```

---

## Database schema

Implement these SQLAlchemy models (async, mapped columns style).

### `users`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| username | varchar(64) unique | |
| hashed_password | varchar(256) | bcrypt via passlib |
| is_superuser | boolean | default false |
| created_at | timestamptz | server default now() |

### `projects`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| slug | varchar(64) unique | URL-safe identifier |
| name | varchar(256) | display name |
| source_path | varchar(1024) | path relative to MEDIA_ROOT |
| description | text | nullable |
| created_at | timestamptz | |

### `project_members`
| column | type | notes |
|---|---|---|
| project_id | UUID FK → projects | |
| user_id | UUID FK → users | |
| role | varchar(16) | `owner` or `viewer` |

### `photos`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| relative_path | varchar(2048) | path relative to project source_path |
| filename | varchar(512) | |
| taken_at | timestamptz | from EXIF or file mtime |
| gps_lat | float8 | nullable |
| gps_lon | float8 | nullable |
| location_name | varchar(512) | nullable, reverse-geocoded |
| width | int | |
| height | int | |
| file_size | int8 | bytes |
| thumb_sm | varchar(512) | relative path to 320px thumb |
| thumb_md | varchar(512) | relative path to 800px thumb |
| indexed_at | timestamptz | |

### `albums`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| project_id | UUID FK → projects | |
| name | varchar(256) | |
| description | text | nullable |
| cover_photo_id | UUID FK → photos | nullable |
| created_at | timestamptz | |

### `album_photos`
| column | type | notes |
|---|---|---|
| album_id | UUID FK → albums | |
| photo_id | UUID FK → photos | |
| sort_order | int | default 0 |

---

## Backend implementation

### `app/config.py`

Use `pydantic-settings`. Fields: `DATABASE_URL`, `REDIS_URL`, `MEDIA_ROOT`, `THUMBS_ROOT`, `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60), `ALGORITHM` (default `HS256`).

### `app/main.py`

- Include all routers under `/api` prefix
- Add CORS middleware allowing frontend origin
- On startup: create thumbs directory if not exists
- Mount `/thumbs` as a StaticFiles route for serving thumbnails directly

### Auth (`routers/auth.py`)

- `POST /api/auth/login` — accepts `username` + `password` (form data), returns `{ access_token, token_type }` JWT
- `POST /api/auth/register` — superuser-only endpoint to create new users
- JWT payload: `{ sub: user_id, exp }`
- Dependency `get_current_user` → inject into protected routes
- Project-level access check dependency: `require_project_member(project_id)` → verifies the current user is in `project_members` for that project, or is superuser

### Projects (`routers/projects.py`)

- `GET /api/projects` — list projects the current user is a member of
- `POST /api/projects` — superuser only; body: `{ slug, name, source_path, description }`
- `GET /api/projects/{slug}` — project detail; requires membership
- `PUT /api/projects/{slug}` — update name/description/source_path; owner or superuser
- `POST /api/projects/{slug}/members` — add user to project; owner or superuser
- `DELETE /api/projects/{slug}/members/{user_id}` — remove member

### Photos (`routers/photos.py`)

- `GET /api/projects/{slug}/photos` — paginated list, sorted by `taken_at` ascending by default
  - Query params: `page`, `page_size` (max 100), `sort` (`asc`/`desc`), `album_id`
  - Response includes `thumb_sm_url`, `thumb_md_url` computed from thumb paths
- `GET /api/projects/{slug}/photos/{photo_id}` — single photo detail
- `POST /api/projects/{slug}/scan` — trigger a background scan of the source folder (enqueue Celery task); owner or superuser only
  - Returns `{ task_id }` immediately
- `GET /api/projects/{slug}/scan/{task_id}` — poll scan task status

### Albums (`routers/albums.py`)

- `GET /api/projects/{slug}/albums` — list albums
- `POST /api/projects/{slug}/albums` — create album; body `{ name, description }`
- `GET /api/projects/{slug}/albums/{album_id}` — album detail with photo list
- `PUT /api/projects/{slug}/albums/{album_id}` — update name/description/cover
- `DELETE /api/projects/{slug}/albums/{album_id}`
- `POST /api/projects/{slug}/albums/{album_id}/photos` — add photos to album; body `{ photo_ids: [uuid] }`
- `DELETE /api/projects/{slug}/albums/{album_id}/photos/{photo_id}` — remove from album
- `PUT /api/projects/{slug}/albums/{album_id}/photos/order` — reorder; body `{ photo_ids: [uuid] }` (ordered list)

### Metadata (`routers/metadata.py`)

- `PATCH /api/projects/{slug}/photos/{photo_id}/metadata` — edit metadata
  - Body: `{ taken_at?: ISO8601, gps_lat?: float, gps_lon?: float }`
  - After DB update, enqueue Celery task to write changes back to the physical file's EXIF
  - If `gps_lat`/`gps_lon` provided and `location_name` not provided, trigger reverse geocoding

### Scanner service (`services/scanner.py`)

Implement `scan_project(project_id, source_path)` as a Celery task:

1. Walk the directory tree under `MEDIA_ROOT / source_path` recursively
2. Collect files with extensions: `.jpg .jpeg .png .tiff .tif .heic .heif .webp`
3. For each file:
   a. Compute relative path from source_path
   b. Check if already in DB (by relative_path); skip if `indexed_at` is recent (< 1 day) and file mtime unchanged
   c. Open with Pillow to get `width`, `height`
   d. Extract EXIF via `piexif`: `taken_at` from `DateTimeOriginal`, GPS from `GPSInfo`
   e. Fall back to file `mtime` if no EXIF date
   f. Upsert the `photos` record
   g. Enqueue thumbnail generation task
4. Delete DB records for files that no longer exist on disk
5. Use `asyncio.to_thread` for file I/O inside the async context; the Celery task itself runs sync but calls an async helper via `asyncio.run()`

### Thumbnailer service (`services/thumbnailer.py`)

Implement `generate_thumbnails(photo_id)` as a Celery task:

1. Load photo from DB, get full path
2. Open with Pillow, apply EXIF orientation via `ImageOps.exif_transpose`
3. Generate two sizes:
   - `sm`: fit within 320×320, JPEG quality 75
   - `md`: fit within 800×800, JPEG quality 82
4. Save to `THUMBS_ROOT/{project_id}/{photo_id}_sm.jpg` and `_md.jpg`
5. Update `thumb_sm` and `thumb_md` columns in DB

### EXIF service (`services/exif.py`)

Implement `write_metadata_to_file(photo_id)` as a Celery task:

1. Load photo + metadata from DB
2. Read existing EXIF with `piexif.load()`
3. Update `Exif.DateTimeOriginal` and `GPS` IFD from DB values
4. `piexif.insert(piexif.dump(exif_dict), filepath)` — in-place write
5. For HEIC files: use `pyheif` or skip write (log warning); HEIC EXIF write is fragile

For reverse geocoding: use `geopy` with `Nominatim` user-agent `photo-service`. Cache results in Redis with a 30-day TTL keyed by `geo:{lat:.4f}:{lon:.4f}`.

---

## Frontend implementation

Use **Next.js 14** with App Router and TypeScript. Use **Tailwind CSS** for styling. Use **TanStack Query** for data fetching and caching.

### Pages and components

**`/login`** — login form, stores JWT in httpOnly cookie via a Next.js route handler

**`/projects`** — grid of project cards the user has access to

**`/projects/[slug]`** — main gallery view
- Top bar: project name, scan button (owners), album selector dropdown
- Photo grid: masonry or uniform grid, lazy-loaded thumbnails (`next/image`)
- Sort toggle: oldest first / newest first
- Infinite scroll or pagination
- Clicking a photo opens lightbox

**`/projects/[slug]/albums`** — album list and album creation form

**`/projects/[slug]/albums/[albumId]`** — album detail, same grid layout, drag-to-reorder photos within the album

**Lightbox component**
- Full-size image (use `thumb_md` URL, link to original)
- EXIF panel on the right: date, GPS map pin (use Leaflet.js), location name
- Edit metadata form: date picker, lat/lon inputs with "Pick on map" modal
- Previous/next navigation

**Admin panel** (superuser only, `/admin`)
- Create project form (slug, name, source_path)
- User management: create user, assign to projects

### API client

Create a typed API client in `src/lib/api.ts` using `fetch`. Attach `Authorization: Bearer {token}` header from cookie/store. Handle 401 by redirecting to `/login`.

---

## nginx/nginx.conf

```nginx
events {}

http {
  upstream backend {
    server backend:8000;
  }

  upstream frontend {
    server frontend:3000;
  }

  server {
    listen 80;
    client_max_body_size 50m;

    # Thumbnails served directly — bypasses backend entirely
    location /thumbs/ {
      alias /thumbs/;
      expires 30d;
      add_header Cache-Control "public, immutable";
    }

    # API
    location /api/ {
      proxy_pass http://backend;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_read_timeout 120s;
    }

    # Frontend (catch-all)
    location / {
      proxy_pass http://frontend;
      proxy_set_header Host $host;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection "upgrade";
    }
  }
}
```

---

## backend/Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libheif-dev libjpeg-turbo-progs \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[all]"

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## frontend/Dockerfile

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

---

## Python dependencies (pyproject.toml)

```toml
[project]
name = "photo-service"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.111",
  "uvicorn[standard]>=0.29",
  "sqlalchemy[asyncio]>=2.0",
  "asyncpg>=0.29",
  "alembic>=1.13",
  "pydantic-settings>=2.2",
  "passlib[bcrypt]>=1.7",
  "python-jose[cryptography]>=3.3",
  "python-multipart>=0.0.9",
  "pillow>=10.3",
  "piexif>=1.1",
  "celery[redis]>=5.3",
  "redis>=5.0",
  "geopy>=2.4",
  "pyheif>=0.7",
]

[project.optional-dependencies]
dev = [
  "pytest>=8",
  "pytest-asyncio>=0.23",
  "httpx>=0.27",
  "anyio>=4",
]
```

---

## Frontend dependencies (package.json key packages)

```json
{
  "dependencies": {
    "next": "14",
    "react": "^18",
    "react-dom": "^18",
    "@tanstack/react-query": "^5",
    "tailwindcss": "^3",
    "yet-another-react-lightbox": "^3",
    "leaflet": "^1.9",
    "@types/leaflet": "^1.9",
    "react-datepicker": "^6",
    "date-fns": "^3"
  }
}
```

---

## Tests

Implement at minimum:

- `test_auth.py` — login success, login wrong password, access protected endpoint without token, access with expired token
- `test_projects.py` — create project (superuser), list projects (member sees own, not others), non-member gets 403
- `test_photos.py` — list photos sorted by taken_at, pagination, filter by album
- `test_albums.py` — create album, add photos, reorder, remove photo
- `test_metadata.py` — PATCH metadata updates DB, invalid lat/lon rejected
- `test_scanner.py` — unit test for `scan_project` using a temp directory with synthetic image files

Use `pytest-asyncio` with `asyncio_mode = "auto"`. Use a separate test database (override `DATABASE_URL` in conftest). Use `httpx.AsyncClient` with FastAPI's `ASGITransport` for integration tests — no live server needed.

---

## Implementation order for the agent

Follow this order to avoid blocked dependencies:

1. `docker-compose.yml` + `.env.example` + both Dockerfiles
2. `pyproject.toml` + `nginx/nginx.conf`
3. DB models + Alembic initial migration
4. `config.py` + `database.py`
5. Auth router + JWT utilities + `get_current_user` dependency
6. Projects router + `require_project_member` dependency
7. Scanner service (sync, testable without Celery)
8. Celery app + scanner task wrapper
9. Thumbnailer task
10. Photos router (read-only first, then scan trigger)
11. Albums router
12. EXIF service + metadata router
13. Frontend: API client + auth pages + project list
14. Frontend: gallery page + lightbox
15. Frontend: album management + metadata edit
16. Frontend: admin panel
17. Tests

---

## Key implementation notes

**File serving**: Never proxy original files through FastAPI. Nginx serves thumbnails directly from the shared volume. For original file download, use an `X-Accel-Redirect` header from FastAPI pointing to an internal Nginx location — this avoids loading files into Python memory.

**HEIC support**: `pyheif` requires `libheif` system library. The Dockerfile installs it. Read HEIC with `pyheif.read()` → convert to Pillow Image. EXIF write for HEIC is unreliable; log a warning and skip the write but still update the DB.

**Chronological order**: `taken_at` is the source of truth. When EXIF has no date, fall back to file `mtime`. Make this fallback visible in the UI (e.g., a small "date estimated" badge).

**Large directories**: The scanner should commit to DB in batches of 100 photos to avoid long-running transactions. Use `INSERT ... ON CONFLICT DO UPDATE` (upsert) so re-scans are idempotent.

**GPS coordinates**: EXIF stores GPS as rational numbers `(degrees, minutes, seconds)` each as `(numerator, denominator)` tuples. Write a helper `parse_gps_exif(gps_ifd) -> tuple[float, float]` that converts to decimal degrees. Test this with known coordinates.

**Security**: The `source_path` stored in the DB must be validated against `MEDIA_ROOT` before any file operation to prevent path traversal. Reject any path containing `..` or that resolves outside `MEDIA_ROOT`.

**Scan deduplication**: Only one scan task per project should run at a time. Use a Redis lock: `SET scan:lock:{project_id} 1 NX EX 600` before starting. Release on completion or failure.
