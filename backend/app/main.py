from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import auth, projects, photos, albums, metadata, setup


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create thumbs directory on startup
    Path(settings.THUMBS_ROOT).mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title="Photo Service", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}

app.include_router(setup.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(photos.router)
app.include_router(photos.scan_router)
app.include_router(albums.router)
app.include_router(metadata.router)

app.mount("/thumbs", StaticFiles(directory=settings.THUMBS_ROOT), name="thumbs")
