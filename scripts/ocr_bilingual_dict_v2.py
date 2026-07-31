#!/usr/bin/env python3
"""
Improved Bilingual Dictionary OCR Pipeline (v2)
================================================

PURPOSE
-------
Convert a scanned PDF dictionary (two-column trilingual layout:
English + Arabic + French, side-by-side) into a clean CSV with paired
(English, Arabic) entries.

PDF LAYOUT (verified on `معجم المصطلحات الاعلامية.pdf`)
---------------------------------------------------------
- 76 pages, each ~2147 px wide at 300 DPI
- TWO columns per page, separated by a vertical gutter at x ≈ 1073
- Each column contains dictionary entries laid out as:
      [entry_number] [English_term]  [Arabic_translation]  [French_translation]
- Entries may span 1-3 lines if Arabic or French translations are long
- Entry numbers are sequential (1, 2, 3, ... up to ~1036 in A–F range)

PREVIOUS PIPELINE FAILURE MODES
-------------------------------
1. Used `term, definition, source_file` schema → all text dumped into one column.
2. Did NOT split left/right columns → English and Arabic got mixed into one stream.
3. Treated each OCR row as one entry → produced 5,726 fragmented rows instead of
   the actual 1,036 entries (A–F range).
4. Did not separate Arabic from Latin script → noise rows slipped through.

IMPROVEMENTS IN v2
------------------
1. Renders at 300 DPI with adaptive-threshold binarization (better OCR).
2. Splits each page into LEFT and RIGHT columns at the page midpoint.
3. Within each column, groups words into Y-rows.
4. For each row, classifies words by script (Latin / Arabic / digit):
   - Leading digit run = entry number (anchors a new entry)
   - Latin words = English term
   - Arabic words = Arabic translation
   - (French words are dropped — not in the target schema)
5. Pairs English + Arabic within the same row.
6. Post-filters: skips noise (page numbers, headers, isolated digits).
7. Deduplicates and emits `id, term, definition, source_file` CSV (UTF-8 BOM).

USAGE
-----
    export TESSDATA_PREFIX=/home/z/my-project/dict_work/tessdata
    python ocr_bilingual_dict_v2.py INPUT.pdf OUTPUT.csv \\
        [--dpi 300] [--start 0] [--end 76] [--src-name NAME] \\
        [--gutter-ratio 0.5] [--row-tol 12]
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image

# ─── Config ────────────────────────────────────────────────────────────────────
TESSDATA_PREFIX = os.environ.get(
    "TESSDATA_PREFIX", "/home/z/my-project/dict_work/tessdata"
)
os.environ.setdefault("TESSDATA_PREFIX", TESSDATA_PREFIX)

# Script detectors
LATIN_RE = re.compile(r"[A-Za-z]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
DIGIT_RE = re.compile(r"^\d{1,4}$")

# Common OCR substitutions (English column)
ENGLISH_OCR_FIXES = [
    (r"\b0([a-z])", r"o\1"),
    (r"([a-z])0\b", r"\1o"),
    (r"\|", "l"),
]

# Noise patterns to skip
NOISE_PATTERNS = [
    re.compile(r"^\d{1,3}$"),                    # bare page numbers
    re.compile(r"^\©.*$"),                       # copyright
    re.compile(r"^(الجامعة|قسم|مجلة|©|صفحة)"),    # Arabic headers
    re.compile(r"^[A-Z\s]{20,}$"),               # all-caps titles
]


@dataclass
class Word:
    text: str
    x: int
    y: int
    w: int
    h: int


@dataclass
class Entry:
    entry_id: Optional[int]
    english: str
    arabic: str
    page: int
    y: int


# ─── Image preprocessing ──────────────────────────────────────────────────────

def render_page(pdf: fitz.Document, page_idx: int, dpi: int) -> np.ndarray:
    page = pdf[page_idx]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if pix.n == 4:
        img = img[:, :, :3]
    return img


def preprocess(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=15
    )
    return cv2.medianBlur(binary, 3)


# ─── OCR ──────────────────────────────────────────────────────────────────────

def ocr_words(binary_img: np.ndarray) -> List[Word]:
    """Single OCR pass with ara+eng. Returns words with bounding boxes."""
    pil = Image.fromarray(binary_img)
    data = pytesseract.image_to_data(
        pil, lang="ara+eng", config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )
    words: List[Word] = []
    for i in range(len(data["text"])):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        try:
            conf = int(data["conf"][i])
        except (ValueError, TypeError):
            conf = -1
        if conf < 30:
            continue
        words.append(
            Word(
                text=txt,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                w=int(data["width"][i]),
                h=int(data["height"][i]),
            )
        )
    return words


# ─── Column splitting + row clustering ────────────────────────────────────────

def split_columns(words: List[Word], page_width: int,
                  gutter_ratio: float = 0.5) -> Tuple[List[Word], List[Word]]:
    gutter = int(page_width * gutter_ratio)
    left = [w for w in words if w.x + w.w // 2 < gutter]
    right = [w for w in words if w.x + w.w // 2 >= gutter]
    return left, right


def cluster_rows(words: List[Word], tol: int = 12) -> List[List[Word]]:
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: w.y)
    rows: List[List[Word]] = []
    cur = [sorted_w[0]]
    cur_y = sorted_w[0].y
    for w in sorted_w[1:]:
        if abs(w.y - cur_y) <= tol:
            cur.append(w)
        else:
            rows.append(cur)
            cur = [w]
            cur_y = w.y
    rows.append(cur)
    for r in rows:
        r.sort(key=lambda w: w.x)
    return rows


# ─── Entry extraction ─────────────────────────────────────────────────────────

def classify_word(w: Word) -> str:
    """Return 'digit' | 'english' | 'arabic' | 'mixed'."""
    t = w.text
    if DIGIT_RE.match(t):
        return "digit"
    has_latin = bool(LATIN_RE.search(t))
    has_arabic = bool(ARABIC_RE.search(t))
    if has_latin and has_arabic:
        return "mixed"
    if has_arabic:
        return "arabic"
    if has_latin:
        return "english"
    return "noise"


def extract_entries_from_column(rows: List[List[Word]],
                                 page_num: int) -> List[Entry]:
    """Walk rows in one column. Each row may contain:
       - a leading digit (entry number) → start new entry
       - Latin words → English term
       - Arabic words → Arabic translation
       Continuation rows (no digit) append to the previous entry's Arabic text.

    Arabic words are sorted by X DESCENDING before joining, because Arabic is
    RTL — the rightmost word on the page is the first word of the sentence.
    """
    entries: List[Entry] = []
    current: Optional[Entry] = None

    for row in rows:
        digits: List[str] = []
        english_words: List[Word] = []
        arabic_words: List[Word] = []

        for w in row:
            kind = classify_word(w)
            if kind == "digit":
                digits.append(w.text)
            elif kind == "english":
                # Skip single-letter noise (likely OCR fragments from
                # adjacent Arabic column bleed-through)
                if len(w.text) >= 2:
                    english_words.append(w)
            elif kind == "arabic":
                arabic_words.append(w)
            elif kind == "mixed":
                lat = "".join(c for c in w.text if LATIN_RE.match(c) or c in " .;,-")
                ara = "".join(c for c in w.text if ARABIC_RE.match(c) or c in " .;,-")
                if lat.strip() and len(lat.strip()) >= 2:
                    english_words.append(Word(lat.strip(), w.x, w.y, w.w, w.h))
                if ara.strip():
                    arabic_words.append(Word(ara.strip(), w.x, w.y, w.w, w.h))

        # Sort English words LTR (by x ascending)
        english_words.sort(key=lambda w: w.x)
        # Sort Arabic words RTL (by x descending) for correct reading order
        arabic_words.sort(key=lambda w: w.x, reverse=True)

        english_parts = [w.text for w in english_words]
        arabic_parts = [w.text for w in arabic_words]

        # Determine if this row starts a new entry
        entry_id = None
        if digits:
            # Take the first digit-run as the entry ID
            try:
                entry_id = int(digits[0])
            except ValueError:
                entry_id = None

        eng_text = " ".join(english_parts).strip()
        ara_text = " ".join(arabic_parts).strip()

        # Skip totally empty rows
        if not eng_text and not ara_text and entry_id is None:
            continue

        # Apply English OCR fixes
        for pat, repl in ENGLISH_OCR_FIXES:
            eng_text = re.sub(pat, repl, eng_text)
        eng_text = re.sub(r"\s+", " ", eng_text).strip()

        # If row has entry_id AND english text → start new entry
        if entry_id is not None and eng_text:
            current = Entry(
                entry_id=entry_id,
                english=eng_text,
                arabic=ara_text,
                page=page_num,
                y=row[0].y,
            )
            entries.append(current)
        elif current is not None:
            # Continuation row: append Arabic (and rare English) to previous
            if ara_text:
                current.arabic = (current.arabic + " " + ara_text).strip()
            # If we found english but no entry_id, it might be a French
            # translation — skip it.
        else:
            # Orphan row with no preceding entry → skip
            continue

    return entries


# ─── Post-processing ──────────────────────────────────────────────────────────

def is_noise(eng: str, ara: str) -> bool:
    for pat in NOISE_PATTERNS:
        if pat.match(eng) or pat.match(ara):
            return True
    if not LATIN_RE.search(eng):
        return True
    if not ARABIC_RE.search(ara):
        return True
    if len(eng) < 2:
        return True
    return False


def clean_arabic(text: str) -> str:
    out = text.strip()
    out = re.sub(r"\s+", " ", out)
    # Remove RLM/LRM marks
    out = out.replace("\u200e", "").replace("\u200f", "")
    return out.strip()


# ─── Main pipeline ────────────────────────────────────────────────────────────

def process_pdf(pdf_path: str, output_csv: str,
                dpi: int = 300, start: int = 0, end: Optional[int] = None,
                src_name: Optional[str] = None,
                gutter_ratio: float = 0.5,
                row_tol: int = 12) -> dict:
    pdf = fitz.open(pdf_path)
    total_pages = pdf.page_count
    end = total_pages if end is None else min(end, total_pages)
    src_name = src_name or Path(pdf_path).stem

    all_entries: List[Entry] = []
    stats = {"pages": 0, "raw_entries": 0, "valid_entries": 0, "skipped": 0}

    for page_idx in range(start, end):
        page_num = page_idx + 1
        try:
            img = render_page(pdf, page_idx, dpi)
        except Exception as e:
            print(f"  [p{page_num}] render error: {e}", file=sys.stderr)
            continue

        binary = preprocess(img)
        page_width = binary.shape[1]

        words = ocr_words(binary)
        left, right = split_columns(words, page_width, gutter_ratio)

        left_rows = cluster_rows(left, tol=row_tol)
        right_rows = cluster_rows(right, tol=row_tol)

        left_entries = extract_entries_from_column(left_rows, page_num)
        right_entries = extract_entries_from_column(right_rows, page_num)

        page_entries = left_entries + right_entries
        stats["pages"] += 1
        stats["raw_entries"] += len(page_entries)

        for e in page_entries:
            e.arabic = clean_arabic(e.arabic)
            if is_noise(e.english, e.arabic):
                stats["skipped"] += 1
                continue
            all_entries.append(e)
            stats["valid_entries"] += 1

        if page_num % 5 == 0 or page_num == end:
            print(f"  [p{page_num}/{end}] cumulative: {len(all_entries)}",
                  file=sys.stderr)

    # Sort by entry_id where possible, fallback to (page, y)
    def sort_key(e: Entry):
        return (e.entry_id if e.entry_id is not None else 10**6,
                e.page, e.y)
    all_entries.sort(key=sort_key)

    # Deduplicate by (english_lower, arabic)
    seen = set()
    deduped: List[Entry] = []
    for e in all_entries:
        key = (e.english.lower(), e.arabic)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    # Reassign sequential IDs
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "term", "definition", "source_file"])
        for i, e in enumerate(deduped, start=1):
            writer.writerow([i, e.english, e.arabic, src_name])

    stats["final_entries"] = len(deduped)
    pdf.close()
    return stats


def main():
    ap = argparse.ArgumentParser(
        description="Bilingual dictionary OCR pipeline v2 (2-column trilingual layout)"
    )
    ap.add_argument("input_pdf")
    ap.add_argument("output_csv")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--src-name", default=None)
    ap.add_argument("--gutter-ratio", type=float, default=0.5,
                    help="Fraction of page width where the column gutter sits")
    ap.add_argument("--row-tol", type=int, default=12,
                    help="Y-tolerance (pixels) for row clustering")
    args = ap.parse_args()

    print(f"OCR v2: {args.input_pdf} → {args.output_csv}", file=sys.stderr)
    stats = process_pdf(
        args.input_pdf, args.output_csv,
        dpi=args.dpi, start=args.start, end=args.end,
        src_name=args.src_name,
        gutter_ratio=args.gutter_ratio,
        row_tol=args.row_tol,
    )
    print(f"\nDone. Stats: {stats}", file=sys.stderr)
    print(f"Output: {args.output_csv}")


if __name__ == "__main__":
    main()
