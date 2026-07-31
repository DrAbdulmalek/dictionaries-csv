#!/usr/bin/env python3
"""
Process Syrian Pharmaceutical Reference PDF - incremental with immediate saves.
Run this script and it will process all pages, saving progress every 5 pages.
"""

import sys, os, json, time, csv
os.environ['TESSDATA_PREFIX'] = '/home/z/my-project/tessdata'

import fitz
import pytesseract
from PIL import Image
import numpy as np
import re

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")

MEDICAL_SECTION_PATTERNS = [
    re.compile(r"^(مضادات|أدوية|فيتامينات|هرمونات|مستحضرات|أشربة|مراهم|قطرات|تحاميل|لصقات|حقن)"),
    re.compile(r"^(الفصل|باب|القسم)\s"),
    re.compile(r"^(أدوية\s+\S+|مضادات\s+\S+)"),
]

def is_text_garbled(text):
    if not text or len(text) < 50:
        return False
    consecutive_diacritics = len(re.findall(r'[\u064B-\u0652]{2,}', text))
    normal_words = len(re.findall(r'[\u0621-\u063A\u0641-\u064A]{2,}', text))
    if normal_words > 0 and consecutive_diacritics / normal_words > 0.15:
        return True
    garbled_chars = len(re.findall(r'[\u0640-\u065F\u0670-\u06FF]', text))
    normal_chars = len(re.findall(r'[\u0621-\u063A\u0641-\u064A]', text))
    if normal_chars > 0 and garbled_chars / normal_chars > 0.5:
        return True
    return False

def detect_content_type(text):
    text = text.strip()
    if not text:
        return "content"
    for pat in MEDICAL_SECTION_PATTERNS:
        if pat.match(text):
            return "chapter"
    if ARABIC_RE.search(text) and len(text) < 60 and text.endswith(":"):
        return "section"
    if re.match(r"^\d+[\.\)_]", text):
        return "list_item"
    if "|" in text or "\t" in text:
        return "table"
    return "content"

PDF_PATH = "/home/z/my-project/upload/المرجع+الدوائي+السوري.pdf"
OUTPUT_PATH = "/home/z/my-project/download/medical_dictionaries/المرجع_الدوائي_السوري_v4.tsv"
PROGRESS_FILE = "/home/z/my-project/scripts/syrian_v4_progress.json"

def main():
    # Load progress
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r') as f:
            progress = json.load(f)
    else:
        progress = {"last_page": 0, "total_lines": 0, "status": "in_progress"}
    
    start_page = progress["last_page"]
    
    pdf = fitz.open(PDF_PATH)
    total_pages = pdf.page_count
    print(f"PDF: {total_pages} pages, starting from page {start_page + 1}", flush=True)
    
    # Write header if starting fresh
    if start_page == 0:
        with open(OUTPUT_PATH, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f, delimiter='\t')
            writer.writerow(["Type", "Section", "Subsection", "Content"])
    
    current_chapter = ""
    current_section = ""
    start_time = time.time()
    
    for page_idx in range(start_page, total_pages):
        page_num = page_idx + 1
        try:
            page = pdf[page_idx]
            text = page.get_text()
            
            # Check if text is garbled
            use_ocr = True
            if len(text.strip()) > 50:
                arabic_chars = len(ARABIC_RE.findall(text))
                if arabic_chars > len(text) * 0.1 and not is_text_garbled(text):
                    use_ocr = False
            
            if use_ocr:
                # Render and OCR
                zoom = 150 / 72.0
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                if pix.n == 4:
                    img = img[:, :, :3]
                
                pil_img = Image.fromarray(img)
                text = pytesseract.image_to_string(pil_img, lang="ara", config="--psm 6")
                if not text or not text.strip():
                    text = pytesseract.image_to_string(pil_img, lang="ara+eng", config="--psm 6")
            
            # Process lines
            rows = []
            for line in text.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                content_type = detect_content_type(line)
                if content_type == "chapter":
                    current_chapter = line
                    current_section = ""
                elif content_type == "section":
                    current_section = line
                rows.append([content_type, current_chapter, current_section, line])
            
            # Append to TSV immediately
            with open(OUTPUT_PATH, 'a', encoding='utf-8-sig', newline='') as f:
                writer = csv.writer(f, delimiter='\t')
                for row in rows:
                    writer.writerow(row)
            
            progress["total_lines"] += len(rows)
            
        except Exception as e:
            print(f"  [p{page_num}] error: {e}", flush=True)
        
        # Save progress every 5 pages
        if page_num % 5 == 0:
            progress["last_page"] = page_idx + 1
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            elapsed = time.time() - start_time
            print(f"  [p{page_num}/{total_pages}] {progress['total_lines']} lines, {elapsed:.0f}s", flush=True)
        
        # Check time limit (25 minutes)
        if time.time() - start_time > 1400:
            progress["last_page"] = page_idx + 1
            progress["status"] = "paused"
            with open(PROGRESS_FILE, 'w') as f:
                json.dump(progress, f, ensure_ascii=False, indent=2)
            print(f"Time limit reached at page {page_num}. Run again to continue.", flush=True)
            pdf.close()
            return
    
    # Done!
    progress["last_page"] = total_pages
    progress["status"] = "completed"
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    
    elapsed = time.time() - start_time
    print(f"COMPLETED! {progress['total_lines']} lines in {elapsed:.0f}s", flush=True)
    pdf.close()

if __name__ == "__main__":
    main()
