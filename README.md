# PhotoLoop

Self-hosted web service for browsing photos stored on a Samba share. Supports multiple projects, per-project authentication, album management, and EXIF metadata editing.

## Requirements

- Docker and Docker Compose
- A mounted Samba share (or any directory with photos)
- `cifs-utils` (if mounting a Samba share)

## Quick Start

### 1. Mount your photo share (skip if using a local directory)

```bash
sudo apt install cifs-utils
sudo mkdir -p /mnt/photos

# Add to /etc/fstab:
# //NAS_IP/share /mnt/photos cifs credentials=/etc/samba/creds,uid=1000,gid=1000,iocharset=utf8 0 0

sudo mount -a
```

Create your Samba credentials file at `/etc/samba/creds`:

```
username=your_user
password=your_password
```

```bash
sudo chmod 600 /etc/samba/creds
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```
POSTGRES_PASSWORD=<strong-random-password>
SECRET_KEY=<generate-with-command-below>
SAMBA_MOUNT_PATH=/mnt/photos
HTTP_PORT=9473
```

Generate a secret key:

```bash
openssl rand -hex 32
```

### 3. Start the services

```bash
docker compose up -d
```

This starts PostgreSQL, Redis, the backend API, a Celery worker, the Next.js frontend, and Nginx as a reverse proxy.

### 4. Create the first admin user

```bash
docker compose exec backend python -c "
import asyncio
from app.database import async_session
from app.models.user import User
from app.routers.auth import hash_password

async def create_admin():
    async with async_session() as db:
        user = User(
            username='admin',
            hashed_password=hash_password('changeme'),
            is_superuser=True,
        )
        db.add(user)
        await db.commit()
        print('Admin user created.')

asyncio.run(create_admin())
"
```

Change the password after first login.

### 5. Open the app

Navigate to `http://your-server:9473` and sign in with the admin credentials.

From the Admin panel you can:

- Create projects (each pointing to a subfolder of your photo share)
- Create users and assign them to projects

## Usage

### Projects

Each project maps to a folder on your mounted share. After creating a project in the admin panel, click **Scan** on the project page to index all photos. The scanner reads EXIF data (dates, GPS coordinates) and generates thumbnails in the background.

### Albums

Create albums within a project to organize photos into groups. Add or remove photos and reorder them with drag-and-drop.

### Metadata Editing

Click any photo to open the lightbox. From the info panel you can edit:

- **Date/time** taken
- **GPS coordinates** (latitude/longitude)

Changes are saved to the database and written back to the file's EXIF data.

## Architecture

```
Browser -> Nginx (:9473)
             ├── /thumbs/  -> served directly from disk (30-day cache)
             ├── /api/     -> FastAPI backend (:8000)
             └── /         -> Next.js frontend (:3000)

Backend -> PostgreSQL (data) + Redis (cache/broker) + Celery (background tasks)
```

| Service    | Purpose                                    |
|------------|--------------------------------------------|
| postgres   | Database for users, projects, photos, albums |
| redis      | Celery task broker + geocoding cache        |
| backend    | FastAPI REST API + Alembic migrations       |
| worker     | Celery worker for scanning, thumbnails, EXIF |
| frontend   | Next.js 14 App Router UI                    |
| nginx      | Reverse proxy, serves thumbnails directly   |

## Development

### Backend

```bash
cd backend
pip install -e ".[dev]"

# Run tests
pytest

# Run server locally (needs DATABASE_URL, SECRET_KEY env vars)
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The dev server runs on `http://localhost:3000` and proxies API calls to the backend.

## Updating

```bash
git pull
docker compose build
docker compose up -d
```

Database migrations run automatically on backend startup.

## Troubleshooting

**Photos not appearing after scan?**
Check the Celery worker logs: `docker compose logs worker`

**Permission denied on photo files?**
Ensure the Samba mount has correct `uid`/`gid` matching the container user (default: root in container).

**Thumbnails not loading?**
Verify the `thumbs_data` volume is shared between `backend`, `worker`, and `nginx` services. Check `docker compose logs nginx`.

**HEIC files not processing?**
The backend Dockerfile installs `libheif-dev`. If building on a different base image, ensure this library is available.
