#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mine bilingual phrase/sentence pairs from POL definitions — v3.

  TIGHT : Arabic words immediately preceding an embedded English span
          (اتصال مباشر Direct  ->  مباشر ↔ Direct), also handles (EN) parens
  LOOSE : span vs enclosing Arabic sentence (context translation)
Output: work/pol_sentences.json
Mines EN↔AR phrase/sentence pairs from political definitions (434 rows).
Inputs: work/pol_entries.json. Outputs: work/pol_sentences.json.

"""
import json, re

LATIN_SPAN = re.compile(r'[A-Za-z][A-Za-z \u0027&,\.\-/]*[A-Za-z\)]|[A-Za-z]')
AR = re.compile(r'[\u0600-\u06FF]')
AR_WORD = re.compile(r'[\u0600-\u06FF\u064b-\u0652]+')
STOP = {'أو', 'و', 'في', 'إلى', 'من', 'على', 'هو', 'هي', 'كان', 'كانت', 'التي',
        'الذي', 'مع', 'بين', 'عن', 'أن', 'إن', 'كما', 'حيث', 'عندما', 'إذا',
        'ما', 'لا', 'ليس', 'قد', 'فهو', 'فهي', 'وهو', 'وهي', 'مثل', 'أي', 'كل',
        'هذا', 'هذه', 'ذلك', 'تلك', 'حتى', 'ثم', 'بعد', 'قبل', 'عبر', 'خلال',
        'لدعم', 'بشكل', 'يكون', 'تكون', 'فهناك', 'وهناك', 'والتي', 'والذي',
        'يعني', 'يقصد', 'مصطلح', 'يسمى', 'تسمى', 'يطلق', 'تعني', 'أيضا',
        'إما', 'سواء', 'بينما', 'عند', 'لدى', 'دون', 'ضد', 'نحو'}
PAREN_PAIR = re.compile(r'\(([A-Za-z][A-Za-z \u0027&,\.\-/]{0,60}?)\)')

def split_sentences(defn):
    parts = re.split(r'(?<=[.!?…])\s+', defn)
    return [p.strip() for p in parts if p.strip()]

MERGE_OK = re.compile(r'^[\u0621-\u064A]$')

def tidy(s):
    s = re.sub(r'\s{2,}', ' ', s)
    # join single-letter fragments broken by the text layer (ع ك سية -> عكسية)
    toks = s.split(' ')
    out = []
    for t in toks:
        if out and MERGE_OK.match(t) and t not in ('و', 'أ', 'ف'):
            out[-1] = out[-1] + t
        elif out and len(t) == 1 and MERGE_OK.match(out[-1][-1:]) and out[-1] not in ('و',):
            out[-1] = out[-1] + t if len(re.sub(r'[^\u0621-\u064A]', '', out[-1])) == 1 and MERGE_OK.match(t) is None and False else out[-1]
            out.append(t) if False else None
        else:
            out.append(t)
    s = ' '.join(out)
    # trailing single letter merges back (رسمي ا -> رسميا)
    def _merge_trailing(mm):
        return mm.group(1) + mm.group(2) if mm.group(2) not in 'وأف' else mm.group(0)
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r'(\S) ([\u0621-\u064A])(?=$|[\s،,.])', _merge_trailing, s)
    s = s.replace('عك سية', 'عكسية')
    s = re.sub(r'\s+([ًٌٍَُِّْ])', r'\1', s)   # tanween spacing
    s = re.sub(r'\s{2,}', ' ', s)
    return s.strip(' ،,.-؛:ـ')

def preceding_arabic(sent, start, max_words=4):
    left = sent[:start]
    left = re.split(r'[،,;؛]', left)[-1]      # stay inside the current clause
    words = AR_WORD.findall(left)
    if not words:
        return ''
    # cut at trailing stopword boundary
    take = []
    for w in reversed(words[-max_words:]):
        if w in STOP:
            break
        take.append(w)
    take.reverse()
    if not take:
        return ''
    # require adjacency: the taken words must end exactly at span start
    tail = left[left.rfind(take[-1]) + len(take[-1]):]
    if tail.strip(' ،,.'):
        return ''
    return ' '.join(take)

def main():
    E = json.load(open('work/pol_entries.json', encoding='utf-8'))
    rows = []
    seen = set()

    def add(en, ar, kind, sent, term_ar, term_en, page):
        en = re.sub(r'\s+', ' ', en).strip(' -.,()')
        ar = tidy(ar)
        if len(en) < 2 or len(AR.findall(ar)) < 2:
            return
        key = (en.lower(), ar[:40])
        if key in seen:
            return
        seen.add(key)
        rows.append({'english': en, 'arabic': ar, 'type': kind,
                     'arabic_context': tidy(sent),
                     'arabic_term': term_ar, 'english_term': term_en, 'page': page})

    for e in E:
        d = e.get('definition') or ''
        if not d:
            continue
        for sent in split_sentences(d):
            covered = []
            # parenthetical english first
            for m in PAREN_PAIR.finditer(sent):
                en = m.group(1).strip()
                if en.lower() == e['en'].lower():
                    continue
                ar = preceding_arabic(sent, m.start(), 4)
                if ar:
                    add(en, ar, 'tight', sent, e['ar'], e['en'], e.get('page'))
                else:
                    add(en, re.sub(r'\([^)]*\)', ' ', sent), 'loose', sent, e['ar'], e['en'], e.get('page'))
                covered.append((m.start(1), m.end(1)))
            for m in LATIN_SPAN.finditer(sent):
                if any(s - 2 <= m.start() < e2 + 2 for s, e2 in covered):
                    continue
                sp = m.group(0)
                if sp.strip().lower() == e['en'].strip().lower():
                    continue
                sp = sp.strip()
                if len(sp) < 2 or re.fullmatch(r'[A-Za-z]', sp):
                    continue
                ar = preceding_arabic(sent, m.start(), 4)
                if ar and len(AR_WORD.findall(ar)) >= 1:
                    add(sp, ar, 'tight', sent, e['ar'], e['en'], e.get('page'))
                else:
                    ar_sent = sent[:m.start()] + ' ' + sent[m.end():]
                    if len(AR.findall(ar_sent)) >= 8:
                        add(sp, ar_sent, 'loose', sent, e['ar'], e['en'], e.get('page'))

    json.dump(rows, open('work/pol_sentences.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    tight = sum(1 for r in rows if r['type'] == 'tight')
    print('rows:', len(rows), '| tight:', tight, '| loose:', len(rows) - tight)
    for r in [x for x in rows if x['type'] == 'tight'][:12]:
        print('T', r['english'][:30], '||', r['arabic'][:50])
    for r in [x for x in rows if x['type'] == 'loose'][:4]:
        print('L', r['english'][:30], '||', r['arabic'][:70])

if __name__ == '__main__':
    main()
