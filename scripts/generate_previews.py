"""Generate JPG preview images from satellite data for frontend demo."""
from PIL import Image, ImageDraw
import os

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "public", "images", "satellite")

FARMS = [
    ("naga-001", "NAGA-001", "Juan Dela Cruz"),
    ("naga-002", "NAGA-002", "Maria Santos"),
    ("naga-003", "NAGA-003", "Pedro Reyes"),
]


def generate():
    os.makedirs(OUT_DIR, exist_ok=True)
    for slug, parcel_id, farmer in FARMS:
        for phase, color, label in [("before", (34, 139, 34), "BEFORE"), ("after", (139, 69, 19), "AFTER")]:
            img = Image.new("RGB", (400, 400), color)
            draw = ImageDraw.Draw(img)
            for y in range(0, 400, 20):
                draw.line([(0, y), (400, y)], fill=tuple(min(c + 30, 255) for c in color), width=1)
            draw.rectangle([10, 10, 390, 390], outline=(255, 255, 255), width=2)
            draw.text((20, 20), f"{parcel_id} - {label}", fill=(255, 255, 255))
            draw.text((20, 50), farmer, fill=(220, 220, 220))
            img.save(os.path.join(OUT_DIR, f"{slug}-{phase}.jpg"), "JPEG", quality=85)


if __name__ == "__main__":
    generate()
    print(f"Previews written to {OUT_DIR}")