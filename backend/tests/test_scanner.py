import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from unittest.mock import patch

from app.services.scanner import (
    parse_gps_exif,
    _read_photo_info,
    _read_video_info,
    MEDIA_EXTENSIONS,
    VIDEO_EXTENSIONS,
    PHOTO_EXTENSIONS,
)


def test_parse_gps_exif_valid():
    """Test GPS EXIF parsing with known coordinates (Eiffel Tower)."""
    import piexif

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"N",
        piexif.GPSIFD.GPSLongitudeRef: b"E",
        piexif.GPSIFD.GPSLatitude: ((48, 1), (51, 1), (2952, 100)),
        piexif.GPSIFD.GPSLongitude: ((2, 1), (17, 1), (4008, 100)),
    }
    result = parse_gps_exif(gps_ifd)
    assert result is not None
    lat, lon = result
    assert abs(lat - 48.8582) < 0.001
    assert abs(lon - 2.2945) < 0.001


def test_parse_gps_exif_south_west():
    """Test GPS coordinates in southern/western hemisphere."""
    import piexif

    gps_ifd = {
        piexif.GPSIFD.GPSLatitudeRef: b"S",
        piexif.GPSIFD.GPSLongitudeRef: b"W",
        piexif.GPSIFD.GPSLatitude: ((33, 1), (51, 1), (3120, 100)),
        piexif.GPSIFD.GPSLongitude: ((151, 1), (12, 1), (3600, 100)),
    }
    result = parse_gps_exif(gps_ifd)
    assert result is not None
    lat, lon = result
    assert lat < 0
    assert lon < 0


def test_parse_gps_exif_missing_data():
    result = parse_gps_exif({})
    assert result is None


def test_read_photo_info_jpeg(tmp_path: Path):
    """Test reading metadata from a synthetic JPEG file."""
    img_path = tmp_path / "test.jpg"
    img = Image.new("RGB", (800, 600), color="blue")
    img.save(str(img_path), "JPEG")

    info = _read_photo_info(img_path)
    assert info["width"] == 800
    assert info["height"] == 600
    assert info["file_size"] > 0
    assert info["taken_at"] is not None  # Falls back to mtime


def test_read_photo_info_png(tmp_path: Path):
    img_path = tmp_path / "test.png"
    img = Image.new("RGBA", (1024, 768), color="red")
    img.save(str(img_path), "PNG")

    info = _read_photo_info(img_path)
    assert info["width"] == 1024
    assert info["height"] == 768
    assert info["gps_lat"] is None
    assert info["gps_lon"] is None


def test_video_extensions_in_media_extensions():
    """Verify video extensions are included in MEDIA_EXTENSIONS."""
    for ext in VIDEO_EXTENSIONS:
        assert ext in MEDIA_EXTENSIONS
    for ext in PHOTO_EXTENSIONS:
        assert ext in MEDIA_EXTENSIONS


def test_read_video_info_with_ffprobe(tmp_path: Path):
    """Test _read_video_info with mocked ffprobe output."""
    video_path = tmp_path / "test.mp4"
    video_path.write_bytes(b"\x00" * 1024)  # dummy file

    mock_probe_result = {
        "format": {
            "duration": "30.5",
            "tags": {
                "creation_time": "2024-06-15T12:00:00.000000Z",
            },
        },
        "streams": [
            {
                "codec_type": "video",
                "width": 1920,
                "height": 1080,
                "duration": "30.5",
            },
            {
                "codec_type": "audio",
            },
        ],
    }

    with patch("ffmpeg.probe", return_value=mock_probe_result):
        info = _read_video_info(video_path)

    assert info["width"] == 1920
    assert info["height"] == 1080
    assert info["duration"] == 30.5
    assert info["media_type"] == "video"
    assert info["file_size"] == 1024
    assert info["taken_at"] is not None
    assert info["taken_at"].year == 2024


def test_read_video_info_ffprobe_failure(tmp_path: Path):
    """Test _read_video_info falls back gracefully when ffprobe fails."""
    video_path = tmp_path / "test.mov"
    video_path.write_bytes(b"\x00" * 512)

    with patch("ffmpeg.probe", side_effect=Exception("ffprobe not found")):
        info = _read_video_info(video_path)

    assert info["width"] == 0
    assert info["height"] == 0
    assert info["duration"] is None
    assert info["media_type"] == "video"
    assert info["file_size"] == 512
    assert info["taken_at"] is not None  # Falls back to mtime
