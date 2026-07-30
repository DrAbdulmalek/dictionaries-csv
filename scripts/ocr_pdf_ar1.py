#!/usr/bin/env python3
"""OCR a scanned PDF (page-by-page) using Tesseract with Arabic + English support.

Produces a CSV with one row per detected line/paragraph.
"""
import csv
import io
import os
import re
import sys
import tempfile
from pathlib import Path

import fitz                       # PyMuPDF — for rasterizing PDF pages
import pytesseract
from PIL import Image
import pdfplumber

PDF = "/home/z/my-project/dict_work/pdf_ar1.pdf"
OUT_CSV = "/home/z/my-project/dict_work/csv_output/معجم_المصطلحات_الاعلامية.csv"
SOURCE_NAME = "معجم المصطلحات الاعلامية"

# Tell tesseract where to find ara.traineddata
os.environ["TESSDATA_PREFIX"] = "/home/z/my-project/dict_work/tessdata"


def _clean(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\xa0", " ").replace("\u200b", "").replace("\u200f", "")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def ocr_pdf(pdf_path: str, out_csv: str, source_name: str, dpi: int = 200) -> int:
    doc = fitz.open(pdf_path)
    print(f"Pages: {len(doc)}; OCR with ara+eng at {dpi} DPI")

    rows: list[tuple[str, str, str]] = []

    for i, page in enumerate(doc):
        # Rasterize page at 200 DPI
        mat = fitz.Matrix(dpi / 72, dpi / 72)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img = Image.open(io.BytesIO(pix.tobytes("png")))

        # OCR with both Arabic and English
        try:
            text = pytesseract.image_to_string(img, lang="ara+eng")
        except Exception as e:
            print(f"  page {i+1} OCR error: {e}")
            continue

        # Each non-empty line becomes a row (heuristic for dictionary layout)
        for line in text.splitlines():
            line = _clean(line)
            if not line or len(line) < 2:
                continue
            # Try to split into term / definition on 2+ spaces or tab
            parts = re.split(r"\s{2,}|\t", line, maxsplit=1)
            if len(parts) == 2:
                rows.append((parts[0], parts[1], source_name))
            else:
                rows.append((line, "", source_name))

        if (i + 1) % 5 == 0 or i == len(doc) - 1:
            print(f"  page {i+1}/{len(doc)} done — {len(rows)} rows so far")

    doc.close()

    # Write CSV
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(["term", "definition", "source_file"])
        for term, definition, _ in rows:
            w.writerow([term, definition, source_name])

    print(f"\nWrote {len(rows)} rows to {out_csv}")
    return len(rows)


if __name__ == "__main__":
    ocr_pdf(PDF, OUT_CSV, SOURCE_NAME)
