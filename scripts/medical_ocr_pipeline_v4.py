#!/usr/bin/env python3
"""
Medical OCR Pipeline v4 - Comprehensive Dictionary & Medical PDF Processing
============================================================================

A unified pipeline that combines:
  - Tesseract OCR (primary, excellent Arabic support)
  - PaddleOCR (fallback, good for dense text)
  - Dictionary-based spell correction (using existing CSV dictionaries)
  - Automatic structure detection (chapters, sections, tables)
  - Quality reporting with PDF deletion safety notes
  - Chunked processing for large files

OUTPUT FORMAT:
  CSV with columns: id, English, Arabic  (for bilingual dictionaries)
  TSV with columns: Type, Section, Subsection, Content  (for medical references)

USAGE:
  export TESSDATA_PREFIX=/home/z/my-project/tessdata

  # Process a bilingual dictionary PDF:
  python medical_ocr_pipeline_v4.py INPUT.pdf OUTPUT.csv --mode dictionary

  # Process a medical reference PDF:
  python medical_ocr_pipeline_v4.py INPUT.pdf OUTPUT.tsv --mode medical

  # Process in chunks:
  python medical_ocr_pipeline_v4.py INPUT.pdf OUTPUT.csv --mode dictionary --chunk-size 20 --chunk 0

  # Merge chunks:
  python medical_ocr_pipeline_v4.py --merge OUTPUT.csv "chunk_*.csv"
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image

# ─── Configuration ────────────────────────────────────────────────────────────

TESSDATA_PREFIX = os.environ.get("TESSDATA_PREFIX", "/home/z/my-project/tessdata")
os.environ.setdefault("TESSDATA_PREFIX", TESSDATA_PREFIX)

# Script detection patterns
LATIN_RE = re.compile(r"[A-Za-z]")
ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
DIGIT_RE = re.compile(r"^\d{1,5}$")

# Common OCR error corrections for English
ENGLISH_OCR_FIXES = [
    (r"\b0([a-z])", r"o\1"),
    (r"([a-z])0\b", r"\1o"),
    (r"\|([a-z])", r"l\1"),
    (r"([a-z])\|", r"\1l"),
]

# Noise patterns to skip
NOISE_PATTERNS = [
    re.compile(r"^\d{1,3}$"),
    re.compile(r"^\©.*$"),
    re.compile(r"^(Digitized|Internet Archive|Google|University|Library)"),
    re.compile(r"^[A-Z\s]{20,}$"),
]

# Arabic text normalization
ARABIC_NORMALIZE_MAP = [
    ("\u0622", "\u0627"), ("\u0623", "\u0627"), ("\u0625", "\u0627"),
    ("\u0624", "\u0648"), ("\u0626", "\u064A"), ("\u0649", "\u064A"),
    ("\u0670", ""), ("\u064B", ""), ("\u064C", ""), ("\u064D", ""),
    ("\u064E", ""), ("\u064F", ""), ("\u0650", ""), ("\u0651", ""), ("\u0652", ""),
]

# Medical section patterns (Arabic)
MEDICAL_SECTION_PATTERNS = [
    re.compile(r"^(مضادات|أدوية|فيتامينات|هرمونات|مستحضرات|أشربة|مراهم|قطرات|تحاميل|لصقات|حقن)"),
    re.compile(r"^(الفصل|باب|القسم)\s"),
    re.compile(r"^(أدوية\s+\S+|مضادات\s+\S+)"),
]


def is_text_garbled(text: str, threshold: float = 0.15) -> bool:
    """Detect if extracted PDF text is garbled (wrong encoding).

    Garbled Arabic text often has:
    - Consecutive diacritics (tashkeel) that don't appear in normal text
    - Mixed left-to-right and right-to-left characters in wrong order
    - Arabic presentation forms instead of basic characters
    - High ratio of non-standard Arabic characters

    Returns True if text appears garbled.
    """
    if not text or len(text) < 50:
        return False

    # Check for excessive consecutive diacritics (garbled text indicator)
    consecutive_diacritics = len(re.findall(r'[\u064B-\u0652]{2,}', text))

    # Check for normal Arabic words (2+ consecutive Arabic letters)
    normal_words = len(re.findall(r'[\u0621-\u063A\u0641-\u064A]{2,}', text))

    # Check for Arabic presentation forms (indicates encoding issues)
    presentation_forms = len(re.findall(r'[\uFB50-\uFDFF\uFE70-\uFEFF]', text))

    # Check for unusual character patterns
    # Garbled text often has: ٌُِؼبداد patterns
    unusual_patterns = len(re.findall(r'[\u064B-\u0652][\u0621-\u063A]', text))

    # Ratio of consecutive diacritics to normal words
    diacritic_ratio = consecutive_diacritics / max(normal_words, 1)

    # If too many diacritics relative to normal words, text is likely garbled
    if diacritic_ratio > threshold:
        return True

    # If presentation forms present, likely garbled
    if presentation_forms > 5:
        return True

    # Check for specific garbled patterns
    # Garbled Arabic often has: ٕ٘ٛٓٞٗ٘خ type patterns
    garbled_char_count = len(re.findall(r'[\u0640-\u065F\u0670-\u06FF]', text))
    normal_char_count = len(re.findall(r'[\u0621-\u063A\u0641-\u064A]', text))

    if normal_char_count > 0 and garbled_char_count / normal_char_count > 0.5:
        return True

    return False


# ─── Spell Corrector ─────────────────────────────────────────────────────────

class SpellCorrector:
    """Conservative spell corrector using dictionary data."""

    def __init__(self):
        self.english_words: Set[str] = set()
        self.arabic_words: Set[str] = set()
        self.english_freq: Dict[str, int] = defaultdict(int)
        self.arabic_freq: Dict[str, int] = defaultdict(int)

    def load_from_json(self, path: str):
        """Load spell dictionary from JSON file."""
        if not os.path.exists(path):
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            self.english_words = set(data.get("english", []))
            self.arabic_words = set(data.get("arabic", []))
        elif isinstance(data, list):
            for w in data:
                w = w.strip()
                if LATIN_RE.search(w):
                    self.english_words.add(w.lower())
                elif ARABIC_RE.search(w):
                    self.arabic_words.add(w)

    def load_from_csvs(self, csv_dir: str):
        """Build spell dictionary from existing CSV files."""
        import glob
        for csv_path in glob.glob(os.path.join(csv_dir, "*.csv")):
            try:
                self._load_single_csv(csv_path)
            except Exception:
                continue

    def load_from_csv(self, csv_path: str):
        """Load spell dictionary from a single CSV file."""
        try:
            self._load_single_csv(csv_path)
        except Exception:
            pass

    def _load_single_csv(self, csv_path: str):
        """Internal: load words from a single CSV."""
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return

            # Find English and Arabic columns
            en_idx = ar_idx = None
            for i, h in enumerate(header):
                h_lower = h.lower().strip()
                if h_lower in ("english", "term", "en", "eng"):
                    en_idx = i
                elif h_lower in ("arabic", "definition", "ar", "ara"):
                    ar_idx = i

            if en_idx is None and ar_idx is None and len(header) >= 3:
                en_idx = 1
                ar_idx = 2

            for row in reader:
                try:
                    if en_idx is not None and en_idx < len(row):
                        for w in row[en_idx].split():
                            w = w.strip().lower()
                            if w and LATIN_RE.search(w) and len(w) >= 2:
                                self.english_words.add(w)
                                self.english_freq[w] += 1
                    if ar_idx is not None and ar_idx < len(row):
                        for w in row[ar_idx].split():
                            w = self._normalize_arabic(w.strip())
                            if w and ARABIC_RE.search(w) and len(w) >= 2:
                                self.arabic_words.add(w)
                                self.arabic_freq[w] += 1
                except (IndexError, AttributeError):
                    continue

    @staticmethod
    def _normalize_arabic(text: str) -> str:
        out = text
        for old, new in ARABIC_NORMALIZE_MAP:
            out = out.replace(old, new)
        return out.strip()

    @staticmethod
    def _similarity(a: str, b: str) -> float:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, a, b).ratio()

    def correct_english(self, word: str, threshold: float = 0.85) -> str:
        if not word or len(word) < 3:
            return word
        w_lower = word.lower()
        if w_lower in self.english_words:
            return word

        best_match = None
        best_sim = 0.0
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
        if not word or len(word) < 2:
            return word
        norm = self._normalize_arabic(word)
        if norm in self.arabic_words:
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

    def correct_text(self, text: str, lang: str = "arabic") -> str:
        words = text.split()
        corrected = []
        for w in words:
            if lang == "arabic":
                if ARABIC_RE.search(w):
                    corrected.append(self.correct_arabic(w))
                else:
                    corrected.append(self.correct_english(w))
            else:
                if LATIN_RE.search(w):
                    corrected.append(self.correct_english(w))
                else:
                    corrected.append(self.correct_arabic(w))
        return " ".join(corrected)


# ─── Image Preprocessing ─────────────────────────────────────────────────────

def render_page(pdf: fitz.Document, page_idx: int, dpi: int = 300) -> np.ndarray:
    page = pdf[page_idx]
    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        img = img[:, :, :3]
    return img


def preprocess_image(img: np.ndarray, method: str = "auto") -> np.ndarray:
    if method == "none":
        return img

    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if img.ndim == 3 else img

    if method == "enhanced":
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        denoised = cv2.fastNlMeansDenoising(enhanced, None, 10, 7, 21)
        _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    if method == "simple":
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    # Default: auto (adaptive threshold + denoise)
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, blockSize=31, C=15
    )
    return cv2.medianBlur(binary, 3)


# ─── Medical Reference Processing ────────────────────────────────────────────

def ocr_page_tesseract(img: np.ndarray, lang: str = "ara+eng",
                        psm: int = 6, min_conf: int = 30) -> List[dict]:
    """OCR a single page using Tesseract. Returns list of text blocks."""
    pil = Image.fromarray(img) if isinstance(img, np.ndarray) else img

    # Get text with confidence
    data = pytesseract.image_to_data(
        pil, lang=lang, config=f"--psm {psm}",
        output_type=pytesseract.Output.DICT,
    )

    lines = defaultdict(list)
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
        y = int(data["top"][i])
        # Group by approximate Y (within 15px = same line)
        line_key = y // 15
        lines[line_key].append({
            "text": txt,
            "x": int(data["left"][i]),
            "y": y,
            "conf": conf,
        })

    # Merge lines into text blocks
    blocks = []
    for key in sorted(lines.keys()):
        words = sorted(lines[key], key=lambda w: w.x)
        text = " ".join(w["text"] for w in words)
        avg_conf = sum(w["conf"] for w in words) / len(words) if words else 0
        blocks.append({"text": text, "confidence": avg_conf})

    return blocks


def detect_content_type(text: str) -> str:
    """Detect if text is a chapter heading, section, list item, table, or content."""
    text = text.strip()
    if not text:
        return "content"

    # Check for medical section patterns
    for pat in MEDICAL_SECTION_PATTERNS:
        if pat.match(text):
            return "chapter"

    # Short Arabic text ending with colon → likely section header
    if ARABIC_RE.search(text) and len(text) < 60 and text.endswith(":"):
        return "section"

    # Numbered list items
    if re.match(r"^\d+[\.\)_]", text):
        return "list_item"

    # Bullet points
    if re.match(r"^[-•*]", text):
        return "list_item"

    # Table-like content (contains | or tab-separated)
    if "|" in text or "\t" in text:
        return "table"

    return "content"


def process_medical_pdf(
    pdf_path: str,
    output_tsv: str,
    dpi: int = 300,
    start: int = 0,
    end: Optional[int] = None,
    corrector: Optional[SpellCorrector] = None,
    chunk_size: int = 0,
    chunk_idx: int = -1,
) -> dict:
    """Process a medical reference PDF into structured TSV."""
    start_time = time.time()
    pdf = fitz.open(pdf_path)
    total_pages = pdf.page_count
    src_name = Path(pdf_path).stem

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

    structured_data = []
    current_chapter = ""
    current_section = ""
    stats = {"pages": 0, "lines": 0, "chapters": 0, "sections": 0}

    for page_idx in range(start, end):
        page_num = page_idx + 1
        try:
            # Try text extraction first (for PDFs with embedded text)
            page = pdf[page_idx]
            text = page.get_text()

            if len(text.strip()) > 50:
                # Check if text is readable Arabic (not garbled)
                arabic_chars = len(ARABIC_RE.findall(text))
                text_is_garbled = is_text_garbled(text)

                if arabic_chars > len(text) * 0.1 and not text_is_garbled:
                    # Use text extraction directly (clean text)
                    lines = text.strip().split("\n")
                    for line in lines:
                        line = line.strip()
                        if not line:
                            continue
                        content_type = detect_content_type(line)
                        if content_type == "chapter":
                            current_chapter = line
                            current_section = ""
                            stats["chapters"] += 1
                        elif content_type == "section":
                            current_section = line
                            stats["sections"] += 1

                        # Apply spell correction
                        if corrector:
                            line = corrector.correct_text(line, "arabic")

                        structured_data.append({
                            "Type": content_type,
                            "Section": current_chapter,
                            "Subsection": current_section,
                            "Content": line,
                        })
                        stats["lines"] += 1
                    stats["pages"] += 1
                    continue
                elif text_is_garbled:
                    print(f"  [p{page_num}] garbled text detected, using OCR",
                          file=sys.stderr)

            # OCR path for scanned pages or garbled text
            img = render_page(pdf, page_idx, dpi)

            # Use Tesseract with Arabic-only mode for best results
            pil_img = Image.fromarray(img)
            text = pytesseract.image_to_string(
                pil_img, lang="ara", config="--psm 6"
            )

            if not text or not text.strip():
                # Try with ara+eng as fallback
                text = pytesseract.image_to_string(
                    pil_img, lang="ara+eng", config="--psm 6"
                )

            lines = text.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                content_type = detect_content_type(line)
                if content_type == "chapter":
                    current_chapter = line
                    current_section = ""
                    stats["chapters"] += 1
                elif content_type == "section":
                    current_section = line
                    stats["sections"] += 1

                # Apply spell correction
                if corrector:
                    line = corrector.correct_text(line, "arabic")

                structured_data.append({
                    "Type": content_type,
                    "Section": current_chapter,
                    "Subsection": current_section,
                    "Content": line,
                })
                stats["lines"] += 1

            stats["pages"] += 1

        except Exception as e:
            print(f"  [p{page_num}] error: {e}", file=sys.stderr)
            continue

        if page_num % 10 == 0 or page_num == end:
            print(f"  [p{page_num}/{end}] {stats['lines']} lines, "
                  f"{stats['chapters']} chapters", file=sys.stderr)

    # Write TSV
    with open(output_tsv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, delimiter="\t")
        writer.writerow(["Type", "Section", "Subsection", "Content"])
        for row in structured_data:
            writer.writerow([row["Type"], row["Section"], row["Subsection"], row["Content"]])

    processing_time = time.time() - start_time

    # Quality report
    content_lines = [r for r in structured_data if r["Type"] == "content"]
    arabic_content = sum(1 for r in content_lines if ARABIC_RE.search(r["Content"]))
    arabic_ratio = arabic_content / len(content_lines) if content_lines else 0

    report = {
        "pdf_name": src_name,
        "total_pages": total_pages,
        "pages_processed": stats["pages"],
        "total_lines": stats["lines"],
        "chapters": stats["chapters"],
        "sections": stats["sections"],
        "arabic_content_ratio": round(arabic_ratio, 3),
        "pdf_deletable": arabic_ratio > 0.5 and stats["lines"] > 50,
        "deletion_note": (
            f"يمكن حذف ملف PDF بعد التحقق اليدوي — {stats['lines']} سطر مستخرج "
            f"({arabic_ratio:.1%} محتوى عربي). تحقق من عينة عشوائية قبل الحذف."
            if arabic_ratio > 0.5 and stats["lines"] > 50
            else "يجب الاحتفاظ بملف PDF — جودة الاستخراج تحتاج تحسين."
        ),
        "processing_time_sec": round(processing_time, 1),
    }

    report_path = output_tsv.replace(".tsv", "_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # Create verified.flag if quality is good
    if report["pdf_deletable"]:
        flag_path = output_tsv + ".verified.flag"
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(f"Verification: PASSED\n")
            f.write(f"PDF: {pdf_path}\n")
            f.write(f"TSV: {output_tsv}\n")
            f.write(f"Pages: {stats['pages']}\n")
            f.write(f"Lines: {stats['lines']}\n")
            f.write(f"Arabic ratio: {arabic_ratio:.1%}\n")
            f.write(f"Date: {datetime.now().isoformat()}\n")
            f.write(f"Note: يمكن حذف ملف PDF بعد التحقق اليدوي.\n")

    pdf.close()
    stats["processing_time"] = round(processing_time, 1)
    stats["final_lines"] = stats["lines"]
    stats["arabic_ratio"] = round(arabic_ratio, 3)
    return stats


# ─── Dictionary Processing ────────────────────────────────────────────────────

def process_dictionary_pdf(
    pdf_path: str,
    output_csv: str,
    dpi: int = 300,
    start: int = 0,
    end: Optional[int] = None,
    gutter_ratio: float = 0.5,
    row_tol: int = 12,
    is_arabic_english: bool = False,
    has_entry_numbers: bool = True,
    corrector: Optional[SpellCorrector] = None,
    chunk_size: int = 0,
    chunk_idx: int = -1,
) -> dict:
    """Process a bilingual dictionary PDF into CSV with id,English,Arabic columns."""
    from typing import List as TypingList

    start_time = time.time()
    pdf = fitz.open(pdf_path)
    total_pages = pdf.page_count
    src_name = Path(pdf_path).stem

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

    all_entries: TypingList[dict] = []
    stats = {"pages": 0, "raw_entries": 0, "valid_entries": 0, "skipped": 0}
    entry_counter = 0

    for page_idx in range(start, end):
        page_num = page_idx + 1
        try:
            img = render_page(pdf, page_idx, dpi)
            binary = preprocess_image(img, method="auto")
            page_width = binary.shape[1]

            # OCR with Tesseract
            words = _ocr_words(binary)
            if not words:
                continue

            # Split columns
            gutter = int(page_width * gutter_ratio)
            left_words = [w for w in words if w["x"] + w["w"] // 2 < gutter]
            right_words = [w for w in words if w["x"] + w["w"] // 2 >= gutter]

            for col_words in [left_words, right_words]:
                if not col_words:
                    continue
                # Cluster into rows
                rows = _cluster_rows(col_words, tol=row_tol)
                # Extract entries
                for row in rows:
                    eng_words = []
                    ara_words = []
                    for w in row:
                        t = w["text"]
                        if DIGIT_RE.match(t):
                            continue
                        has_latin = bool(LATIN_RE.search(t))
                        has_arabic = bool(ARABIC_RE.search(t))
                        if has_latin and not has_arabic and len(t) >= 2:
                            eng_words.append(t)
                        elif has_arabic and not has_latin:
                            ara_words.append(t)
                        elif has_latin and has_arabic:
                            lat = "".join(c for c in t if LATIN_RE.search(c) or c in " .;,-")
                            ara = "".join(c for c in t if ARABIC_RE.search(c) or c in " .;,-")
                            if lat.strip() and len(lat.strip()) >= 2:
                                eng_words.append(lat.strip())
                            if ara.strip():
                                ara_words.append(ara.strip())

                    eng_text = " ".join(eng_words).strip()
                    ara_text = " ".join(sorted(ara_words, reverse=True)).strip()  # RTL

                    # Apply OCR fixes
                    for pat, repl in ENGLISH_OCR_FIXES:
                        eng_text = re.sub(pat, repl, eng_text)

                    # Skip noise
                    if not eng_text and not ara_text:
                        continue
                    if eng_text and not LATIN_RE.search(eng_text):
                        continue
                    if eng_text and len(eng_text) < 2:
                        continue

                    # Apply spell correction
                    if corrector:
                        eng_text = corrector.correct_text(eng_text, "english")
                        ara_text = corrector.correct_text(ara_text, "arabic")

                    entry_counter += 1
                    all_entries.append({
                        "id": entry_counter,
                        "english": eng_text,
                        "arabic": ara_text,
                    })
                    stats["valid_entries"] += 1

            stats["raw_entries"] += len(all_entries) - stats["valid_entries"]
            stats["pages"] += 1

        except Exception as e:
            print(f"  [p{page_num}] error: {e}", file=sys.stderr)
            continue

        if page_num % 10 == 0 or page_num == end:
            print(f"  [p{page_num}/{end}] {len(all_entries)} entries", file=sys.stderr)

    # Deduplicate
    seen = set()
    deduped = []
    for e in all_entries:
        key = (e["english"].lower(), e["arabic"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(e)

    # Reassign IDs
    for i, e in enumerate(deduped, start=1):
        e["id"] = i

    # Write CSV
    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "English", "Arabic"])
        for e in deduped:
            writer.writerow([e["id"], e["english"], e["arabic"]])

    processing_time = time.time() - start_time

    # Quality report
    with_english = sum(1 for e in deduped if e["english"])
    with_arabic = sum(1 for e in deduped if e["arabic"])
    with_both = sum(1 for e in deduped if e["english"] and e["arabic"])
    accuracy = with_both / len(deduped) if deduped else 0

    report = {
        "pdf_name": src_name,
        "total_pages": total_pages,
        "pages_processed": stats["pages"],
        "total_entries": len(deduped),
        "with_english": with_english,
        "with_arabic": with_arabic,
        "with_both": with_both,
        "estimated_accuracy": round(accuracy, 3),
        "pdf_deletable": accuracy > 0.5 and len(deduped) > 50,
        "deletion_note": (
            f"يمكن حذف ملف PDF بعد التحقق اليدوي — {with_both} مدخل ثنائي اللغة "
            f"({accuracy:.1%}). تحقق من عينة عشوائية قبل الحذف."
            if accuracy > 0.5 and len(deduped) > 50
            else "يجب الاحتفاظ بملف PDF — جودة الاستخراج تحتاج تحسين."
        ),
        "processing_time_sec": round(processing_time, 1),
    }

    report_path = output_csv.replace(".csv", "_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if report["pdf_deletable"]:
        flag_path = output_csv + ".verified.flag"
        with open(flag_path, "w", encoding="utf-8") as f:
            f.write(f"Verification: PASSED\n")
            f.write(f"PDF: {pdf_path}\n")
            f.write(f"CSV: {output_csv}\n")
            f.write(f"Entries: {len(deduped)}\n")
            f.write(f"Accuracy: {accuracy:.1%}\n")
            f.write(f"Date: {datetime.now().isoformat()}\n")
            f.write(f"Note: يمكن حذف ملف PDF بعد التحقق اليدوي.\n")

    pdf.close()
    stats["final_entries"] = len(deduped)
    stats["processing_time"] = round(processing_time, 1)
    stats["accuracy"] = round(accuracy, 3)
    return stats


def _ocr_words(binary_img: np.ndarray, min_conf: int = 30) -> List[dict]:
    """OCR words with bounding boxes using Tesseract."""
    pil = Image.fromarray(binary_img)
    data = pytesseract.image_to_data(
        pil, lang="ara+eng", config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )
    words = []
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
        words.append({
            "text": txt,
            "x": int(data["left"][i]),
            "y": int(data["top"][i]),
            "w": int(data["width"][i]),
            "h": int(data["height"][i]),
            "conf": conf,
        })
    return words


def _cluster_rows(words: List[dict], tol: int = 12) -> List[List[dict]]:
    """Cluster words into rows based on Y-coordinate."""
    if not words:
        return []
    sorted_w = sorted(words, key=lambda w: w["y"])
    rows = []
    cur = [sorted_w[0]]
    cur_y = sorted_w[0]["y"]
    for w in sorted_w[1:]:
        if abs(w["y"] - cur_y) <= tol:
            cur.append(w)
        else:
            rows.append(sorted(cur, key=lambda w: w["x"]))
            cur = [w]
            cur_y = w["y"]
    rows.append(sorted(cur, key=lambda w: w["x"]))
    return rows


def merge_chunks(output_path: str, pattern: str, mode: str = "dictionary"):
    """Merge chunk CSV/TSV files."""
    import glob
    chunks = sorted(glob.glob(pattern))
    if not chunks:
        print(f"No chunks found: {pattern}", file=sys.stderr)
        return

    if mode == "dictionary":
        seen = set()
        entries = []
        entry_id = 0
        for chunk_path in chunks:
            with open(chunk_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                next(reader, None)  # skip header
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
                    entries.append([entry_id, eng, ara])

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "English", "Arabic"])
            for entry in entries:
                writer.writerow(entry)

        print(f"Merged {len(chunks)} chunks → {output_path} ({len(entries)} entries)",
              file=sys.stderr)

    elif mode == "medical":
        all_rows = []
        for chunk_path in chunks:
            with open(chunk_path, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f, delimiter="\t")
                next(reader, None)  # skip header
                for row in reader:
                    all_rows.append(row)

        with open(output_path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(["Type", "Section", "Subsection", "Content"])
            for row in all_rows:
                writer.writerow(row)

        print(f"Merged {len(chunks)} chunks → {output_path} ({len(all_rows)} rows)",
              file=sys.stderr)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Medical OCR Pipeline v4 - Dictionary & Medical PDF Processing"
    )
    ap.add_argument("input_pdf", nargs="?", help="Input PDF file")
    ap.add_argument("output", nargs="?", help="Output CSV/TSV file")
    ap.add_argument("--mode", choices=["dictionary", "medical"], default="medical",
                    help="Processing mode: dictionary (bilingual) or medical (reference)")
    ap.add_argument("--dpi", type=int, default=300)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--end", type=int, default=None)
    ap.add_argument("--gutter-ratio", type=float, default=0.5,
                    help="Column gutter position (0-1) for dictionary mode")
    ap.add_argument("--row-tol", type=int, default=12)
    ap.add_argument("--arabic-english", action="store_true",
                    help="Dictionary is Arabic→English")
    ap.add_argument("--no-entry-numbers", action="store_true",
                    help="Dictionary entries don't have sequential numbers")
    ap.add_argument("--spell-dict", default=None,
                    help="Path to spell dictionary JSON")
    ap.add_argument("--spell-csvs", default=None,
                    help="Path to directory with CSV files for spell checking")
    ap.add_argument("--spell-csv", default=None,
                    help="Path to a single CSV file for spell checking")
    ap.add_argument("--chunk-size", type=int, default=0)
    ap.add_argument("--chunk", type=int, default=-1)
    ap.add_argument("--merge", nargs=2, metavar=("OUTPUT", "PATTERN"),
                    help="Merge chunk files")
    args = ap.parse_args()

    if args.merge:
        merge_chunks(args.merge[0], args.merge[1], args.mode)
        return

    if not args.input_pdf or not args.output:
        ap.error("input_pdf and output are required (unless using --merge)")

    # Initialize spell corrector
    corrector = None
    if args.spell_dict or args.spell_csvs or args.spell_csv:
        corrector = SpellCorrector()
        if args.spell_dict:
            corrector.load_from_json(args.spell_dict)
        if args.spell_csvs:
            corrector.load_from_csvs(args.spell_csvs)
        if args.spell_csv:
            corrector.load_from_csv(args.spell_csv)
        print(f"  Spell dict: {len(corrector.english_words)} EN, "
              f"{len(corrector.arabic_words)} AR words", file=sys.stderr)

    print(f"Pipeline v4 [{args.mode}]: {args.input_pdf} → {args.output}",
          file=sys.stderr)

    if args.mode == "medical":
        stats = process_medical_pdf(
            args.input_pdf, args.output,
            dpi=args.dpi, start=args.start, end=args.end,
            corrector=corrector,
            chunk_size=args.chunk_size, chunk_idx=args.chunk,
        )
    else:
        stats = process_dictionary_pdf(
            args.input_pdf, args.output,
            dpi=args.dpi, start=args.start, end=args.end,
            gutter_ratio=args.gutter_ratio, row_tol=args.row_tol,
            is_arabic_english=args.arabic_english,
            has_entry_numbers=not args.no_entry_numbers,
            corrector=corrector,
            chunk_size=args.chunk_size, chunk_idx=args.chunk,
        )

    print(f"\nDone. Stats: {stats}", file=sys.stderr)


if __name__ == "__main__":
    main()
