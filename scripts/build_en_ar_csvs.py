#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the deliverable CSVs in the repo root (repo convention: UTF-8 no BOM,
Builds the four deliverable CSVs in the repo root from work/*.json.

quoted, headers 'English Term','Arabic Term' / 'English Sentence','Arabic Sentence')."""
import json, csv, re

REPO = 'repo'

def clean_cell(s):
    s = re.sub(r'\s+', ' ', s or '').strip()
    return s

def main():
    pol = json.load(open('work/pol_entries.json', encoding='utf-8'))
    med = json.load(open('work/media_entries.json', encoding='utf-8'))
    sen = json.load(open('work/pol_sentences.json', encoding='utf-8'))

    # 1. political terms (EN,AR)
    rows = [(e['en'], e['ar']) for e in pol if e['en'] and e['ar']]
    rows = sorted(set(rows), key=lambda r: (r[0].lower(), r[1]))
    with open(f'{REPO}/political_encyclopedia_terms_en_ar.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writerow(['English Term', 'Arabic Term'])
        w.writerows(rows)
    print('political_encyclopedia_terms_en_ar.csv:', len(rows))

    # 2. political definitions (EN,AR,DEF)
    rows = [(e['en'], e['ar'], e['definition']) for e in pol if e['en'] and e['ar'] and e['definition']]
    rows = sorted(set(rows), key=lambda r: (r[0].lower(), r[1]))
    with open(f'{REPO}/political_encyclopedia_definitions_en_ar.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writerow(['English Term', 'Arabic Term', 'Arabic Definition'])
        w.writerows((a, b, clean_cell(c)) for a, b, c in rows)
    print('political_encyclopedia_definitions_en_ar.csv:', len(rows))

    # 3. bilingual sentences/phrases mined from definitions
    rows = [(r['english'], r['arabic']) for r in sen]
    rows = sorted(set(rows), key=lambda r: r[0].lower())
    with open(f'{REPO}/political_encyclopedia_sentences_en_ar.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writerow(['English Sentence', 'Arabic Sentence'])
        w.writerows((a, clean_cell(b)) for a, b in rows)
    print('political_encyclopedia_sentences_en_ar.csv:', len(rows))

    # 4. media terms (EN,AR)
    rows = [(e['en'], e['ar']) for e in med if e['en'] and e['ar']]
    rows = sorted(set(rows), key=lambda r: (r[0].lower(), r[1]))
    with open(f'{REPO}/media_dictionary_terms_en_ar.csv', 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL, lineterminator='\n')
        w.writerow(['English Term', 'Arabic Term'])
        w.writerows(rows)
    print('media_dictionary_terms_en_ar.csv:', len(rows))

if __name__ == '__main__':
    main()
