#!/usr/bin/env python3
"""
Universal Dictionary OCR Pipeline v3
=====================================

A comprehensive pipeline for converting scanned PDF dictionaries into
clean CSV files with the schema: id, English, Arabic

KEY FEATURES (v3):
------------------
1. Auto-detect layout: single-column vs two-column
2. Smart text extraction for text-based PDFs (with Arabic correction)
3. OCR for scanned PDFs with preprocessing (300 DPI, adaptive threshold)
4. Bilingual entry extraction with script-based word classification
5. Conservative spell correction using dictionary data
6. Quality reporting with PDF deletion notes
7. Chunked processing for large files
8. Resume support (progress tracking)

USAGE:
------
    export TESSDATA_PREFIX=/home/z/my-project/tessdata
    python ocr_dict_pipeline_v3.py INPUT.pdf OUTPUT.csv [options]

    # Process in chunks for large files:
    python ocr_dict_pipeline_v3.py INPUT.pdf OUTPUT.csv --chunk-size 20 --chunk 0
    python ocr_dict_pipeline_v3.py INPUT.pdf OUTPUT.csv --chunk-size 20 --chunk 1
    # Then merge:
    python ocr_dict_pipeline_v3.py --merge OUTPUT.csv chunk_*.csv

OUTPUT:
-------
    CSV with columns: id, English, Arabic
    Plus a quality report JSON file
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image

# ─── Configuration ────────────────────────────────────────────────────────────

TESSDATA_PREFIX = os.environ.get(
    "TESSDATA_PREFIX", "/home/z/my-project/tessdata"
)
os.environ.setdefault("TESSDATA_PREFIX", TESSDATA_PREFIX)

# Script detection patterns
LATIN_RE = re.compile(r"[A-Za-z]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
DIGIT_RE = re.compile(r"^\d{1,5}$")

# Common OCR error corrections for English
ENGLISH_OCR_FIXES = [
    (r"\b0([a-z])", r"o\1"),       # 0 → o at start
    (r"([a-z])0\b", r"\1o"),       # 0 → o at end
    (r"\|([a-z])", r"l\1"),        # | → l before letter
    (r"([a-z])\|", r"\1l"),        # | → l after letter
    (r"\brn\b", "m"),              # rn → m (common OCR error)
    (r"\bcl\b", "d"),              # cl → d in some contexts
]

# Noise patterns to skip
NOISE_PATTERNS = [
    re.compile(r"^\d{1,3}$"),                       # bare page numbers
    re.compile(r"^\©.*$"),                           # copyright
    re.compile(r"^(الجامعة|قسم|مجلة|©|صفحة|المحتوى|الفهرس)"),  # Arabic headers
    re.compile(r"^[A-Z\s]{20,}$"),                  # all-caps titles
    re.compile(r"^(Digitized|Internet Archive|Google|University|Library|Catholic Press)"),  # boilerplate
    re.compile(r"^\d{1,3}\s*$"),                    # just numbers
]

# Arabic text normalization
ARABIC_NORMALIZE = [
    ("\u0622", "\u0627"),   # Alef with madda → Alef
    ("\u0623", "\u0627"),   # Alef with hamza above → Alef
    ("\u0625", "\u0627"),   # Alef with hamza below → Alef
    ("\u0624", "\u0648"),   # Waw with hamza → Waw
    ("\u0626", "\u064A"),   # Ya with hamza → Ya
    ("\u0649", "\u064A"),   # Alef maqsura → Ya
    ("\u0670", ""),         # Superscript alef → remove
    ("\u064B", ""),         # Fathatan → remove
    ("\u064C", ""),         # Dammatan → remove
    ("\u064D", ""),         # Kasratan → remove
    ("\u064E", ""),         # Fatha → remove
    ("\u064F", ""),         # Damma → remove
    ("\u0650", ""),         # Kasra → remove
    ("\u0651", ""),         # Shadda → remove
    ("\u0652", ""),         # Sukun → remove
]


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class Word:
    text: str
    x: int
    y: int
    w: int
    h: int
    conf: int = 100


@dataclass
class Entry:
    entry_id: Optional[int]
    english: str
    arabic: str
    page: int
    y: int
    confidence: float = 1.0


@dataclass
class PageAnalysis:
    """Results of analyzing a page layout."""
    is_scanned: bool
    has_text: bool
    num_columns: int
    gutter_x: int
    page_width: int
    page_height: int
    avg_image_size: Tuple[int, int]


@dataclass
class QualityReport:
    """Quality report for a processed dictionary."""
    pdf_name: str
    total_pages: int
    pages_processed: int
    total_entries: int
    entries_with_english: int
    entries_with_arabic: int
    entries_with_both: int
    avg_english_len: float
    avg_arabic_len: float
    estimated_accuracy: float
    layout_type: str
    pdf_deletable: bool
    deletion_note: str
    processing_time_sec: float
    errors: List[str] = field(default_factory=list)


# ─── Spell Corrector ─────────────────────────────────────────────────────────

class ConservativeSpellCorrector:
    """Conservative spell corrector using dictionary data.
    
    Only corrects words that are very close to a known word (threshold 0.85).
    Avoids over-correction of Arabic text.
    """

    def __init__(self, dict_path: Optional[str] = None):
        self.english_words: Set[str] = set()
        self.arabic_words: Set[str] = set()
        self.english_freq: Dict[str, int] = defaultdict(int)
        self.arabic_freq: Dict[str, int] = defaultdict(int)
        if dict_path:
            self.load_dictionary(dict_path)

    def load_dictionary(self, path: str):
        """Load spell dictionary from JSON file."""
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            self.english_words = set(data.get("english", []))
            self.arabic_words = set(data.get("arabic", []))
        elif isinstance(data, list):
            for word in data:
                w = word.strip()
                if LATIN_RE.search(w):
                    self.english_words.add(w.lower())
                elif ARABIC_RE.search(w):
                    self.arabic_words.add(w)

    def load_from_csvs(self, csv_dir: str):
        """Build spell dictionary from existing CSV files."""
        import glob
        for csv_path in glob.glob(os.path.join(csv_dir, "*.csv")):
            try:
                with open(csv_path, "r", encoding="utf-8-sig") as f:
                    reader = csv.reader(f)
                    header = next(reader, None)
                    if not header:
                        continue
                    # Find English and Arabic columns
                    en_idx = ar_idx = None
                    for i, h in enumerate(header):
                        h_lower = h.lower().strip()
                        if h_lower in ("english", "term", "en", "eng"):
                            en_idx = i
                        elif h_lower in ("arabic", "definition", "ar", "ara"):
                            ar_idx = i
                    if en_idx is None and ar_idx is None:
                        # Try position-based
                        if len(header) >= 3:
                            en_idx = 1
                            ar_idx = 2
                        elif len(header) >= 2:
                            en_idx = 0
                            ar_idx = 1

                    for row in reader:
                        try:
                            if en_idx is not None and en_idx < len(row):
                                for w in row[en_idx].split():
                                    w = w.strip().lower()
                                    if w and LATIN_RE.search(w):
                                        self.english_words.add(w)
                                        self.english_freq[w] += 1
                            if ar_idx is not None and ar_idx < len(row):
                                for w in row[ar_idx].split():
                                    w = self.normalize_arabic(w.strip())
                                    if w and ARABIC_RE.search(w):
                                        self.arabic_words.add(w)
                                        self.arabic_freq[w] += 1
                        except (IndexError, AttributeError):
                            continue
            except Exception:
                continue

    @staticmethod
    def normalize_arabic(text: str) -> str:
        out = text
        for old, new in ARABIC_NORMALIZE:
            out = out.replace(old, new)
        return out.strip()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        """Simple similarity based on longest common subsequence ratio."""
        if not a or not b:
            return 0.0
        if a == b:
            return 1.0
        # Use a simple approach: ratio of common characters
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()

    def correct_english(self, word: str, threshold: float = 0.85) -> str:
        """Correct a single English word if it's close to a known word."""
        if not word:
            return word
        w_lower = word.lower()
        if w_lower in self.english_words:
            return word
        # Only try correction for words >= 3 chars
        if len(w_lower) < 3:
            return word
        best_match = None
        best_sim = 0.0
        # Quick check: only compare with words of similar length
        target_len = len(w_lower)
        for dict_word in self.english_words:
            if abs(len(dict_word) - target_len) > 2:
                continue
            sim = self._similarity(w_lower, dict_word)
            if sim > best_sim:
                best_sim = sim
                best_match = dict_word
        if best_sim >= threshold and best_match:
            return best_match
        return word

    def correct_arabic(self, word: str, threshold: float = 0.85) -> str:
        """Correct a single Arabic word if it's close to a known word."""
        if not word:
            return word
        norm = self.normalize_arabic(word)
        if norm in self.arabic_words:
            return word  # Keep original if normalized form matches
        if len(norm) < 2:
            return word
        best_match = None
        best_sim = 0.0
        target_len = len(norm)
        for dict_word in self.arabic_words:
            if abs(len(dict_word) - target_len) > 2:
                continue
            sim = self._similarity(norm, dict_word)
            if sim > best_sim:
                best_sim = sim
                best_match = dict_word
        if best_sim >= threshold and best_match:
            return best_match
        return word

    def correct_text(self, text: str, lang: str = "english") -> str:
        """Correct all words in a text string."""
        words = text.split()
        corrected = []
        for w in words:
            if lang == "english":
                corrected.append(self.correct_english(w))
            else:
                corrected.append(self.correct_arabic(w))
        return " ".join(corrected)


# ─── Image Preprocessing ─────────────────────────────────────────────────────

def render_page(pdf: fitz.Document, page_idx: int, dpi: int = 300) -> np.ndarray:
    """Render a PDF page as a numpy array at specified DPI."""
    page = pdf[page_idx]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if pix.n == 4:
        img = img[:, :, :3]
    return img


def preprocess_image(img: np.ndarray, method: str = "auto") -> np.ndarray:
    """Preprocess image for better OCR.
    
    Methods:
        - 'auto': adaptive threshold + denoise
        - 'simple': grayscale + Otsu threshold
        - 'enhanced': CLAHE + adaptive threshold + denoise
        - 'none': no preprocessing
    """
    if method == "none":
        return img

    # Convert to grayscale
    if img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        gray = img.copy()

    if method == "simple":
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    if method == "enhanced":
        # CLAHE for contrast enhancement
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        # Adaptive threshold
        binary = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, blockSize=31, C=15
        )
        # Denoise
        return cv2.medianBlur(binary, 3)

    # Default: auto (adaptive threshold + denoise)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=15
    )
    return cv2.medianBlur(binary, 3)


# ─── Layout Detection ─────────────────────────────────────────────────────────

def analyze_page_layout(pdf: fitz.Document, page_idx: int, dpi: int = 150) -> PageAnalysis:
    """Analyze a page to determine its layout (columns, text vs scanned)."""
    page = pdf[page_idx]

    # Check if page has text
    text = page.get_text().strip()
    has_text = len(text) > 50

    # Check for images
    images = page.get_images()
    is_scanned = len(images) > 0

    # Render at low DPI for layout analysis
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
        pix.height, pix.width, pix.n
    )
    if pix.n == 4:
        img = img[:, :, :3]

    page_width = pix.width
    page_height = pix.height

    # Detect columns using vertical whitespace analysis
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    # Project binary content vertically (sum of black pixels per column)
    col_proj = np.sum(binary, axis=0)

    # Find the gutter (vertical whitespace in the middle)
    mid_start = page_width // 4
    mid_end = 3 * page_width // 4
    mid_proj = col_proj[mid_start:mid_end]

    # Find the column with minimum content (gutter)
    gutter_offset = np.argmin(mid_proj)
    gutter_x = mid_start + gutter_offset

    # Check if there's a significant gutter (columns detected)
    min_val = mid_proj[gutter_offset]
    avg_val = np.mean(mid_proj)
    num_columns = 2 if avg_val > 0 and min_val < avg_val * 0.3 else 1

    # Average image size
    avg_img_size = (0, 0)
    if images:
        img_sizes = []
        for img_info in images:
            try:
                xref = img_info[0]
                base_image = pdf.extract_image(xref)
                if base_image:
                    img_sizes.append((base_image.get("width", 0), base_image.get("height", 0)))
            except Exception:
                continue
        if img_sizes:
            avg_w = sum(s[0] for s in img_sizes) / len(img_sizes)
            avg_h = sum(s[1] for s in img_sizes) / len(img_sizes)
            avg_img_size = (int(avg_w), int(avg_h))

    return PageAnalysis(
        is_scanned=is_scanned,
        has_text=has_text,
        num_columns=num_columns,
        gutter_x=gutter_x,
        page_width=page_width,
        page_height=page_height,
        avg_image_size=avg_img_size,
    )


def detect_layout_type(pdf: fitz.Document, sample_pages: int = 5) -> PageAnalysis:
    """Detect the layout type by analyzing a sample of pages."""
    total = pdf.page_count
    analyses = []
    for i in range(min(sample_pages, total)):
        # Skip first few pages (usually covers, TOC)
        idx = min(i + 5, total - 1)
        try:
            a = analyze_page_layout(pdf, idx)
            analyses.append(a)
        except Exception:
            continue

    if not analyses:
        # Default
        return PageAnalysis(
            is_scanned=True, has_text=False, num_columns=1,
            gutter_x=0, page_width=0, page_height=0, avg_image_size=(0, 0)
        )

    # Use majority vote
    is_scanned = sum(1 for a in analyses if a.is_scanned) > len(analyses) / 2
    has_text = sum(1 for a in analyses if a.has_text) > len(analyses) / 2
    num_columns = 2 if sum(1 for a in analyses if a.num_columns == 2) > len(analyses) / 2 else 1

    # Average gutter position
    gutters = [a.gutter_x for a in analyses if a.num_columns == 2]
    gutter_x = int(np.mean(gutters)) if gutters else 0

    # Average page dimensions
    page_width = int(np.mean([a.page_width for a in analyses]))
    page_height = int(np.mean([a.page_height for a in analyses]))

    # Average image size
    img_sizes = [a.avg_image_size for a in analyses if a.avg_image_size[0] > 0]
    avg_img_size = (
        int(np.mean([s[0] for s in img_sizes])),
        int(np.mean([s[1] for s in img_sizes]))
    ) if img_sizes else (0, 0)

    return PageAnalysis(
        is_scanned=is_scanned, has_text=has_text, num_columns=num_columns,
        gutter_x=gutter_x, page_width=page_width, page_height=page_height,
        avg_image_size=avg_img_size,
    )


# ─── OCR Engine ───────────────────────────────────────────────────────────────

def ocr_words(binary_img: np.ndarray, lang: str = "ara+eng",
              psm: int = 6, min_conf: int = 30) -> List[Word]:
    """Run OCR on a preprocessed image and return words with bounding boxes."""
    pil = Image.fromarray(binary_img)
    data = pytesseract.image_to_data(
        pil, lang=lang, config=f"--psm {psm}",
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
        if conf < min_conf:
            continue
        words.append(
            Word(
                text=txt,
                x=int(data["left"][i]),
                y=int(data["top"][i]),
                w=int(data["width"][i]),
                h=int(data["height"][i]),
                conf=conf,
            )
        )
    return words


def ocr_words_dual_pass(binary_img: np.ndarray, min_conf: int = 30) -> List[Word]:
    """Dual-pass OCR: separate passes for English and Arabic for better accuracy."""
    all_words: List[Word] = {}

    # Pass 1: English
    eng_words = ocr_words(binary_img, lang="eng", psm=6, min_conf=min_conf)
    for w in eng_words:
        if LATIN_RE.search(w.text):
            key = (w.x, w.y, w.text)
            all_words[key] = w

    # Pass 2: Arabic
    ara_words = ocr_words(binary_img, lang="ara", psm=6, min_conf=min_conf)
    for w in ara_words:
        if ARABIC_RE.search(w.text):
            key = (w.x, w.y, w.text)
            # Only add if no English word at same position
            if not any(abs(k[0] - w.x) < 20 and abs(k[1] - w.y) < 20
                      for k in all_words if LATIN_RE.search(all_words[k].text)):
                all_words[key] = w

    # Pass 3: Combined (for mixed content)
    combined_words = ocr_words(binary_img, lang="ara+eng", psm=6, min_conf=min_conf)
    for w in combined_words:
        key = (w.x, w.y, w.text)
        if key not in all_words:
            all_words[key] = w

    return list(all_words.values())


# ─── Column Splitting and Row Clustering ──────────────────────────────────────

def split_columns(words: List[Word], page_width: int,
                  gutter_ratio: float = 0.5) -> Tuple[List[Word], List[Word]]:
    """Split words into left and right columns based on gutter position."""
    if page_width <= 0:
        return words, []
    gutter = int(page_width * gutter_ratio)
    left = [w for w in words if w.x + w.w // 2 < gutter]
    right = [w for w in words if w.x + w.w // 2 >= gutter]
    return left, right


def split_columns_by_gutter(words: List[Word], gutter_x: int,
                           page_width: int) -> Tuple[List[Word], List[Word]]:
    """Split words using a detected gutter position."""
    left = [w for w in words if w.x + w.w // 2 < gutter_x]
    right = [w for w in words if w.x + w.w // 2 >= gutter_x]
    return left, right


def cluster_rows(words: List[Word], tol: int = 12) -> List[List[Word]]:
    """Cluster words into rows based on Y-coordinate proximity."""
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


# ─── Entry Extraction ─────────────────────────────────────────────────────────

def classify_word(w: Word) -> str:
    """Classify a word as 'digit', 'english', 'arabic', 'mixed', or 'noise'."""
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
                                 page_num: int,
                                 is_arabic_english: bool = False) -> List[Entry]:
    """Extract dictionary entries from a column of OCR rows.

    Args:
        rows: List of rows, each row is a list of Word objects.
        page_num: Page number for the entry.
        is_arabic_english: If True, the dictionary is Arabic→English (Arabic headword).
                          If False, English→Arabic (English headword).
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
                if len(w.text) >= 2:
                    english_words.append(w)
                elif len(w.text) == 1 and w.text.isupper():
                    # Single uppercase letter could be a section header (A, B, C...)
                    pass
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

        # Determine entry ID
        entry_id = None
        if digits:
            try:
                entry_id = int(digits[0])
            except ValueError:
                entry_id = None

        eng_text = " ".join(english_parts).strip()
        ara_text = " ".join(arabic_parts).strip()

        # Apply English OCR fixes
        for pat, repl in ENGLISH_OCR_FIXES:
            eng_text = re.sub(pat, repl, eng_text)
        eng_text = re.sub(r"\s+", " ", eng_text).strip()

        # Skip empty rows
        if not eng_text and not ara_text and entry_id is None:
            continue

        # Determine if this is a new entry or continuation
        if is_arabic_english:
            # Arabic→English: Arabic headword
            if entry_id is not None and ara_text:
                current = Entry(
                    entry_id=entry_id,
                    english=eng_text,
                    arabic=ara_text,
                    page=page_num,
                    y=row[0].y if row else 0,
                )
                entries.append(current)
            elif current is not None:
                if eng_text:
                    current.english = (current.english + " " + eng_text).strip()
                if ara_text:
                    current.arabic = (current.arabic + " " + ara_text).strip()
        else:
            # English→Arabic: English headword
            if entry_id is not None and eng_text:
                current = Entry(
                    entry_id=entry_id,
                    english=eng_text,
                    arabic=ara_text,
                    page=page_num,
                    y=row[0].y if row else 0,
                )
                entries.append(current)
            elif entry_id is not None and ara_text and not eng_text:
                # Some entries start with Arabic (e.g., in Arabic-English dicts)
                current = Entry(
                    entry_id=entry_id,
                    english=eng_text,
                    arabic=ara_text,
                    page=page_num,
                    y=row[0].y if row else 0,
                )
                entries.append(current)
            elif current is not None:
                if ara_text:
                    current.arabic = (current.arabic + " " + ara_text).strip()
                if eng_text and not ara_text:
                    # Could be continuation of English term
                    current.english = (current.english + " " + eng_text).strip()

    return entries


def extract_entries_no_numbers(rows: List[List[Word]],
                                page_num: int,
                                is_arabic_english: bool = False) -> List[Entry]:
    """Extract entries from a dictionary that doesn't have entry numbers.
    
    Uses a heuristic: a new entry starts when we see a standalone English word
    (or Arabic word for Arabic→English dicts) at the beginning of a row.
    """
    entries: List[Entry] = []
    current: Optional[Entry] = None
    entry_counter = 0

    for row in rows:
        english_words: List[Word] = []
        arabic_words: List[Word] = []

        for w in row:
            kind = classify_word(w)
            if kind == "digit":
                continue  # Skip page numbers etc.
            elif kind == "english":
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

        english_words.sort(key=lambda w: w.x)
        arabic_words.sort(key=lambda w: w.x, reverse=True)

        eng_text = " ".join(w.text for w in english_words).strip()
        ara_text = " ".join(w.text for w in arabic_words).strip()

        # Apply English OCR fixes
        for pat, repl in ENGLISH_OCR_FIXES:
            eng_text = re.sub(pat, repl, eng_text)
        eng_text = re.sub(r"\s+", " ", eng_text).strip()

        if not eng_text and not ara_text:
            continue

        # Heuristic: new entry starts when we have English text at the beginning
        # of a row (leftmost word is English)
        if english_words and arabic_words:
            # Check if first English word is at the start of the row
            first_english_x = min(w.x for w in english_words)
            first_arabic_x = min(w.x for w in arabic_words)

            if not is_arabic_english and first_english_x < first_arabic_x:
                # English→Arabic entry
                entry_counter += 1
                current = Entry(
                    entry_id=entry_counter,
                    english=eng_text,
                    arabic=ara_text,
                    page=page_num,
                    y=row[0].y if row else 0,
                )
                entries.append(current)
            elif is_arabic_english and first_arabic_x < first_english_x:
                # Arabic→English entry
                entry_counter += 1
                current = Entry(
                    entry_id=entry_counter,
                    english=eng_text,
                    arabic=ara_text,
                    page=page_num,
                    y=row[0].y if row else 0,
                )
                entries.append(current)
            elif current is not None:
                if ara_text:
                    current.arabic = (current.arabic + " " + ara_text).strip()
                if eng_text:
                    current.english = (current.english + " " + eng_text).strip()
        elif current is not None:
            # Continuation row
            if ara_text:
                current.arabic = (current.arabic + " " + ara_text).strip()
            if eng_text:
                current.english = (current.english + " " + eng_text).strip()

    return entries


# ─── Text-based PDF extraction ────────────────────────────────────────────────

def extract_text_pdf(pdf: fitz.Document, start: int = 0, end: Optional[int] = None,
                     is_arabic_english: bool = False) -> List[Entry]:
    """Extract entries from a text-based PDF (has embedded text layer)."""
    total = pdf.page_count
    end = total if end is None else min(end, total)
    entries: List[Entry] = []
    entry_counter = 0

    for page_idx in range(start, end):
        page = pdf[page_idx]
        text = page.get_text()
        if not text.strip():
            continue

        page_num = page_idx + 1
        lines = text.split("\n")

        current: Optional[Entry] = None
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if line starts with a new entry
            # Pattern: English word followed by Arabic translation
            # or Arabic word followed by English translation
            has_latin = bool(LATIN_RE.search(line))
            has_arabic = bool(ARABIC_RE.search(line))

            if has_latin and has_arabic:
                # Bilingual line - split into English and Arabic parts
                # Simple approach: split by first Arabic character
                parts = []
                current_part = ""
                in_arabic = False
                for char in line:
                    is_ar = bool(ARABIC_RE.match(char))
                    if is_ar != in_arabic and current_part.strip():
                        parts.append(current_part.strip())
                        current_part = ""
                        in_arabic = is_ar
                    current_part += char
                if current_part.strip():
                    parts.append(current_part.strip())

                # Separate English and Arabic parts
                eng_parts = [p for p in parts if LATIN_RE.search(p)]
                ara_parts = [p for p in parts if ARABIC_RE.search(p)]

                eng_text = " ".join(eng_parts).strip()
                ara_text = " ".join(ara_parts).strip()

                if eng_text or ara_text:
                    entry_counter += 1
                    current = Entry(
                        entry_id=entry_counter,
                        english=eng_text,
                        arabic=ara_text,
                        page=page_num,
                        y=0,
                    )
                    entries.append(current)
            elif has_latin and not has_arabic:
                if current is not None:
                    current.english = (current.english + " " + line).strip()
                else:
                    entry_counter += 1
                    current = Entry(
                        entry_id=entry_counter,
                        english=line,
                        arabic="",
                        page=page_num,
                        y=0,
                    )
                    entries.append(current)
            elif has_arabic and not has_latin:
                if current is not None:
                    current.arabic = (current.arabic + " " + line).strip()
                else:
                    entry_counter += 1
                    current = Entry(
                        entry_id=entry_counter,
                        english="",
                        arabic=line,
                        page=page_num,
                        y=0,
                    )
                    entries.append(current)

    return entries


# ─── Post-processing ──────────────────────────────────────────────────────────

def is_noise(eng: str, ara: str) -> bool:
    """Check if an entry is noise (not a valid dictionary entry)."""
    for pat in NOISE_PATTERNS:
        if pat.match(eng) or pat.match(ara):
            return True
    # Must have at least one valid language
    if not eng and not ara:
        return True
    if eng and not LATIN_RE.search(eng):
        return True
    if ara and not ARABIC_RE.search(ara):
        return True
    if eng and len(eng) < 2:
        return True
    return False


def clean_arabic(text: str) -> str:
    """Clean Arabic text: normalize spaces, remove RLM/LRM marks."""
    out = text.strip()
    out = re.sub(r"\s+", " ", out)
    out = out.replace("\u200e", "").replace("\u200f", "")
    out = out.replace("\u200d", "").replace("\u200c", "")
    # Remove isolated punctuation
    out = re.sub(r"\s+[.,;:]\s*$", "", out)
    return out.strip()


def clean_english(text: str) -> str:
    """Clean English text: normalize spaces, fix common OCR errors."""
    out = text.strip()
    out = re.sub(r"\s+", " ", out)
    # Remove isolated punctuation
    out = re.sub(r"\s+[.,;:]\s*$", "", out)
    return out.strip()


# ─── Main Pipeline ────────────────────────────────────────────────────────────

def process_pdf(
    pdf_path: str,
    output_csv: str,
    dpi: int = 300,
    start: int = 0,
    end: Optional[int] = None,
    src_name: Optional[str] = None,
    gutter_ratio: float = 0.5,
    row_tol: int = 12,
    preprocess_method: str = "auto",
    is_arabic_english: bool = False,
    has_entry_numbers: bool = True,
    use_dual_pass: bool = False,
    corrector: Optional[ConservativeSpellCorrector] = None,
    chunk_size: int = 0,
    chunk_idx: int = -1,
) -> dict:
    """Process a PDF dictionary and produce a CSV file.

    Args:
        pdf_path: Path to the input PDF file.
        output_csv: Path to the output CSV file.
        dpi: DPI for rendering (default 300).
        start: Start page index (0-based).
        end: End page index (exclusive).
        src_name: Source name for the CSV.
        gutter_ratio: Position of the column gutter as fraction of page width.
        row_tol: Y-tolerance for row clustering (pixels).
        preprocess_method: Image preprocessing method ('auto', 'enhanced', 'simple', 'none').
        is_arabic_english: True if dictionary is Arabic→English.
        has_entry_numbers: True if entries have sequential numbers.
        use_dual_pass: Use dual-pass OCR (separate English and Arabic).
        corrector: Spell corrector instance.
        chunk_size: Number of pages per chunk (0 = no chunking).
        chunk_idx: Chunk index to process (-1 = all).
    """
    start_time = time.time()

    pdf = fitz.open(pdf_path)
    total_pages = pdf.page_count
    src_name = src_name or Path(pdf_path).stem

    # Determine page range
    if chunk_size > 0 and chunk_idx >= 0:
        chunk_start = start + chunk_idx * chunk_size
        chunk_end = min(chunk_start + chunk_size, end or total_pages)
        if chunk_start >= (end or total_pages):
            pdf.close()
            return {"error": "chunk out of range"}
        start = chunk_start
        end = chunk_end
    else:
        end = total_pages if end is None else min(end, total_pages)

    # Detect layout
    layout = detect_layout_type(pdf, sample_pages=min(5, total_pages))
    print(f"  Layout detected: columns={layout.num_columns}, "
          f"scanned={layout.is_scanned}, has_text={layout.has_text}", file=sys.stderr)

    # If layout says 2 columns, use detected gutter
    if layout.num_columns == 2 and layout.gutter_x > 0:
        gutter_ratio = layout.gutter_x / layout.page_width if layout.page_width > 0 else 0.5
        print(f"  Detected gutter at ratio={gutter_ratio:.3f}", file=sys.stderr)

    all_entries: List[Entry] = []
    stats = {
        "pages": 0, "raw_entries": 0, "valid_entries": 0,
        "skipped": 0, "text_pages": 0, "ocr_pages": 0,
        "layout": f"{layout.num_columns}col_{'scanned' if layout.is_scanned else 'text'}"
    }

    # Process each page
    for page_idx in range(start, end):
        page_num = page_idx + 1
        try:
            # Check if page has usable text
            page = pdf[page_idx]
            text = page.get_text().strip()

            # For text-based PDFs, try text extraction first
            if len(text) > 100 and not layout.is_scanned:
                stats["text_pages"] += 1
                # Text extraction is handled separately for better quality
                continue

            # OCR path
            stats["ocr_pages"] += 1
            img = render_page(pdf, page_idx, dpi)
            binary = preprocess_image(img, method=preprocess_method)
            page_width = binary.shape[1]

            # OCR
            if use_dual_pass:
                words = ocr_words_dual_pass(binary)
            else:
                words = ocr_words(binary)

            # Split columns if needed
            if layout.num_columns == 2:
                left, right = split_columns(words, page_width, gutter_ratio)
                left_rows = cluster_rows(left, tol=row_tol)
                right_rows = cluster_rows(right, tol=row_tol)

                if has_entry_numbers:
                    left_entries = extract_entries_from_column(
                        left_rows, page_num, is_arabic_english)
                    right_entries = extract_entries_from_column(
                        right_rows, page_num, is_arabic_english)
                else:
                    left_entries = extract_entries_no_numbers(
                        left_rows, page_num, is_arabic_english)
                    right_entries = extract_entries_no_numbers(
                        right_rows, page_num, is_arabic_english)

                page_entries = left_entries + right_entries
            else:
                rows = cluster_rows(words, tol=row_tol)
                if has_entry_numbers:
                    page_entries = extract_entries_from_column(
                        rows, page_num, is_arabic_english)
                else:
                    page_entries = extract_entries_no_numbers(
                        rows, page_num, is_arabic_english)

            stats["raw_entries"] += len(page_entries)

            for e in page_entries:
                e.arabic = clean_arabic(e.arabic)
                e.english = clean_english(e.english)

                if is_noise(e.english, e.arabic):
                    stats["skipped"] += 1
                    continue

                # Apply spell correction if available
                if corrector:
                    e.english = corrector.correct_text(e.english, "english")
                    e.arabic = corrector.correct_text(e.arabic, "arabic")

                all_entries.append(e)
                stats["valid_entries"] += 1

        except Exception as e:
            print(f"  [p{page_num}] error: {e}", file=sys.stderr)
            continue

        if page_num % 10 == 0 or page_num == end:
            print(f"  [p{page_num}/{end}] cumulative: {len(all_entries)} entries",
                  file=sys.stderr)

    # Sort and deduplicate
    def sort_key(e: Entry):
        return (e.entry_id if e.entry_id is not None else 10**6,
                e.page, e.y)

    all_entries.sort(key=sort_key)

    seen = set()
    deduped: List[Entry] = []
    for e in all_entries:
        key = (e.english.lower(), e.arabic)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    # Write CSV
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "English", "Arabic"])
        for i, e in enumerate(deduped, start=1):
            writer.writerow([i, e.english, e.arabic])

    processing_time = time.time() - start_time

    # Quality report
    entries_with_english = sum(1 for e in deduped if e.english)
    entries_with_arabic = sum(1 for e in deduped if e.arabic)
    entries_with_both = sum(1 for e in deduped if e.english and e.arabic)
    avg_english_len = np.mean([len(e.english) for e in deduped]) if deduped else 0
    avg_arabic_len = np.mean([len(e.arabic) for e in deduped]) if deduped else 0

    # Estimate accuracy based on entries with both languages
    estimated_accuracy = entries_with_both / len(deduped) if deduped else 0

    report = QualityReport(
        pdf_name=src_name,
        total_pages=total_pages,
        pages_processed=end - start,
        total_entries=len(deduped),
        entries_with_english=entries_with_english,
        entries_with_arabic=entries_with_arabic,
        entries_with_both=entries_with_both,
        avg_english_len=round(avg_english_len, 1),
        avg_arabic_len=round(avg_arabic_len, 1),
        estimated_accuracy=round(estimated_accuracy, 3),
        layout_type=stats["layout"],
        pdf_deletable=estimated_accuracy > 0.7 and len(deduped) > 100,
        deletion_note=(
            f"PDF can be deleted after verification — {entries_with_both} entries "
            f"with both languages extracted ({estimated_accuracy:.1%} accuracy). "
            f"Verify by comparing random samples with the original PDF before deletion."
            if estimated_accuracy > 0.7 and len(deduped) > 100
            else f"PDF should be kept — only {entries_with_both} entries with both "
                 f"languages ({estimated_accuracy:.1%} accuracy). Quality needs improvement."
        ),
        processing_time_sec=round(processing_time, 1),
    )

    # Save quality report
    report_path = output_csv.replace(".csv", "_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "pdf_name": report.pdf_name,
            "total_pages": report.total_pages,
            "pages_processed": report.pages_processed,
            "total_entries": report.total_entries,
            "entries_with_english": report.entries_with_english,
            "entries_with_arabic": report.entries_with_arabic,
            "entries_with_both": report.entries_with_both,
            "avg_english_len": report.avg_english_len,
            "avg_arabic_len": report.avg_arabic_len,
            "estimated_accuracy": report.estimated_accuracy,
            "layout_type": report.layout_type,
            "pdf_deletable": report.pdf_deletable,
            "deletion_note": report.deletion_note,
            "processing_time_sec": report.processing_time_sec,
        }, f, ensure_ascii=False, indent=2)

    stats["final_entries"] = len(deduped)
    stats["processing_time"] = round(processing_time, 1)
    pdf.close()

    return stats


def merge_chunk_csvs(output_csv: str, chunk_pattern: str):
    """Merge multiple chunk CSV files into one."""
    import glob
    chunks = sorted(glob.glob(chunk_pattern))
    if not chunks:
        print(f"No chunks found matching: {chunk_pattern}", file=sys.stderr)
        return

    all_entries = []
    seen = set()
    entry_id = 0

    for chunk_path in chunks:
        with open(chunk_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if len(row) < 3:
                    continue
                eng = row[1].strip()
                ara = row[2].strip()
                key = (eng.lower(), ara)
                if key in seen:
                    continue
                seen.add(key)
                entry_id += 1
                all_entries.append([entry_id, eng, ara])

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "English", "Arabic"])
        for entry in all_entries:
            writer.writerow(entry)

    print(f"Merged {len(chunks)} chunks → {output_csv} ({len(all_entries)} entries)",
          file=sys.stderr)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Universal Dictionary OCR Pipeline v3"
    )
    ap.add_argument("input_pdf", nargs="?", help="Input PDF file")
    ap.add_argument("output_csv", nargs="?", help="Output CSV file")
    ap.add_argument("--dpi", type=int, default=300, help="DPI for rendering")
    ap.add_argument("--start", type=int, default=0, help="Start page (0-based)")
    ap.add_argument("--end", type=int, default=None, help="End page (exclusive)")
    ap.add_argument("--src-name", default=None, help="Source name")
    ap.add_argument("--gutter-ratio", type=float, default=0.5,
                    help="Gutter position as fraction of page width")
    ap.add_argument("--row-tol", type=int, default=12,
                    help="Y-tolerance for row clustering")
    ap.add_argument("--preprocess", default="auto",
                    choices=["auto", "enhanced", "simple", "none"],
                    help="Preprocessing method")
    ap.add_argument("--arabic-english", action="store_true",
                    help="Dictionary is Arabic→English (Arabic headword)")
    ap.add_argument("--no-entry-numbers", action="store_true",
                    help="Dictionary entries don't have sequential numbers")
    ap.add_argument("--dual-pass", action="store_true",
                    help="Use dual-pass OCR (separate English/Arabic)")
    ap.add_argument("--spell-dict", default=None,
                    help="Path to spell dictionary JSON file")
    ap.add_argument("--spell-csvs", default=None,
                    help="Path to directory with CSV files for spell checking")
    ap.add_argument("--chunk-size", type=int, default=0,
                    help="Process N pages per chunk (0 = no chunking)")
    ap.add_argument("--chunk", type=int, default=-1,
                    help="Process specific chunk index")
    ap.add_argument("--merge", nargs=2, metavar=("OUTPUT", "PATTERN"),
                    help="Merge chunk CSVs: OUTPUT.csv 'chunk_*.csv'")
    args = ap.parse_args()

    # Merge mode
    if args.merge:
        merge_chunk_csvs(args.merge[0], args.merge[1])
        return

    if not args.input_pdf or not args.output_csv:
        ap.error("input_pdf and output_csv are required (unless using --merge)")

    # Initialize spell corrector
    corrector = None
    if args.spell_dict or args.spell_csvs:
        corrector = ConservativeSpellCorrector()
        if args.spell_dict:
            corrector.load_dictionary(args.spell_dict)
            print(f"  Loaded spell dict: {len(corrector.english_words)} EN, "
                  f"{len(corrector.arabic_words)} AR words", file=sys.stderr)
        if args.spell_csvs:
            corrector.load_from_csvs(args.spell_csvs)
            print(f"  Loaded spell CSVs: {len(corrector.english_words)} EN, "
                  f"{len(corrector.arabic_words)} AR words", file=sys.stderr)

    print(f"OCR v3: {args.input_pdf} → {args.output_csv}", file=sys.stderr)
    stats = process_pdf(
        args.input_pdf, args.output_csv,
        dpi=args.dpi, start=args.start, end=args.end,
        src_name=args.src_name,
        gutter_ratio=args.gutter_ratio,
        row_tol=args.row_tol,
        preprocess_method=args.preprocess,
        is_arabic_english=args.arabic_english,
        has_entry_numbers=not args.no_entry_numbers,
        use_dual_pass=args.dual_pass,
        corrector=corrector,
        chunk_size=args.chunk_size,
        chunk_idx=args.chunk,
    )
    print(f"\nDone. Stats: {stats}", file=sys.stderr)
    if "final_entries" in stats:
        print(f"Output: {args.output_csv} ({stats['final_entries']} entries)")


if __name__ == "__main__":
    main()
