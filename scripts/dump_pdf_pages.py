#!/usr/bin/env python3
"""Step 0: dump normalized raw text of the source PDFs, page-tagged.

Reads the two dictionary PDFs from uploads/ and writes work/pol_raw.txt and
work/media_raw.txt with <<<PAGE n>>> markers (NFKC-normalized text layer).
Run from the conversion workspace root containing uploads/ and work/.
import fitz, unicodedata, os

UP = os.path.join('uploads')
files = os.listdir(UP)
pol = os.path.join(UP, [f for f in files if f.startswith('1575')][0])
media = os.path.join(UP, [f for f in files if f.startswith('1605')][0])

for name, p in [('pol_raw.txt', pol), ('media_raw.txt', media)]:
    doc = fitz.open(p)
    out = []
    for i in range(len(doc)):
        t = unicodedata.normalize('NFKC', doc[i].get_text())
        out.append(f"<<<PAGE {i+1}>>>\n" + t)
    dst = os.path.join('work', name)
    with open(dst, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(name, 'pages:', len(doc), 'bytes:', os.path.getsize(dst))
