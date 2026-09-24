# خوارزميات ومنطق قواعد الترجمة (Translation Rule Algorithms)

يقدم هذا المستند معالجة منطقية وقواعدية لعملية الترجمة، حيث تم تحويل القواعد اللغوية والأساليب النقلية إلى **خوارزميات برمجة هيكلية (Algorithms)** وأشجار قرارات منطقية (Decision Trees) تسهل برمجتها أو تطبيقها الآلي.

---

## 1. الخوارزمية العامة لمعالجة وترجمة النص (Main Translation Flowchart/Algorithm)

### Input: `Source_Text` (النص المصدر)
### Output: `Target_Text` (النص الهدف المترجم)

```text
Algorithm Main_Translation_Process(Source_Text):
    1. Sentences = Split_Into_Sentences(Source_Text)
    2. Target_Sentences = Empty List
    
    3. FOR EACH sentence IN Sentences DO:
          a. Tokens = Tokenize_And_POS_Tag(sentence) // تحليل الأجزاء النحوية
          b. Context = Analyze_Context(Tokens)       // تحديد المجال (طبي، قانوني، عام)
          c. Transformed_Tokens = Apply_Structural_Rules(Tokens, Context)
          d. Translated_Sentence = Generate_Target_Sentence(Transformed_Tokens)
          e. Polished_Sentence = Apply_Stylistic_Enhancements(Translated_Sentence)
          f. Append Polished_Sentence TO Target_Sentences
       END FOR
       
    4. Target_Text = Join_Sentences(Target_Sentences)
    5. RETURN Target_Text
```

---

## 2. خوارزمية تحديد المعنى السياقي للألفاظ (Word Sense Disambiguation - WSD Algorithm)

تُحل هذه الخوارزمية مشكلة الألفاظ متعددة المعاني (Polysemous Words) بناءً على الكلمات المجاورة والمجال.

```text
Algorithm Resolve_Word_Sense(Word, Surrounding_Context, Field_Domain):
    1. Meaning_Candidates = Fetch_Dictionary_Meanings(Word)
    
    2. IF Field_Domain IS "Legal" THEN:
          IF Word == "Right" RETURN "حَق"
          IF Word == "Court" RETURN "محكمة"
          IF Word == "Party" RETURN "طَرَف"
          
    3. ELSE IF Field_Domain IS "Medical" THEN:
          IF Word == "Tender" RETURN "حساس لللمس / مؤلم"
          IF Word == "Culture" RETURN "مزرعة بكتيرية"
          IF Word == "Patient" RETURN "مريض"
          
    4. ELSE (General Context):
          IF Word == "Right" THEN:
             IF Next_Word IS "Side" OR Prev_Word IN ["Turn", "On"] THEN
                 RETURN "يمين"
             ELSE IF Next_Word IS "To" THEN
                 RETURN "حَق"
             ELSE
                 RETURN "صحيح / صواب"
          END IF
          
    5. RETURN Default_Most_Frequent_Meaning(Word)
```

---

## 3. خوارزمية ترتيب الجملة والتحويل الهيكلي (Sentence Restructuring Algorithm)

تحويل الجمل من التركيب الإنجليزي (SVO: الفاعل -> الفعل -> المفعول) إلى التركيب العربي الشائع (VSO: الفعل -> الفاعل -> المفعول) أو (SVO) المتوازن.

```text
Algorithm Restructure_SVO_To_VSO(EN_Sentence_Structure):
    // Structure input: [Subject] + [Verb] + [Object] + [Adverbials/Modifiers]
    
    1. Subject = EN_Sentence_Structure.Subject
    2. Verb = EN_Sentence_Structure.Verb
    3. Object = EN_Sentence_Structure.Object
    4. Modifiers = EN_Sentence_Structure.Modifiers
    
    // فحص نوع الجملة المستهدفة في العربية
    5. IF Sentence_Type == "Verbal_Preferred" (جملة فعلية):
          Target_Structure = [Translate(Verb), Translate(Subject), Translate(Object), Translate(Modifiers)]
          
    6. ELSE IF Sentence_Type == "Nominal_Focus" (جملة اسمية للتأكيد):
          Target_Structure = [Translate(Subject), Translate(Verb), Translate(Object), Translate(Modifiers)]
          
    7. Adjust_Gender_And_Number_Agreement(Target_Structure) // مطابقة التذكير والتأنيث والعدد
    8. RETURN Consolidate_Sentence(Target_Structure)
```

---

## 4. خوارزمية ترجمة الصفات والتراكيب الوصفية (Adjective Order & Attributive Rule)

تتبع الخوارزمية قاعدة عكس ترتيب الصفات (لأن الصفة في الإنجليزية تسبق الموصوف، بينما تتبعه في العربية).

```text
Algorithm Translate_Adjectives(Adjective_List, Noun):
    // English Pattern: Adj1 + Adj2 + Noun (e.g., "A huge black bear")
    // Target Arabic Pattern: Noun + Adj1 + Adj2 (e.g., "دُبّ أسود ضخم")
    
    1. Arabic_Noun = Translate_Term(Noun)
    2. Arabic_Noun_Gender = Get_Gender(Arabic_Noun) // MASCULINE or FEMININE
    3. Arabic_Noun_Plurality = Get_Plurality(Arabic_Noun) // SINGULAR, DUAL, PLURAL
    
    4. Translated_Adjectives = Empty List
    
    5. FOR EACH adj IN Reverse(Adjective_List) DO:
          a. Ar_Adj = Translate_Term(adj)
          b. Ar_Adj = Match_Agreement(Ar_Adj, Arabic_Noun_Gender, Arabic_Noun_Plurality)
          c. Append Ar_Adj TO Translated_Adjectives
       END FOR
       
    6. RESULT = Arabic_Noun + " " + Join(Translated_Adjectives, " ")
    7. RETURN RESULT
```

---

## 5. خوارزمية معالجة المبني للمجهول (Passive to Active/Passive Algorithm)

تعتمد هذه الخوارزمية تحويل صيغة المبني للمجهول الإنجليزي إلى المبني للمعلوم في العربية عندما يكون الفاعل (Agent) معلوماً، أو صياغتها بأسلوب مبني للمجهول فصيح عند غياب الفاعل.

```text
Algorithm Process_Passive_Voice(Sentence):
    // Passive Pattern: Object + [Be] + Verb_Past_Participle + [By + Agent]
    
    1. Agent = Extract_Agent(Sentence) // المستخلص من عبارة "By ..."
    2. Action_Verb = Extract_Main_Verb(Sentence)
    3. Receiver = Extract_Subject(Sentence) // المفعول به في الأصل
    
    4. IF Agent IS NOT NULL THEN:
          // تحويل للمعلوم (Active Voice in Arabic)
          Arabic_Verb = Conjugate_Active(Action_Verb, Subject=Agent)
          RETURN Arabic_Verb + " " + Translate(Agent) + " " + Translate(Receiver)
          
    5. ELSE:
          // مبني للمجهول في العربية (Passive Voice)
          Arabic_Verb = Conjugate_Passive(Action_Verb, Subject=Receiver)
          // خيار استخدام صيغة "تمّ / جرى"
          IF Preferred_Style == "Modern_Standard" THEN:
             Masdar = Get_Verbal_Noun(Action_Verb)
             RETURN "تمَّ " + Masdar + " " + Translate(Receiver)
          ELSE:
             RETURN Arabic_Verb + " " + Translate(Receiver)
          END IF
    6. END IF
```

---

## 6. خوارزمية معالجة الأدوات (Articles: A, An, The Algorithm)

```text
Algorithm Process_Articles(Article, Noun, Next_Word):
    1. IF Article IN ["a", "an"] THEN:
          Arabic_Noun = Translate(Noun)
          // عدم إضافة أداة تعريف (تنكير)
          RETURN Make_Indefinite(Arabic_Noun)
          
    2. ELSE IF Article == "the" THEN:
          Arabic_Noun = Translate(Noun)
          
          IF Is_Generic_Concept(Noun) OR Is_Abstract(Noun) THEN:
             // العربية تعرف الجينات والمفاهيم المجرّدة بالـ بعكس الانكليزية أحياناً
             RETURN Add_Al_Definition(Arabic_Noun)
          ELSE IF Is_Proper_Noun(Noun) THEN:
             RETURN Arabic_Noun // عدم إضافة الـ للأعلام التي لا تقبلها
          ELSE:
             RETURN Add_Al_Definition(Arabic_Noun)
          END IF
          
    3. ELSE (Zero Article in English):
          IF Is_Plural_Generic(Noun) THEN:
             // مثل: "Dogs are loyal" -> "الكلاب وفية"
             RETURN Add_Al_Definition(Translate(Noun))
          ELSE:
             RETURN Translate(Noun)
    4. END IF
```

---

## 7. خوارزمية ترجمة الحال والظروف (Adverbs Transformation Algorithm)

تحويل الأظرف والأحوال الإنجليزية (المكونة غالباً بإضافة `-ly`) إلى الصياغات العربية المناسبة (جار ومجرور، مفعول مطلق، أو حال منصوب).

```text
Algorithm Translate_Adverb(Adverb, Verb):
    1. Base_Adjective = Extract_Base_Adjective(Adverb) // Quickly -> Quick
    2. Arabic_Adj = Translate(Base_Adjective)
    
    3. SWITCH (Target_Adverb_Style):
          CASE "Maf'ool_Mutlaq" (مفعول مطلق):
              Arabic_Masdar = Get_Verbal_Noun(Verb)
              RETURN Arabic_Masdar + " " + Arabic_Adj // مثال: ركض ركضاً سريعاً
              
          CASE "Prepositional_Phrase" (جار ومجرور):
              RETURN "بـ" + Arabic_Adj // مثال: بسرعة / ببطء
              
          CASE "Compound_Phrase" (تركيب إضافي):
              RETURN "على نحو " + Arabic_Adj // أو "بشكل ..."
              
          DEFAULT:
              RETURN Make_Hal_Accusative(Arabic_Adj) // حال منصوب: مسرعاً
    4. END SWITCH
```

---

## 8. خوارزمية ترجمة المختصرات والأسماء المركبة (Acronyms & Abbreviations Algorithm)

```text
Algorithm Process_Abbreviation(Abbrev_Text, Context):
    1. IF Abbrev_Text IN Known_Acronyms_Database THEN:
          Entry = Fetch_Acronym(Abbrev_Text)
          
          IF Entry.Has_Transliteration AND Strategy == "Phonetic" THEN:
             RETURN Entry.Transliteration // مثال: UNESCO -> يونسكو
          ELSE IF Entry.Has_Arabic_Translation THEN:
             RETURN Entry.Arabic_Translation // مثال: WHO -> منظمة الصحة العالمية
          END IF
          
    2. ELSE IF Is_Measurement_Unit(Abbrev_Text) THEN:
          RETURN Translate_Unit(Abbrev_Text) // e.g., "km" -> "كم", "ppm" -> "جزء في المليون"
          
    3. ELSE:
          // إذا كان اختصاراً غير معروف، قم بفك الضغط أولاً ثم الترجمة
          Expanded_Text = Expand_Acronym(Abbrev_Text)
          RETURN Translate_Sentence_Or_Phrase(Expanded_Text)
    4. END IF
```

---

## 9. خوارزمية التحسين والضبط الأسلوبي (Post-Processing & Polishing Algorithm)

```text
Algorithm Post_Process_Arabic_Output(Draft_Arabic_Text):
    1. Text = Remove_Redundant_Words(Draft_Arabic_Text) // إزالة التكرار اللفظي الحرفي
    2. Text = Fix_Punctuation_Spacing(Text)            // ضبط المسافات وعلامات الترقيم
    3. Text = Correct_Grammar_And_Diacritics(Text)     // التدقيق النحوي والإعرابي
    
    4. FOR EACH Connector IN Text DO:
          // ضبط أدوات الربط (مثل عدم بدء الجمل بـ "أن" بشكل خاطئ أو ضبط استعمال الواو)
          Fix_Arabic_Connectors_Rules(Connector)
       END FOR
       
    5. RETURN Text
```
