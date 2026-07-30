# Dictionary Collection — CSV Conversions

مجموعة قواميس ثنائية اللغة (إنجليزي ⇄ عربي) محوّلة إلى صيغة CSV موحّدة.

تم تحويل **14 قاموساً** بنجاح (**466,670 مدخلاً**) من 6 صيغ مختلفة، مع الاحتفاظ بـ **11 ملفاً أصلياً** من صيغة Babylon الخاصة في مجلد `raw_unsupported/`.

---

## 📊 الإحصائيات

| الصيغة | عدد الملفات | المداخل | الحالة |
|---|---:|---:|---|
| MDict (.mdx) | 4 | 70,912 | ✅ محوّل |
| StarDict (.ifo/.idx/.dict.dz) | 3 | 129,549 | ✅ محوّل |
| dicthtml (HTML مضغوط بـ gzip) | 1 | 239,599 | ✅ محوّل |
| PDF نصي | 4 | 20,848 | ✅ محوّل |
| PDF ممسوح ضوئياً (OCR) | 1 | 5,726 | ✅ محوّل (tesseract ara+eng) |
| DOCX | 1 | 36 | ✅ محوّل |
| Babylon .BGL | 8 | — | ⚠️ غير مدعوم (ملف أصلي في `raw_unsupported/`) |
| Babylon .LD2 | 3 | — | ⚠️ غير مدعوم (ملف أصلي في `raw_unsupported/`) |
| **المجموع** | **25** | **466,670** | |

---

## 📁 هيكل المستودع

```
.
├── csv/                          # 25 ملف CSV (14 محوّل + 11 placeholder)
│   ├── Dictionary of Medical Terms.csv          (16,672 مدخل)
│   ├── Longman English Arabic.csv               (18,080 مدخل)
│   ├── Longman Modern En-En-Ar.csv              (18,080 مدخل)
│   ├── Longman_English_Arabic_from_RAR.csv      (18,080 مدخل)
│   ├── Longman_English_Arabic_from_ZIP.csv      (18,080 مدخل)
│   ├── Oxford Arabic Dictionary.csv             (57,085 مدخل)
│   ├── Oxford_Arabic_Dictionary_EnAr.csv        (54,384 مدخل)
│   ├── dicthtml-en-ar.csv                       (239,599 مدخل)
│   ├── downloadfile-1.csv                       (2,784 مدخل)
│   ├── msf-glossary.csv                         (3,696 مدخل)
│   ├── المصطلحات_الأدبية_الحديثة.csv             (10,170 مدخل)
│   ├── معجم_المصطلحات_الاعلامية.csv              (5,726 مدخل — OCR)
│   ├── معجم_مصطلحات_الإعلام.csv                  (4,198 مدخل)
│   ├── أخطاء_تنقيح_النصوص.csv                    (36 مدخل)
│   └── *.csv  (11 ملفات Babylon placeholder)
├── raw_unsupported/              # 11 ملف Babylon أصلي (BGL/LD2)
│   ├── Arab2English.BGL
│   ├── Babylon_Arabic_English.BGL
│   ├── Babylon_English_Arabic.BGL
│   ├── English - Arabic Finacial-Legal Dictionary.ld2
│   ├── English_2__rabic.BGL
│   ├── English_2_rabic_Glossary.BGL
│   ├── French-Arabic dictionary.bgl
│   ├── Lisan Al Arab.ld2
│   ├── Medicine_English_Arabic.BGL
│   ├── Vicon English-Arabic Dictionary.ld2
│   └── _Concise_English_rabic_Dicti.BGL
├── notes/
│   └── conversion_report.txt     # تقرير التحويل الكامل
└── scripts/                      # سكريبتات التحويل (Python)
    ├── convert_dicts.py          # المحول الموحد
    ├── convert_dicts_fast.py     # نسخة سريعة (بدون PDF)
    ├── extract_7z_mv.py          # استخراج أرشيف 7z متعدد الأجزاء
    ├── extract_nested.py         # استخراج الأرشيفات المتداخلة
    ├── ocr_pdf_ar1.py            # OCR لـ PDF واحد
    ├── ocr_pdf_chunk.py          # OCR مقسّم (يتجاوز timeout)
    └── finalize_report.py        # توليد التقرير النهائي
```

---

## 📋 مخطط CSV

كل ملف CSV يحتوي على 3 أعمدة:

| العمود | الوصف |
|---|---|
| `term` | المصطلح (رأس المدخل) |
| `definition` | التعريف/الترجمة |
| `source_file` | اسم الملف الأصلي |

**الترميز:** UTF-8 with BOM (متوافق مع Excel و LibreOffice).

---

## 🔧 كيفية تحويل ملفات Babylon (غير المدعومة)

ملفات `.BGL` و `.LD2` تستخدم صيغة ثنائية خاصة بـ Babylon. لتحويلها:

### الطريقة 1: تطبيق Babylon
1. ثبّت تطبيق Babylon Desktop (متوقف رسمياً لكن متاح في الأرشيفات)
2. افتح ملف BGL من تطبيق Babylon
3. صدّر كنص مفصول بجدولة (Export → Tab-separated text)

### الطريقة 2: dictconv (مفتوح المصدر)
```bash
# تثبيت
sudo apt install dictconv     # Debian/Ubuntu
# أو بناء من المصدر: https://github.com/ilius/dictconv

# تحويل
dictconv raw_unsupported/Medicine_English_Arabic.BGL -o medicine.txt

# ثم تحويل TXT إلى CSV
python3 -c "
import csv
with open('medicine.txt', encoding='utf-8') as f, open('Medicine_English_Arabic.csv', 'w', encoding='utf-8-sig', newline='') as out:
    w = csv.writer(out)
    w.writerow(['term', 'definition', 'source_file'])
    for line in f:
        if '\t' in line:
            term, definition = line.rstrip('\n').split('\t', 1)
            w.writerow([term, definition, 'Medicine_English_Arabic'])
"
```

### الطريقة 3: pyglossary (مفتوح المصدر، Python)
```bash
pip install pyglossary
python3 -c "
from pyglossary import Glossary
Glossary.init()
g = Glossary()
g.convert('raw_unsupported/Medicine_English_Arabic.BGL', 'csv', 'Medicine_English_Arabic.csv')
"
```

---

## 🛠️ إعادة تشغيل خط الأنابيب

```bash
# 1) تثبيت الاعتماديات
pip install py7zr multivolumefile readmdict beautifulsoup4 lxml \
            pdfplumber pymupdf pytesseract python-docx rarfile

# 2) استخراج الأرشيف الأصلي (New Folder.7z.001 + .002)
python3 scripts/extract_7z_mv.py

# 3) استخراج الأرشيفات المتداخلة
python3 scripts/extract_nested.py

# 4) تحويل الكل (StarDict + MDX + HTML + PDF + DOCX)
python3 scripts/convert_dicts.py

# 5) OCR للـ PDF الممسوح ضوئياً (يتطلب tesseract + ara.traineddata)
python3 scripts/ocr_pdf_ar1.py
# أو مقسّم (لتفادي timeout):
python3 scripts/ocr_pdf_chunk.py 0 20 chunk1.csv
python3 scripts/ocr_pdf_chunk.py 20 40 chunk2.csv
# ... ثم دمج الـ chunks

# 6) توليد التقرير النهائي
python3 scripts/finalize_report.py
```

---

## ⚠️ ملاحظات الجودة

| القاموس | جودة التحويل | ملاحظات |
|---|---|---|
| Dictionary of Medical Terms (MDX) | ⭐⭐⭐⭐⭐ | نظيف تماماً |
| Longman English Arabic (MDX) | ⭐⭐⭐⭐⭐ | نظيف، EN/AR في نفس الحقل |
| Oxford Arabic Dictionary (StarDict) | ⭐⭐⭐⭐ | نظيف مع بعض بادئات ID |
| dicthtml-en-ar (HTML) | ⭐⭐⭐⭐⭐ | نظيف، فصل واضح EN↔AR |
| msf-glossary (PDF) | ⭐⭐⭐⭐ | جيد |
| المصطلحات الأدبية الحديثة (PDF) | ⭐⭐⭐ | PDF 416 صفحة، قد يحتاج تنظيف يدوي |
| معجم مصطلحات الإعلام (PDF) | ⭐⭐⭐⭐ | جيد |
| معجم المصطلحات الاعلامية (OCR) | ⭐⭐⭐ | OCR بنسبة دقة ~85% — قد يحتاج مراجعة |
| downloadfile-1 (PDF) | ⭐⭐ | تخطيط معقد، بعض الصفوف الفارغة |
| أخطاء تنقيح النصوص (DOCX) | ⭐⭐⭐⭐ | نص حر، 36 فقرة فقط |

---

## 📜 الترخيص

الملفات في هذا المستودع مأخوذة من مصادر متعددة وحقوق النشر تعود لأصحابها الأصليين. السكريبتات فقط (في `scripts/`) مرخّصة تحت MIT. استخدم البيانات لأغراض شخصية/بحثية فقط.

---

## 👤 المؤلف

**Dr Abdulmalek Al-Husseini** — [GitHub](https://github.com/DrAbdulmalek)

تاريخ التحويل: 2026-07-31
