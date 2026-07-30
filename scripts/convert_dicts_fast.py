#!/usr/bin/env python3
"""Convert only the fast formats first: StarDict, MDX, dicthtml, DOCX."""
import sys, os
sys.path.insert(0, "/home/z/my-project/scripts")
# Reuse the converter module but call parsers directly
import convert_dicts as cd
from pathlib import Path

# Limit CONVERSIONS to fast formats only
fast = [c for c in cd.CONVERSIONS if c[3] in (cd.parse_mdx, cd.parse_stardict, cd.parse_dicthtml_folder, cd.parse_docx)]
cd.CONVERSIONS = fast
cd.main()
