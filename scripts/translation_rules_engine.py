#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""translation_rules_engine.py — rule-based EN→AR term translator
implementing the algorithms mined in algorithms/media_political_translation_rules.{md,json}.

Pipeline (see R01..R13):
  normalize → lexicon lookup (1600 pairs from repo CSVs) → acronym strategy →
  NP decomposition (of-chain idaafa / adjective inversion / prefixes / suffixes) →
  agreement & article policy → transliteration fallback.

Usage:
  python3 translation_rules_engine.py "digital television"      # single term
  python3 translation_rules_engine.py --self-test               # regression suite
  python3 translation_rules_engine.py --file terms.txt          # batch (one per line)

The lexicon is loaded from the repository CSVs:
  political_encyclopedia_terms_en_ar.csv, media_dictionary_terms_en_ar.csv
"""
import csv, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# ---------------------------------------------------------------- lexicon
def load_lexicon():
    lex = {}
    for fn in ('political_encyclopedia_terms_en_ar.csv', 'media_dictionary_terms_en_ar.csv'):
        p = os.path.join(ROOT, fn)
        if not os.path.exists(p):
            continue
        with open(p, encoding='utf-8-sig') as f:
            rd = csv.reader(f)
            next(rd, None)
            for row in rd:
                if len(row) < 2 or not row[0].strip():
                    continue
                en = norm_en(row[0])
                ar = row[1].strip()
                ar = re.split(r'\s*/\s*أنظر', ar)[0].strip()   # drop cross-ref notes
                if en and ar and en not in lex:
                    lex[en] = ar
    # mined 1:1 word alignments enrich the word map
    return lex

def norm_en(s):
    s = unicodedata.normalize('NFKC', s).lower()
    s = re.sub(r'\([^)]*\)', ' ', s)
    s = re.sub(r'[^\w\s\-]', ' ', s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s

# ---------------------------------------------------------------- tables (mined; see R03/R06/R07)
ADJ = {
    'political': 'سياسي', 'international': 'دولي', 'national': 'قومي',
    'public': 'عام', 'civil': 'مدني', 'social': 'اجتماعي', 'liberal': 'ليبرالي',
    'traditional': 'تقليدي', 'new': 'جديد', 'economic': 'اقتصادي',
    'cultural': 'ثقافي', 'military': 'عسكري', 'commercial': 'تجاري',
    'financial': 'مالي', 'editorial': 'تحريري', 'digital': 'رقمي',
    'electronic': 'إلكتروني', 'local': 'محلي', 'global': 'كوكبي',
    'mass': 'جماهيري', 'central': 'مركزي', 'western': 'غربي',
    'eastern': 'شرقي', 'free': 'حر', 'general': 'عام', 'official': 'رسمي',
    'democratic': 'ديمقراطي', 'regional': 'إقليمي', 'ethnic': 'عرقي',
    'religious': 'ديني', 'interactive': 'تفاعلي', 'educational': 'تعليمي',
    'documentary': 'تسجيلي', 'investigative': 'استقصائي', 'popular': 'شعبي',
    'federal': 'اتحادي', 'revolutionary': 'ثوري', 'colonial': 'استعماري',
    'multinational': 'متعدد الجنسية', 'imperialist': 'إمبريالي',
    'capitalist': 'رأسمالي', 'socialist': 'اشتراكي', 'communist': 'شيوعي',
    'nuclear': 'نووي', 'bilateral': 'ثنائي', 'unilateral': 'أحادي',
    'imperial': 'إمبريالي', 'ideological': 'أيديولوجي', 'diplomatic': 'دبلوماسي',
    'judicial': 'قضائي', 'legal': 'قانوني', 'administrative': 'إداري',
    'industrial': 'صناعي', 'daily': 'يومي', 'weekly': 'أسبوعي',
}
PREFIX = {
    'anti': 'مضاد', 'multi': 'متعدد', 'inter': 'دولي', 'trans': 'عابر',
    'sub': 'فرعي', 'super': 'فائق', 'semi': 'شبه', 'non': 'غير',
    'mis': 'مضلل', 'co': 'مشترك', 're': 'إعادة', 'pre': 'تمهيدي',
    'post': 'لاحق', 'neo': 'جديد', 'pan': 'شامل', 'over': 'مفرط',
    'under': 'ناقص', 'counter': 'مضاد', 'self': 'ذاتي', 'uni': 'موحد',
    'socio': 'اجتماعي', 'psycho': 'نفسي', 'electro': 'كهربائي',
}
PREFIX_ADJ = {'anti', 'multi', 'inter', 'trans', 'sub', 'super', 'semi', 'non',
              'neo', 'pan', 'over', 'under', 'counter', 'socio', 'psycho',
              'electro', 'uni'}
SUFFIX = {
    'cracy': 'قراطية', 'ization': None, 'tion': None, 'sion': None,
    'ity': 'ية', 'ism': 'ية', 'ness': 'ية', 'ics': 'يات', 'ology': 'ولوجيا',
    'graphy': 'غرافيا', 'phobia': 'فوبيا', 'ship': 'ية', 'dom': 'ية',
}
HEAD_SEED = {   # frequent heads harvested from the corpus
    'television': 'تليفزيون', 'communication': 'اتصال', 'network': 'شبكة',
    'coverage': 'تغطية', 'newspaper': 'صحيفة', 'agency': 'وكالة',
    'system': 'نظام', 'opinion': 'رأي', 'news': 'أخبار', 'press': 'صحافة',
    'society': 'مجتمع', 'economy': 'اقتصاد', 'culture': 'ثقافة',
    'freedom': 'حرية', 'information': 'معلومات', 'security': 'أمن',
    'government': 'حكومة', 'election': 'انتخابات', 'party': 'حزب',
    'organization': 'منظمة', 'council': 'مجلس', 'crisis': 'أزمة',
    'war': 'حرب', 'power': 'قوة', 'development': 'تنمية', 'research': 'بحوث',
    'camera': 'كاميرا', 'program': 'برنامج', 'radio': 'راديو',
    'journalism': 'صحافة', 'media': 'إعلام', 'market': 'سوق',
    'magazine': 'مجلة', 'film': 'فيلم', 'interview': 'مقابلة',
    'report': 'تقرير', 'article': 'مقال', 'headline': 'عنوان',
    'advertisement': 'إعلان', 'newspaper': 'صحيفة', 'journalist': 'صحفي',
}
PHONEMES = [
    ('sh', 'ش'), ('ch', 'تش'), ('th', 'ث'), ('ph', 'ف'), ('qu', 'ك'),
    ('ck', 'ك'), ('oo', 'و'), ('ee', 'ي'), ('ea', 'ي'),
    ('a', 'ا'), ('b', 'ب'), ('c', 'ك'), ('d', 'د'), ('e', 'ي'), ('f', 'ف'),
    ('g', 'ج'), ('h', 'ه'), ('i', 'ي'), ('j', 'ج'), ('k', 'ك'), ('l', 'ل'),
    ('m', 'م'), ('n', 'ن'), ('o', 'و'), ('p', 'ب'), ('q', 'ق'), ('r', 'ر'),
    ('s', 'س'), ('t', 'ت'), ('u', 'و'), ('v', 'ف'), ('w', 'و'), ('x', 'كس'),
    ('y', 'ي'), ('z', 'ز'),
]
FEM_HEADS = ('ة',)   # Arabic heads that force feminine adjectives
STOP_EN = {'the', 'a', 'an', 'and', 'of', 'for', 'to', 'in', 'on'}

# ---------------------------------------------------------------- helpers
def transliterate(word):
    w = word.lower()
    out = []
    i = 0
    while i < len(w):
        for dig, ar in PHONEMES:
            if w.startswith(dig, i):
                out.append(ar)
                i += len(dig)
                break
        else:
            i += 1
    s = ''.join(out)
    if w.startswith('u') and not w.startswith('oo'):
        s = 'يو' + s[1:] if s.startswith('و') else s
    s = re.sub(r'(.)\1{2,}', r'\1\1', s)
    s = re.sub(r'يي+$', 'ي', s)
    s = re.sub(r'او', 'و', s)
    return s or word

def ar_words(s):
    return [w for w in s.split() if re.search(r'[\u0621-\u064A]', w)]

def agree(adj_ar, head_ar):
    """R13: gender/number/definiteness agreement (applies to adjective's first word)."""
    toks = adj_ar.split()
    if not toks:
        return adj_ar
    if head_ar.endswith(FEM_HEADS) and not toks[0].endswith('ة'):
        toks[0] += 'ة'
    if head_ar.startswith('ال') and not toks[0].startswith('ال'):
        toks[0] = 'ال' + toks[0]
    return ' '.join(toks)

def definite(word_ar):
    return word_ar if word_ar.startswith('ال') else 'ال' + word_ar

# ---------------------------------------------------------------- engine
class Engine:
    def __init__(self):
        self.lex = load_lexicon()
        self.word_map = self._mine_word_map()
        self.word_map.update({k: v for k, v in HEAD_SEED.items() if k not in self.word_map})

    def _mine_word_map(self):
        """mine 1:1 EN word ↔ AR word from the lexicon itself"""
        wm = {}
        for en, ar in self.lex.items():
            ew = en.split()
            aw = ar_words(ar)
            if len(ew) == 1 and len(aw) == 1:
                wm.setdefault(ew[0], aw[0])
        return wm

    def lookup_word(self, w):
        if w in self.word_map:
            return self.word_map[w]
        if w in ADJ:
            return ADJ[w]
        if w in HEAD_SEED:
            return HEAD_SEED[w]
        return None

    def decompose_prefixed(self, w):
        """multinational → multi+national → متعدد + قومي → متعدد قومي"""
        for p in sorted(PREFIX, key=len, reverse=True):
            if w.startswith(p) and len(w) > len(p) + 2:
                stem = w[len(p):]
                if stem in ADJ:
                    return PREFIX[p] + ' ' + ADJ[stem]
                sa = self.lookup_word(stem)
                if sa:
                    return PREFIX[p] + ' ' + sa
        return None

    def translate(self, term):
        trace = []
        t = norm_en(term)
        if not t:
            return {'input': term, 'output': None, 'method': 'empty', 'trace': trace}

        # R01 dictionary
        if t in self.lex:
            return {'input': term, 'output': self.lex[t], 'method': 'dictionary',
                    'trace': ['R01 exact lexicon hit']}

        raw = term.strip()
        # R09 acronyms
        acronyms = re.findall(r'\b[A-Z]{2,}\b', raw)
        if acronyms and all(not c.islower() for c in raw.replace('(', ' ').replace(')', ' ')):
            a = acronyms[0]
            if a.lower() in self.lex:
                return {'input': term, 'output': self.lex[a.lower()], 'method': 'dictionary(acronym)',
                        'trace': ['R09 acronym lexicon hit']}
            tr = transliterate(a.lower())
            trace.append('R09 acronym → transliterate (no established expansion found)')
            return {'input': term, 'output': 'ال' + tr if len(a) > 3 else tr,
                    'method': 'transliteration', 'trace': trace}

        words = t.split()

        # R04 of-chain → idaafa
        if ' of ' in f' {t} ':
            parts = [p.strip() for p in re.split(r'\s+of\s+', t)]
            ars = [self._translate_simple(p, trace) for p in parts]
            ars = [re.sub(r'^ال', '', a) if i == 0 else definite(a)
                   for i, a in enumerate(ars)]
            out = ' '.join(a for a in ars if a)
            trace.append('R04 of-chain → idaafa (no preposition; first member indefinite)')
            return {'input': term, 'output': out, 'method': 'rule-composition', 'trace': trace}

        # two-word Adj+N or N+N (R03/R05)
        if len(words) == 2:
            w1, w2 = words
            a1, a2 = self.lookup_word(w1), self.lookup_word(w2)
            if (w1 in ADJ or w1 in PREFIX_ADJ) and (a2 or True):
                head = a2 or self.lex.get(w2) or HEAD_SEED.get(w2) or transliterate(w2)
                adj = ADJ.get(w1) or PREFIX[w1]
                out = f'{head} {agree(adj, head)}'
                trace.append(f'R03 adjective inversion: {w1}→{adj} postposed after head {head}')
                return {'input': term, 'output': out, 'method': 'rule-composition', 'trace': trace}
            if a1 and a2:
                out = f'{a2} {definite(a1)}'
                trace.append(f'R05 compound reversal (idaafa): {w2} {a1} → {a2} {definite(a1)}')
                return {'input': term, 'output': out, 'method': 'rule-composition', 'trace': trace}

        # single unknown word: prefix/suffix decomposition, then transliteration
        if len(words) == 1:
            w = words[0]
            for p, par in sorted(PREFIX.items(), key=lambda x: -len(x[0])):
                if w.startswith(p) and len(w) > len(p) + 2:
                    stem = w[len(p):].lstrip('-')
                    sa = self.lookup_word(stem) or self.lex.get(stem)
                    if sa:
                        trace.append(f'R06 prefix {p}- → {par}')
                        return {'input': term, 'output': f'{sa} {par}',
                                'method': 'rule-composition', 'trace': trace}
            for s, sar in sorted(SUFFIX.items(), key=lambda x: -len(x[0])):
                if w.endswith(s) and len(w) > len(s) + 2 and sar:
                    base = w[:len(w) - len(s)]
                    ba = self.lookup_word(base)
                    if ba:
                        trace.append(f'R07 suffix -{s} → {sar}')
                        base_clean = re.sub(r'ة$', '', ba)
                        return {'input': term, 'output': base_clean + sar,
                                'method': 'rule-composition', 'trace': trace}
            tr = transliterate(w)
            trace.append('R08 no lexicon/morphology match → phonemic transliteration')
            return {'input': term, 'output': tr, 'method': 'transliteration', 'trace': trace}

        # generic multiword: translate head (last noun), attach known mods
        words = [w for w in words if w not in STOP_EN] or words
        head = words[-1]
        head_ar = self.lookup_word(head) or self.lex.get(head) or transliterate(head)
        noun_mods, adj_mods = [], []
        for w in reversed(words[:-1]):
            if w in ADJ:
                adj_mods.append(agree(ADJ[w], head_ar))
                trace.append(f'R03 adjective {w} → {ADJ[w]} (postposed)')
            elif w in PREFIX_ADJ:
                pa = agree(PREFIX[w], head_ar)
                adj_mods.append(pa)
                trace.append(f'R06 prefix-as-adjective {w}- → {pa} (postposed)')
            else:
                ma = self.lookup_word(w)
                if ma:
                    noun_mods.append(definite(ma))
                    trace.append(f'R05 noun modifier {w} → {definite(ma)}')
                else:
                    composed = self.decompose_prefixed(w)
                    if composed:
                        adj_mods.append(agree(composed, head_ar))
                        trace.append(f'R06 decomposed prefixed modifier {w} → {composed}')
                    else:
                        noun_mods.append(transliterate(w))
                        trace.append(f'R08 transliterate modifier {w}')
        if noun_mods:
            head_is_def = True   # idaafa chain makes NP definite
            adj_mods = [a if a.startswith('ال') else 'ال' + a for a in adj_mods]
        mods = noun_mods + adj_mods
        out = ' '.join([head_ar] + mods) if mods else head_ar
        if not any(x.startswith('ال') for x in mods) and head_ar in ('تليفزيون', 'راديو'):
            pass  # generic mass usage stays indefinite
        return {'input': term, 'output': out, 'method': 'rule-composition', 'trace': trace}

    def _translate_simple(self, phrase, trace):
        t = norm_en(phrase)
        if t in self.lex:
            return self.lex[t]
        ws = [w for w in t.split() if w not in STOP_EN] or t.split()
        if len(ws) == 1:
            return self.lookup_word(ws[0]) or transliterate(ws[0])
        # Adj + N phrase inside of-chain
        if ws[0] in ADJ:
            head = self._translate_simple(' '.join(ws[1:]), trace)
            return f'{head} {agree(ADJ[ws[0]], head)}'
        head = self.lookup_word(ws[-1]) or transliterate(ws[-1])
        mods = []
        for w in ws[:-1]:
            if w in ADJ:
                mods.append(agree(ADJ[w], head))
            else:
                ma = self.lookup_word(w)
                mods.append(definite(ma) if ma else transliterate(w))
        return ' '.join([head] + mods) if mods else head

# ---------------------------------------------------------------- self test
SELF_TEST = [
    # dictionary hits (R01)
    ('Public Opinion', 'الرأي العام', 'dictionary'),
    ('content analysis', 'تحليل المضمون', 'dictionary'),
    ('inverted pyramid', 'الهرم المقلوب', 'dictionary'),
    ('United Nations', 'الأمم المتحدة', 'dictionary'),
    # composition (R03/R05/R04/R06)
    ('digital television', 'تليفزيون رقمي', 'composition'),
    ('mass communication', 'الجماهيري', 'composition'),
    ('international communication', 'الدولي', 'composition'),
    ('local newspaper', 'صحيفة محلية', 'composition'),
    ('freedom of information', 'حرية المعلومات', 'composition'),
    ('camera network', 'شبكة الكاميرا', 'composition'),
    # transliteration (R08)
    ('Bundestag', 'بوندستاج', 'translit'),
]

def self_test(eng):
    passed = 0
    for src, expected, kind in SELF_TEST:
        r = eng.translate(src)
        ok = expected in (r['output'] or '')
        passed += ok
        mark = 'PASS' if ok else 'FAIL'
        print(f"[{mark}] {kind:12s} {src!r:32s} → {r['output']!r} (expected ⊇ {expected!r})")
    print(f"self-test: {passed}/{len(SELF_TEST)} passed; lexicon size = {len(eng.lex)}")
    return passed == len(SELF_TEST)

def main():
    eng = Engine()
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    if args[0] == '--self-test':
        sys.exit(0 if self_test(eng) else 1)
    if args[0] == '--file':
        for line in open(args[1], encoding='utf-8'):
            line = line.strip()
            if line:
                print(json.dumps(eng.translate(line), ensure_ascii=False))
        return
    print(json.dumps(eng.translate(' '.join(args)), ensure_ascii=False, indent=1))

if __name__ == '__main__':
    main()
