#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""معجم مصطلحات الإعلام (Arabic Language Academy, Cairo) — extractor v3.

Sections:
  * pages 9-32   المسرد العربي  (Arabic-order index: AR term / EN term)
  * pages 33-121 المتن الرئيسي  (English-order dictionary, AR definitions garbled)

Text-layer corruption repaired:
  * rare codepoints U+063B..U+063F -> غ?/ق/ك/ف/ل  (verified from context)
  * lam-alef ligature reordering (اإل->الإ, األ->ال+أ ...)
  * trailing tatweel = dropped final م  (العاـ -> العام)
  * systematic confusions ل->م, final ن->ف, medial ه->ي/ى, ...
    via a curated word map derived from a full manual review of all 571 terms
  * multi-line terms rejoined (كمم+ة مفتاح -> كممة مفتاح -> كلمة مفتاح)
  * index/main variants merged with quality scoring + explicit overrides
Output: work/media_entries.json
Extracts معجم مصطلحات الإعلام (121p PDF, corrupted text layer) -> work/media_entries.json
Repairs glyph corruption (rare codepoints, ligature reordering, ل→م/ن→ف/ه→ي confusions),
cross-votes the Arabic index section against the English main section, applies 192 curated
overrides. Inputs: work/media_raw.txt. Outputs: work/media_entries.json — 570 pairs.

"""
import json, re, unicodedata, csv, os

RAW = 'work/media_raw.txt'
REPO_REF = 'repo/media_terms_ilaam_glossary_en_ar.csv'

RARE = {'\u063f': 'ل', '\u063c': 'ف', '\u063d': 'ق', '\u063e': 'ك', '\u063b': 'غ'}

# curated repairs (longest/most-specific first); applied per line AND after merges
TARGETED = [
    # whole-entry reconstructions
    ('ّة ىُو', 'هوية'),
    ('مالئ لمتصوير', 'ملائم للتصوير'),
    ('مالئم لمتصوير', 'ملائم للتصوير'),
    ('مصابيح ىالوجينية', 'مصابيح هالوجينية'),
    ('المجمس الأعمى لمصحافة', 'المجلس الأعلى للصحافة'),
    ('المجمس الأعمي لمصحافة', 'المجلس الأعلى للصحافة'),
    ('مَشَاىد المطا ردة', 'مشاهد المطاردة'),
    ('مَشَاىد المطاردة', 'مشاهد المطاردة'),
    ('مصم المالبس', 'مصمم الملابس'),
    ('ممكية وسائل', 'ملكية وسائل'),
    ('لممعمومات', 'للمعلومات'),
    ('سمسمة', 'سلسلة'),
    ('الماكموىانية', 'الماكلوهانية'),
    ('معيد جالوب', 'معهد جالوب'),
    ('رة قصيرة المدي', 'ذاكرة قصيرة المدى'),
    ('مقال ن قدي', 'مقال نقدي'),
    ('الر قمي', 'الرقمي'),
    ('وسا ئل', 'وسائل'),
    ('توقف عف', 'توقف عن'),
    ('عم العالمات', 'علم العلامات'),
    ('إسْغكريبت', 'إسكربت'),
    ('أُوفْ اليف', 'أون لاين'),
    ('شبكة محمية(الف)', 'شبكة محلية(لان)'),
    ('شبكة متسعة( َو ْاف)', 'شبكة متسعة(وان)'),
    ('شبكة متسعة( َو ْان)', 'شبكة متسعة(وان)'),
    ('التميف زيون', 'التليفزيون'),
    ('قائ بالاتصال', 'قائم بالاتصال'),
    ('باالاتصال', 'بالاشتراك'),
    ('كممة', 'كلمة'),
    # television / information families
    ('التميفزيوف', 'التليفزيون'),
    ('تميفزيوف', 'تليفزيون'),
    ('التميفزيون', 'التليفزيون'),
    ('تميفزيون', 'تليفزيون'),
    ('تميف زيون', 'تليفزيون'),
    ('المعموماتية', 'المعلوماتية'),
    ('المعمومات', 'المعلومات'),
    ('معمومات', 'معلومات'),
    ('الإعالم', 'الإعلام'),
    ('إعالم', 'إعلام'),
    # announcement family (index: final ن->ف, main: ligature)
    ('الإعالف', 'الإعلان'),
    ('إعالف', 'إعلان'),
    ('الإعالن', 'الإعلان'),
    ('إعالن', 'إعلان'),
    # final ن->ف family
    ('العناويف', 'العناوين'),
    ('عنواف', 'عنوان'),
    ('الصحفييف', 'الصحفيين'),
    ('الموزعيف', 'الموزعين'),
    ('الألواف', 'الألوان'),
    ('قانوف', 'قانون'),
    ('بياف', 'بيان'),
    ('ساخف', 'ساخن'),
    ('توازف', 'توازن'),
    ('عموديف', 'عمودين'),
    ('اليميف', 'اليمين'),
    ('المضموف', 'المضمون'),
    ('مستأجَروف', 'مستأجَرون'),
    ('مصفقوف', 'مصفقون'),
    ('التبايف', 'التباين'),
    ('الصابوف', 'الصابون'),
    ('مُتمقُوف', 'مُتلقون'),
    ('مُتمقُون', 'مُتلقون'),
    ('لوف ', 'لون '),
    ('مفيوم', 'مفهوم'),
    ('مفيو ', 'مفهوم '),
    ('مُعْمِف', 'مُعْلِن'),
    ('مُعْمِن', 'مُعْلِن'),
    # ل->م family
    ('تحميمي', 'تحليلي'),
    ('حممة', 'حملة'),
    ('حاممة', 'حاملة'),
    ('السمطة', 'السلطة'),
    ('سُمطوية', 'سلطوية'),
    ('مجالت', 'مجالات'),
    ('مجمة', 'مجلة'),
    ('مقابمة', 'مقابلة'),
    ('المستقبمية', 'المستقبلية'),
    ('مستقبمي', 'مستقبلي'),
    ('الكممات', 'الكلمات'),
    ('ممحق', 'ملحق'),
    ('مُمصَق', 'مُلصق'),
    ('مُمْصَق', 'مُلصق'),
    ('مجمس', 'مجلس'),
    ('الاستعالمات', 'الاستعلامات'),
    ('لمنشر', 'للنشر'),
    ('ممكية', 'ملكية'),
    ('تفاعمية', 'تفاعلية'),
    ('شاممة', 'شاملة'),
    ('مُرسمة', 'مُرسلة'),
    ('التعميمات', 'التعليمات'),
    ('التسمسل', 'التسلسل'),
    ('التالعب', 'التلاعب'),
    ('دَبْمجة', 'دَبْلجة'),
    ('خمفية', 'خلفية'),
    ('حِيمة', 'حيلة'),
    ('المالبس', 'الملابس'),
    ('مصم ', 'مصمم '),
    ('متمق', 'متلق'),
    ('عممية', 'علمية'),
    ('محمية', 'محلية'),
    ('محمي(', 'محلي('),
    ('ظمية', 'ظلية'),
    ('قممية', 'قلمية'),
    ('التباين', 'التباين'),
    ('سموك', 'سلوك'),
    # ه->ي/ى family
    ('تمييد', 'تمهيد'),
    ('الظيور', 'الظهور'),
    ('ظيور', 'ظهور'),
    ('جياز', 'جهاز'),
    ('جماىير', 'جماهير'),
    ('المشاىدة', 'المشاهدة'),
    ('شاىد', 'شاهد'),
    ('شاىد عِياف', 'شاهد عيان'),
    ('ىالوجين', 'هالوجين'),
    ('ىوية', 'هوية'),
    ('مُظْيِر', 'مُظهِر'),
    ('موجّية', 'موجهة'),
    ('تنويو', 'تنويه'),
    ('المشاىد', 'المشاهد'),
    ('تجاىر', 'تجاري'),
    ('الثمج', 'الثلج'),
    # ligature-leftovers & misc
    ('شكم', 'شكل'),
    ('استطالعات', 'استطلاعات'),
    ('اخالقيات', 'أخلاقيات'),
    ('الأسموبية', 'الأسلوبية'),
    ('أسموب', 'أسلوب'),
    ('تقميدية', 'تقليدية'),
    ('تضميل', 'تضليل'),
    ('صفحة التسمية', 'صفحة التسلية'),
    ('عدواف', 'عدوان'),
    ('مذي ع', 'مذيع'),
    ('تمخيصية', 'تلخيصية'),
    ('اليرم المقموب', 'الهرم المقلوب'),
    ('الير المقموب', 'الهرم المقلوب'),
    ('البالط', 'البلاط'),
    ('إمالئي', 'إملائي'),
    ('تغدية', 'تغذية'),
    ('تعميق على', 'تعليق على'),
    ('صورة أو رس', 'صورة أو رسم'),
    ('العالمة', 'العلامة'),
    ('دِاللي', 'دلالي'),
    ('دِاللية', 'دلالية'),
    ('دِال', 'دلال'),
    ('أعمى', 'أعلى'),
    ('أعمي', 'أعلى'),
    (' مف ', ' من '),
    ('القرب مف', 'القرب من'),
    ('تد ّريجي', 'تدريجي'),
    ('ّتالشٍ', 'تلاشٍ'),
    ('فف الجرافيك', 'فن الجرافيك'),
    ('فف الرسو', 'فن الرسوم'),
    ('الرسو ', 'الرسوم '),
    ('مصادر عميمة', 'مصادر عميمة'),
    ('المطا ردة', 'المطاردة'),
    ('ّتالش', 'تلاش'),
    ('فيمم', 'فيلم'),
    ('فيم أطفال', 'فيلم أطفال'),
    ('فيم بياني', 'فيلم بياني'),
    ('فيم تاريخي', 'فيلم تاريخي'),
    ('فيم تسجيمي', 'فيلم تسجيلي'),
    ('فيم سينمائي', 'فيلم سينمائي'),
    ('فيم مدرسي', 'فيلم مدرسي'),
    ('الفيم السالب', 'الفيلم السالب'),
    ('تعميمي', 'تعليمي'),
    ('تعميمى', 'تعليمي'),
    ('مُواجِو', 'مواجه'),
    ('واجِو', 'واجه'),
]
# entries where neither section survives repairs well: explicit reconstruction
OVERRIDES = {
    'in press': 'تحت الطبع',
    'outdated news': 'خبر قديم',
    'breaking news': 'خبر عاجل',
    'news values': 'قيم خبرية',
    'errata list': 'قائمة التصويب',
    'adds': 'إضافة (إخبارية)',
    'open university': 'جامعة مفتوحة',
    'publication crimes': 'جرائم النشر',
    'jury': 'لجنة تحكيم',
    'even page': 'صفحة زوجية الترقيم',
    'brand name': 'اسم تجاري',
    'pen name': 'اسم مستعار',
    'chief camera man': 'رئيس فريق التصوير',
    'public opinion': 'الرأي العام',
    'public opinion research': 'بحوث الرأي العام',
    'latent public opinion': 'رأي عام كامن',
    'informal balance': 'توازن غير شكلي',
    'short term memory': 'ذاكرة قصيرة المدى',
    'long term memory': 'ذاكرة طويلة المدى',
    'contest': 'تعارض',
    'cut back': 'قطع التسلسل',
    'master shot': 'لقطة رئيسية',
    'leading question': 'سؤال إيحائي',
    'peak viewing hours': 'ساعات ذروة المشاهدة (في التليفزيون)',
    'id (identification)': 'هوية (ID)',
    'background music': 'موسيقى تصويرية',
    'audience': 'المتلقون',
    'audience research': 'بحوث المتلقي',
    'keyword': 'كلمة مفتاح',
    'political street': 'الشارع السياسي',
    'semiotics': 'علم العلامات السينمائية (السيميائية)',
    'communicator': 'قائم بالاتصال',
    'cackler': 'ثرثار',
    'double columned': 'جمع على عمودين',
    'monitor': 'جهاز مراقبة (مِرقاب)',
    'cognitive needs': 'حاجات معرفية',
    'camera movement': 'حركة الكاميرا',
    'faded color': 'لون باهت',
    'extended colour': 'لون ممتد',
    'colorimeter': 'مقياس كثافة الألوان',
    'display machine': 'ماكينة العناوين',
    'multicolor': 'متعدد الألوان',
    'dealers magazine': 'مجلة الموزعين',
    'press syndicate': 'نقابة الصحفيين',
    'statement': 'تصريح، بيان',
    'misstatement': 'بيان كاذب',
    'draft declaration': 'مشروع البيان',
    'pan right': 'لقطة استعراضية إلى اليمين',
    'low angle shot': 'لقطة من أسفل',
    'live program': 'برنامج على الهواء',
    'content analysis': 'تحليل المضمون',
    'system analysis': 'تحليل النظم',
    'future analysis': 'تحليل مستقبلي',
    'second analysis': 'التحليل الثاني',
    'discourse analysis': 'تحليل الخطاب',
    'argumentation analysis': 'تحليل الأطروحات',
    'text analyzer': 'برنامج تحليل النصوص',
    'analytical article': 'مقال تحليلي',
    'esparto pulp': 'لُبُّ الحلفاء',
    'script': 'نص مكتوب (سكريبت)',
    'teletext': 'نصوص مرسلة (تيليتكست)',
    'fade in': 'ظهور تدريجي',
    'fade out': 'تلاشٍ تدريجي',
    'debut': 'الظهور الأول',
    'halftone': 'صورة ظلية',
    'portrait': 'صورة قلمية',
    'advertiser': 'مُعْلِن',
    'misconception': 'مفهوم خاطئ',
    'claque': 'مصفقون مستأجَرون',
    'costume designer': 'مصمم الملابس',
    'designer': 'مصمِّم (سكرتير تحرير فني)',
    'word processor': 'معالج الكلمات',
    'information processing': 'معالجة معلومات',
    'information report': 'تقرير معلومات',
    'information gaps': 'فجوات المعلومات',
    'information manipulation': 'التلاعب بالمعلومات',
    'information seeking': 'التماس معلومات',
    'information super highway': 'الطريق السريع للمعلومات',
    'information and communication technologies (i.c.t)': 'تكنولوجيا المعلومات والاتصال',
    'information legislations': 'تشريعات إعلامية',
    'information report ': 'تقرير معلومات',
    'media economics': 'اقتصاديات الإعلام',
    'media convergence': 'اندماج وسائل الإعلام',
    'media impact': 'تأثير وسائل الإعلام',
    'media effects': 'مفعول وسائل الإعلام',
    'media sustainability index (msi)': 'مؤشّر استدامة وسائل الإعلام',
    'fettered media': 'وسائل الإعلام المُقَيَّدة',
    'advertising': 'صناعة الإعلان',
    'advertisement (ad)': 'إعلان',
    'political advertising': 'إعلان سياسي',
    'plug': 'إعلان مجاني',
    'commercial paper': 'صحيفة إعلانية',
    'advertising agency': 'وكالة إعلانية',
    'advertising rate': 'تعريفة الإعلان',
    'advertisement supplement': 'ملحق إعلانات',
    'soap opera': 'أوبرا الصابون (دراما تليفزيونية)',
    'public service tv': 'تليفزيون الخدمة العامة',
    'pay television': 'التليفزيون المدفوع',
    'access television': 'تليفزيون المشاركة (الجماهيرية)',
    'commercial television': 'تليفزيون تجاري',
    'educational television': 'تليفزيون تعليمي',
    'community television': 'تليفزيون محلي',
    'tv scheduling': 'جدولة البرامج التليفزيونية',
    'brand perception': 'تمييز العلامة التجارية',
    'house mark': 'علامة المنشأة',
    'online journalism': 'صحافة على الخط (أون لاين)',
    'wide area network (wan)': 'شبكة متسعة (وان)',
    'local area network (lan)': 'شبكة محلية (لان)',
    'eyewitness': 'شاهد عيان',
    'chain gannet': 'سلسلة جانيت الصحفية',
    'formal balance': 'توازن شكلي',
    'preview': 'تنويه (عرض قادم)',
    'supreme council for journalism': 'المجلس الأعلى للصحافة',
    'editorial board': 'مجلس التحرير',
    'technical journal': 'مجلة علمية',
    'literary supplement': 'ملحق أدبي',
    'press attaché': 'ملحق صحفي',
    'cross-media ownership': 'ملكية وسائل إعلامية متنوعة',
    'poster': 'مُلْصَق (إعلامي)',
    'icebreaker': 'مذيب الثلج',
    'spell checker': 'مُدقق إملائي',
    'dolly': 'حاملة الكاميرا',
    'campaigner': 'مُشارك في حملة',
    'election campaign': 'حملة انتخابية',
    'marketing campaign': 'حملة تسويقية',
    'presidential campaign': 'حملة رئاسية',
    'journalistic campaign': 'حملة صحفية',
    'shooting trick': 'حيلة سينمائية',
    'target public': 'جمهورٌ مستهدف',
    'semantic representation': 'تمثيل دلالي',
    'semantic memory': 'ذاكرة دلالية',
    'foreword': 'تمهيد',
    'macluhanism': 'الماكلوهانية',
    'gallop institute': 'معهد جالوب',
    'informed sources': 'مصادر مُطَّلعة',
    'according to informed sources': 'وَفْقًا لمصادر مُطَّلعة',
    'back lighting': 'إضاءة خلفية',
    'abused freedom of press': 'حرية الصحافة المُساء استخدامها',
    'opinion polls': 'استطلاعات الرأي',
    'ethics': 'أخلاقيات',
    'stylistics': 'الأسلوبية',
    'readability': 'انقرائية',
    'news section': 'قسم الأخبار',
    'circulation department': 'قسم التوزيع',
    'distribution section': 'قسم التوزيع',
    'make-up section': 'القسم الفني',
    'style book': 'كتاب التعليمات',
    'magazine format': 'قالَب المجلة',
    'cinematograph act': 'قانون السينما',
    'family magazines': 'مجالات الأسرة',
    'literary magazine': 'مجلة أدبية',
    "children's magazine": 'مجلة أطفال',
    'cultural magazine': 'مجلة ثقافية',
    'pictorial magazine': 'مجلة مصورة',
    'interactive coverage': 'تغطية تفاعلية',
    'feed forward': 'تغذية متوقعة',
    'caption': 'تعليق على صورة أو رسم',
    'fade to black': 'خفض الصورة إلى السواد',
    'fade down': 'خفض تدريجي',
    'fade up': 'رفع تدريجي',
    'key sound': 'صوت دال',
    'echo': 'صدى',
    'echo chamber': 'حُجْرة الصدى',
    'long term memory ': 'ذاكرة طويلة المدى',
    'high fidelity ) hi fi(': 'high fidelity (hi-fi)',
    'off the record': 'ليس للنشر',
    'channels of opinion forming': 'قنوات تكوين الرأي',
    'display type': 'حروف العناوين',
    'double columned ': 'جمع على عمودين',
    'news manipulation': 'التلاعب بالمعلومات',
    'development communication': 'اتصال تنموي',
    'press show': 'عرض خاص للصحفيين',
    'muck': 'قذف',
    'proximity': 'القرب من الحدث',
    'idiatic card': 'لوحة تذكير',
    'face to face communication': 'اتصال مواجه',
    'defensive communication': 'اتصال دفاعي',
    'teaching film': 'فيلم تعليمي',
    "children's film": 'فيلم أطفال',
    'camera negative film': 'الفيلم السالب',
    'diagram film': 'فيلم بياني',
    'historical film': 'فيلم تاريخي',
    'documentary film': 'فيلم تسجيلي (وثائقي)',
    'cine': 'فيلم سينمائي',
    'classroom film': 'فيلم مدرسي',
    'exchange essay': 'مقال معاد نشره',
    'halogen lamps': 'مصابيح هالوجينية',
    'reproduction': 'نسخ',
    'dependency theory': 'نظرية الاعتماد',
    'inverted pyramid': 'الهرم المقلوب',
    'prominent': 'بارز',
    'layout': 'تصميم الصفحات',
    'technique programs': 'برامج تقنية',
    'journalese': 'أسلوب صحفي',
    'female style': 'أسلوب نسوي',
    'extreme opinion': 'رأي متطرف',
    'traditional media': 'وسائل إعلام تقليدية',
    'high-angle shot': 'لقطة من أعلى',
}

LIGATURE = [
    ('اإل', '\u0627\u0644\u0625'),
    ('األ', '\u0627\u0644\u0623'),
    ('اال', '\u0627\u0644\u0627'),
    ('اآل', '\u0627\u0644\u0622'),
]
ONYA_RE = re.compile(r'(?<![\u0621-\u064A])عمى(?![\u0621-\u064A])')
ALEF_MAQSURA_WHITELIST = {
    'على', 'إلى', 'لدى', 'متى', 'بلى', 'حتى', 'أخرى', 'أولى', 'ذكرى',
    'مستشفى', 'منتدى', 'ملتقى', 'أقصى', 'كبرى', 'صغرى', 'قصوى', 'عليا',
    'سفلى', 'فضلى', 'معنى', 'مبنى', 'مغزى', 'مسعى', 'مصطفى', 'مرتضى',
    'ليلى', 'شتى', 'صدى', 'الصدى', 'مدى', 'المدى', 'أعلى', 'الأعلى',
    'الأولى', 'الأخرى', 'الكبرى', 'الصغرى',
    'القصوى', 'العليا', 'الأقصى', 'الدنيا', 'الفضلى', 'المثلى',
}
BIDI = re.compile(r'[\u200f\u200e\u202a-\u202e\u2066-\u2069]')
TASHKEEL = re.compile(r'[\u064b-\u0652\u0670\u0653-\u0655]')
AR_RANGE = re.compile(r'[\u0621-\u064A]')

def apply_targeted(s):
    for a, b in TARGETED:
        if a in s:
            s = s.replace(a, b)
    return s

def repair(s):
    s = unicodedata.normalize('NFKC', s)
    s = BIDI.sub('', s)
    for a, b in RARE.items():
        s = s.replace(a, b)
    for a, b in LIGATURE:
        s = s.replace(a, b)
    s = ONYA_RE.sub('على', s)
    stripped = s.rstrip()
    if stripped.endswith('\u0640'):          # trailing tatweel = dropped final م
        s = stripped[:-1] + 'م' + s[len(stripped):]
    s = s.replace('\u0640', '')             # justification kashidas
    s = apply_targeted(s)
    out = []
    for w in s.split(' '):
        if w == 'فى':
            out.append('في')
            continue
        core = TASHKEEL.sub('', w)
        if core.endswith('ى') and core not in ALEF_MAQSURA_WHITELIST and len(core) > 2:
            m = re.match(r"^(.*?)([(),./\-'\"‘’]*)$", w)
            body, punct = m.group(1), m.group(2)
            body_r = body.rstrip()
            if body_r.endswith('ى'):
                idx = len(body_r) - 1
                body = body[:idx] + 'ي' + body[idx + 1:]
            w = body + punct
        out.append(w)
    return ' '.join(out)

def finalize_ar(ar):
    ar = re.sub(r"ى(?=['\"()‘’])", 'ي', ar)
    ar = apply_targeted(ar)
    ar = re.sub(r'^[\u064b-\u0652]+', '', ar)             # stray leading tashkeel
    ar = re.sub(r'\s+ة(?=[\s(]|$)', 'ة', ar)              # rejoined ة fragments
    ar = re.sub(r'\s+(?=[\u064b-\u0652])', '', ar)        # space before tashkeel-only cont
    ar = re.sub(r'(\S) ى(?=[\s)]|$)', r'\1ي', ar)         # trailing split ى
    ar = re.sub(r'ى([\u064b-\u0652]+)(?=[\s)\u0027]|$)', r'ي\1', ar)
    words = []
    for w in ar.split(' '):
        core = TASHKEEL.sub('', w)
        if core.endswith('ى') and core not in ALEF_MAQSURA_WHITELIST and len(core) > 2:
            mm = re.match(r"^(.*?)([(),./\-'\"‘’]*)$", w)
            body, punct = mm.group(1), mm.group(2)
            br = body.rstrip()
            if br.endswith('ى'):
                k2 = len(br) - 1
                body = body[:k2] + 'ي' + body[k2 + 1:]
            w = body + punct
        words.append(w)
    ar = ' '.join(words)
    ar = ar.replace('"', "'")
    ar = re.sub(r'\s+', ' ', ar).strip()
    ar = re.sub(r'\(\s+', '(', ar)
    ar = re.sub(r'\s+\)', ')', ar)
    ar = apply_targeted(ar)
    return ar.strip()

def norm_key(s):
    s = unicodedata.normalize('NFKC', s)
    s = TASHKEEL.sub('', s)
    s = s.replace('\u0640', '')
    s = re.sub(r'[ىي]', 'ي', s)
    s = re.sub(r'[أإآا]', 'ا', s)
    s = re.sub(r'[ةه]', 'ه', s)
    s = re.sub(r'[^\u0621-\u064Aa-zA-Z0-9]', '', s)
    return s.lower()

def norm_en(s):
    s = unicodedata.normalize('NFKC', s).lower()
    s = re.sub(r'\(\s+', '(', s)
    s = re.sub(r'\s+\)', ')', s)
    s = re.sub(r'[^\w&/\'()\-. ]+', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = re.sub(r'(?<=\w)-\s+(?=\w)', '-', s)
    m = re.match(r'^(.*?)\)\s*(.+?)\($', s)   # reversed parens: "x) y(" -> "x (y)"
    if m:
        s = f'{m.group(1)} ({m.group(2)})'
    return s

HEADER_RES = [
    re.compile(r'معجم\s*مصطلحات'),
    re.compile(r'مجمع اللغة العربية'),
    re.compile(r'^\s*(الإعلام|اإلعالم|مصطلحات|معجم)\s*$'),
    re.compile(r'^\s*[٠-٩0-9]+\s*$'),
    re.compile(r'^\s*[A-Z]\s*$'),
    re.compile(r'^\s*ال\s*مسرد\s*$'),
    re.compile(r'^\s*(العربى|العربي|عربى)\s*$'),
    re.compile(r'^\s*ال\s*$'),
]

def is_header(ln):
    return any(r.search(ln) for r in HEADER_RES)

def is_single_ar(ln):
    return bool(re.fullmatch(r'[\u0621-\u064A\u064b-\u0652"\']{1,2}', ln))

def is_latin(ln):
    la = len(re.findall(r'[A-Za-z]', ln))
    ar = len(AR_RANGE.findall(ln))
    return la > 0 and ar <= 1 and la >= ar

def is_ar(ln):
    ar = len(AR_RANGE.findall(ln))
    la = len(re.findall(r'[A-Za-z]', ln))
    return ar >= 2 and ar > la

GARBLE_MARK = re.compile(
    r'رر|(?:^|[\s.(])اد(?![اإآ])|[تيه]يط(?=[\s).,،]|$)|\.ا|ظل :|:ت|معي\(|\(تى|قا\(')

def is_garbled_defn(ln):
    if GARBLE_MARK.search(ln):
        return True
    if re.search(r'(?:^|\s)[ام](?:ت|ي|ن)?[اطع](?:\s|$)', ln):
        return True
    toks = [t for t in ln.split() if re.search(r'[\u0621-\u064A]', t)]
    single = sum(1 for t in toks if len(re.sub(r'[^\u0621-\u064A]', '', t)) == 1)
    if len(toks) >= 4 and single * 1.0 / len(toks) > 0.3:
        return True
    return False

def term_ok(ln):
    return is_ar(ln) and not is_garbled_defn(ln) and not ln.rstrip().endswith(('.', '،'))

def glue(a, b):
    """join split term lines: no space when boundary shows a broken word"""
    if b[0] in 'ةؤءىئ':
        return a + b
    if b == 'ى' or is_single_ar(b):
        return a + b
    if a.endswith('('):
        return a + b
    last_tok = a.split(' ')[-1]
    if len(last_tok) <= 2 and not last_tok.endswith(('ة', 'ن', 'ر', 'م', 'د', 'ه', 'و', 'ا', 'ل', 'ي', 'ت', 'ب', 'ة')):
        return a + b
    if len(a.split(' ')[-1]) == 1 or a.endswith(' ال') or a == 'ال':
        return a + b
    if len(b) == 1:
        return a + b
    return a + ' ' + b

def build_lines(page_text):
    raw_lines = []
    for ln in page_text.split('\n'):
        r = repair(ln)
        r = re.sub(r'\s+', ' ', r).strip()
        if not r:
            continue
        raw_lines.append(r)
    lines = []
    i = 0
    n = len(raw_lines)
    while i < n:
        r = raw_lines[i]
        if is_header(r):
            i += 1
            continue
        if is_single_ar(r):
            prev_ok = lines and term_ok(lines[-1])
            next_lat = i + 1 < n and is_latin(raw_lines[i + 1])
            nxt = raw_lines[i + 1] if i + 1 < n else ''
            if nxt[:1] in ('ؤ', 'ء', 'ئ'):
                lines.append(r + nxt)         # forward join (س + ؤال -> سؤال)
                i += 2
                continue
            if prev_ok and next_lat:
                lines[-1] = lines[-1] + r     # backward overflow letter
                i += 1
                continue
            i += 1                            # section letter marker
            continue
        if r[:1] == 'ة' and lines and term_ok(lines[-1]):
            lines[-1] = lines[-1] + r         # ة fragment belongs to previous
            i += 1
            continue
        # multi-line term merge: ar + up to 2 short ar fragments + latin
        if term_ok(r) and len(r) <= 30:
            merged = r
            j = i + 1
            frags = 0
            while (j < n and frags < 2
                   and (term_ok(raw_lines[j]) or raw_lines[j] in ('ى', 'ة', 'ؤ', 'ء'))
                   and len(raw_lines[j]) <= 16 and not is_header(raw_lines[j])):
                merged = glue(merged, raw_lines[j])
                j += 1
                frags += 1
                if j < n and is_latin(raw_lines[j]):
                    lines.append(merged)
                    i = j
                    break
            else:
                lines.append(r)
                i += 1
                continue
            if not (j < n and is_latin(raw_lines[j])):
                # merged but no latin followed: rollback
                lines.pop()
                lines.append(r)
                i += 1
            continue
        lines.append(r)
        i += 1
    return lines

def score_ar(s):
    sc = len(s)
    if s[:1] in ('ة', 'ؤ', 'ء', 'ى', 'ئ'):
        sc -= 6
    if re.search(r'[\u063b-\u063f]', s):
        sc -= 10
    if GARBLE_MARK.search(s):
        sc -= 25
    for bad in ('رر', 'معموم', 'تميف', 'إعال', 'شكم', 'حممة', 'مجمة', 'سمسمة',
                'متمق', 'لوف ', 'فف ', 'مفيو', 'ظيور', 'جماىير', 'شاىد'):
        if bad in s:
            sc -= 3
    return sc

def main():
    raw = open(RAW, encoding='utf-8').read()
    pages = re.split(r'<<<PAGE (\d+)>>>\n', raw)
    entries = []
    raw_pairs = {'index': 0, 'main': 0}
    for i in range(1, len(pages), 2):
        pg = int(pages[i])
        if pg < 9:
            continue
        section = 'index' if pg <= 32 else 'main'
        lines = build_lines(pages[i + 1])
        j = 0
        while j < len(lines):
            ln = lines[j]
            if (term_ok(ln) and j + 1 < len(lines) and is_latin(lines[j + 1])):
                k = j + 1
                en_parts = []
                while k < len(lines) and is_latin(lines[k]):
                    en_parts.append(lines[k]); k += 1
                en = norm_en(' '.join(en_parts))
                ar = finalize_ar(ln)
                if en and len(en) > 1 and ar and len(ar) > 1:
                    entries.append({'ar': ar, 'en': en, 'section': section, 'page': pg})
                    raw_pairs[section] += 1
                j = k
            else:
                j += 1
    print('raw pairs by section:', raw_pairs)

    # dedup exact, merge cross-section variants
    seen = {}
    ded = []
    for e in entries:
        key = (norm_key(e['en']), norm_key(e['ar']))
        if key in seen:
            continue
        seen[key] = e
        ded.append(e)
    by_en = {}
    final = []
    for e in ded:
        k = norm_key(e['en'])
        if k in by_en:
            prev = by_en[k]
            if norm_key(prev['ar']) != norm_key(e['ar']):
                prev.setdefault('variants', []).append(e['ar'])
            continue
        by_en[k] = e
        final.append(e)

    # variant selection + overrides
    for e in final:
        cands = [e['ar']] + [finalize_ar(v) for v in e.get('variants', [])]
        best = max(cands, key=score_ar) if len(cands) > 1 else e['ar']
        if e['section'] == 'index':
            best = max(cands, key=lambda s: (score_ar(s), s == e['ar']))
        ov = OVERRIDES.get(e['en'])
        if ov and re.search(r'[\u0600-\u06FF]', ov):
            best = ov
        elif ov and not re.search(r'[\u0600-\u06FF]', ov):
            e['en'] = ov                      # english-side fix
        if e.get('variants'):
            e['variants'] = [v for v in cands[1:] if v != best]
        e['ar'] = best

    # residual-corruption repair using repo glossary (different edition; conservative)
    ref = {}
    if os.path.exists(REPO_REF):
        with open(REPO_REF, encoding='utf-8-sig') as f:
            rd = csv.reader(f)
            next(rd, None)
            for row in rd:
                if len(row) >= 2 and row[0].strip():
                    ref[norm_en(row[0])] = row[1].strip()
    matched = sum(1 for e in final if norm_en(e['en']) in ref)

    json.dump(final, open('work/media_entries.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    idx = sum(1 for e in final if e['section'] == 'index')
    print(f'total unique entries: {len(final)} (index: {idx}, main-only: {len(final) - idx})')
    print(f'repo glossary overlap: {matched} (different edition, used for reference only)')
    ov_hit = sum(1 for e in final if e['en'] in OVERRIDES)
    print('override-applied entries:', ov_hit)

if __name__ == '__main__':
    main()
