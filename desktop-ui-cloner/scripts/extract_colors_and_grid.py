#!/usr/bin/env python3
"""Measure a desktop-UI screenshot: exact colours, panel geometry, corner radii,
type sizes and the spacing grid.

Example
-------
    python3 extract_colors_and_grid.py shots/original/window.png \
        --json  spec/window.json \
        --md    spec/window.md \
        --overlay spec/window.overlay.png

What it measures
----------------
* every distinct colour with its pixel share, extent and an assigned role
  (background / surface / text / border / accent)
* panels: rectangles of one fill colour, with position, size, fill ratio and
  corner radius measured from the top-row inset of the shape
* layout: rows of panels, column x-positions, the gaps between them
* typography: ink bands inside each panel — ink height, estimated font size
  range, line advance, text colour, inset from the panel edge
* spacing: every gap and inset, plus the base unit they snap to

Everything is reported in the screenshot's own pixels; pass --dpr 2 for a
Retina/HiDPI capture to also get logical (dp) values.

Requires: pillow, numpy, scipy
    python3 -m pip install pillow numpy scipy
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage as ndi
except ImportError as exc:  # pragma: no cover - dependency guard
    sys.exit(
        f"extract_colors_and_grid.py is missing a dependency: {exc}\n"
        "Install with: python3 -m pip install pillow numpy scipy"
    )

RADIUS_SNAPS = (0, 1, 2, 3, 4, 6, 8, 10, 12, 14, 16, 20, 24, 28, 32)
SPACING_BASES = (2, 3, 4, 5, 6, 8, 10, 12, 16)


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def hexc(c: Any) -> str:
    r, g, b = (int(round(float(v))) for v in np.asarray(c).reshape(-1)[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


def parse_hex(text: str) -> tuple[int, int, int]:
    t = text.strip().lstrip("#")
    if len(t) == 3:
        t = "".join(ch * 2 for ch in t)
    if len(t) != 6:
        raise argparse.ArgumentTypeError(f"expected #RRGGBB — got {text!r}")
    return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)


def parse_rect(text: str) -> tuple[int, int, int, int]:
    parts = [p for p in text.replace(" ", ",").split(",") if p]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"expected x,y,w,h — got {text!r}")
    return tuple(int(p) for p in parts)  # type: ignore[return-value]


def color_distance(rgb: np.ndarray, ref: np.ndarray) -> np.ndarray:
    """'redmean' perceptual distance, scaled roughly 0-100."""
    a = rgb.astype(np.float32)
    b = np.asarray(ref, dtype=np.float32)
    rmean = (a[..., 0] + b[..., 0]) / 2.0
    dr = a[..., 0] - b[..., 0]
    dg = a[..., 1] - b[..., 1]
    db = a[..., 2] - b[..., 2]
    d2 = (2 + rmean / 256.0) * dr**2 + 4.0 * dg**2 + (2 + (255.0 - rmean) / 256.0) * db**2
    return np.sqrt(d2) / 2.55


def load_rgb(path: Path, crop: tuple[int, int, int, int] | None) -> np.ndarray:
    if not path.exists():
        raise SystemExit(f"[error] no such file: {path}")
    with Image.open(path) as im:
        rgb = np.asarray(im.convert("RGB"), dtype=np.uint8)
    if crop:
        x, y, w, h = crop
        rgb = rgb[y : y + h, x : x + w]
        if rgb.size == 0:
            raise SystemExit("[error] --crop is outside the image")
    return np.ascontiguousarray(rgb)


def group_runs(flags: np.ndarray, max_gap: int = 1, min_len: int = 2) -> list[tuple[int, int]]:
    """Group a 1-D boolean profile into (start, stop) runs."""
    runs: list[tuple[int, int]] = []
    start: int | None = None
    gap = 0
    for i, f in enumerate(flags):
        if f:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap > max_gap:
                stop = i - gap + 1
                if stop - start >= min_len:
                    runs.append((start, stop))
                start, gap = None, 0
    if start is not None:
        stop = len(flags) - (gap if gap else 0)
        if stop - start >= min_len:
            runs.append((start, stop))
    return runs


def snap_radius(r: float) -> int:
    return int(min(RADIUS_SNAPS, key=lambda v: abs(v - r)))


def load_font(size: int = 13) -> Any:
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover
        return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# colour palette
# --------------------------------------------------------------------------- #
def exact_palette(rgb: np.ndarray, top: int = 24) -> list[dict[str, Any]]:
    h, w = rgb.shape[:2]
    flat = rgb.reshape(-1, 3)
    colors, counts = np.unique(flat, axis=0, return_counts=True)
    order = np.argsort(-counts)[:top]
    total = h * w
    out: list[dict[str, Any]] = []
    for i in order:
        color = colors[i]
        mask = np.all(rgb == color, axis=2)
        rows = np.flatnonzero(mask.any(axis=1))
        cols = np.flatnonzero(mask.any(axis=0))
        out.append(
            {
                "hex": hexc(color),
                "rgb": [int(v) for v in color],
                "px": int(counts[i]),
                "pct": round(100.0 * counts[i] / total, 3),
                "extent": {
                    "x": int(cols[0]),
                    "y": int(rows[0]),
                    "w": int(cols[-1] - cols[0] + 1),
                    "h": int(rows[-1] - rows[0] + 1),
                },
                "chroma": int(color.max()) - int(color.min()),
            }
        )
    return out


def posterize(rgb: np.ndarray, n_colors: int) -> tuple[np.ndarray, np.ndarray]:
    """Index image + palette RGB, so near-identical shades group together."""
    im = Image.fromarray(rgb)
    q = im.quantize(
        colors=n_colors,
        method=Image.Quantize.MEDIANCUT,
        dither=Image.Dither.NONE,
    )
    idx = np.asarray(q, dtype=np.int32)
    pal = np.array(q.getpalette()[: n_colors * 3], dtype=np.uint8).reshape(-1, 3)
    return idx, pal


# --------------------------------------------------------------------------- #
# panel geometry
# --------------------------------------------------------------------------- #
def edge_coverage(sub: np.ndarray, frac: float = 0.25) -> float:
    """How solid the middle of each bbox edge is (1.0 = straight filled edge)."""
    h, w = sub.shape
    if h < 4 or w < 4:
        return 0.0
    my0, my1 = max(0, int(h * frac)), min(h, max(int(h * frac) + 1, int(h * (1 - frac))))
    mx0, mx1 = max(0, int(w * frac)), min(w, max(int(w * frac) + 1, int(w * (1 - frac))))
    vals = [
        sub[0, mx0:mx1].mean(),
        sub[-1, mx0:mx1].mean(),
        sub[my0:my1, 0].mean(),
        sub[my0:my1, -1].mean(),
    ]
    return float(min(vals))


def corner_insets(sub: np.ndarray, probe: int = 40) -> list[int]:
    """Inset of the first filled pixel along each edge, per corner.

    For a rounded rectangle of radius r the top row of the shape starts r px in,
    so this inset *is* the radius (within a pixel)."""
    h, w = sub.shape
    out: list[int] = []
    for i in range(min(probe, max(1, h // 2))):
        xs = np.flatnonzero(sub[i])
        if xs.size:
            out.append(int(xs[0]))
            break
    for i in range(min(probe, max(1, h // 2))):
        xs = np.flatnonzero(sub[-1 - i])
        if xs.size:
            out.append(int(w - 1 - xs[-1]))
            break
    for i in range(min(probe, max(1, w // 2))):
        ys = np.flatnonzero(sub[:, i])
        if ys.size:
            out.append(int(ys[0]))
            break
    for i in range(min(probe, max(1, w // 2))):
        ys = np.flatnonzero(sub[:, -1 - i])
        if ys.size:
            out.append(int(h - 1 - ys[-1]))
            break
    return out


def radius_of(sub: np.ndarray) -> tuple[int, list[int]]:
    insets = [v for v in corner_insets(sub) if v >= 0]
    if len(insets) < 3:
        return 0, insets
    # horizontal and vertical insets are both ~r; the median rejects one
    # clipped/cropped corner without hiding a real radius.
    est = float(np.median(insets))
    if est <= 1.0:
        return 0, insets
    return int(round(est)), insets


def _fit_arc(points: list[tuple[int, float]], max_r: int = 32) -> float:
    """Least-squares fit of a quarter-circle to (row, inset) boundary samples.

    The apex row is allowed to sit a few rows above the first sample (anti-aliased
    arc tips are not pure fill), which is what makes this recover r=8 instead of
    the r=3 an exact-colour inset suggests."""
    if len(points) < 5:
        return 0.0
    best_err: float | None = None
    best_r = 0.0
    for offset in range(0, 4):
        for r in np.arange(1.0, max_r + 0.51, 0.5):
            err = 0.0
            for i, inset in points:
                j = i + offset
                # sample at pixel centres: the arc's apex falls half a row above
                # the first row that contains it
                t = r - (j + 0.5)
                pred = 0.0 if t <= 0 else float(r - math.sqrt(max(0.0, r * r - t * t)))
                err += (pred - inset) ** 2
            err /= len(points)
            if best_err is None or err < best_err:
                best_err, best_r = err, float(r)
    if best_err is None or best_err > 2.5:
        return 0.0
    return best_r


def measure_radius(
    rgb: np.ndarray, x0: int, y0: int, x1: int, y1: int, probe: int = 24, tol: float = 10.0
) -> tuple[int, list[int]]:
    """Corner radius of a panel, measured against the colour around it.

    Samples the left/right-most panel pixel per row near all four corners and
    fits a quarter circle. Works on anti-aliased corners, where the exact-fill
    component starts several rows below the visual corner."""
    h, w = rgb.shape[:2]
    pad = 4
    sx0, sy0 = max(0, x0 - pad), max(0, y0 - pad)
    sx1, sy1 = min(w, x1 + pad), min(h, y1 + pad)
    if sx0 == 0 or sy0 == 0 or sx1 == w or sy1 == h:
        return 0, []
    sub = rgb[sy0:sy1, sx0:sx1]
    fx, fy = x0 - sx0, y0 - sy0
    pw, ph = x1 - x0, y1 - y0
    if fx < 1 or fy < 1 or fx + pw >= sub.shape[1] or fy + ph >= sub.shape[0]:
        return 0, []
    blocks = [sub[0:2, 0:2], sub[0:2, -2:], sub[-2:, 0:2], sub[-2:, -2:]]
    outside = np.median(np.concatenate([b.reshape(-1, 3) for b in blocks]), axis=0)
    shape = color_distance(sub, outside) > tol

    fits: list[int] = []
    n = min(probe, ph // 2, pw // 2)
    for corner in range(4):
        rows = range(n) if corner in (0, 1) else range(n)
        pts: list[tuple[int, float]] = []
        for i in rows:
            y = fy + i if corner in (0, 1) else fy + ph - 1 - i
            xs = np.flatnonzero(shape[y, fx : fx + pw])
            if not xs.size:
                continue
            inset = float(xs[0]) if corner in (0, 2) else float(pw - 1 - xs[-1])
            pts.append((i, inset))
        r = _fit_arc(pts)
        if r >= 2.0:
            fits.append(int(round(r)))
    if not fits:
        return 0, []
    return int(round(float(np.median(fits)))), sorted(fits)


def find_panels(
    rgb: np.ndarray,
    idx: np.ndarray,
    pal: np.ndarray,
    min_w: int,
    min_h: int,
    min_fill: float,
) -> list[dict[str, Any]]:
    h, w = rgb.shape[:2]
    panels: list[dict[str, Any]] = []
    for ci in range(len(pal)):
        mask = idx == ci
        count = int(mask.sum())
        if count < min_w * min_h:
            continue
        labels, n = ndi.label(mask)
        if not n:
            continue
        for i, sl in enumerate(ndi.find_objects(labels), start=1):
            if sl is None:
                continue
            y0, y1 = sl[0].start, sl[0].stop
            x0, x1 = sl[1].start, sl[1].stop
            pw, ph = x1 - x0, y1 - y0
            if pw < min_w or ph < min_h:
                continue
            sub = labels[sl] == i
            area = int(sub.sum())
            fill = area / float(pw * ph)
            if fill < min_fill:
                continue
            if edge_coverage(sub) < 0.9:
                continue
            if edge_coverage(sub, 0.05) < 0.55:
                continue
            block = rgb[y0:y1, x0:x1][sub]
            fill_rgb = np.median(block, axis=0)
            radius, insets = measure_radius(rgb, x0, y0, x1, y1)
            if radius == 0 and not insets:
                radius, insets = radius_of(sub)
            touches = {
                "left": x0 == 0,
                "right": x1 == w,
                "top": y0 == 0,
                "bottom": y1 == h,
            }
            panels.append(
                {
                    "x": int(x0),
                    "y": int(y0),
                    "w": int(pw),
                    "h": int(ph),
                    "area_px": area,
                    "fill_ratio": round(fill, 3),
                    "color": hexc(fill_rgb),
                    "radius_px": int(radius),
                    "radius_snap_px": snap_radius(radius),
                    "corner_insets_px": insets,
                    "touches_frame": [k for k, v in touches.items() if v],
                    "role": "background" if all(touches.values()) else "surface",
                }
            )

    # keep the biggest component per (x, y, w, h): posterization can nest surfaces
    seen: dict[tuple[int, int, int, int], dict[str, Any]] = {}
    for p in panels:
        key = (p["x"], p["y"], p["w"], p["h"])
        if key not in seen or p["area_px"] > seen[key]["area_px"]:
            seen[key] = p
    panels = sorted(seen.values(), key=lambda p: (-p["area_px"], p["y"], p["x"]))
    return panels


# --------------------------------------------------------------------------- #
# typography and insets
# --------------------------------------------------------------------------- #
def analyse_text(rgb: np.ndarray, panel: dict[str, Any], max_ink: int = 20) -> list[dict[str, Any]]:
    """Ink bands inside a panel, measured against the panel's fill colour."""
    x0, y0, w, h = panel["x"], panel["y"], panel["w"], panel["h"]
    sub = rgb[y0 : y0 + h, x0 : x0 + w]
    fill_rgb = np.array(
        [int(panel["color"][1:3], 16), int(panel["color"][3:5], 16), int(panel["color"][5:7], 16)],
        dtype=np.uint8,
    )
    dist = color_distance(sub, fill_rgb)
    # ignore a 1px rim: it is the AA of the panel border, not content
    dist[:1, :] = 0
    dist[-1:, :] = 0
    dist[:, :1] = 0
    dist[:, -1:] = 0
    ink = dist > 12
    if not ink.any():
        return []

    rows = ink.any(axis=1)
    bands = group_runs(rows, max_gap=1, min_len=7)
    out: list[dict[str, Any]] = []
    for (b0, b1) in bands:
        band = ink[b0:b1]
        ink_h = b1 - b0
        cols = np.flatnonzero(band.any(axis=0))
        # 7px is below the smallest UI text size; shorter runs are hairlines
        if cols.size == 0 or ink_h < 7:
            continue
        # reject blobs that are obviously another surface, not a line of text
        if ink.mean() > 0.85:
            continue
        strong = dist[b0:b1] > 25
        if strong.any():
            pixels = sub[b0:b1][strong]
            text_color = np.median(pixels, axis=0)
            text_share = float(strong.mean())
        else:
            text_color = np.median(sub[b0:b1][band], axis=0)
            text_share = 0.0
        if text_share > 0.75:
            continue
        # cap height is the distance from the ink top to the baseline: the modal
        # bottom row of the glyph columns, which ignores descenders (g, p, y).
        # Font size ≈ cap height / 0.72 for the common UI faces.
        bottoms = np.array([int(np.flatnonzero(band[:, c])[-1]) for c in cols])
        baseline = int(np.bincount(bottoms, minlength=ink_h).argmax())
        cap_h = max(1, baseline + 1)
        out.append(
            {
                "y": int(y0 + b0),
                "x": int(x0 + cols[0]),
                "w": int(cols[-1] - cols[0] + 1),
                "ink_height_px": int(ink_h),
                "cap_height_px": int(cap_h),
                "estimated_font_size_px": int(round(cap_h / 0.72)),
                "font_size_range_px": [
                    int(max(6, round(cap_h / 0.82))),
                    int(round(cap_h / 0.64)),
                ],
                "color": hexc(text_color),
                "left_inset_px": int(cols[0]),
                "top_inset_px": int(b0),
            }
        )
        if len(out) >= max_ink:
            break

    # line advance from consecutive bands in the same text block
    for a, b in zip(out, out[1:]):
        if abs(a["x"] - b["x"]) <= 3:
            a["line_advance_px"] = int(b["y"] - a["y"])
    return out


# --------------------------------------------------------------------------- #
# layout grid
# --------------------------------------------------------------------------- #
def build_rows(panels: list[dict[str, Any]]) -> list[dict[str, Any]]:
    content = [p for p in panels if p["role"] != "background"]
    content.sort(key=lambda p: (p["y"], p["x"]))
    rows: list[list[dict[str, Any]]] = []
    for p in content:
        for row in rows:
            y0 = min(q["y"] for q in row)
            y1 = max(q["y"] + q["h"] for q in row)
            overlap = min(y1, p["y"] + p["h"]) - max(y0, p["y"])
            if overlap > 0.5 * min(p["h"], y1 - y0):
                row.append(p)
                break
        else:
            rows.append([p])
    out: list[dict[str, Any]] = []
    for row in rows:
        row.sort(key=lambda q: q["x"])
        y0 = min(q["y"] for q in row)
        y1 = max(q["y"] + q["h"] for q in row)
        gaps = [row[i + 1]["x"] - (row[i]["x"] + row[i]["w"]) for i in range(len(row) - 1)]
        out.append(
            {
                "y": int(y0),
                "h": int(y1 - y0),
                "panels": len(row),
                "x": [int(q["x"]) for q in row],
                "widths": [int(q["w"]) for q in row],
                "gaps_px": [int(g) for g in gaps],
            }
        )
    return out


def build_columns(panels: list[dict[str, Any]], tol: int = 6) -> list[dict[str, Any]]:
    content = sorted(
        (p for p in panels if p["role"] != "background"), key=lambda p: p["x"]
    )
    cols: list[list[dict[str, Any]]] = []
    for p in content:
        for col in cols:
            if abs(col[0]["x"] - p["x"]) <= tol:
                col.append(p)
                break
        else:
            cols.append([p])
    out = []
    for col in cols:
        out.append(
            {
                "x": int(round(np.median([q["x"] for q in col]))),
                "panels": len(col),
                "widths": sorted({int(q["w"]) for q in col}),
            }
        )
    return out


def spacing_base(values: list[int]) -> dict[str, Any]:
    vals = [v for v in values if 0 < v <= 400]
    if not vals:
        return {"base_px": None, "residual_px": None, "samples": 0}
    scored = []
    for b in sorted(SPACING_BASES, reverse=True):
        residual = float(np.mean([min(v % b, b - v % b) for v in vals]))
        scored.append((b, residual))
    # the largest base that still explains the measurements: 2 "fits" every even
    # gap and tells the build nothing, so only fall back to it when nothing else
    # comes close
    fitting = [(b, r) for b, r in scored if r <= max(1.0, 0.06 * b)]
    base, residual = fitting[0] if fitting else min(scored, key=lambda br: br[1])
    return {
        "base_px": int(base),
        "residual_px": round(residual, 2),
        "samples": len(vals),
    }


# --------------------------------------------------------------------------- #
# roles
# --------------------------------------------------------------------------- #
def detect_background(
    rgb: np.ndarray, palette: list[dict[str, Any]], ring: int = 6
) -> dict[str, Any] | None:
    """The window colour is the dominant colour of the outer frame ring.

    "Most common colour overall" is wrong in real apps: a big list panel can
    out-area the background it sits on, and a full-width toolbar can win the top
    edge. The ring is what a person would sample to describe "the background"."""
    h, w = rgb.shape[:2]
    r = max(1, min(ring, h // 2, w // 2))
    border = np.concatenate(
        [
            rgb[:r, :].reshape(-1, 3),
            rgb[-r:, :].reshape(-1, 3),
            rgb[:, :r].reshape(-1, 3),
            rgb[:, -r:].reshape(-1, 3),
        ]
    )
    colors, counts = np.unique(border, axis=0, return_counts=True)
    if not len(colors):
        return palette[0] if palette else None
    top = colors[int(np.argmax(counts))]
    top_hex = hexc(top)
    ring_share = float(counts.max()) / len(border)
    for c in palette:
        if c["hex"] == top_hex:
            return {**c, "ring_share": round(ring_share, 3)}
    mask = np.all(rgb == top, axis=2)
    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    return {
        "hex": top_hex,
        "rgb": [int(v) for v in top],
        "px": int(counts.max()),
        "pct": round(100.0 * counts.max() / (h * w), 3),
        "extent": {
            "x": int(cols[0]),
            "y": int(rows[0]),
            "w": int(cols[-1] - cols[0] + 1),
            "h": int(rows[-1] - rows[0] + 1),
        },
        "chroma": int(top.max()) - int(top.min()),
        "ring_share": round(ring_share, 3),
    }


def assign_roles(
    rgb: np.ndarray,
    palette: list[dict[str, Any]],
    panels: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    background: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bg = background or (palette[0] if palette else None)
    surface_panels = [p for p in panels if p["role"] == "surface"]
    surfaces: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in sorted(surface_panels, key=lambda q: -q["area_px"]):
        if p["color"] in seen:
            continue
        seen.add(p["color"])
        surfaces.append(
            {
                "hex": p["color"],
                "panel": [p["x"], p["y"], p["w"], p["h"]],
                "radius_px": p["radius_px"],
            }
        )

    text_counts: dict[str, int] = {}
    for t in texts:
        text_counts[t["color"]] = text_counts.get(t["color"], 0) + t["ink_height_px"]
    ordered_text = sorted(text_counts.items(), key=lambda kv: -kv[1])

    # thin, widespread colours are hairlines: borders, dividers, focus rings,
    # scrollbar tracks. A 1-2px line disappears under a 3x3 erosion.
    borders: list[dict[str, Any]] = []
    for c in palette:
        if c["px"] < 30 or c["pct"] > 20:
            continue
        mask = np.all(rgb == np.array(c["rgb"], dtype=np.uint8), axis=2)
        total = int(mask.sum())
        if total == 0:
            continue
        eroded = int(ndi.binary_erosion(mask, structure=np.ones((3, 3), bool)).sum())
        thinness = 1.0 - eroded / total
        if thinness >= 0.9 and c["pct"] >= 0.002:
            borders.append({"hex": c["hex"], "pct": c["pct"], "thinness": round(thinness, 3)})
    borders.sort(key=lambda b: -b["pct"])

    accents = [
        {"hex": c["hex"], "pct": c["pct"], "chroma": c["chroma"]}
        for c in palette
        if c["chroma"] >= 40 and c["pct"] >= 0.002
    ]
    accents.sort(key=lambda a: (-a["chroma"], -a["pct"]))

    return {
        "background": bg["hex"] if bg else None,
        "background_pct": bg["pct"] if bg else None,
        "surfaces": surfaces[:8],
        "text": [
            {"hex": h, "role": "primary" if i == 0 else ("secondary" if i == 1 else "tertiary")}
            for i, (h, _) in enumerate(ordered_text[:4])
        ],
        "accent": accents[:4],
        "borders": borders,
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def render_overlay(
    rgb: np.ndarray,
    panels: list[dict[str, Any]],
    texts: list[dict[str, Any]],
    out: Path,
) -> None:
    im = Image.fromarray(rgb).convert("RGB")
    im = Image.blend(im, Image.new("RGB", im.size, (0, 0, 0)), 0.35)
    draw = ImageDraw.Draw(im)
    font = load_font(13)
    for i, p in enumerate(panels, start=1):
        x, y, w, h = p["x"], p["y"], p["w"], p["h"]
        color = (255, 0, 200) if p["role"] == "surface" else (0, 180, 255)
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=color, width=2)
        label = f"P{i} {p['color']} r{p['radius_px']}"
        tw = draw.textlength(label, font=font)
        ty = max(0, y - 15)
        draw.rectangle([x, ty, x + tw + 6, ty + 15], fill=color)
        draw.text((x + 3, ty + 1), label, fill=(0, 0, 0), font=font)
    for t in texts:
        draw.line(
            [t["x"], t["y"] + t["ink_height_px"], t["x"] + t["w"], t["y"] + t["ink_height_px"]],
            fill=(0, 255, 120),
            width=1,
        )
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)


def write_markdown(report: dict[str, Any], path: Path) -> None:
    m = report["meta"]
    roles = report["roles"]
    lines: list[str] = []
    lines.append(f"# Measured layout — {Path(m['source']).name}")
    lines.append("")
    lines.append(
        f"{m['width']}x{m['height']} px, DPR {m['dpr']}. Window background "
        f"`{roles['background']}` ({roles['background_pct']:.1f}% of the frame)."
    )
    lines.append("")
    lines.append("## Palette (exact, by area)")
    lines.append("")
    lines.append("| # | colour | share | px | extent | chroma |")
    lines.append("|---|--------|-------|----|--------|--------|")
    for i, c in enumerate(report["palette"][:16], start=1):
        e = c["extent"]
        lines.append(
            f"| {i} | `{c['hex']}` | {c['pct']:.2f}% | {c['px']} | "
            f"{e['x']},{e['y']} {e['w']}x{e['h']} | {c['chroma']} |"
        )
    lines.append("")
    lines.append("## Roles")
    lines.append("")
    lines.append(f"- background: `{roles['background']}` ({roles['background_pct']}% of frame)")
    if roles["surfaces"]:
        lines.append("- surfaces: " + ", ".join(f"`{s['hex']}`" for s in roles["surfaces"]))
    if roles["text"]:
        lines.append(
            "- text: "
            + ", ".join(f"`{t['hex']}` ({t['role']})" for t in roles["text"])
        )
    if roles["accent"]:
        lines.append("- accents: " + ", ".join(f"`{a['hex']}`" for a in roles["accent"]))
    lines.append("")
    lines.append("## Panels")
    lines.append("")
    lines.append("| id | x,y | w x h | fill | radius | snap |")
    lines.append("|----|-----|-------|------|--------|------|")
    for i, p in enumerate(report["panels"], start=1):
        lines.append(
            f"| P{i} | {p['x']},{p['y']} | {p['w']} x {p['h']} | `{p['color']}` | "
            f"{p['radius_px']} | {p['radius_snap_px']} |"
        )
    if report["rows"]:
        lines.append("")
        lines.append("## Rows and gaps")
        lines.append("")
        for i, r in enumerate(report["rows"], start=1):
            gaps = ", ".join(str(g) for g in r["gaps_px"]) or "—"
            lines.append(
                f"- R{i}: y={r['y']} h={r['h']}, {r['panels']} panel(s) at x="
                f"{r['x']}, widths {r['widths']}, gaps {gaps}"
            )
    if report["text"]:
        lines.append("")
        lines.append("## Text lines (ink measured, size estimated)")
        lines.append("")
        lines.append("| panel | x,y | cap h | ink h | font size (est, range) | colour | advance |")
        lines.append("|-------|-----|-------|-------|------------------------|--------|---------|")
        for t in report["text"][:40]:
            lo, hi = t["font_size_range_px"]
            adv = t.get("line_advance_px", "—")
            lines.append(
                f"| P{t['panel']} | {t['x']},{t['y']} | {t.get('cap_height_px', '—')} | "
                f"{t['ink_height_px']} | {t['estimated_font_size_px']} ({lo}–{hi}) | "
                f"`{t['color']}` | {adv} |"
            )
    lines.append("")
    lines.append("## Spacing")
    lines.append("")
    sp = report["spacing"]
    lines.append(
        f"- base unit: {sp['base']['base_px']} px "
        f"(mean residual {sp['base']['residual_px']} px over {sp['base']['samples']} gaps)"
    )
    lines.append("- observed gaps: " + (", ".join(map(str, sp["gaps_px"])) or "—"))
    lines.append(
        "- panel insets to first text: "
        + (", ".join(map(str, sp["insets_px"])) or "—")
    )
    if report["warnings"]:
        lines.append("")
        lines.append("## Warnings")
        lines.append("")
        for wmsg in report["warnings"]:
            lines.append(f"- {wmsg}")
    lines.append("")
    lines.append(
        "Type sizes above are estimated from cap height (≈0.72 em for common UI "
        "faces), with the range covering a 0.64–0.82 em cap ratio. Confirm against "
        "the real font by re-rendering a sample string and diffing it."
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


# --------------------------------------------------------------------------- #
# main
# --------------------------------------------------------------------------- #
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Measure colours, panels, radii, type and spacing in a UI screenshot.",
        epilog=(
            "examples:\n"
            "  python3 extract_colors_and_grid.py shot.png --json spec/shot.json\n"
            "  python3 extract_colors_and_grid.py shot.png --overlay spec/shot.overlay.png \\\n"
            "      --md spec/shot.md --min-panel 24 --dpr 2\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("image", help="screenshot to measure")
    p.add_argument("--json", help="write the full measurement report here")
    p.add_argument("--md", help="write a human-readable summary here")
    p.add_argument("--overlay", help="write a debug image with panel boxes drawn")
    p.add_argument("--crop", type=parse_rect, help="measure only x,y,w,h of the image")
    p.add_argument("--dpr", type=float, default=1.0, help="device pixel ratio of the capture (default 1)")
    p.add_argument("--colors", type=int, default=32, help="quantisation palette size (default 32)")
    p.add_argument("--top-colors", type=int, default=24, help="palette entries to report (default 24)")
    p.add_argument("--min-panel", type=int, nargs=2, default=(24, 16), metavar=("W", "H"),
                   help="smallest panel to report (default 24 16)")
    p.add_argument("--min-fill", type=float, default=0.6,
                   help="minimum fill ratio for a rectangle candidate (default 0.6)")
    p.add_argument("--bg", type=parse_hex, help="override the detected background colour")
    args = p.parse_args(argv)

    rgb = load_rgb(Path(args.image), args.crop)
    h, w = rgb.shape[:2]
    if h < 16 or w < 16:
        print("[error] image is too small to measure", file=sys.stderr)
        return 2

    idx, pal = posterize(rgb, args.colors)
    palette = exact_palette(rgb, args.top_colors)
    warnings: list[str] = []

    panels = find_panels(rgb, idx, pal, args.min_panel[0], args.min_panel[1], args.min_fill)
    if not panels:
        warnings.append(
            "no panels detected — the UI may be a gradient/photo background or one "
            "flat surface; lower --min-panel or raise --min-fill"
        )
    background = detect_background(rgb, palette)
    bg_hex = hexc(args.bg) if args.bg else (background["hex"] if background else None)
    if background and background.get("ring_share", 1.0) < 0.25:
        warnings.append(
            "the window frame is split between many colours "
            f"(largest share {background['ring_share']:.0%}) — the background is "
            "probably a gradient, texture or photo; sample it per region instead "
            "of using one hex"
        )

    # a synthetic frame panel keeps full-window text measurable when the
    # detector found no containers (e.g. a plain dialog on a flat background)
    text_panels = [p for p in panels if p["role"] == "surface" and p["w"] > 40 and p["h"] > 18]
    if not text_panels:
        text_panels = [
            {
                "x": 0,
                "y": 0,
                "w": w,
                "h": h,
                "color": bg_hex or "#FFFFFF",
                "role": "surface",
                "radius_px": 0,
            }
        ]
        warnings.append("no surface panel found; text measured against the background colour")

    texts: list[dict[str, Any]] = []
    for i, panel in enumerate(text_panels, start=1):
        if panel.get("radius_px", 0) > 0 and panel["w"] - 2 * panel["radius_px"] < 30:
            continue
        for t in analyse_text(rgb, panel):
            t["panel"] = i
            texts.append(t)

    rows = build_rows(panels)
    columns = build_columns(panels)
    gaps = [g for r in rows for g in r["gaps_px"] if g > 0]
    insets = [t["left_inset_px"] for t in texts if 0 < t["left_inset_px"] < 200]
    spacing = {
        "base": spacing_base(gaps + insets),
        "gaps_px": sorted({g for g in gaps if g > 0}),
        "insets_px": sorted({v for v in insets}),
    }

    roles = assign_roles(rgb, palette, panels, texts, background)

    report: dict[str, Any] = {
        "meta": {
            "source": str(args.image),
            "width": w,
            "height": h,
            "dpr": args.dpr,
            "generated_by": "desktop-ui-cloner/scripts/extract_colors_and_grid.py",
        },
        "roles": roles,
        "palette": palette,
        "panels": panels,
        "panels_dp": [
            {k: (round(p[k] / args.dpr, 1) if args.dpr != 1 else p[k])
             for k in ("x", "y", "w", "h", "radius_px")}
            for p in panels
        ],
        "rows": rows,
        "columns": columns,
        "text": texts,
        "spacing": spacing,
        "warnings": warnings,
    }

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(report, indent=2) + "\n")
    if args.md:
        write_markdown(report, Path(args.md))
    if args.overlay:
        render_overlay(rgb, panels, texts, Path(args.overlay))

    print(f"{args.image}: {w}x{h}, {len(palette)} colours, {len(panels)} panels, {len(texts)} text lines")
    print(f"  background {roles['background']}   surfaces "
          f"{', '.join(s['hex'] for s in roles['surfaces'][:5]) or '—'}")
    if roles["accent"]:
        print(f"  accents    {', '.join(a['hex'] for a in roles['accent'][:4])}")
    if panels:
        for i, pnl in enumerate(panels[:6], start=1):
            print(
                f"  P{i} {pnl['role']:<10} {pnl['x']:>4},{pnl['y']:<4} {pnl['w']:>4}x{pnl['h']:<4} "
                f"{pnl['color']}  r={pnl['radius_px']}"
            )
    if texts:
        sizes = sorted({t["estimated_font_size_px"] for t in texts})
        print(f"  font sizes (est) {sizes}")
    if spacing["base"]["base_px"]:
        print(
            f"  spacing base {spacing['base']['base_px']}px "
            f"(residual {spacing['base']['residual_px']}px); gaps {spacing['gaps_px']}"
        )
    for wmsg in warnings:
        print(f"  ! {wmsg}")
    written = [x for x in (args.json, args.md, args.overlay) if x]
    if written:
        print("  wrote " + ", ".join(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
