#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""الموسوعة الميسرة للمصطلحات السياسية — extractor v3.

  * digit-only lines dropped as page noise ONLY when leading a page
  * RTL-reversed Arabic digit runs flipped back (٨٤٩١ -> ١٩٤٨)
  * word-internal line splits rejoined (العام + ة -> العامة)
  * cross-reference entries (أمريكا America / أنظر ...) split into ar/en/note
  * duplicated words from double text layer collapsed; 'الال' artifact removed
  * unbalanced parens in English terms repaired
Extracts الموسوعة الميسرة للمصطلحات السياسية (508p PDF) -> work/pol_entries.json
Run layout: PDFs in uploads/, raw dumps via dump step below, outputs under work/.
Inputs:  work/pol_raw.txt  (per-page NFKC-normalized text dump of the PDF)
Outputs: work/pol_entries.json  [{ar,en,definition,page}] — 1035 entries.

"""
import json, re, unicodedata, collections

TATWEEL = '\u0640'
TITLE_RE = re.compile(r'الموسوعة\s*الميسرة\s*للمصطلحات\s*السياسية')
DIGITS_RE = re.compile(r'^[\s٠-٩0-9]+$')
AR_RE = re.compile(r'[\u0600-\u06FF]')
LATIN_RE = re.compile(r'[A-Za-z]')
BIDI = re.compile(r'[\u200f\u200e\u202a-\u202e\u2066-\u2069]')
AR_DIGITS = '٠١٢٣٤٥٦٧٨٩'
SLASHY = re.compile(r'(\s*/\s*)+')

def clean_line(ln):
    ln = unicodedata.normalize('NFKC', ln).replace(TATWEEL, '')
    return BIDI.sub('', ln).strip()

def flip_ar_digits(m):
    return m.group(0)[::-1]

def fix_numbers(text):
    return re.sub('[' + AR_DIGITS + ']{2,}', flip_ar_digits, text)

def lang_ratio(ln):
    ar = len(AR_RE.findall(ln)); la = len(LATIN_RE.findall(ln))
    return ar / (ar + la) if ar + la else -1.0

def merge_defn(lines):
    out = []
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if re.fullmatch(r'[.,،؛:!?…]+', ln) and out:
            out[-1] = out[-1].rstrip() + ln
            continue
        core = re.sub(r'[.,،؛:!?…()\s"\']', '', ln)
        if out and core and len(core) <= 2 and all(c in 'ةهوىيئأإ' for c in core):
            punct = ln[len(core):] if ln.endswith(('.', ',', '،', '؛', ':', '!', '?', '…')) else ''
            out[-1] = out[-1].rstrip() + core + punct
            continue
        if ln in ('(', ')') and out:
            out[-1] = out[-1] + ln
            continue
        out.append(ln)
    text = ' '.join(out)
    text = re.sub(r'\s+([.,،؛:!?…])', r'\1', text)
    text = re.sub(r'\(\s+', '(', text)
    text = re.sub(r'\s+\)', ')', text)
    text = fix_numbers(text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()

def dedup_words(s):
    toks = s.split()
    out = []
    for t in toks:
        if out and out[-1] == t:
            continue
        out.append(t)
    return ' '.join(out)

def balance_parens(s):
    d = s.count('(') - s.count(')')
    if d > 0:
        s = s + ')' * d
    elif d < 0:
        s = '(' * (-d) + s
    return s

FRAG = ('(?:' + '|'.join(['ح','لح','ون','ية','ء','سا','صا','ام','ذه','ة','ل','ن','س','ت',
                          'ر','ز','د','ص','ط','ف','ق','ك','ه','ب','ا','اد']) + ')')
FRAG_RE = re.compile(r'(?<=[\u0621-\u064A]) (' + FRAG + r')(?=[\s،,.؛]|$)')
ALIF_LAM_RE = re.compile(r'(?<![\u0621-\u064A])ا (ل[\u0621-\u064A])')
WAW_RE = re.compile(r'(?<=\s)و (?=[\u0621-\u064A])')

def _find_tail_dup(t):
    w = t.split()
    n = len(w)
    for k in (4, 3, 2, 1):
        if n >= 2 * k and w[-k:] == w[-2 * k:-k]:
            return ' '.join(w[:-k])
    return None

def dedup_tail(s):
    """collapse doubled text layers: 'X Y X Y' -> 'X Y' (with ad-glue tolerance)"""
    r = _find_tail_dup(s)
    if r:
        return r
    for m in re.finditer(r'\S{3,}اد(?=\s|$)', s):
        cand = s[:m.start()] + m.group(0)[:-2] + s[m.end():]
        r = _find_tail_dup(cand)
        if r:
            return r
    return s

def join_fragments(s):
    s = re.sub(r'أن\s*/\s*ظر', 'أنظر', s)
    s = re.sub(r'أنظ\s*/\s*ر', 'أنظر', s)
    s = ALIF_LAM_RE.sub(r'ا\1', s)
    s = WAW_RE.sub('و', s)
    prev = None
    while prev != s:
        prev = s
        s = FRAG_RE.sub(r'\1', s)
    return s

def clean_note(t):
    t = SLASHY.sub(' / ', t)
    t = dedup_words(t)
    return t.strip(' /،,.')

def split_crossref(ar, en, defn):
    """'أمريكا أمريكا America / أنظر الولايات المتحدة ... U.S.A.' ->
    (ar='أمريكا', en='America', defn=defn+'أنظر: ...')"""
    if en or not LATIN_RE.search(ar):
        return ar, en, defn
    text = dedup_words(ar.replace('الال', ''))
    m = re.search(r"([A-Za-z][A-Za-z0-9 .,&'\u2019\-\(\)/]*[A-Za-z0-9\.\)])", text)
    if not m:
        return ar, en, defn
    en2 = re.sub(r'\s*/\s*$', '', m.group(1)).strip()
    ar2 = dedup_words(text[:m.start()]).strip(' /،,')
    tail = clean_note(text[m.end():])
    note = ''
    if tail:
        mr = re.search(r'أنظر\s*(.*)$', tail)
        note = ('أنظر: ' + clean_note(mr.group(1))) if mr else tail
    newdef = defn if defn else note
    if defn and note and note not in defn:
        newdef = defn.rstrip('.،, ') + '. ' + note
    return ar2, balance_parens(en2), newdef

def main():
    raw = open('work/pol_raw.txt', encoding='utf-8').read()
    pages = re.split(r'<<<PAGE (\d+)>>>\n', raw)
    stream = []
    for i in range(1, len(pages), 2):
        pg = int(pages[i])
        body_lines = [clean_line(x) for x in pages[i + 1].split('\n')]
        body_lines = [x for x in body_lines if x]
        k = 0
        while k < min(3, len(body_lines)) and (TITLE_RE.search(body_lines[k]) or DIGITS_RE.match(body_lines[k])):
            k += 1
        body_lines = [x for x in body_lines[k:] if not TITLE_RE.search(x)]
        prev = None
        for c in body_lines:
            if c == prev:
                continue
            stream.append((c, pg)); prev = c

    segments = []; cur = []; curpg = None; open_paren = False
    for c, pg in stream:
        if '\u2022' in c:
            parts = c.split('\u2022')
            head = parts[0]
            if head.strip():
                if curpg is None: curpg = pg
                cur.append(head.strip())
            if cur:
                segments.append((cur, curpg, open_paren))
            cur = []; curpg = pg
            open_paren = head.rstrip().endswith('(')
            tail = '\u2022'.join(parts[1:]).strip()
            if tail:
                cur.append(tail)
        else:
            if curpg is None: curpg = pg
            cur.append(c)
    if cur:
        segments.append((cur, curpg, open_paren))

    seg_typed = []
    for ls, pg, op in segments:
        ls = [l for l in ls if l.strip()]
        if not ls:
            continue
        if op:
            ls = ['(' + ls[0]] + ls[1:]
        r = lang_ratio(ls[0])
        kind = 'en' if (r < 0.5 and LATIN_RE.search(ls[0])) else ('ar' if r >= 0.5 else 'x')
        seg_typed.append((kind, ls, pg))

    entries = []; stats = collections.Counter()
    pending_ar = None; pending_pg = None
    idx = 0; N = len(seg_typed)
    while idx < N:
        kind, ls, pg = seg_typed[idx]
        if kind == 'en':
            j = 0; en_lines = []
            while j < len(ls) and lang_ratio(ls[j]) < 0.5 and LATIN_RE.search(ls[j]):
                en_lines.append(ls[j]); j += 1
            en_term = ' '.join(en_lines).strip()
            defn = merge_defn(ls[j:])
            k = idx + 1
            while k < N and seg_typed[k][0] == 'ar':
                nxt_first = seg_typed[k][1][0]
                nxt_text = ' '.join(seg_typed[k][1])
                followed_by_en = (k + 1 < N and seg_typed[k + 1][0] == 'en')
                a, e, _n = split_crossref(nxt_first, '', '')
                if not e and LATIN_RE.search(nxt_text):
                    full_k = dedup_words(merge_defn(seg_typed[k][1]))
                    _a2, e2, _n2 = split_crossref(full_k, '', '')
                    if e2 and full_k.find(e2) <= 60:
                        e = e2
                if followed_by_en or e:
                    break
                defn = (defn + ' ' + merge_defn(seg_typed[k][1])).strip()
                k += 1
            if pending_ar:
                entries.append({'ar': pending_ar, 'en': en_term, 'definition': defn, 'page': pending_pg})
                stats['paired'] += 1
                pending_ar = None
            else:
                entries.append({'ar': '', 'en': en_term, 'definition': defn, 'page': pg})
                stats['en_orphan'] += 1
            idx = k
            continue
        elif kind == 'ar':
            first = ls[0]
            a, e, note = split_crossref(first, '', '')
            if e and not pending_ar:
                defn_parts = ([note] if note else []) + ls[1:]
                defn = merge_defn([x for x in defn_parts if x.strip()])
                entries.append({'ar': dedup_words(a.replace('الال', '')), 'en': balance_parens(e),
                                'definition': defn, 'page': pg})
                stats['inline'] += 1
                idx += 1
                continue
            full = dedup_words(merge_defn(ls)).replace('الال', '').strip()
            if not e and not pending_ar and LATIN_RE.search(full):
                a2, e2, n2 = split_crossref(full, '', '')
                if e2 and full.find(e2) <= 60:
                    entries.append({'ar': dedup_words(a2), 'en': balance_parens(e2),
                                    'definition': n2, 'page': pg})
                    stats['inline_full'] += 1
                    idx += 1
                    continue
            term_text = full
            if pending_ar is not None:
                if term_text == pending_ar or term_text in pending_ar or pending_ar in term_text:
                    pending_ar = max((pending_ar, term_text), key=len)
                    stats['ar_dedup'] += 1
                    idx += 1
                    continue
                entries.append({'ar': pending_ar, 'en': '', 'definition': '', 'page': pending_pg})
                stats['ar_flush'] += 1
            pending_ar = term_text; pending_pg = pg
        else:
            stats['x'] += 1
        idx += 1
    if pending_ar:
        entries.append({'ar': pending_ar, 'en': '', 'definition': '', 'page': pending_pg})

    clean = []
    for e in entries:
        ar, en, defn = split_crossref(e['ar'], e['en'], e['definition'])
        ar = dedup_words(re.sub(r'\s{2,}', ' ', ar)).strip(' -\u0640\u2022/،,.')
        ar = join_fragments(ar)
        ar = dedup_tail(ar)
        en = balance_parens(re.sub(r'\s+', ' ', en)).strip(' -\u2022')
        en = re.sub(r'\s*/\s*', ' / ', en).strip('/ ،,.')
        en = re.sub(r'\(\s*\)', '', en).strip()
        ar = re.sub(r'\(\s*\)', '', ar).strip()
        ar = re.sub(r'\(\s*$', '', ar).strip()
        en = re.sub(r'\(\s*$', '', en).strip()
        defn = re.sub(r'\s{2,}', ' ', defn).strip(' -\u2022')
        defn = join_fragments(defn)
        defn = re.sub(r'([\u0600-\u06FF])([A-Za-z(])', r'\1 \2', defn)
        defn = re.sub(r'([A-Za-z).])([\u0600-\u06FF])', r'\1 \2', defn)
        if not ar and not en:
            continue
        if len(ar) > 120:
            continue
        if en and not LATIN_RE.search(en):
            continue
        e.update(ar=ar, en=en, definition=defn)
        clean.append(e)

    seen = set(); ded = []
    for e in clean:
        k = (e['ar'], e['en'].lower())
        if k in seen:
            continue
        seen.add(k); ded.append(e)

    json.dump(ded, open('work/pol_entries.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    both = sum(1 for e in ded if e['ar'] and e['en'])
    aronly = sum(1 for e in ded if e['ar'] and not e['en'])
    withdef = sum(1 for e in ded if e['definition'])
    print('total:', len(ded), '| ar+en:', both, '| ar-only:', aronly, '| with-defn:', withdef, dict(stats))
    for e in ded[:4]:
        print('-', e['ar'], '|', e['en'], '|', e['definition'][:70])

if __name__ == '__main__':
    main()
