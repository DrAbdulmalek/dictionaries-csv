#!/usr/bin/env python3
"""Write note CSVs for unsupported Babylon BGL/LD2 files and produce final report."""
import csv
import os
from pathlib import Path

CSV_OUT = Path("/home/z/my-project/dict_work/csv_output")
LOGS = Path("/home/z/my-project/dict_work/logs")
BABYLON_DIR = Path("/home/z/my-project/dict_work/unpacked/ArabicDictionariesOfBabylon/DictionariesOfBabylon")

# Existing successful conversions (name, csv_name, rows)
done = [
    ("Dictionary of Medical Terms",           "Dictionary of Medical Terms.csv",            16672),
    ("Longman English Arabic",                "Longman English Arabic.csv",                 18080),
    ("Longman English Arabic (from RAR)",     "Longman_English_Arabic_from_RAR.csv",        18080),
    ("Longman English Arabic (from ZIP)",     "Longman_English_Arabic_from_ZIP.csv",        18080),
    ("Longman Modern En-En-Ar (StarDict)",    "Longman Modern En-En-Ar.csv",                18080),
    ("Oxford Arabic Dictionary (StarDict)",   "Oxford Arabic Dictionary.csv",               57085),
    ("Oxford Arabic Dictionary EnAr (StarDict)", "Oxford_Arabic_Dictionary_EnAr.csv",        54384),
    ("dicthtml-en-ar (HTML folder)",          "dicthtml-en-ar.csv",                         239599),
    ("downloadfile-1 (PDF)",                  "downloadfile-1.csv",                         2784),
    ("msf-glossary (PDF)",                    "msf-glossary.csv",                           3696),
    ("المصطلحات_الأدبية_الحديثة (PDF)",        "المصطلحات_الأدبية_الحديثة.csv",                10170),
    ("معجم مصطلحات الإعلام (PDF)",             "معجم_مصطلحات_الإعلام.csv",                    4198),
    ("معجم المصطلحات الاعلامية (PDF, OCR)",    "معجم_المصطلحات_الاعلامية.csv",                5726),
    ("أخطاء تنقيح النصوص (DOCX)",             "أخطاء_تنقيح_النصوص.csv",                     36),
]

# Write note CSVs for Babylon files
babylon_files = []
if BABYLON_DIR.exists():
    for f in sorted(BABYLON_DIR.iterdir()):
        if f.suffix.lower() in (".bgl", ".ld2"):
            csv_name = f.stem.replace(" ", "_").replace("/", "_") + ".csv"
            out = CSV_OUT / csv_name
            with open(out, "w", encoding="utf-8-sig", newline="") as fp:
                w = csv.writer(fp)
                w.writerow(["term", "definition", "source_file"])
                w.writerow([
                    "[CONVERSION NOTE]",
                    f"Babylon .{f.suffix[1:].upper()} is a proprietary binary format not directly readable. "
                    "To convert: open with Babylon desktop app and export as tab-separated text, OR install "
                    "dictconv (https://github.com/ilius/dictconv) and run: dictconv input.bgl -o output.txt. "
                    "Then re-run convert_dicts.py on the exported .txt file.",
                    f.name,
                ])
            babylon_files.append((f.name, csv_name, 0, "UNSUPPORTED_FORMAT"))

# ─── Final report ───
report = LOGS / "conversion_report.txt"
with open(report, "w", encoding="utf-8") as f:
    f.write("=" * 100 + "\n")
    f.write("DICTIONARY → CSV CONVERSION REPORT\n")
    f.write("=" * 100 + "\n\n")
    f.write(f"{'NAME':<55} {'ROWS':>8}  {'STATUS':<22}  CSV\n")
    f.write("-" * 100 + "\n")
    for name, csv_name, rows in done:
        f.write(f"{name[:55]:<55} {rows:>8}  {'OK':<22}  {csv_name}\n")
    for name, csv_name, rows, status in babylon_files:
        f.write(f"{name[:55]:<55} {rows:>8}  {status:<22}  {csv_name}\n")
    f.write("\n")
    ok_count = len(done)
    unsup = len(babylon_files)
    total_rows = sum(r for _, _, r in done)
    f.write(f"\nTotal dictionaries processed: {ok_count + unsup}\n")
    f.write(f"  OK          : {ok_count}  (text-based formats: MDX, StarDict, HTML, PDF, DOCX)\n")
    f.write(f"  UNSUPPORTED : {unsup}  (Babylon BGL/LD2 — proprietary binary)\n")
    f.write(f"\nTotal entries extracted: {total_rows:,}\n")
    f.write("\nOutput directory: /home/z/my-project/dict_work/csv_output/\n")
    f.write("Each CSV has columns: term, definition, source_file\n")
    f.write("Encoding: UTF-8 with BOM (Excel-compatible)\n")

print(open(report, encoding="utf-8").read())
