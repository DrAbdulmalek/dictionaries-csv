#!/usr/bin/env python3
"""Extract all nested archives in the extracted folder."""
import os
import zipfile
import tarfile
import multivolumefile
import py7zr
import rarfile
from pathlib import Path

ROOT = Path("/home/z/my-project/dict_work/extracted/New Folder")
DEST_BASE = Path("/home/z/my-project/dict_work/unpacked")
DEST_BASE.mkdir(parents=True, exist_ok=True)


def safe_name(name: str) -> str:
    return name.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_").replace("\\", "_")


def extract_zip(src: Path, dest: Path):
    with zipfile.ZipFile(src) as z:
        z.extractall(dest)


def extract_7z(src: Path, dest: Path):
    # Multi-volume 7z files have parts .001, .002 — single-file 7z just has .7z
    if src.suffix == ".7z":
        # try multi-volume first (won't hurt if only one part)
        try:
            with multivolumefile.open(str(src), mode="rb") as target:
                with py7zr.SevenZipFile(target, "r") as z:
                    z.extractall(dest)
            return
        except Exception:
            pass
    with py7zr.SevenZipFile(src, "r") as z:
        z.extractall(dest)


def extract_rar(src: Path, dest: Path):
    with rarfile.RarFile(src) as rf:
        rf.extractall(dest)


ARCHIVES = [
    ("ArabicDictionariesOfBabylon.zip", "ArabicDictionariesOfBabylon", extract_zip),
    ("Longman Modern En-En-Ar.zip", "Longman_Modern_EnEnAr_zip", extract_zip),
    ("dicthtml-en-ar.zip", "dicthtml_en_ar", extract_zip),
    ("Longman Modern En-En-Ar.rar", "Longman_Modern_EnEnAr_rar", extract_rar),
    ("Oxford Arabic Dictionary.7z", "Oxford_Arabic_Dictionary_1", extract_7z),
    ("Oxford Arabic Dictionary (En-Ar).7z", "Oxford_Arabic_Dictionary_EnAr", extract_7z),
]


for src_name, dest_name, fn in ARCHIVES:
    src = ROOT / src_name
    dest = DEST_BASE / dest_name
    if dest.exists():
        print(f"[skip] {src_name} -> already extracted to {dest}")
        continue
    dest.mkdir(parents=True, exist_ok=True)
    print(f"[extract] {src_name} -> {dest}")
    try:
        fn(src, dest)
        print(f"  OK")
    except Exception as e:
        print(f"  ERROR: {e}")

print("\n--- Final unpacked layout ---")
for root, dirs, files in os.walk(DEST_BASE):
    level = root.replace(str(DEST_BASE), "").count(os.sep)
    indent = "  " * level
    print(f"{indent}{os.path.basename(root)}/")
    for f in sorted(files)[:20]:
        size = os.path.getsize(os.path.join(root, f))
        print(f"{indent}  {size:>10}  {f}")
    if len(files) > 20:
        print(f"{indent}  ... and {len(files)-20} more files")
