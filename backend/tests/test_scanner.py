import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from PIL import Image

from app.services.scanner import parse_gps_exif, _read_photo_info


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
