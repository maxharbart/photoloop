import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import piexif
from PIL import Image
from sqlalchemy import select, delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.photo import Photo
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic", ".heif", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp", ".m4v"}
MEDIA_EXTENSIONS = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS


def parse_gps_exif(gps_ifd: dict) -> tuple[float, float] | None:
    """Convert EXIF GPS rational numbers to decimal degrees."""
    try:
        lat_ref = gps_ifd.get(piexif.GPSIFD.GPSLatitudeRef, b"N")
        lon_ref = gps_ifd.get(piexif.GPSIFD.GPSLongitudeRef, b"E")
        lat_data = gps_ifd[piexif.GPSIFD.GPSLatitude]
        lon_data = gps_ifd[piexif.GPSIFD.GPSLongitude]

        def to_decimal(dms_rationals):
            d = dms_rationals[0][0] / dms_rationals[0][1]
            m = dms_rationals[1][0] / dms_rationals[1][1]
            s = dms_rationals[2][0] / dms_rationals[2][1]
            return d + m / 60.0 + s / 3600.0

        lat = to_decimal(lat_data)
        lon = to_decimal(lon_data)
        if lat_ref == b"S":
            lat = -lat
        if lon_ref == b"W":
            lon = -lon
        return (lat, lon)
    except (KeyError, IndexError, ZeroDivisionError, TypeError):
        return None


def _parse_exif_date(date_str: bytes | str) -> datetime | None:
    try:
        if isinstance(date_str, bytes):
            date_str = date_str.decode("utf-8")
        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return None


def _read_photo_info(filepath: Path) -> dict:
    """Read photo metadata from file. Runs in thread."""
    info: dict = {"width": 0, "height": 0, "taken_at": None, "gps_lat": None, "gps_lon": None}
    info["file_size"] = filepath.stat().st_size

    ext = filepath.suffix.lower()
    if ext in {".heic", ".heif"}:
        try:
            import pyheif
            heif = pyheif.read(str(filepath))
            info["width"] = heif.size[0]
            info["height"] = heif.size[1]
            for md in heif.metadata or []:
                if md["type"] == "Exif":
                    exif_dict = piexif.load(md["data"])
                    date_val = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
                    if date_val:
                        info["taken_at"] = _parse_exif_date(date_val)
                    gps = exif_dict.get("GPS", {})
                    if gps:
                        coords = parse_gps_exif(gps)
                        if coords:
                            info["gps_lat"], info["gps_lon"] = coords
        except Exception:
            logger.warning("Failed to read HEIC file: %s", filepath)
    else:
        try:
            with Image.open(filepath) as img:
                info["width"], info["height"] = img.size
            exif_dict = piexif.load(str(filepath))
            date_val = exif_dict.get("Exif", {}).get(piexif.ExifIFD.DateTimeOriginal)
            if date_val:
                info["taken_at"] = _parse_exif_date(date_val)
            gps = exif_dict.get("GPS", {})
            if gps:
                coords = parse_gps_exif(gps)
                if coords:
                    info["gps_lat"], info["gps_lon"] = coords
        except Exception:
            logger.warning("Failed to read EXIF from: %s", filepath)
            try:
                with Image.open(filepath) as img:
                    info["width"], info["height"] = img.size
            except Exception:
                pass

    if info["taken_at"] is None:
        mtime = filepath.stat().st_mtime
        info["taken_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc)

    return info


def _read_video_info(filepath: Path) -> dict:
    """Read video metadata using ffprobe. Runs in thread."""
    import ffmpeg

    info: dict = {
        "width": 0,
        "height": 0,
        "taken_at": None,
        "gps_lat": None,
        "gps_lon": None,
        "duration": None,
        "media_type": "video",
    }
    info["file_size"] = filepath.stat().st_size

    try:
        probe = ffmpeg.probe(str(filepath))

        # Get duration from format
        fmt = probe.get("format", {})
        if "duration" in fmt:
            info["duration"] = float(fmt["duration"])

        # Get dimensions from first video stream
        for stream in probe.get("streams", []):
            if stream.get("codec_type") == "video":
                info["width"] = int(stream.get("width", 0))
                info["height"] = int(stream.get("height", 0))
                if info["duration"] is None and "duration" in stream:
                    info["duration"] = float(stream["duration"])
                break

        # Try to get creation date from format tags
        tags = fmt.get("tags", {})
        creation_time = tags.get("creation_time") or tags.get("com.apple.quicktime.creationdate")
        if creation_time:
            # Handle ISO format like "2024-06-15T12:00:00.000000Z"
            try:
                dt = datetime.fromisoformat(creation_time.replace("Z", "+00:00"))
                info["taken_at"] = dt
            except ValueError:
                pass

    except Exception:
        logger.warning("Failed to probe video: %s", filepath)

    if info["taken_at"] is None:
        mtime = filepath.stat().st_mtime
        info["taken_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc)

    return info


async def scan_project_async(project_id: str, source_path: str) -> dict:
    """Scan a project directory and upsert photos into DB."""
    import redis as redis_lib

    r = redis_lib.Redis.from_url(settings.REDIS_URL)
    lock_key = f"scan:lock:{project_id}"
    if not r.set(lock_key, "1", nx=True, ex=600):
        return {"status": "skipped", "reason": "scan already running"}

    try:
        media_root = Path(settings.MEDIA_ROOT)
        full_path = media_root / source_path
        if not full_path.exists():
            return {"status": "error", "reason": f"Path does not exist: {full_path}"}

        engine = create_async_engine(settings.DATABASE_URL)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        found_paths: set[str] = set()
        batch: list[dict] = []
        scanned = 0
        proj_uuid = uuid.UUID(project_id)

        for root, _dirs, files in os.walk(full_path):
            for fname in files:
                ext = Path(fname).suffix.lower()
                if ext not in MEDIA_EXTENSIONS:
                    continue

                fpath = Path(root) / fname
                rel_path = str(fpath.relative_to(full_path))
                found_paths.add(rel_path)

                is_video = ext in VIDEO_EXTENSIONS
                if is_video:
                    info = await asyncio.to_thread(_read_video_info, fpath)
                else:
                    info = await asyncio.to_thread(_read_photo_info, fpath)

                batch.append({
                    "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{project_id}/{rel_path}"),
                    "project_id": proj_uuid,
                    "relative_path": rel_path,
                    "filename": fname,
                    "taken_at": info["taken_at"],
                    "gps_lat": info["gps_lat"],
                    "gps_lon": info["gps_lon"],
                    "width": info["width"],
                    "height": info["height"],
                    "file_size": info["file_size"],
                    "media_type": info.get("media_type", "photo"),
                    "duration": info.get("duration"),
                    "indexed_at": datetime.now(timezone.utc),
                })

                if len(batch) >= 100:
                    async with session_factory() as session:
                        stmt = pg_insert(Photo).values(batch)
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["id"],
                            set_={
                                "taken_at": stmt.excluded.taken_at,
                                "gps_lat": stmt.excluded.gps_lat,
                                "gps_lon": stmt.excluded.gps_lon,
                                "width": stmt.excluded.width,
                                "height": stmt.excluded.height,
                                "file_size": stmt.excluded.file_size,
                                "media_type": stmt.excluded.media_type,
                                "duration": stmt.excluded.duration,
                                "indexed_at": stmt.excluded.indexed_at,
                            },
                        )
                        await session.execute(stmt)
                        await session.commit()
                    scanned += len(batch)
                    batch.clear()

        # Flush remaining batch
        if batch:
            async with session_factory() as session:
                stmt = pg_insert(Photo).values(batch)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["id"],
                    set_={
                        "taken_at": stmt.excluded.taken_at,
                        "gps_lat": stmt.excluded.gps_lat,
                        "gps_lon": stmt.excluded.gps_lon,
                        "width": stmt.excluded.width,
                        "height": stmt.excluded.height,
                        "file_size": stmt.excluded.file_size,
                        "indexed_at": stmt.excluded.indexed_at,
                    },
                )
                await session.execute(stmt)
                await session.commit()
            scanned += len(batch)

        # Delete photos no longer on disk
        async with session_factory() as session:
            result = await session.execute(
                select(Photo.id, Photo.relative_path).where(Photo.project_id == proj_uuid)
            )
            for photo_id, rel_path in result.all():
                if rel_path not in found_paths:
                    await session.execute(delete(Photo).where(Photo.id == photo_id))
            await session.commit()

        # Enqueue thumbnail generation for photos missing thumbs
        async with session_factory() as session:
            result = await session.execute(
                select(Photo.id).where(
                    Photo.project_id == proj_uuid,
                    Photo.thumb_sm.is_(None),
                )
            )
            for (photo_id,) in result.all():
                from app.services.thumbnailer import generate_thumbnails
                generate_thumbnails.delay(str(photo_id))

        await engine.dispose()
        return {"status": "completed", "scanned": scanned}

    finally:
        r.delete(lock_key)
        r.close()


@celery_app.task(name="scan_project")
def scan_project(project_id: str, source_path: str) -> dict:
    return asyncio.run(scan_project_async(project_id, source_path))
