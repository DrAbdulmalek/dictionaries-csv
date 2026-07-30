# ملاحظات التحويل

## 1) ملفات Babylon (11 ملفاً في `raw_unsupported/`)

هذه الملفات بصيغة `BGL` (Babylon Glossary) أو `LD2` (Lingvo Dictionary) — صيغ ثنائية خاصة لا يمكن قراءتها مباشرة بـ Python.

**طرق التحويل المقترحة (انظر README.md للتفاصيل):**

| الملف | الحجم | الأداة الموصى بها |
|---|---:|---|
| Babylon_English_Arabic.BGL | 6.9M | تطبيق Babylon Desktop → Export |
| Lisan Al Arab.ld2 | 12M | ABBYY Lingvo → Export |
| Medicine_English_Arabic.BGL | 1.4M | `dictconv` أو `pyglossary` |
| Vicon English-Arabic Dictionary.ld2 | 2.0M | ABBYY Lingvo → Export |
| باقي الملفات | — | `dictconv` (مفتوح المصدر) |

**ملاحظة:** ملفات LD2 هي صيغة ABBYY Lingvo (وليس Babylon رغم وجودها في الأرشيف). تحتاج أداة `dictconv` مبنية بدعم Lingvo.

---

## 2) جودة OCR لـ "معجم المصطلحات الاعلامية"

الملف الأصلي PDF ممسوح ضوئياً (76 صفحة صور). تم استخدام:

- **Tesseract 5** مع `ara.traineddata` + `eng.traineddata` (من `tessdata_fast`)
- **PyMuPDF (fitz)** لرسترنة الصفحات بدقة 200 DPI
- تشغيل مقسّم إلى 5 دفعات (chunked) لتجنب timeout

**دقة متوقعة:** ~80-90% للنصوص العربية الواضحة، أقل للأسماء العلمية والأرقام.

**لتحسين الدقة:**
1. ارفع DPI إلى 300 في `scripts/ocr_pdf_chunk.py` (السطر 36)
2. أضف معالجة مسبقة للصور (threshold، denoising)
3. جرّب نماذج OCR أحدث (EasyOCR، PaddleOCR)

---

## 3) ملاحظات على ملفات PDF الفردية

### `downloadfile-1.pdf` (92 صفحة)
- ينتج صفوفاً فارغة/مقطعة بسبب تخطيط PDF معقد (أعمدة متعددة + جداول)
- يُنصح بمراجعة يدوية أو إعادة التحويل باستخدام Adobe Acrobat → Export to Excel

### `المصطلحات_الأدبية_الحديثة.pdf` (416 صفحة)
- أكبر ملف PDF (10,170 مدخل)
- التحويل جيد لكن قد يحتاج تنظيف صفوف العناوين/الفهرس

### `معجم مصطلحات الإعلام.pdf` (121 صفحة)
- جودة جيدة، 4,198 مدخل

---

## 4) ملفات Longman المكررة

يوجد 3 نسخ من "Longman English Arabic" — كلها تعطي نفس 18,080 مدخلاً:

| الملف | المصدر |
|---|---|
| `Longman English Arabic.csv` | الملف المباشر في الأرشيف |
| `Longman_English_Arabic_from_RAR.csv` | من داخل Longman_Modern_EnEnAr.rar |
| `Longman_English_Arabic_from_ZIP.csv` | من داخل Longman_Modern_EnEnAr.zip |

والنسخة الرابعة:
| `Longman Modern En-En-Ar.csv` | StarDict (.ifo/.idx/.dict) — نفس المحتوى بصيغة مختلفة |

يمكنك حذف 3 من الـ 4 نسخ إن أردت.

---

## 5) إعادة التحويل

السكريبتات في `scripts/` قابلة لإعادة التشغيل. الاعتماديات:

```bash
pip install py7zr multivolumefile readmdict beautifulsoup4 lxml \
            pdfplumber pymupdf pytesseract python-docx rarfile
# لتثبيت readmdict بدون lzo:
#   sys.modules['lzo'] = type(sys)('lzo')
#   sys.modules['lzo'].decompress = lambda x, y=None: x
#   sys.modules['lzo'].compress = lambda x, y=None: x
#   from readmdict import MDX

# تثبيت tesseract + بيانات العربية:
sudo apt install tesseract-ocr tesseract-ocr-ara
# أو تنزيل ara.traineddata من tessdata_fast يدوياً
```

---

تاريخ الإنشاء: 2026-07-31
