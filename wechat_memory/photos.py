"""Photo calendar adapter; missing capture dates are reported, never invented."""
from datetime import datetime
from pathlib import Path


def scan_photos(folder):
    try:
        from PIL import Image
    except ImportError as exc:
        raise ValueError('照片扫描需要安装：pip install -e ".[photos]"') from exc
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError("照片目录不存在")
    events, skipped = [], []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}:
            continue
        try:
            with Image.open(path) as img:
                exif = img.getexif()
                original = exif.get(36867) or exif.get_ifd(34665).get(36867)
                if not original:
                    raise ValueError("缺少 EXIF 拍摄日期")
                day = datetime.strptime(str(original), "%Y:%m:%d %H:%M:%S").date()
            events.append({"date": day.isoformat(), "title": path.stem,
                           "description": f"日期依据：EXIF DateTimeOriginal\n照片：{path.relative_to(folder)}"})
        except (OSError, ValueError, SyntaxError) as exc:
            skipped.append({"file": str(path.relative_to(folder)), "reason": str(exc)})
    return events, skipped
