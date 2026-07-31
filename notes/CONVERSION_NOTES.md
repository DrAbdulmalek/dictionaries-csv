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

الملف الأصلي PDF ممسوح ضوئياً (76 صفحة صور، Canon iR C4580). التخطيط:
**عمودان لكل صفحة، كل مدخل = رقم + إنجليزي + عربي + فرنسي** (قاموس رباعي اللغة).

### النسخة النهائية المعتمدة (في `csv/معجم_المصطلحات_الاعلامية.csv`)
- **1,036 مدخلاً** نظيفاً يغطي الحروف A–F
- مخطط: `id, English, Arabic` (3 أعمدة)
- هذه هي النسخة الذهبية المُراجعة يدوياً — استخدمها كمرجع.

### النسخة الأولية (مهملة، لم تُحفظ)
أنتجت 5,726 مدخلاً مجزّأً بـ OCR بسيط (DPI=200، بدون فصل أعمدة، بدون تمييز
بين العربي واللاتيني). كل النصوص وضعت في عمود واحد فاختلط الإنجليزي بالعربي
بالفرنسي. **تم استبدالها بالنسخة الذهبية.**

### خوارزمية OCR المحسّنة v2 (`scripts/ocr_bilingual_dict_v2.py`)
طوّرنا خط معالجة جديد يعالج مشاكل النسخة الأولية:

1. **دقة 300 DPI** (بدل 200) — حروف أوضح
2. **عتبة ثنائية تكيّفية** (adaptive threshold، OpenCV) — تنظيف ضوضاء الماسح
3. **فصل العمودين** عند منتصف الصفحة (gutter ratio = 0.5)
4. **تمييز الكلمات حسب الخط**: لاتيني → إنجليزي، عربي → عربي، أرقام → رقم المدخل
5. **فرز الكلمات العربية RTL** (تنازلياً حسب X) للحصول على ترتيب قراءة صحيح
6. **تجميع الصفوف** بتسامح Y = 12 بكسل
7. **فلتر الضوضاء**: تخطّي الأرقام المنفردة، العناوين، الصفوف بلا نص لاتيني أو عربي
8. **إزالة التكرارات** بزوج (english_lower, arabic)

**نتائج v2 مقارنة بالمرجع:**
| المقياس | المرجع | v2 |
|---|---:|---:|
| إجمالي المداخل | 1,036 | 1,337 |
| مصطلحات مشتركة (case-insensitive) | — | 540 (52.1%) |
| أزواج متطابقة تماماً | — | 147 (14.2%) |

ملف v2 محفوظ في `csv/معجم_المصطلحات_الاعلامية_ocr_v2.csv` لأغراض المقارنة.

### كيفية إعادة تشغيل v2 على قاموس PDF آخر ممسوح ضوئياً
```bash
export TESSDATA_PREFIX=/path/to/tessdata   # يجب أن يحوي ara.traineddata + eng.traineddata
python scripts/ocr_bilingual_dict_v2.py INPUT.pdf OUTPUT.csv \
    --dpi 300 --start 0 --end N --src-name "Dictionary Name"
```
للملفات الكبيرة (>20 صفحة): شغّل على دفعات (chunks) ثم ادمج بـ `scripts/merge_chunks.py`.

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

---

## 6) المرجع الدوائي السوري (200 صفحة)

### المشكلة
ملف PDF يحتوي على طبقة نص مضمنة (embedded text) لكنها **مشوهة** (garbled encoding) —
الأحرف العربية تظهر بشكل خاطئ عند الاستخراج المباشر.

### الحل
استخدام OCR (Tesseract) بدلاً من استخراج النص المباشر:
- اكتشاف تلقائي للنص المشوه عبر دالة `is_text_garbled()`
- Tesseract مع `lang='ara'` و `--psm 6` أعطى نتائج ممتازة
- DPI = 150 (كافٍ لجودة النص العربي)

### النتائج
| المقياس | القيمة |
|---|---:|
| إجمالي الصفحات | 200 |
| إجمالي الأسطر المستخرجة | 19,927 |
| نسبة المحتوى العربي | 100% |
| عدد الفصول | 249 |
| عدد الأقسام | 652 |

### خوارزمية v4 (`scripts/medical_ocr_pipeline_v4.py`)
النسخة المحسّنة تتضمن:
1. **اكتشاف النص المشوه**: تحليل طبقة النص المضمنة وتحديد ما إذا كانت مشوهة
2. **OCR محسّن**: Tesseract مع `lang='ara'` (أفضل من `ara+eng` للنصوص العربية الكثيفة)
3. **هيكلة تلقائية**: اكتشاف الفصول والأقسام والجداول
4. **حفظ تدريجي**: حفظ كل 5 صفحات لتجنب فقدان البيانات
5. **إشارة الحذف الآمن**: ملف `.verified.flag` بدلاً من الحذف الفعلي

### ملفات مرجعية
- `csv/المرجع_الدوائي_السوري_v4.tsv` — الناتج النهائي
- `csv/المرجع_الدوائي_السوري_v4_report.json` — تقرير الجودة
- `csv/المرجع_الدوائي_السوري_v4.tsv.verified.flag` — علامة التحقق
- `scripts/medical_ocr_pipeline_v4.py` — خط المعالجة الشامل
- `scripts/process_syrian_v4.py` — سكريبت المعالجة التدريجية

تاريخ التحديث: 2026-07-31
