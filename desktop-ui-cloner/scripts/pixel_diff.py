#!/usr/bin/env python3
"""Pixel-by-pixel comparison of an original desktop-UI screenshot and a rebuild.

Example
-------
    python3 pixel_diff.py \
        --original shots/original/window.png \
        --clone    shots/clone/window.png \
        --out      diffs/window.png \
        --report   diffs/window.json \
        --mask 900,24,540,32          # a live clock / user name is dynamic

Writes a visual diff image in which every mismatched area is painted bright red,
prints a similarity score, and optionally writes a JSON report with one entry
per differing region (what changed is guessed from edges vs. flat colour).

The score deliberately ignores sub-pixel font anti-aliasing: the colour
comparison tolerates a 1px local offset (--aa-radius) and thin 1px mismatch
lines are opened away before counting. Layout shifts, spacing changes, size
changes and colour changes all survive that filtering.

Exit codes
----------
    0  score >= --fail-under (default 97) and both images are the same size
    1  score below threshold, or the two captures are not the same size
    2  bad arguments / unreadable input

Requires: pillow, numpy, scipy, scikit-image
    python3 -m pip install pillow numpy scipy scikit-image
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    from scipy import ndimage as ndi
    from skimage.color import rgb2lab
    from skimage.metrics import structural_similarity
except ImportError as exc:  # pragma: no cover - dependency guard
    sys.exit(
        f"pixel_diff.py is missing a dependency: {exc}\n"
        "Install with: python3 -m pip install pillow numpy scipy scikit-image"
    )

RED = (255, 0, 0)
BOX = (255, 64, 64)
INK = (255, 255, 255)
EXIT_PASS, EXIT_FAIL, EXIT_ERROR = 0, 1, 2


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def parse_rect(text: str) -> tuple[int, int, int, int]:
    """Parse 'x,y,w,h' (commas, spaces or 'x' separators)."""
    parts = [p for p in re.split(r"[,\sx]+", text.strip()) if p]
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"expected x,y,w,h — got {text!r}"
        )
    try:
        x, y, w, h = (int(round(float(p))) for p in parts)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"not numeric: {text!r}") from exc
    if w <= 0 or h <= 0:
        raise argparse.ArgumentTypeError(f"w and h must be > 0 — got {text!r}")
    return x, y, w, h


def load_rgb(path: Path) -> np.ndarray:
    if not path.exists():
        raise SystemExit(f"[error] no such file: {path}")
    with Image.open(path) as im:
        return np.asarray(im.convert("RGB"), dtype=np.uint8)


def mask_rects(args: argparse.Namespace) -> list[dict[str, Any]]:
    rects: list[dict[str, Any]] = []
    for r in args.mask or []:
        rects.append({"x": r[0], "y": r[1], "w": r[2], "h": r[3], "reason": "cli"})
    if args.mask_file:
        path = Path(args.mask_file)
        if not path.exists():
            raise SystemExit(f"[error] no such mask file: {path}")
        data = json.loads(path.read_text())
        entries = data.get("masks", data) if isinstance(data, dict) else data
        for item in entries:
            if isinstance(item, (list, tuple)):
                x, y, w, h = item
                rects.append({"x": x, "y": y, "w": w, "h": h, "reason": "file"})
            elif isinstance(item, dict):
                rects.append(
                    {
                        "x": int(item["x"]),
                        "y": int(item["y"]),
                        "w": int(item["w"]),
                        "h": int(item["h"]),
                        "reason": str(item.get("reason", "file")),
                    }
                )
            else:
                raise SystemExit(f"[error] unsupported mask entry: {item!r}")
    return rects


def rect_mask(shape: tuple[int, int], rects: Iterable[dict[str, Any]]) -> np.ndarray:
    """True = ignore this pixel."""
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    for r in rects:
        x0 = max(0, int(r["x"]))
        y0 = max(0, int(r["y"]))
        x1 = min(w, int(r["x"]) + int(r["w"]))
        y1 = min(h, int(r["y"]) + int(r["h"]))
        if x1 > x0 and y1 > y0:
            mask[y0:y1, x0:x1] = True
    return mask


def align_sizes(
    a: np.ndarray, b: np.ndarray, mode: str
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Return (a, b, mismatch). Pads with white or crops to the common area."""
    if a.shape == b.shape:
        return a, b, False
    ha, wa = a.shape[:2]
    hb, wb = b.shape[:2]
    if mode == "crop":
        h, w = min(ha, hb), min(wa, wb)
        return a[:h, :w], b[:h, :w], True
    h, w = max(ha, hb), max(wa, wb)
    pa = np.full((h, w, 3), 255, dtype=np.uint8)
    pb = np.full((h, w, 3), 255, dtype=np.uint8)
    pa[:ha, :wa] = a
    pb[:hb, :wb] = b
    return pa, pb, True


def luma(rgb: np.ndarray) -> np.ndarray:
    return (
        0.2126 * rgb[..., 0].astype(np.float32)
        + 0.7152 * rgb[..., 1].astype(np.float32)
        + 0.0722 * rgb[..., 2].astype(np.float32)
    )


def edge_map(rgb: np.ndarray) -> np.ndarray:
    g = luma(rgb)
    return np.hypot(ndi.sobel(g, axis=0), ndi.sobel(g, axis=1))


def load_font(size: int = 14) -> Any:
    try:  # Pillow >= 10.1
        return ImageFont.load_default(size=size)
    except TypeError:  # pragma: no cover - older Pillow
        return ImageFont.load_default()


def hexc(rgb: tuple[float, float, float] | np.ndarray) -> str:
    r, g, b = (int(round(float(v))) for v in rgb[:3])
    return f"#{r:02X}{g:02X}{b:02X}"


# --------------------------------------------------------------------------- #
# comparison
# --------------------------------------------------------------------------- #
def delta_e_map(lab_a: np.ndarray, lab_b: np.ndarray) -> np.ndarray:
    d = lab_a - lab_b
    return np.sqrt(d[..., 0] ** 2 + d[..., 1] ** 2 + d[..., 2] ** 2)


def downsample_box(rgb: np.ndarray, factor: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    if factor <= 1 or min(h, w) <= 6 * factor:
        return rgb
    w2, h2 = (w // factor) * factor, (h // factor) * factor
    return np.asarray(
        Image.fromarray(rgb[:h2, :w2]).resize((w2 // factor, h2 // factor), Image.BOX)
    )


def detail_metrics(
    a: np.ndarray,
    b: np.ndarray,
    ignore: np.ndarray | None = None,
    factor: int = 2,
    content_threshold: float = 20.0,
) -> tuple[float, float, float]:
    """SSIM on a box-downsampled pair, reported twice.

    A whole-window mean is useless for a UI: most of a desktop window is flat
    panels, so a rebuilt window with the wrong font still scores 0.98 there. The
    number that decides the verdict is the mean SSIM over *content* cells — cells
    that contain an edge in either image (text, icons, borders, chrome) — with
    the caller's dynamic-content mask removed.

    Returns (ssim_overall, ssim_content, content_coverage).
    """
    da, db = downsample_box(a, factor), downsample_box(b, factor)
    ga = luma(da).astype(np.float64)
    gb = luma(db).astype(np.float64)
    ssim_map = structural_similarity(
        ga,
        gb,
        gaussian_weights=True,
        sigma=2.0,
        use_sample_covariance=False,
        data_range=255,
        full=True,
    )[1]
    overall = float(ssim_map.mean())
    ea = np.hypot(ndi.sobel(ga, axis=0), ndi.sobel(ga, axis=1))
    eb = np.hypot(ndi.sobel(gb, axis=0), ndi.sobel(gb, axis=1))
    content = np.maximum(ea, eb) > content_threshold
    content = ndi.binary_dilation(content, structure=np.ones((3, 3), bool))
    if ignore is not None:
        ig = np.asarray(
            Image.fromarray((ignore * 255).astype(np.uint8)).resize(
                (ga.shape[1], ga.shape[0]), Image.BOX
            )
        ) > 8
        content &= ~ig
    coverage = float(content.mean())
    detail = float(ssim_map[content].mean()) if content.any() else 1.0
    return overall, detail, coverage


def classify_region(
    edges_a: np.ndarray,
    edges_b: np.ndarray,
    de: np.ndarray,
    mean_de: float,
    bbox_h: int,
) -> str:
    """Guess why a region differs, from edges vs. flat colour.

    The caller passes the region *plus a margin*, because a colour-offset strip
    sits next to a moved edge and the edge itself may be clean in both images.
    """
    disagree = float(np.mean((edges_a > 60) != (edges_b > 60)))
    mag = float(np.mean(np.abs(edges_a - edges_b))) / 20.0
    if mag >= 1.0 and disagree >= 0.08:
        return "layout/structure — element moved, resized, missing or misaligned"
    if disagree >= 0.15:
        return "typography — glyph size, weight, tracking or wrapping differs"
    if mean_de > 18:
        return "color/fill — surface, border or accent shade differs"
    if bbox_h <= 22:
        return "detail — radius, 1px border, shadow or icon stroke"
    return "small area — spacing or edge anti-aliasing"


def probe_shift(
    a: np.ndarray,
    b: np.ndarray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    frame_w: int,
    frame_h: int,
    window: int = 96,
    max_shift: int = 8,
) -> tuple[int, int, str]:
    """Does this area match better when displaced? Returns (dx, dy, cause).

    A region whose colour is off *because an element moved* looks like a flat
    strip next to an edge, not like a moved edge. Searching a small displacement
    around the region turns that into an actionable answer: "this matches if
    moved by (-8, 0) px"."""
    cw, ch = min(window, frame_w), min(window, frame_h)
    if cw < 16 or ch < 16:
        return 0, 0, ""
    cx = max(0, min(frame_w - cw, (x0 + x1) // 2 - cw // 2))
    cy = max(0, min(frame_h - ch, (y0 + y1) // 2 - ch // 2))
    wa = a[cy : cy + ch, cx : cx + cw]
    wb = b[cy : cy + ch, cx : cx + cw]
    base_err = float(np.abs(wa - wb).mean())
    if base_err < 0.5:
        return 0, 0, ""
    best = (base_err, 0, 0)
    for dy in range(-max_shift, max_shift + 1):
        ay0, ay1 = max(0, dy), min(ch, ch + dy)
        by0, by1 = max(0, -dy), min(ch, ch - dy)
        if ay1 - ay0 < ch // 2:
            continue
        for dx in range(-max_shift, max_shift + 1):
            if dx == 0 and dy == 0:
                continue
            ax0, ax1 = max(0, dx), min(cw, cw + dx)
            bx0, bx1 = max(0, -dx), min(cw, cw - dx)
            if ax1 - ax0 < cw // 2:
                continue
            err = float(
                np.abs(wa[ay0:ay1, ax0:ax1] - wb[by0:by1, bx0:bx1]).mean()
            )
            if err < best[0]:
                best = (err, dx, dy)
    err, dx, dy = best
    if (dx or dy) and err <= 0.7 * base_err:
        improvement = (1.0 - err / base_err) * 100.0
        # the search shifts the clone back onto the original, so the offset the
        # rebuild has to apply is the opposite sign
        move_x, move_y = -dx, -dy
        return (
            move_x,
            move_y,
            f"layout/shift — aligns {improvement:.0f}% better if the clone's "
            f"content moves by ({move_x:+d}, {move_y:+d}) px",
        )
    return 0, 0, ""


def render_diff(
    orig: np.ndarray,
    mismatch: np.ndarray,
    regions: list[dict[str, Any]],
    out: Path,
    title: str,
) -> None:
    """Bright red where the clone differs, over a dimmed copy of the original."""
    base = Image.fromarray(orig).convert("RGB")
    base = Image.blend(base, Image.new("RGB", base.size, (10, 10, 12)), 0.62)
    alpha = Image.fromarray((mismatch * 255).astype(np.uint8), mode="L")
    base.paste(Image.new("RGB", base.size, RED), (0, 0), alpha)

    draw = ImageDraw.Draw(base)
    font = load_font(13)
    for i, reg in enumerate(regions, start=1):
        x, y, w, h = reg["x"], reg["y"], reg["w"], reg["h"]
        draw.rectangle([x, y, x + w - 1, y + h - 1], outline=BOX, width=1)
        label = str(i)
        tw = draw.textlength(label, font=font)
        draw.rectangle([x, max(0, y - 15), x + tw + 6, max(0, y - 15) + 15], fill=BOX)
        draw.text((x + 3, max(0, y - 14)), label, fill=(20, 0, 0), font=font)

    bar = 20
    canvas = Image.new("RGB", (base.width, base.height + bar), (18, 18, 20))
    canvas.paste(base, (0, bar))
    ImageDraw.Draw(canvas).text((6, 4), title, fill=INK, font=font)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def render_composite(
    orig: np.ndarray,
    clone: np.ndarray,
    diff: np.ndarray,
    mismatch: np.ndarray,
    regions: list[dict[str, Any]],
    out: Path,
) -> None:
    """original | clone | diff, side by side, for eyeballing the red areas."""
    gap, bar = 12, 22
    h, w = orig.shape[:2]
    canvas = Image.new("RGB", (w * 3 + gap * 2, h + bar), (24, 24, 26))
    panels = [
        ("original", Image.fromarray(orig)),
        ("clone", Image.fromarray(clone)),
        ("diff (red = mismatch)", Image.fromarray(diff)),
    ]
    draw = ImageDraw.Draw(canvas)
    font = load_font(13)
    for i, (label, img) in enumerate(panels):
        x = i * (w + gap)
        canvas.paste(img, (x, bar))
        draw.text((x + 4, 5), label, fill=INK, font=font)
    for reg in regions:
        x, y, ww, hh = reg["x"], reg["y"] + bar, reg["w"], reg["h"]
        draw.rectangle([x, y, x + ww - 1, y + hh - 1], outline=BOX, width=1)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def analyse(args: argparse.Namespace) -> int:
    original_path, clone_path = Path(args.original), Path(args.clone)
    orig_raw = load_rgb(original_path)
    clone_raw = load_rgb(clone_path)

    orig, clone, size_mismatch = align_sizes(orig_raw, clone_raw, args.on_size_mismatch)
    h, w = orig.shape[:2]
    total = h * w

    ignore = rect_mask((h, w), mask_rects(args))
    valid = ~ignore
    valid_count = int(valid.sum())
    if valid_count == 0:
        raise SystemExit("[error] the ignore masks cover the whole frame")

    lab_a = rgb2lab(orig.astype(np.float32) / 255.0).astype(np.float32)
    lab_b = rgb2lab(clone.astype(np.float32) / 255.0).astype(np.float32)
    de = delta_e_map(lab_a, lab_b)

    # --- noise suppression ------------------------------------------------- #
    # 1. tolerate a 1px local offset: sub-pixel glyph rasterisation moves edges
    de_local = (
        ndi.minimum_filter(de, size=2 * args.aa_radius + 1)
        if args.aa_radius > 0
        else de
    )
    candidate = de_local > args.color_tolerance

    # 2. kill thin 1-2px lines only when they are low-contrast: that is exactly
    #    what an anti-aliased glyph edge looks like. A thin line far from the
    #    reference colour is a real difference (icon stroke, hairline border).
    if args.aa_radius > 0:
        opened = ndi.binary_opening(candidate, structure=np.ones((3, 3), bool))
        thin = candidate & ~opened
        candidate = candidate & ~(thin & (de_local < args.aa_contrast))

    # 3. drop specks smaller than min_region_px
    labels, n = ndi.label(candidate)
    if n:
        sizes = ndi.sum(candidate, labels, index=np.arange(1, n + 1))
        keep = np.zeros(n + 1, dtype=bool)
        keep[1:] = sizes >= args.min_region_px
        candidate = keep[labels]

    mismatch = candidate & valid

    # --- score ------------------------------------------------------------- #
    mismatch_fraction = float(mismatch.sum()) / valid_count
    ssim_overall, ssim_detail, content_coverage = detail_metrics(orig, clone, ignore)
    mean_de = float(de[valid].mean())
    tone_penalty = min(max(mean_de, 0.0) / 10.0, 1.0)
    penalty = (
        0.25 * mismatch_fraction
        + 0.65 * (1.0 - ssim_detail)
        + 0.10 * tone_penalty
    )
    score = max(0.0, min(100.0, 100.0 * (1.0 - penalty)))
    pixel_score = 100.0 * (1.0 - mismatch_fraction)

    # --- regions ----------------------------------------------------------- #
    edges_a = edge_map(orig)
    edges_b = edge_map(clone)
    orig_luma = luma(orig)
    clone_luma = luma(clone)
    margin = args.classify_margin
    regions: list[dict[str, Any]] = []
    rlab, rn = ndi.label(mismatch)
    if rn:
        for idx, sl in enumerate(ndi.find_objects(rlab), start=1):
            if sl is None:
                continue
            comp = rlab[sl] == idx
            area = int(comp.sum())
            if area < args.min_region_px:
                continue
            y0, y1 = sl[0].start, sl[0].stop
            x0, x1 = sl[1].start, sl[1].stop
            sub_de = de[sl][comp]
            region_de = float(sub_de.mean())
            cy0, cy1 = max(0, y0 - margin), min(h, y1 + margin)
            cx0, cx1 = max(0, x0 - margin), min(w, x1 + margin)
            dx, dy, shift_cause = probe_shift(orig_luma, clone_luma, x0, y0, x1, y1, w, h)
            regions.append(
                {
                    "x": int(x0),
                    "y": int(y0),
                    "w": int(x1 - x0),
                    "h": int(y1 - y0),
                    "area_px": area,
                    "mismatch_share": round(area / max(1, int(mismatch.sum())), 4),
                    "mean_delta_e": round(region_de, 2),
                    "max_delta_e": round(float(sub_de.max()), 2),
                    "original_color": hexc(orig[sl][comp].mean(axis=0)),
                    "clone_color": hexc(clone[sl][comp].mean(axis=0)),
                    "likely_cause": shift_cause
                    or classify_region(
                        edges_a[cy0:cy1, cx0:cx1],
                        edges_b[cy0:cy1, cx0:cx1],
                        sub_de,
                        region_de,
                        int(y1 - y0),
                    ),
                    "suggested_shift": [dx, dy] if shift_cause else None,
                }
            )
    regions.sort(key=lambda r: r["area_px"], reverse=True)
    if size_mismatch:
        regions.insert(
            0,
            {
                "x": 0,
                "y": 0,
                "w": int(w),
                "h": int(h),
                "area_px": total,
                "mismatch_share": 1.0,
                "mean_delta_e": 0.0,
                "max_delta_e": 0.0,
                "original_color": "",
                "clone_color": "",
                "likely_cause": (
                    f"canvas size differs — original {orig_raw.shape[1]}x{orig_raw.shape[0]}, "
                    f"clone {clone_raw.shape[1]}x{clone_raw.shape[0]}; capture both at the "
                    "same window size"
                ),
            },
        )

    passed = bool(score >= args.fail_under and not size_mismatch)
    verdict = "PASS" if passed else "FAIL"

    # --- outputs ----------------------------------------------------------- #
    if args.out:
        render_diff(
            orig,
            mismatch,
            regions[: args.max_boxes],
            Path(args.out),
            f"{verdict}  score {score:.2f}%  (threshold {args.fail_under:.1f}%)  "
            f"red = {int(mismatch.sum())} mismatched px",
        )
    composite_path = None
    if args.composite:
        diff_rgb = np.asarray(
            Image.open(args.out).convert("RGB").crop((0, 20, w, h + 20))
        ) if args.out else orig.copy()
        render_composite(orig, clone, diff_rgb, mismatch, regions[: args.max_boxes], Path(args.composite))
        composite_path = str(args.composite)

    report = {
        "verdict": verdict,
        "score": round(score, 3),
        "threshold": args.fail_under,
        "score_formula": (
            "100 * (1 - (0.25 * mismatch_fraction + 0.65 * (1 - ssim_detail) "
            "+ 0.10 * min(mean_delta_e / 10, 1)))"
        ),
        "pixel_match_percent": round(pixel_score, 3),
        "ssim_detail": round(ssim_detail, 5),
        "ssim_overall": round(ssim_overall, 5),
        "content_coverage": round(content_coverage, 5),
        "tone_penalty": round(tone_penalty, 5),
        "mismatch_fraction": round(mismatch_fraction, 6),
        "mismatch_px": int(mismatch.sum()),
        "compared_px": valid_count,
        "mean_delta_e": round(mean_de, 3),
        "p95_delta_e": round(float(np.percentile(de[valid], 95)), 3),
        "size_mismatch": bool(size_mismatch),
        "original": {
            "path": str(original_path),
            "width": int(orig_raw.shape[1]),
            "height": int(orig_raw.shape[0]),
        },
        "clone": {
            "path": str(clone_path),
            "width": int(clone_raw.shape[1]),
            "height": int(clone_raw.shape[0]),
        },
        "parameters": {
            "color_tolerance_delta_e": args.color_tolerance,
            "aa_radius_px": args.aa_radius,
            "min_region_px": args.min_region_px,
            "ignored_rects": mask_rects(args),
        },
        "diff_image": str(args.out) if args.out else None,
        "composite_image": composite_path,
        "regions": regions[: args.max_regions],
        "regions_total": len(regions),
    }

    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=2) + "\n")
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print_report(report, args)
    return EXIT_PASS if passed else EXIT_FAIL


def print_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    o, c = report["original"], report["clone"]
    print(f"original : {o['path']}  {o['width']}x{o['height']}")
    print(f"clone    : {c['path']}  {c['width']}x{c['height']}")
    if report["size_mismatch"]:
        print("!! canvas sizes differ — re-capture both windows at the same size")
    print(
        f"score    : {report['score']:.2f}   threshold {report['threshold']:.1f}   "
        f"{report['verdict']}"
    )
    print(f"  pixel match      : {report['pixel_match_percent']:.2f}%   "
          f"({report['mismatch_px']:,} of {report['compared_px']:,} px differ)")
    print(f"  detail (SSIM)    : {report['ssim_detail']:.4f} over content cells   "
          f"(whole frame {report['ssim_overall']:.4f})")
    print(f"  colour           : mean deltaE {report['mean_delta_e']:.2f}   "
          f"p95 {report['p95_delta_e']:.2f}")
    if report["diff_image"]:
        print(f"  diff image       : {report['diff_image']}")
    if report["composite_image"]:
        print(f"  composite        : {report['composite_image']}")

    regions = report["regions"][: args.top]
    if not regions:
        print("regions  : none — nothing above the noise floor")
        return
    print(f"regions  : {report['regions_total']} total, largest first")
    for i, r in enumerate(regions, start=1):
        print(
            f"  {i:>2}. {r['x']:>5},{r['y']:<5} {r['w']:>4}x{r['h']:<4} "
            f"dE {r['mean_delta_e']:>5.1f}  {r['original_color'] or '--':>7} -> "
            f"{r['clone_color'] or '--':<7} {r['likely_cause']}"
        )
    print(
        "\nnext: open the diff image, fix the red areas in the code (largest region "
        "first), then re-run this command."
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Compare an original desktop-UI screenshot with its clone.",
        epilog=(
            "examples:\n"
            "  python3 pixel_diff.py -o shots/original/window.png -c shots/clone/window.png \\\n"
            "      --out diffs/window.png --report diffs/window.json\n"
            "  python3 pixel_diff.py -o a.png -c b.png --out diff.png \\\n"
            "      --mask 1200,20,240,40 --mask-file masks.json --fail-under 97\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--original", "-o", required=True, help="reference screenshot")
    p.add_argument("--clone", "-c", required=True, help="screenshot of the rebuild")
    p.add_argument("--out", help="visual diff image (bright red = mismatch)")
    p.add_argument("--composite", help="original | clone | diff strip")
    p.add_argument("--report", help="JSON report path")
    p.add_argument("--json", action="store_true", help="print the JSON report instead of the summary")
    p.add_argument(
        "--fail-under",
        type=float,
        default=97.0,
        help="similarity threshold that counts as a pass (default: 97)",
    )
    p.add_argument(
        "--color-tolerance",
        type=float,
        default=4.0,
        help="per-pixel CIELAB deltaE below which colours count as equal (default: 4.0)",
    )
    p.add_argument(
        "--aa-contrast",
        type=float,
        default=22.0,
        help="thin 1-2px mismatches below this deltaE are treated as glyph "
        "anti-aliasing and ignored (default: 22.0)",
    )
    p.add_argument(
        "--classify-margin",
        type=int,
        default=8,
        help="px of context used when guessing why a region differs (default: 8)",
    )
    p.add_argument(
        "--aa-radius",
        type=int,
        default=1,
        choices=(0, 1, 2),
        help="local offset tolerance in px that absorbs anti-aliasing (default: 1)",
    )
    p.add_argument(
        "--min-region-px",
        type=int,
        default=24,
        help="ignore mismatch blobs smaller than this (default: 24)",
    )
    p.add_argument(
        "--mask",
        type=parse_rect,
        action="append",
        metavar="X,Y,W,H",
        help="ignore this rectangle (repeatable) — use it for clocks, avatars, live data",
    )
    p.add_argument("--mask-file", help="JSON list of {x,y,w,h,reason} rectangles to ignore")
    p.add_argument(
        "--on-size-mismatch",
        choices=("pad", "crop", "fail"),
        default="pad",
        help="what to do when the two images are not the same size (default: pad)",
    )
    p.add_argument("--top", type=int, default=6, help="regions to print (default: 6)")
    p.add_argument("--max-regions", type=int, default=40, help="regions stored in the report")
    p.add_argument("--max-boxes", type=int, default=25, help="region boxes drawn on the diff")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.on_size_mismatch == "fail":
        a = load_rgb(Path(args.original))
        b = load_rgb(Path(args.clone))
        if a.shape != b.shape:
            print(
                f"[error] sizes differ: {a.shape[1]}x{a.shape[0]} vs "
                f"{b.shape[1]}x{b.shape[0]} — capture both windows at the same size",
                file=sys.stderr,
            )
            return EXIT_FAIL
    try:
        return analyse(args)
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - unexpected
        print(f"[error] {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
