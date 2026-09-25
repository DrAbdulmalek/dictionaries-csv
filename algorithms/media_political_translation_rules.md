# خوارزميات قواعد الترجمة: معجما المصطلحات السياسية والإعلامية
# Translation Rule Algorithms — Political & Media Terminology

قواعد الترجمة الإنجليزية ⇄ العربية المستخرجة **آلياً وإحصائياً** من مدونة متوازية قوامها **1600 زوج مصطلحات** + **434 زوج عبارات/جمل** + **1007 تعريفات عربية**، مصدرها:

| المصدر | الصفحات | المداخل المستخرجة |
|---|---:|---:|
| الموسوعة الميسرة للمصطلحات السياسية (د. إسماعيل عبد الفتاح) | 508 | 1035 مدخلاً (1030 ثنائي اللغة) + 1007 تعريفات |
| معجم مصطلحات الإعلام (مجمع اللغة العربية بالقاهرة) | 121 | 570 مصطلحاً (مطابقة قسمي الفهرس والمتن) |

الملفات المرافقة:
- `media_political_translation_rules.json` — القواعد بصيغة آلية (support/precision/أمثلة)
- `media_political_rules_mined_evidence.json` — دليل التعدين الإحصائي الخام
- `../scripts/translation_rules_engine.py` — محرك قواعد قابل للتنفيذ يطبق الخوارزميات أدناه

---

## 1. الخوارزمية الرئيسية لترجمة المصطلح (Main Term Translation)

```text
Algorithm Translate_Term(en_term, domain):
    1. t ← Normalize(en_term)                     # lower, fold spaces, strip punctuation
    2. IF t ∈ BilingualLexicon(1600)              # R01
           RETURN Lexicon[t]                      # أعلى موثوقية
    3. IF IsAcronym(t)                            # R09
           RETURN Acronym_Strategy(t)
    4. np ← ParseNP(t)                            # [MODS][HEAD] + of-phrases
    5. head_ar ← Translate_Head(np.head, domain)  # R15 (اطراد المجال)
       IF head_ar = ∅: head_ar ← Transliterate(np.head)   # R08
    6. ar ← head_ar
    7. FOR mod IN np.of_chain (right-to-left):    # R04
           ar ← ar + " " + Definite?(Translate(mod))      # إضافة بلا حرف جر
    8. FOR adj IN np.adjectives:                  # R03 + R06
           adj_ar ← ADJ_TABLE[adj] or Prefix_Table(adj)
           ar ← ar + " " + Agree(adj_ar, head_ar) # R13 (نوع/عدد)
    9. FOR noun_mod IN np.noun_modifiers:         # R05
           ar ← ar + " " + Definite(Translate(noun_mod))
   10. ar ← Article_Policy(ar, np)                # R02
   11. RETURN PostProcess(ar)                     # تطبيع همزات/مسافات/تشكيل
```

### شجرة القرار (Decision Tree)

```text
en_term
├─ موجود في المعجم؟ ────────────── نعم → إرجاع المقابل (R01)
├─ اختصار بأحرف كبيرة؟ ─────────── نعم → R09:
│     ├─ منظمة لها اسم وصفي → ترجمة الموسَّع (GATT → الاتفاقية العامة...)
│     ├─ معرَّب دارج → نقل صوتي (NATO → الناتو، OAPEC → أوابك)
│     └─ إلحاق الأصل اللاتيني بين قوسين اختياراً: صندوق النقد الدولي (IMF)
├─ علم (اسم/مكان/مفهوم أجنبي)؟ ─── نعم → R08 نقل صوتي (Bundestag → البوندستاج)
└─ عبارة اسمية → التحليل:
      ├─ Adj + N ............... → R03 قلب + مطابقة (pay television → التليفزيون المدفوع)
      ├─ N1 + of + N2 .......... → R04 إضافة (Concentration Of Ownership → تركيز الملكية)
      ├─ N1 + N2 (وصفي) ......... → R05 قلب مركّب (camera angle → زاوية الكاميرا)
      ├─ prefix + stem ......... → R06 جدول السوابق (multi + national → متعددة الجنسية)
      └─ stem + suffix ......... → R07 جدول اللواحق (-cracy → قراطية، -ity → ية)
```

---

## 2. القواعد الهيكلية (Structural)

### R02 — سياسة أداة التعريف
- **القياس:** 599/1600 (37.4%) من المقابلات العربية تبدأ بـ«ال» مقابل 1.7% فقط في الإنجليزية تحمل the.
- **الخوارزمية:** الرأس المؤسسي/المجرد (نظام، منظمة، مجلس، السلطة) ← معرَّف؛ العام المعدود (خبر، إعلان) ← بحسب السابقة المعجمية.
- `Public Opinion → الرأي العام`، `political street → الشارع السياسي`

### R03 — قلب موقع الصفة
- **الدليل:** 19 انقلاباً مؤكداً آلياً + جدول الصفات المعدَّن: political→السياسي/السياسية (n=36)، international→الدولي/الدولية (n=14)، national→القومي/الوطني (n=14)، public→العام (n=6)، civil→المدني، social→الاجتماعي.
- **الخوارزمية:** `Adj N → N + (ال)Adj` مع مطابقة النوع والعدد (R13):
```text
"Central America" → أمريكا + الوسطى
"Political Parties" → الأحزاب + السياسية   (جمع غير عاقل ← صفة مفردة مؤنثة)
```

### R04 — of ← إضافة (بلا حرف جر)
- **الدليل:** 92 مصطلحاً فيها of؛ في 78 (85%) العضو الثاني معرَّف بـ«ال».
- **القيد الحاسم:** المضاف يبقى **نكرة** — لا يجوز «التركيز الملكية» بل «تركيز الملكية».
```text
Algorithm Idaafa(n1, n2):
    RETURN Strip_Al(Translate(n1)) + " " + Definite(Translate(n2))
"Bill Of Human Rights" → إعلان + حقوق + الإنسان   (سلسلة إضافات متداخلة)
```

### R05 — المركّب الاسمي N+N
```text
"press gallery"   → شرفة + الصحافة      (إضافة)
"broadcast network" → شبكة + إذاعية      (نسبة بديلة للإضافة)
اختيار النسبة عندما يكون المعدِّل مجرداً/جماعياً، والإضافة عندما يكون عينياً.
```

---

## 3. القواعد الصرفية (Morphological)

### R06 — السوابق (بأرقام الدعم المعدَّنة)
| السابقة | المقابل | دعم | مثال |
|---|---|---:|---|
| inter- | الدولي/بين/تفاعلي | 28 | interactive coverage → تغطية تفاعلية |
| national | القومي/الوطني | 15 | National Minorities → الأقليات القومية |
| uni- | المتحد(ة) | 13 | United Nations → الأمم المتحدة |
| mass | جماهيري | 10 | mass culture → ثقافة جماهيرية |
| multi- | متعدد(ة) | 7 | multimedia → وسائط متعددة |
| mis- | خاطئ/سوء/تضليل | 7 | misinformation → تضليل إعلامي |
| global | كوكبي/عالمي | 6 | global media → وسائل إعلام كوكبية |
| local | محلي | 4 | localism → عولمة محلية |
| anti- | مضاد/مناهضة | — | anti propaganda → دعاية مضادة |
| self- | الذاتي | — | ego involvement → الاندماج الذاتي |
| re- | إعادة/مُعاد | — | republication → إعادة نشر |

### R07 — اللواحق
| اللاحقة | الوزن/المقابل | دعم | دقة | مثال |
|---|---|---:|---:|---|
| -cracy | قراطية | 13 | 0.76 | Autocracy → أتوقراطية |
| -al/-ial | ـي (نسبة) | 232 | 0.83 | political → السياسي |
| -dom | حرية/ـية | 12 | 0.89 | freedom → حرية |
| -ization | فعلة/إفعال | 49 | — | americanization → أمركة، privatization → خصخصة |
| -tion/-sion | مصدر (إفعال/تفعيل) | 312 | — | persuasion → إقناع |
| -ness | ـية/اسم مجرد | 14 | — | consciousness → وعي |
| -ics | ـيات/علم | 22 | — | ethics → أخلاقيات |
| -ology | علم الـ/ـولوجيا | 9 | — | Anthropology → علم الإنسان |
| -ity | ـية | — | — | credibility → مصداقية |
| -ette | تصغير | — | — | booklet → كُتَيِّب |

### R10 — التسمية المصدرية (Nominalization)
- **الدليل:** من 312 مصطلحاً بـ tion/sion/ment: ‏97 على وزن تفعيل، 16 على إفعال، والبقية فَعْل/فِعال/فعلة.
```text
"Goal Attainment" → إنجاز الأهداف    # مصدر + مفعول به مضاف
"encoding" → تفعيل/تشفير             # تفعيل للرُّباعي
```

### R11 — اسم الفاعل للمهن (Agent Nouns)
```text
Algorithm AgentNoun(en):
    verb ← VerbFor(en)                    # أخرج، صمم، حرر، راسل، أعلن
    RETURN ActiveParticiple(verb)         # مُخْرِج، مُصمم، مُحرر، مُراسل، مُعْلِن
    plural → ون/ين                        # مصفقون، صحفيون
director → مُخْرِج | designer → مصمِّم | advertiser → مُعْلِن | rewriter → مُراجع صياغة
```
(31/87 من نهايات er/or الخام تبدأ بـ م؛ وللمهن الحقيقية تقترب النسبة من 100% بعد استبعاد مثل charter.)

---

## 4. النقل الصوتي والاختصارات

### R08 — جدول الفونيمات (Transliteration)
```text
a→ا/أ  ā→آ  b→ب  c/k→ك  ch→تش  d→د  e→ي/إ  f→ف  g→ج(غ للفرنسية)  h→ه
i→ي/إ  j→ج  l→ل  m→م  n→ن  o→و/أو  p→ب  q→ق  r→ر  s→س  sh→ش  t→ت
th→ث/ت  u→و  v→ف  w→و  x→كس  y→ي  z→ز
+ ال للمؤسسات: NATO→الناتو، Bundestag→البوندستاج، Kulak→الكولاك، ASEAN→آسيان
```
**القياس:** 91/1600 (5.7%) قروض صوتية (تشابه رومنة ≥ 0.70)، و158 جزئية، والباقي (1351) ترجمات دلالية — أي أن **الأصل الترجمة الدلالية والتعريب استثناء مضبوط**.

### R09 — شجرة قرار الاختصار
```text
Acronym_Strategy(A):
    IF A منظمة ذات اسم وصفي → ترجم الموسَّع:
        GATT → الاتفاقية العامة الخاصة بالتعرفة والتنمية   (66/71 حالة)
    ELIF A شاع معرَّباً → انقله صوتياً:
        NATO → الناتو | OAPEC → أوابك | COMESA → الكوميسا  (5/71)
    OPTIONALLY → ألحق الأصل بين قوسين: صندوق النقد الدولي (IMF)
    NEVER → لا تُبقِ الاختصار اللاتيني وحده (0/71 في المدونة)
```

---

## 5. قواعد الخطاب والترقيم

### R14 — الحاشية الثنائية (Code-Switch Annotation)
نمط الشرح السائد في المدونة: `العبارة العربية (English)` أو الإلحاق المباشر — 434 زوج عبارات مستخرج:
```text
"...في حالة مقبولة من التوازن Stable Equilibrium لفترة طويلة"
"...وهو تصغير سوسيولوجي للسياسة Sociological Reduction Of Politics"
خوارزمية التوليد: عند تقديم مصطلح منقول أو مترجم حديثاً → ألحق الأصل اللاتيني
بعد العبارة العربية مباشرة مع عزل اتجاه النص (bidi isolation).
```

### R16 — توطين الأرقام والتواريخ
```text
1. أرقام هندية مشرقية: ٠١٢٣٤٥٦٧٨٩
2. السنة الميلادية + " م": ١٩٤٨ م
3. في طبقات نص PDF العربية: سلاسل الأرقام مخزونة بالمقلوب البصري → اعكسها
   (٨٤٩١ ← ١٩٤٨) — تم التحقق تاريخياً (كفر قاسم ١٩٥٦، صبرا ١٩٨٢)
```

---

## 6. خوارزميات إصلاح النص (زمن التحويل) — R17

```text
Algorithm Repair_Arabic_TextLayer(line):
    1. NFKC(line); remove bidi marks
    2. IF line ends with tatweel(ـ) → replace with م      # العاـ ← العام
    3. strip remaining tatweels                            # كشيدة تسوية
    4. map rare codepoints: ؿ→ل ؼ→ف ؽ→ق ؾ→ك ػ→غ           # خريطة خط معجم الإعلام
    5. reorder ligatures: اإل→الإ، األ→ال+أ، اال→الا، اآل→الآ
    6. apply curated confusion map: final ن→ف, ل→م, medial ه→ي/ى
       (ناتجة عن مراجعة يدوية كاملة لـ 571 مصطلحاً)
    7. merge split word fragments (ع ك سية ← عكسية؛ ا لأرض ← الأرض)
    8. flip reversed Arabic digit runs
    9. cross-vote sections: score(index_variant, main_variant) → pick cleanest
       + 192 override مقنّن
```

### قياسات الجودة
| المقياس | القيمة |
|---|---|
| أزواج ثنائية اللغة (سياسي) | 1030 |
| تعريفات عربية سليمة | 1007 (97.3%) |
| أزواج ثنائية اللغة (إعلام) | 570 بعد دمج تصويت قسمين مستقلين |
| بقايا فساد مكتشفة بعد الإصلاح | 0 في المصطلحات |
| تواريخ قابلة للتحقق أُصلحت | 116 سنة (١٩٤٨، ١٩٥٦، ١٩٧٦، ١٩٨٢، ١٩٨٧...) |

---

## 7. كيفية إعادة الإنتاج
```bash
python3 scripts/extract_political_encyclopedia.py   # PDF السياسي → pol_entries.json
python3 scripts/extract_media_dictionary.py         # PDF الإعلام → media_entries.json
python3 scripts/mine_bilingual_sentences.py         # الجمل/العبارات الثنائية
python3 scripts/mine_translation_rules.py           # التعدين الإحصائي للقواعد
python3 scripts/build_en_ar_csvs.py                 # توليد ملفات CSV النهائية
python3 scripts/translation_rules_engine.py --self-test   # اختبار محرك القواعد
```
