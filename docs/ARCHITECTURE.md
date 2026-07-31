# Architecture — dictionaries-csv

Data pipeline that converts 25 heterogeneous dictionary sources
(MDict / StarDict / HTML / PDF / DOCX) into 14 normalized UTF-8 CSV
files (466,670 entries total). Used downstream by the spell-checker
and search layers of `omni-medical-suite` and `intelli-file-manager`.

```
┌────────────────────────────────────────────────────────────────────┐
│                        INPUT SOURCES (25 files)                    │
│  .mdx/.mdd  .ifo/.idx/.dict  .html(.gz)  .pdf  .docx  .bgl/.ld2   │
└─────┬────────────┬────────────┬──────────┬──────┬──────┬───────────┘
      │            │            │          │      │      │
      ▼            ▼            ▼          ▼      ▼      ▼
┌───────────┐ ┌───────────┐ ┌────────┐ ┌──────┐ ┌──────┐ ┌─────────┐
│ readmdict │ │  StarDict │ │ bs4 +  │ │pdfplu│ │python│ │ unsup.  │
│  (mdx)    │ │  reader   │ │ regex  │ │ mber │ │ -docx│ │  stub   │
└─────┬─────┘ └─────┬─────┘ └───┬────┘ └──┬───┘ └──┬───┘ └────┬────┘
      │             │           │         │        │          │
      ▼             ▼           ▼         ▼        ▼          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PROCESSING LAYER                             │
│  • term/definition extraction (format-specific)                 │
│  • Arabic BiDi / Presentation Forms normalization               │
│  • CID marker stripping                                          │
│  • deduplication (term, definition) pairs                        │
│  • filename sanitization (_safe_csv_name)                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OUTPUT LAYER                                 │
│  csv_output/<source_name>.csv  × 14                             │
│  Schema: term, definition, source_file                          │
│  Encoding: UTF-8 with BOM                                        │
│  Total: 466,670 entries                                          │
└─────────────────────────────────────────────────────────────────┘

P0 fixes applied (branch fix/kimi-review-p0-p1):
  1. ROOT hardcoded path → argparse --root + DICT_WORK_DIR env var
  2. LZO stub no-op → magic-byte check (b'\\x89LZO') raises RuntimeError
  3. ocr_pdf_ar1.py hardcoded paths → argparse + env vars
  4. _safe_csv_name over-strips dots → preserve single dots
