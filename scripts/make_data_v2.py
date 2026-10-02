"""Create the second DVC dataset without changing valid source records."""

import csv
import hashlib
from pathlib import Path


def main() -> None:
    path = Path("data/credit_score.csv")
    original = path.read_bytes()
    lines = original.decode("utf-8-sig").splitlines(keepends=True)
    if len(lines) < 2:
        raise RuntimeError("Dataset is empty")

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

    if removed != 270:
        raise RuntimeError(f"Expected 270 invalid rows, found {removed}; V1 may not be checked out")

    updated = "".join(keep).encode("utf-8")
    path.write_bytes(updated)
    print(f"V1 rows={len(lines) - 1} md5={hashlib.md5(original).hexdigest()}")
    print(f"V2 rows={len(keep) - 1} removed={removed} md5={hashlib.md5(updated).hexdigest()}")


if __name__ == "__main__":
    main()
