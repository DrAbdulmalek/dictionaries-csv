#!/usr/bin/env python3
"""Extract a multi-volume 7z archive using py7zr + multivolumefile."""
import os
import multivolumefile
import py7zr

SRC_BASE = "/home/z/my-project/upload/New Folder.7z"   # multivolumefile appends .001, .002, ...
DEST = "/home/z/my-project/dict_work/extracted"

os.makedirs(DEST, exist_ok=True)
print(f"Source base: {SRC_BASE}")

with multivolumefile.open(SRC_BASE, mode="rb") as target:
    with py7zr.SevenZipFile(target, "r") as z:
        names = z.getnames()
        print(f"Total entries: {len(names)}")
        print("--- Listing ---")
        for n in names:
            print(" ", n)
        print("--- Extracting to", DEST, "---")
        z.extractall(DEST)

print("Done.")
