import asyncio
import logging
import uuid
from pathlib import Path

import piexif
import redis as redis_lib
from geopy.geocoders import Nominatim
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.photo import Photo
from app.models.project import Project
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

geolocator = Nominatim(user_agent="photo-service")


def _decimal_to_dms(decimal: float) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
    """Convert decimal degrees to EXIF DMS rational tuples."""
    d = int(abs(decimal))
    m_float = (abs(decimal) - d) * 60
    m = int(m_float)
    s = int((m_float - m) * 60 * 10000)
    return ((d, 1), (m, 1), (s, 10000))


def _write_exif(filepath: str, taken_at, gps_lat, gps_lon) -> None:
    """Write EXIF data to file. Runs in thread."""
    try:
        exif_dict = piexif.load(filepath)
    except Exception:
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}}

    if taken_at is not None:
        date_str = taken_at.strftime("%Y:%m:%d %H:%M:%S")
        exif_dict["Exif"][piexif.ExifIFD.DateTimeOriginal] = date_str.encode()

    if gps_lat is not None and gps_lon is not None:
        gps_ifd = {
            piexif.GPSIFD.GPSLatitudeRef: b"N" if gps_lat >= 0 else b"S",
            piexif.GPSIFD.GPSLatitude: _decimal_to_dms(gps_lat),
            piexif.GPSIFD.GPSLongitudeRef: b"E" if gps_lon >= 0 else b"W",
            piexif.GPSIFD.GPSLongitude: _decimal_to_dms(gps_lon),
        }
        exif_dict["GPS"] = gps_ifd

    exif_bytes = piexif.dump(exif_dict)
    piexif.insert(exif_bytes, filepath)


def reverse_geocode(lat: float, lon: float) -> str | None:
    """Reverse geocode with Redis caching (30-day TTL)."""
    r = redis_lib.Redis.from_url(settings.REDIS_URL)
    cache_key = f"geo:{lat:.4f}:{lon:.4f}"
    try:
        cached = r.get(cache_key)
        if cached:
            return cached.decode("utf-8")

        location = geolocator.reverse(f"{lat}, {lon}", exactly_one=True, timeout=10)
        if location and location.address:
            r.setex(cache_key, 30 * 86400, location.address)
            return location.address
    except Exception:
        logger.warning("Reverse geocoding failed for %s, %s", lat, lon)
    finally:
        r.close()
    return None


async def write_metadata_async(photo_id: str) -> dict:
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            photo = await session.get(Photo, uuid.UUID(photo_id))
            if photo is None:
                return {"status": "error", "reason": "photo not found"}

            project = await session.get(Project, photo.project_id)
            if project is None:
                return {"status": "error", "reason": "project not found"}

            media_root = Path(settings.MEDIA_ROOT)
            full_path = media_root / project.source_path / photo.relative_path

            if not full_path.exists():
                return {"status": "error", "reason": "file not found"}

            ext = full_path.suffix.lower()
            if ext in {".heic", ".heif"}:
                logger.warning("HEIC EXIF write not supported, skipping: %s", full_path)
                return {"status": "skipped", "reason": "HEIC EXIF write not supported"}

            await asyncio.to_thread(
                _write_exif, str(full_path), photo.taken_at, photo.gps_lat, photo.gps_lon
            )

            # Reverse geocode if GPS present but no location name
            if photo.gps_lat is not None and photo.gps_lon is not None and not photo.location_name:
                location_name = await asyncio.to_thread(
                    reverse_geocode, photo.gps_lat, photo.gps_lon
                )
                if location_name:
                    photo.location_name = location_name
                    await session.commit()

            return {"status": "completed"}
    finally:
        await engine.dispose()


@celery_app.task(name="write_metadata_to_file")
def write_metadata_to_file(photo_id: str) -> dict:
    return asyncio.run(write_metadata_async(photo_id))
