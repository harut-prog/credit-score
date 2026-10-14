"""Recreate the initial DVC dataset from a byte-verified public source mirror."""

import argparse
import csv
import hashlib
import urllib.request
from pathlib import Path

SOURCE_URL = (
    "https://raw.githubusercontent.com/JLZml/Credit-Scoring-Data-Sets/master/"
    "3.%20Kaggle/Give%20Me%20Some%20Credit/cs-training.csv"
)
SOURCE_SHA256 = "1bd46da486a5708c58c7b01a034fae2a13b327f6f7b62ea7ba4fe3b5824b24ac"
BASELINE_MD5 = "d7123f735b51ec6675c136a2a944aa25"


def make_baseline(original: bytes) -> bytes:
    if hashlib.sha256(original).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source CSV checksum changed")
    lines = original.decode("utf-8-sig").splitlines(keepends=True)
    reader = csv.DictReader(lines)
    keep = [lines[0]]
    removed = 0
    for line, row in zip(lines[1:], reader, strict=True):
        invalid = (
            row["NumberOfTime30-59DaysPastDueNotWorse"] in {"96", "98"}
            or row["NumberOfTime60-89DaysPastDueNotWorse"] in {"96", "98"}
            or row["NumberOfTimes90DaysLate"] in {"96", "98"}
            or float(row["age"]) == 0
        )
        if invalid:
            removed += 1
        else:
            keep.append(line)
    result = "".join(keep).encode("utf-8")
    if removed != 270 or hashlib.md5(result).hexdigest() != BASELINE_MD5:
        raise ValueError("Reconstructed CSV differs from the initial DVC version")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Use a downloaded source CSV")
    args = parser.parse_args()
    source = args.source.read_bytes() if args.source else urllib.request.urlopen(SOURCE_URL, timeout=120).read()
    result = make_baseline(source)
    target = Path("data/credit_score.csv")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(result)
    print(f"Restored {target}: md5={BASELINE_MD5}, rows=149730")


if __name__ == "__main__":
    main()
