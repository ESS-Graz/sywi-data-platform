"""Normalize table-name case in the original SQL so it runs on
case-sensitive MySQL (Linux default). The SQL mixes `Teilnahme_AV`,
`Teilnahme_av`, `Master_Avi`, `Master_AVI`, `city3A` / `city3AV` / `city3Av`
etc. We lowercase every occurrence to a canonical form and emit a patched file.

Output tables A_DS / AVI_DS / I_DS are NOT touched — they're consistent.
"""

from __future__ import annotations

import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent.parent / "Alle_Queries_DE_hintereinander.sql"
DST = HERE / "Alle_Queries_patched.sql"

# Canonical lowercase name -> regex pattern (case-insensitive, word-bounded)
REPLACEMENTS = {
    "teilnahme_av":   r"\bTeilnahme_AV\b|\bTeilnahme_Av\b|\bTeilnahme_av\b",
    "master_avi":     r"\bMaster_Avi\b|\bMaster_AVI\b",
    "city3a":         r"\bCity3A\b|\bCity3a\b|\bcity3A\b",
    "city3av":        r"\bCity3Av\b|\bcity3Av\b|\bcity3AV\b",
    "city4i":         r"\bCity4I\b|\bcity4I\b",
    "city4isl":       r"\bCity4Isl\b|\bcity4Isl\b",
    "donation3a":     r"\bDonation3A\b|\bDonation3a\b|\bdonation3A\b",
    "donation3av":    r"\bDonation3Av\b|\bdonation3Av\b|\bdonation3AV\b",
    "donation4i":     r"\bDonation4I\b|\bdonation4I\b",
    "donation4isl":   r"\bdonation4Isl\b",
}


def main() -> None:
    text = SRC.read_text(encoding="utf-8", errors="replace")
    total = 0
    for canonical, pattern in REPLACEMENTS.items():
        text, n = re.subn(pattern, canonical, text)
        total += n
        print(f"  {canonical:14s}  {n:5d} replacements")
    DST.write_text(text, encoding="utf-8")
    print(f"\nTotal: {total} replacements")
    print(f"Wrote: {DST}")


if __name__ == "__main__":
    main()
