"""Rebuild the two selected ROOT OS emoji assets and the contact sheet."""

from __future__ import annotations

import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent
SOURCES = ROOT / "sources-svg"
PNGS = ROOT / "png"
SCALE = 4
SIZE = 128
STROKE = 8

ICONS = {
    "root_verrou": {
        "usage": "Profil verrouillé après dégâts critiques",
        "color": "#B66DFF",
        "svg": '''<path d="M64 12 105 28v29c0 28-17 45-41 59C40 102 23 85 23 57V28z"/><rect x="43" y="57" width="42" height="35" rx="6"/><path d="M52 57V46a12 12 0 0 1 24 0v11"/><circle cx="64" cy="73" r="3"/><path d="M64 76v7"/>''',
        "draw": "lock",
    },
    "root_usd": {
        "usage": "Paiement en USD",
        "color": "#FFC15A",
        "svg": '''<circle cx="64" cy="64" r="48"/><path d="M80 43c-4-6-10-9-18-9-10 0-17 6-17 14 0 21 39 10 39 31 0 9-8 16-20 16-9 0-17-4-22-11M64 25v78"/>''',
        "draw": "usd",
    },
}


def make_canvas(color: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    image = Image.new("RGBA", (SIZE * SCALE, SIZE * SCALE), (0, 0, 0, 0))
    return image, ImageDraw.Draw(image)


def box(coords: tuple[float, ...]) -> tuple[int, ...]:
    return tuple(round(value * SCALE) for value in coords)


def draw_icon(kind: str, color: str) -> Image.Image:
    image, d = make_canvas(color)
    stroke = color
    width = STROKE * SCALE

    def line(points, fill=stroke, w=width):
        d.line([box(point) for point in points], fill=fill, width=w, joint="curve")

    def rect(coords, radius=0, fill=None, outline=stroke, w=width):
        d.rounded_rectangle(box(coords), radius=radius * SCALE, fill=fill, outline=outline, width=w)

    def ellipse(coords, fill=None, outline=stroke, w=width):
        d.ellipse(box(coords), fill=fill, outline=outline, width=w)

    if kind == "lock":
        line([(64, 12), (105, 28), (105, 57), (101, 73), (91, 88), (64, 116), (37, 88), (27, 73), (23, 57), (23, 28), (64, 12)])
        rect((43, 57, 85, 92), radius=6)
        d.arc(box((52, 34, 76, 68)), start=180, end=360, fill=stroke, width=width)
        ellipse((61, 70, 67, 76), fill=stroke, outline=stroke, w=1)
        line([(64, 75), (64, 83)])
    elif kind == "usd":
        ellipse((16, 16, 112, 112))
        line([(80, 43), (76, 38), (70, 35), (62, 34), (55, 36), (49, 41), (46, 47), (47, 53), (51, 58), (59, 61), (70, 64), (78, 68), (82, 73), (82, 80), (79, 86), (73, 91), (65, 93), (57, 92), (50, 89), (46, 85)])
        line([(64, 25), (64, 103)])
    else:
        raise ValueError(kind)

    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def choose_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = Path("C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf")
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def build_preview(manifest: list[dict]) -> None:
    cols, cell_w, cell_h = 6, 180, 158
    header_h, rows = 78, math.ceil(len(manifest) / cols)
    image = Image.new("RGB", (cols * cell_w, header_h + rows * cell_h), "#232529")
    d = ImageDraw.Draw(image)
    d.text((32, 20), "ROOT OS / EMOJIS", font=choose_font(22, True), fill="#EEF1F5")
    d.text((32, 49), f"{len(manifest)} PNG transparents · 128 × 128 · aperçu à taille Discord", font=choose_font(13), fill="#A8ABB2")

    for index, item in enumerate(manifest):
        col, row = index % cols, index // cols
        x, y = col * cell_w, header_h + row * cell_h
        icon = Image.open(ROOT / item["file"]).convert("RGBA")
        large = icon.resize((64, 64), Image.Resampling.LANCZOS)
        small = icon.resize((28, 28), Image.Resampling.LANCZOS)
        image.alpha_composite(large, (x + 45, y + 8)) if image.mode == "RGBA" else image.paste(large, (x + 45, y + 8), large)
        image.paste(small, (x + 117, y + 44), small)
        d = ImageDraw.Draw(image)
        name = item["name"]
        name_w = d.textbbox((0, 0), name, font=choose_font(12, True))[2]
        d.text((x + (cell_w - name_w) / 2, y + 82), name, font=choose_font(12, True), fill="#EEF1F5")
        usage = item["usage"]
        use_w = d.textbbox((0, 0), usage, font=choose_font(10))[2]
        d.text((x + (cell_w - use_w) / 2, y + 103), usage, font=choose_font(10), fill="#A8ABB2")

    image.save(ROOT / "apercu.png", optimize=True)


def main() -> None:
    SOURCES.mkdir(exist_ok=True)
    PNGS.mkdir(exist_ok=True)
    with (ROOT / "manifest.json").open(encoding="utf-8") as file:
        manifest = json.load(file)
    rejected_drafts = {"root_contrat", "root_macro", "root_intrusion"}
    manifest = [item for item in manifest if item["name"] not in rejected_drafts]
    known = {item["name"] for item in manifest}

    for name, spec in ICONS.items():
        (SOURCES / f"{name}.svg").write_text(
            f'''<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128" fill="none" stroke="{spec['color']}" stroke-width="8" stroke-linecap="round" stroke-linejoin="round">{spec['svg']}</svg>\n''',
            encoding="utf-8",
        )
        out = PNGS / f"{name}.png"
        draw_icon(spec["draw"], spec["color"]).save(out, optimize=True)
        record = {
            "name": name,
            "usage": spec["usage"],
            "color": spec["color"],
            "file": f"png/{name}.png",
            "bytes": out.stat().st_size,
            "source": "Original ROOT OS icon, built from the matching SVG source in this pack",
            "size": 128,
        }
        if name in known:
            manifest = [record if item["name"] == name else item for item in manifest]
        else:
            manifest.append(record)
    (ROOT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    build_preview(manifest)


if __name__ == "__main__":
    main()
