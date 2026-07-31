#!/usr/bin/env python3
"""Concatenate OCR chunk CSVs into a single final CSV.

Reads chunk1.csv ... chunkN.csv (each with same schema:
id,term,definition,source_file), strips per-chunk 'id' column,
re-numbers sequentially, deduplicates, and writes the merged result.
"""
import csv
import sys
from pathlib import Path

def main(chunk_dir: str, output_csv: str):
    chunk_paths = sorted(Path(chunk_dir).glob("chunk*.csv"))
    if not chunk_paths:
        print(f"No chunk*.csv files in {chunk_dir}", file=sys.stderr)
        sys.exit(1)

    all_entries = []
    seen = set()
    for cp in chunk_paths:
        with open(cp, encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                term = (row.get("term") or "").strip()
                definition = (row.get("definition") or "").strip()
                source = (row.get("source_file") or "").strip()
                if not term or not definition:
                    continue
                key = (term.lower(), definition)
                if key in seen:
                    continue
                seen.add(key)
                all_entries.append({
                    "term": term,
                    "definition": definition,
                    "source_file": source,
                })

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "term", "definition", "source_file"])
        for i, e in enumerate(all_entries, start=1):
            writer.writerow([i, e["term"], e["definition"], e["source_file"]])

    print(f"Merged {len(chunk_paths)} chunks → {output_csv}")
    print(f"Total entries: {len(all_entries)}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <chunk_dir> <output_csv>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
