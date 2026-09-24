# المرجع الشامل للأنظمة الحاسوبية للترجمة — المستخرج والمطوَّر عن «أسس الترجمة» (د. عز الدين محمد نجيب)

**الغرض:** قاعدة منطقية برمجية جاهزة لمحركات الترجمة الآلية (MT)، ومعالجة اللغات الطبيعية (NLP)، وأدوات CAT (Translation Memory / Glossaries).

---

## 1. القواعد والخوارزميات البرمجية لمعالجة النصوص (Translation Algorithms)

المنطق الشرطي (Decision Logic) الذي يُبنى عليه المحرك لنقل النص من الإنجليزية (SL) إلى العربية (TL).

### ⚙️ خوارزمية (1): معالجة أسماء الأعلام (Proper Nouns Handling)

```text
Input: Token (proper_noun)
IF proper_noun IN Dictionary_Standard_Names THEN
    Output = Arabic_Standard_Translation
    // e.g., "London" -> "لندن", "Cairo" -> "القاهرة"
ELSE IF proper_noun HAS_TRANSLITERATION_RULE THEN
    Output = Apply Transliteration_Rules(proper_noun)
    // تحويل الحروف والجبر الصوتي: "Smith" -> "سميث", "Alexander" -> "ألكسندر"
ELSE IF proper_noun IS_DESCRIPTIVE_TITLE THEN
    Output = Translate_Meaning(proper_noun)
    // e.g., "The White House" -> "البيت الأبيض"
ELSE
    Output = Phonetic_Transliteration(proper_noun)
END IF
```

### ⚙️ خوارزمية (2): معالجة الأسماء الكلية والجمع (Collective Nouns Agreement)

```text
Input: Sentence (Collective_Noun + Verb/Pronoun)
IF Dialect == "British_English" THEN
    IF Verb IS_PLURAL THEN
        // السياق يشير إلى الأفراد داخل المجموعة
        Output_Arabic = "أعضاء/أفراد + الاسم الكلي" + فعل جمع
        // e.g., "The team are arguing" -> "يتجادل أعضاء الفريق"
    ELSE
        Output_Arabic = "الاسم الكلي" + فعل مفرد
        // e.g., "The team has won" -> "فاز الفريق"
    END IF
ELSE IF Dialect == "American_English" THEN
    Output_Arabic = "الاسم الكلي" + فعل مفرد (مذكر/مؤنث بحسب القواعد)
END IF
```

### ⚙️ خوارزمية (3): معالجة الأسماء المجردة (Abstract Nouns Morphological Conversion)

```text
Input: Abstract_Noun in Sentence
IF Sentence_Structure == "Abstract_Noun + Passive_Verb" THEN
    Convert Abstract_Noun TO Arabic_Masdar (مصدر) OR Verb (فعل)
    // e.g., "Justice must be served" -> "يجب أن تتحقق العدالة" / "يجب إقامة العدل"
ELSE IF Abstract_Noun IS_QUALIFIER THEN
    Convert Abstract_Noun TO Arabic_Adjective (صفة)
    // e.g., "He spoke with courage" -> "تحدث بشجاعة" / "تحدث شجاعاً"
END IF
```

### ⚙️ خوارزمية (4): التوفيق بين البريطانية والأمريكية (UK/US Dialect Normalization)

```text
Input: Source_Text (English)
Step 1: Check Token against UK/US Mapping Dictionary
    IF Spelling == "UK" THEN Normalize to Standard
        // e.g., "colour" -> "color", "centre" -> "center"
    IF Grammar == "UK_Present_Perfect" AND US_Past_Simple_Equivalent THEN
        Map to single Semantic Meaning in Arabic
        // e.g., "I have just seen him" == "I just saw him" -> "لقد رأيته للتو"
Step 2: Generate Target Arabic Translation based on unified Semantic Representation
```

---

## 2. قاعدة بيانات الجمل والتعبيرات التطبيقية (Parallel Corpus)

أزواج مترجمة جاهزة لتدريب نماذج MT وذاكرة الترجمة (TM). الملف الكامل: translation_reference_glossary_en_ar.csv على الفرع main.

### 1️⃣ التعبيرات الاصطلاحية (Idiomatic Expressions)

| EN | ❌ حرفية | ✅ اصطلاحية |
|---|---|---|
| It is raining cats and dogs. | إنها تمطر قططاً وكلاباً. | إنها تمطر بغزارة / كأفواه القِرَب. |
| He bit the dust. | عضّ التراب. | لَقيَ حَتْفَه / سَقَطَ قَتِيلاً. |
| To burn the midnight oil. | حرق زيت منتصف الليل. | يسهر الليالي في العمل / يجهد نفسه بالعمل ليلاً. |
| Beat around the bush. | يضرب حول الشجيرة. | يدور ويُلف / يراوغ في الكلام. |

### 2️⃣ الأسماء المجردة والكلية

| EN | ✅ الترجمة |
|---|---|
| Honesty is the best policy. | الأمانة هي أفضل خصلة / الصدق خير مسلك. |
| The government is/are taking new measures. | تتخذ الحكومة إجراءات جديدة (الحكومة مفرد مؤنث في العربية). |
| The staff were divided in their opinions. | انقسم أعضاء الكادر / الموظفون في آرائهم. |
| Freedom of speech must be preserved. | يجب صون حرية التعبير / الكلام. |

### 3️⃣ أسماء الأعلام والمؤسسات

| EN | ✅ الترجمة | القاعدة |
|---|---|---|
| The United Nations Security Council | مجلس الأمن التابع للأمم المتحدة | ترجمة المعنى المعتمد |
| Shakespeare | شيكسبير / شكسبير | نقحرة |
| The Pacific Ocean | المحيط الهادئ | ترجمة الصفة الجغرافية |
| New York | نيو يورك / نيويورك | نقحرة |

### 4️⃣ الفروق الإقليمية (UK/US Variants)

| UK | US | العربية |
|---|---|---|
| Flat | Apartment | شقة سكنية |
| Lift | Elevator | مصعد |
| Petrol | Gas / Gasoline | وقود / بنزين |
| Lorry | Truck | شاحنة |
| Pavement | Sidewalk | رصيف الشارع |
| Autumn | Fall | فصل الخريف |
| Colour / Honour | Color / Honor | لون / شرف (فرق إملائي) |
| Centre / Theatre | Center / Theater | مركز / مسرح (فرق إملائي) |
| At the weekend | On the weekend | في عطلة نهاية الأسبوع (حرف الجر) |
| I have just eaten. | I just ate. | لقد أكلتُ للتوّ (صيغة الزمن) |

---

## 3. دليل البناء الهيكلي لبرمجيات الترجمة (Software Implementation Guide)

مكونات نظام MT / CAT المطلوبة وفق أسس الكتاب:

1. **وحدة التجزئة والتحليل اللغوي (Tokenizer & POS Tagger):** التعرف على أجزاء الكلام (أسماء أعلام، أسماء مجردة، أفعال، صفات).
2. **قاموس المطابقة التلقائية (TM & Glossary Lookup Module):** البحث عن المصطلحات والملازمات اللفظية وتطبيقها قبل الترجمة الحرفية.
3. **محرك التعبيرات الاصطلاحية (Idiom Engine):** كشف العبارات المركبة ككتلة واحدة بدل ترجمة كل كلمة على حدة.
4. **محول القواعد الهيكلي (Grammar & Syntactic Re-ordering Engine):** تحويل [S+V+O] إلى الجملة الفعلية العربية [فعل + فاعل + مفعول] أو الجملة الاسمية بحسب السياق.
5. **مدقق السلاسة (Post-Editing / Spell-Checker):** معالجة التذكير والتأنيث وعلامات الترقيم وتناسق الضمائر.

**خريطة الاستدعاء (Pipeline):**
```text
Tokenizer/POS → TM/Glossary → Idiom Engine → Re-ordering Engine → Post-Editing
```

---

## الربط ببقية المنظومة

- الخوارزمية (1) هي التفصيل التنفيذي لقواعد الأعلام في algorithms/naguib_translation_rules.md والمرحلة 2.1 في algorithms/naguib_translation_workflow.md.
- الخوارزمية (2) و(4) تتكاملان مع جدول الفروق البريطانية/الأمريكية في usul_al_tarjama_terms_en_ar.csv.
- الخوارزمية (4) هي الطبقة التمهيدية (Pre-processing) لخوارزمية WSD في translation_rule_algorithms.md.
- مكونات الدليل الهيكلي (القسم 3) هي التجسيد المعماري لخطوات نجيب السبع ونموذجه ثنائي اللغة.
