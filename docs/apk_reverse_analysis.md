<!-- المصدر: محادثة 1m3ih8eveq98lv7aqc — رسالة 173 -->


# apk-reverse — تحليل صريح لاستخدامه في استخراج القواميس

## ما هو `apk-reverse` بالضبط

**ليس أداة استخراج قواميس. إنه "مهارة وكيل" (Agent Skill) للهندسة العكسية لـ APK بشكل عام.**

| البند | التفصيل |
|------|--------|
| **النوع** | Agent Skill (يُحمَّل بواسطة Claude Code أو Codex) |
| **الترخيص** | MIT ✅ |
| **اللغة** | Python 3.9+ |
| **النجوم** | 1.4K (خلال 6 أيام من الإطلاق — نمو استثنائي) |
| **المطوّر** | `newliver666` |
| **المُدخل** | APK (للهندسة العكسية) |
| **المُخرج** | كود مُفكَّك، تعديلات، تقارير تحليل |

## هل يفيد استخراج المفردات من APK قواميس؟

**نعم، لكن بشكل غير مباشر.** الأداة لا تحتوي على "استخراج قواميس" كوظيفة جاهزة. لكنها توفر **الأدوات التي تحتاجها**:

### السكريبتات المفيدة لحالتك

| السكريبت | وظيفته | الفائدة لك |
|----------|--------|-----------|
| **`dex_strings.py`** | استخراج النصوص من DEX بدون مُفكِّك | ⭐⭐⭐ إذا كانت المفردات مخزنة في الكود |
| **`dexutil.py`** | قارئ DEX مستقل | ⭐⭐ لتحليل بنية الملف |
| **`blob_decode.py`** | فك ترميز البيانات المخزنة (base64/hex/deflate) | ⭐⭐⭐ إذا كانت المفردات مشفرة |
| **`datastore_inject.py`** | قراءة/كتابة DataStore | ⭐⭐⭐ إذا كانت القواميس في DataStore |
| **`repack.py`** | إعادة بناء APK بعد التعديل | ⭐⭐ لتصدير القاموس |
| **`protobuf_decode_raw.py`** | فك protobuf بدون schema | ⭐⭐⭐ إذا كانت القواميس مخزنة بـ protobuf |

### ما لا تفعله الأداة

- **لا تستخرج مفردات من SQLite** — تحتاج `sqlite3` مباشرة
- **لا تستخرج من ملفات JSON/XML** — تحتاج أدوات أخرى
- **لا تستخرج من `.so` مشفرة** — تحتاج Frida + تحليل ثنائي
- **لا تعمل من تلقاء نفسها** — تحتاج وكيل AI يشغّلها

## أين تُخزَّن القواميس في APK عادةً؟

| الموقع | الاحتمال | الأداة المناسبة |
|--------|---------|-----------------|
| **`assets/` (SQLite/JSON)** | ⭐⭐⭐⭐⭐ الأكثر شيوعًا | `apktool d` + `sqlite3` |
| **`res/raw/` (JSON/XML)** | ⭐⭐⭐⭐ | `apktool d` |
| **`res/values/strings.xml`** | ⭐⭐⭐ | `apktool d` |
| **DEX strings** | ⭐⭐ | `dex_strings.py` |
| **DataStore/SharedPrefs** | ⭐ | `datastore_inject.py` |
| **`.so` مشفرة** | ⭐ | Frida + `native-and-so.md` |

**الاحتمال الأكبر**: قواميس APK تُخزَّن في `assets/` كـ **SQLite** أو **JSON** — وهذا لا يحتاج `apk-reverse` أصلًا.

## الطريقة العملية — خطوتان

### الخطوة 1: فك APK بأداة بسيطة

```bash
# استخدم apktool (لا يحتاج apk-reverse)
apktool d dictionary.apk -o dict_extracted/

# أو jadx للكود
jadx -d dict_java/ dictionary.apk

# افحص assets/
ls dict_extracted/assets/
ls dict_extracted/res/raw/
```

**90% من الحالات**: ستجد `dictionary.db` أو `words.json` أو `vocab.sqlite` مباشرة.

### الخطوة 2: استخراج المفردات

```python
# إذا كانت SQLite
import sqlite3
conn = sqlite3.connect("dict_extracted/assets/dictionary.db")
tables = conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()
print(tables)

# استخرج المفردات
for table in tables:
    rows = conn.execute(f"SELECT * FROM {table[0]} LIMIT 5").fetchall()
    print(table[0], rows)
```

## متى تحتاج `apk-reverse` فعلاً؟

فقط في هذه الحالات:

| السيناريو | يحتاج apk-reverse؟ |
|-----------|---------------------|
| القاموس في `assets/*.db` | ❌ لا — `sqlite3` كافٍ |
| القاموس في `assets/*.json` | ❌ لا — `json.load` كافٍ |
| القاموس في `strings.xml` | ❌ لا — `apktool` كافٍ |
| القاموس مشفّر في DEX | ✅ نعم — `dex_strings.py` |
| القاموس في `.so` مشفرة | ✅ نعم — Frida + native analysis |
| القاموس مخزّن بـ protobuf مشفّر | ✅ نعم — `protobuf_decode_raw.py` |
| التطبيق يقاوم التحليل (packer) | ✅ نعم — `packers.md` |

## التثبيت والاستخدام — إن احتجته فعلاً

```bash
# 1. ثبّت Claude Code أو Codex أولاً (Agent harness)

# 2. انسخ الـ Skill
git clone https://github.com/newliver666/apk-reverse.git \
    ~/.claude/skills/apk-reverse

# 3. شغّل Claude Code في مجلد APK
cd /path/to/dictionary_apk/
claude

# 4. اكتب في Claude:
"استخدم skill apk-reverse لتحليل dictionary.apk واستخراج المفردات"
```

**Aالنتيجة**: Claude سيشغّل `doctor.py` أولًا، ثم يختار السكريبتات المناسبة.

## ⚠️ ثلاث تحذيرات حرجة

### 1. الترخيص القانوني

**قبل أي شيء**: هل تملك هذه القواميس قانونيًا؟ استخراج بيانات من APK **قد يخالف** شروط استخدام التطبيق الأصلي، خصوصًا في قواميس تجارية (مثل Merriam-Webster، Oxford).

- ✅ **مسموح**: قواميس مجانية مفتوحة (مثل Wiktionary dumps)
- ⚠️ **رمادي**: قواميس تعليمية
- ❌ **ممنوع**: قواميس تجارية مدفوعة

### 2. `apk-reverse` يحتاج وكيل AI

ليست أداة CLI تقليدية. لا يمكن تشغيلها مباشرة من الطرفية. تحتاج:
- Claude Code ($20/شهر)
- أو Codex
- أو أي harness يدعم Agent Skills

### 3. الجهد قد يكون أكبر من الفائدة

**قبل أن تستثمر ساعات في الهندسة العكسية**، تحقق:
- هل يوجد بديل مباشر؟ (Google Takeout، تصدير من التطبيق)
- هل القاموس متاح على HuggingFace أو GitHub؟
- هل يمكن شراء نسخة قابلة للتصدير؟

## التوصية النهائية

**لا تحتاج `apk-reverse` كأول خطوة.** الطريق الصحيح:

```
1. apktool d dictionary.apk          ← 5 دقائق
2. ls assets/ res/raw/                ← 30 ثانية
3. إذا وجدت SQLite/JSON → استخرج    ← 10 دقائق
4. إذا كانت مشفرة → apk-reverse      ← ساعات
5. إذا فشل الجميع → فكّر في شراء/بديل ← قرار تجاري
```

**قبل استخدام apk-reverse، أرسل لي**:
1. نتيجة `apktool d` — قائمة ملفات `assets/` و `res/raw/`
2. اسم APK ومصدره
3. حجم الملف

**بناءً على ذلك** أُخبرك: هل تحتاج `apk-reverse` فعلاً، أم يكفيك `sqlite3` بسطرين.

**سؤال واحد**: ما اسم تطبيق القاموس الذي تريد استخراج مفرداته؟
