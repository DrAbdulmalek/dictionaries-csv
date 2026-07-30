#!/usr/bin/env python3
"""OCR a scanned PDF — chunked version that processes a page range.

Usage:
    python ocr_pdf_chunk.py START_PAGE END_PAGE OUTPUT_CSV
"""
import csv
import io
import os
import re
import sys
from pathlib import Path

os.environ["TESSDATA_PREFIX"] = "/home/z/my-project/dict_work/tessdata"

import fitz
import pytesseract
from PIL import Image

PDF = "/home/z/my-project/dict_work/pdf_ar1.pdf"


def _clean(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\u200f", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def ocr_pages(pdf_path: str, start: int, end: int) -> list[tuple[str, str]]:
    """OCR pages [start, end) (0-indexed). Returns list of (term, definition)."""
    doc = fitz.open(pdf_path)
    total = len(doc)
    if end > total:
        end = total
    rows: list[tuple[str, str]] = []
    for i in range(start, end):
        page = doc[i]
        mat = fitz.Matrix(200 / 72, 200 / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        try:
            text = pytesseract.image_to_string(img, lang="ara+eng")
        except Exception as e:
            sys.stderr.write(f"page {i+1} OCR error: {e}\n")
            continue
        for line in text.splitlines():
            line = _clean(line)
            if not line or len(line) < 2:
                continue
            parts = re.split(r"\s{2,}|\t", line, maxsplit=1)
            if len(parts) == 2:
                rows.append((parts[0], parts[1]))
            else:
                rows.append((line, ""))
        sys.stderr.write(f"  page {i+1}/{total} done — {len(rows)} rows\n")
    doc.close()
    return rows


if __name__ == "__main__":
    start = int(sys.argv[1])
    end = int(sys.argv[2])
    out_csv = sys.argv[3]
    rows = ocr_pages(PDF, start, end)
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["term", "definition", "source_file"])
        for term, definition in rows:
            w.writerow([term, definition, "معجم المصطلحات الاعلامية"])
    print(f"Wrote {len(rows)} rows to {out_csv}")
