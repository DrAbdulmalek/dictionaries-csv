#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mine EN->AR translation rules (as algorithms) from the two dictionaries.

Corpus: political encyclopedia pairs (with definitions) + media dictionary pairs.
Analyses:
  A. transliteration vs semantic-translation profiling (romanization similarity)
  B. head-word / adjective order inversion evidence
  C. prefix & suffix affix correspondence mining (support + precision)
  D. genitive 'of' -> idaafa elision statistics
  E. definite-article policy statistics
  F. acronym handling strategies
  G. nominalization (masdar) patterns
Output: work/rules_mined.json
Statistical rule mining over 1600 parallel pairs (transliteration profiling, order
inversion, affix correspondence mining, genitive/article/acronym/masdar statistics).
Inputs: work/pol_entries.json + work/media_entries.json.
Outputs: work/rules_mined.json (evidence behind algorithms/media_political_translation_rules.json).

"""
import json, re, collections, itertools, unicodedata

TASH = re.compile(r'[\u064b-\u0652\u0670]')

ROMAN = {
    'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'aa', 'ب': 'b', 'ت': 't', 'ث': 't',
    'ج': 'j', 'ح': 'h', 'خ': 'x', 'د': 'd', 'ذ': 'd', 'ر': 'r', 'ز': 'z',
    'س': 's', 'ش': 's', 'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z', 'ع': '',
    'غ': 'g', 'ف': 'f', 'ق': 'q', 'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
    'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a', 'ة': 't', 'ئ': 'y', 'ء': '',
    'ؤ': 'w', 'لإ': 'li', 'أل': 'al',
}

ROMAN2 = dict(ROMAN)
ROMAN2.update({'و': 'o', 'ي': 'i', 'ى': 'a', 'ؤ': 'o', 'ئ': 'e'})

def romanize(s, table=None):
    s = TASH.sub('', s)
    t = table or ROMAN
    return ''.join(t.get(c, c if re.match(r'[a-z]', c) else '') for c in s.lower() if c not in ' ')

def collapse(s):
    s = re.sub(r'[^a-z]', '', s)
    s = re.sub(r'(.)\1+', r'\1', s)
    return s

def en_forms(w):
    w = re.sub(r'[^a-z]', '', w.lower())
    return {w, re.sub(r'[aeiou]+', '', w)}

def ar_forms(w):
    w = TASH.sub('', w)
    outs = set()
    for t in (ROMAN, ROMAN2):
        r = ''.join(t.get(c, '') for c in w)
        r = re.sub(r'[^a-z]', '', r)
        r = re.sub(r'^al', '', r)
        outs.add(r)
        outs.add(re.sub(r'[aeiou]+', '', r))
        outs.add(re.sub(r'^[aeiou]+', '', r))
    return {collapse(x) for x in outs if x}

def best_ratio(ar, en):
    import difflib
    b = 0.0
    for x in ar_forms(ar):
        for y in en_forms(en):
            if x and y:
                b = max(b, difflib.SequenceMatcher(None, x, y).ratio())
    return b

def pair_sim(p):
    en_clean = re.sub(r'\(.*?\)', '', p['en'])
    ew = [w for w in re.split(r'[\s/\-]+', en_clean.lower()) if re.match(r'^[a-z]{2,}$', w)]
    aw = ar_words(p['ar'])
    if not ew or not aw:
        return 0.0
    whole = best_ratio(' '.join(aw).replace(' ', ''), en_clean.replace(' ', ''))
    # greedy word alignment: each en word matched to its best ar word
    sims = []
    for y in ew:
        sims.append(max(best_ratio(x, y) for x in aw))
    wordwise = sum(sims) / len(sims)
    return max(whole * 0.9, wordwise)

def load_pairs():
    pol = json.load(open('work/pol_entries.json', encoding='utf-8'))
    med = json.load(open('work/media_entries.json', encoding='utf-8'))
    pairs = []
    for e in pol:
        if e['ar'] and e['en']:
            pairs.append({'ar': e['ar'], 'en': e['en'], 'src': 'political',
                          'defn': e.get('definition', '')})
    for e in med:
        if e['ar'] and e['en']:
            pairs.append({'ar': e['ar'], 'en': e['en'], 'src': 'media', 'defn': ''})
    return pairs

def ar_words(s):
    return [w for w in TASH.sub('', s).split() if re.search(r'[\u0621-\u064A]', w)]

def en_words(s):
    s = re.sub(r'\([^)]*\)', ' ', s)
    return [w for w in re.split(r'[\s/\-]+', s.lower()) if re.match(r'^[a-z]+$', w)]

# ---------------- A. transliteration profiling ----------------
def profile(pairs):
    trans, semi, sem = [], [], []
    for p in pairs:
        r = pair_sim(p)
        if r >= 0.70:
            trans.append((round(r, 2), p))
        elif r >= 0.52:
            semi.append((round(r, 2), p))
        else:
            sem.append(p)
    return trans, semi, sem

# ---------------- B. order inversion evidence ----------------
def order_evidence(pairs):
    inv, same = [], []
    for p in pairs:
        ew = [w for w in re.split(r'[\s/\-]+', re.sub(r'\(.*?\)', '', p['en']).lower()) if re.match(r'^[a-z]{2,}$', w)]
        aw = ar_words(p['ar'])
        if len(ew) == 2 and len(aw) == 2:
            a1, a2 = aw[0], aw[1]
            a1d = re.sub(r'^ال', '', a1); a2d = re.sub(r'^ال', '', a2)
            if max(best_ratio(a1, ew[1]), best_ratio(a1d, ew[1])) >= 0.62 and best_ratio(a2, ew[0]) < 0.5:
                inv.append(p)
            elif max(best_ratio(a1, ew[0]), best_ratio(a1d, ew[0])) >= 0.62 and best_ratio(a2, ew[1]) < 0.5:
                same.append(p)
    return inv, same

# ---------------- C. affix correspondence mining ----------------
PREFIXES = ['anti', 'auto', 'bi', 'co', 'counter', 'cross', 'de', 'dis', 'electro',
            'ex', 'free', 'global', 'hyper', 'inter', 'intra', 'local', 'mass',
            'micro', 'mid', 'mis', 'multi', 'national', 'neo', 'non', 'over',
            'pan', 'post', 'pre', 'pro', 'psycho', 're', 'self', 'semi', 'socio',
            'sub', 'super', 'trans', 'ultra', 'under', 'uni']
SUFFIXES = ['ology', 'ics', 'ism', 'ist', 'tion', 'sion', 'ment', 'ness', 'cracy',
            'graphy', 'phobia', 'ity', 'ization', 'ive', 'al', 'ic', 'ary', 'ance',
            'ship', 'dom', 'hood', 'ese', 'ian']

def ngrams(s, lo=3, hi=6):
    s = TASH.sub('', s).replace(' ', '')
    out = set()
    for n in range(lo, hi + 1):
        for i in range(len(s) - n + 1):
            out.add(s[i:i + n])
    return out

def mine_affix(pairs, affixes, kind):
    results = []
    all_terms = [p['ar'] for p in pairs]
    for af in affixes:
        if kind == 'pre':
            sel = [p for p in pairs if re.match(r'^' + af + r'[\s\-]?[a-z]', ' '.join(en_words(p['en'])) or '')
                   or p['en'].lower().startswith(af)]
            sel = [p for p in sel if re.match(r'^' + af + r'(?![a-z])|^' + af, p['en'].lower())]
        else:
            sel = [p for p in pairs if any(w.endswith(af) and len(w) > len(af) + 2 for w in en_words(p['en']))]
        if len(sel) < 4:
            continue
        cnt = collections.Counter()
        for p in sel:
            for g in ngrams(p['ar']):
                cnt[g] += 1
        bg = collections.Counter()
        for t in all_terms:
            gs = ngrams(t)
            for g in gs:
                bg[g] += 1
        best = []
        for g, n in cnt.most_common():
            if n < max(3, int(0.18 * len(sel))):
                continue
            prec = n / max(1, bg[g])
            if prec >= 0.4 and len(g) >= 3:
                best.append((g, n, round(prec, 2)))
        # remove substrings dominated by longer ones
        best.sort(key=lambda x: (-len(x[0]), -x[1]))
        keep = []
        for g, n, pr in best:
            if any(g in k[0] and k[0] != g for k in keep):
                continue
            keep.append((g, n, pr))
            if len(keep) >= 6:
                break
        if keep:
            results.append({
                'affix': af, 'kind': kind, 'support_terms': len(sel),
                'arabic_correspondences': [{'ar': g, 'n': n, 'precision': pr} for g, n, pr in keep],
                'examples': [{'en': p['en'], 'ar': p['ar']} for p in sel[:6]],
            })
    return results

# ---------------- D. 'of' genitive ----------------
def of_stats(pairs):
    sel = [p for p in pairs if re.search(r'\bof\b', p['en'].lower())]
    idaafa = [p for p in sel if len(ar_words(p['ar'])) >= 2 and
              any(w.startswith('ال') for w in ar_words(p['ar'])[1:])]
    return {'total_of_terms': len(sel),
            'with_definite_second_member': len(idaafa),
            'examples': [{'en': p['en'], 'ar': p['ar']} for p in sel[:8]]}

# ---------------- E. article policy ----------------
def article_stats(pairs):
    heads = [ar_words(p['ar'])[0] for p in pairs if ar_words(p['ar'])]
    withal = sum(1 for w in heads if w.startswith('ال'))
    en_the = sum(1 for p in pairs if p['en'].lower().startswith('the '))
    return {'ar_terms_starting_with_AL': withal, 'total': len(heads),
            'en_terms_with_the': en_the,
            'ratio_ar_definite': round(withal / max(1, len(heads)), 3)}

# ---------------- F. acronyms ----------------
def acronym_stats(pairs):
    sel = [p for p in pairs if re.search(r'\b[A-Z]{2,}\b|\([A-Z]{2,}\)', p['en'])]
    translit, kept, translated = [], [], []
    for p in sel:
        acr = [a for a in re.findall(r'\b[A-Z]{2,}\b', p['en']) if len(a) >= 3]
        if any(best_ratio(p['ar'], a) >= 0.55 for a in acr):
            translit.append(p)
        elif any(a in p['ar'] for a in re.findall(r'\b[A-Z]{2,}\b', p['en'])):
            kept.append(p)
        else:
            translated.append(p)
    return {'total': len(sel), 'acronym_transliterated': len(translit),
            'acronym_kept_latin': len(kept), 'fully_translated': len(translated),
            'examples_transliterated': [{'en': p['en'], 'ar': p['ar']} for p in translit[:8]],
            'examples_translated': [{'en': p['en'], 'ar': p['ar']} for p in translated[:8]]}

# ---------------- G. masdar / nominalization ----------------
MASDAR_PAT = {
    'if3aal (إفعال)': r'^إ[\u0621-\u064A]{3,}$',
    'taf3iil (تفعيل)': r'^ت[\u0621-\u064A]?\w*ي[\u0621-\u064A]$',
    'fu3uul (فعول)': r'^[\u0621-\u064A]و[\u0621-\u064A]$',
}
def masdar_stats(pairs):
    sel = [p for p in pairs if any(w.endswith(('tion', 'sion', 'ment')) for w in en_words(p['en']))]
    m = {'if3aal': 0, 'taf3iil': 0, 'other': 0}
    ex = collections.defaultdict(list)
    for p in sel:
        ws = ar_words(p['ar'])
        if not ws:
            continue
        w = ws[0].lstrip('ال')
        if re.match(r'^إ.+$', w) and len(w) >= 4:
            m['if3aal'] += 1; ex['if3aal'].append(p)
        elif re.match(r'^ت.+ي.+$', w) or re.match(r'^ت.{3,}$', w):
            m['taf3iil'] += 1; ex['taf3iil'].append(p)
        else:
            m['other'] += 1
    return {'tion_sion_ment_terms': len(sel), 'patterns': m,
            'examples': {k: [{'en': p['en'], 'ar': p['ar']} for p in v[:5]] for k, v in ex.items()}}

def main():
    pairs = load_pairs()
    print('pairs:', len(pairs), collections.Counter(p['src'] for p in pairs))
    trans, semi, sem = profile(pairs)
    inv, same = order_evidence(pairs)
    out = {
        'corpus': {'total_pairs': len(pairs),
                   'political': sum(1 for p in pairs if p['src'] == 'political'),
                   'media': sum(1 for p in pairs if p['src'] == 'media')},
        'A_strategy_profile': {
            'transliteration_like': len(trans), 'partial': len(semi), 'semantic': len(sem),
            'transliteration_examples': [{'en': p['en'], 'ar': p['ar'], 'sim': r} for r, p in sorted(trans, key=lambda x: -x[0])[:15]],
        },
        'B_order_inversion': {
            'inverted_evidence': len(inv), 'same_order_evidence': len(same),
            'examples_inverted': [{'en': p['en'], 'ar': p['ar']} for p in inv[:12]],
            'examples_same': [{'en': p['en'], 'ar': p['ar']} for p in same[:8]],
        },
        'C_prefix_rules': mine_affix(pairs, PREFIXES, 'pre'),
        'C_suffix_rules': mine_affix(pairs, SUFFIXES, 'suf'),
        'D_genitive_of': of_stats(pairs),
        'E_article_policy': article_stats(pairs),
        'F_acronyms': acronym_stats(pairs),
        'G_nominalization': masdar_stats(pairs),
    }
    json.dump(out, open('work/rules_mined.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('A:', out['A_strategy_profile']['transliteration_like'], 'transliterated;',
          out['A_strategy_profile']['semantic'], 'semantic')
    print('B: inversion evidence', len(inv), 'vs same-order', len(same))
    print('C: prefix rules', len(out['C_prefix_rules']), '| suffix rules', len(out['C_suffix_rules']))
    print('D:', out['D_genitive_of'])
    print('E:', out['E_article_policy'])
    print('G:', out['G_nominalization']['patterns'], 'of', out['G_nominalization']['tion_sion_ment_terms'])

if __name__ == '__main__':
    main()
