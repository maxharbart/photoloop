import asyncio
import logging
import uuid
from pathlib import Path

from PIL import Image, ImageOps
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.config import settings
from app.models.photo import Photo
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp", ".m4v"}

THUMB_SIZES = {
    "sm": (320, 320, 75),
    "md": (800, 800, 82),
}


def _extract_video_frame(video_path: str, output_path: str, timestamp: float = 1.0) -> None:
    """Extract a single frame from a video file using ffmpeg."""
    import ffmpeg

    try:
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(output_path, vframes=1, format="image2")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
    except ffmpeg.Error:
        # Fallback: try at 0 seconds if the timestamp fails
        (
            ffmpeg
            .input(video_path, ss=0)
            .output(output_path, vframes=1, format="image2")
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )


def _generate(photo_path: str, output_dir: Path, photo_id: str) -> dict[str, str]:
    """Generate thumbnails. Runs in thread."""
    output_dir.mkdir(parents=True, exist_ok=True)
    results = {}

    with Image.open(photo_path) as img:
        img = ImageOps.exif_transpose(img)
        for suffix, (w, h, quality) in THUMB_SIZES.items():
            thumb = img.copy()
            thumb.thumbnail((w, h), Image.LANCZOS)
            if thumb.mode in ("RGBA", "P"):
                thumb = thumb.convert("RGB")
            out_name = f"{photo_id}_{suffix}.jpg"
            out_path = output_dir / out_name
            thumb.save(out_path, "JPEG", quality=quality)
            results[suffix] = out_name

    return results


async def generate_thumbnails_async(photo_id: str) -> dict:
    engine = create_async_engine(settings.DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        async with session_factory() as session:
            photo = await session.get(Photo, uuid.UUID(photo_id))
            if photo is None:
                return {"status": "error", "reason": "photo not found"}

            # Resolve full path
            from sqlalchemy import select as sel
            from app.models.project import Project
            project = await session.get(Project, photo.project_id)
            if project is None:
                return {"status": "error", "reason": "project not found"}

            media_root = Path(settings.MEDIA_ROOT)
            full_path = media_root / project.source_path / photo.relative_path

            if not full_path.exists():
                return {"status": "error", "reason": "file not found on disk"}

            thumbs_root = Path(settings.THUMBS_ROOT)
            output_dir = thumbs_root / str(photo.project_id)

            ext = full_path.suffix.lower()
            if ext in VIDEO_EXTENSIONS:
                try:
                    import tempfile

                    # Determine timestamp: 1s or 10% of duration
                    timestamp = 1.0
                    if photo.duration and photo.duration > 10:
                        timestamp = photo.duration * 0.1

                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        await asyncio.to_thread(
                            _extract_video_frame, str(full_path), tmp.name, timestamp
                        )
                        results = await asyncio.to_thread(_generate, tmp.name, output_dir, photo_id)
                        Path(tmp.name).unlink()
                except Exception:
                    logger.warning("Failed to generate thumbnails for video: %s", full_path)
                    return {"status": "error", "reason": "Video thumbnail extraction failed"}
            elif ext in {".heic", ".heif"}:
                try:
                    import pyheif
                    heif = pyheif.read(str(full_path))
                    pil_img = Image.frombytes(heif.mode, heif.size, heif.data)
                    # Save as temp JPEG for thumbnail generation
                    import tempfile
                    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                        pil_img.save(tmp.name, "JPEG", quality=90)
                        results = await asyncio.to_thread(_generate, tmp.name, output_dir, photo_id)
                        Path(tmp.name).unlink()
                except Exception:
                    logger.warning("Failed to generate thumbnails for HEIC: %s", full_path)
                    return {"status": "error", "reason": "HEIC processing failed"}
            else:
                results = await asyncio.to_thread(_generate, str(full_path), output_dir, photo_id)

            # Update DB
            rel_prefix = f"{photo.project_id}"
            photo.thumb_sm = f"{rel_prefix}/{results['sm']}"
            photo.thumb_md = f"{rel_prefix}/{results['md']}"
            await session.commit()

            return {"status": "completed"}

    finally:
        await engine.dispose()


@celery_app.task(name="generate_thumbnails")
def generate_thumbnails(photo_id: str) -> dict:
    return asyncio.run(generate_thumbnails_async(photo_id))
