"""Make Microsoft's AdventureWorks CSVs readable by Postgres COPY.

    python scripts/convert_csvs.py data/download/microsoft/extracted

A line-by-line Python port of update_csvs.rb from lorint/AdventureWorks-for-Postgres
(MIT licence, Lorin Thwaits), so you don't need Ruby installed. It edits the CSVs in place.

Why it's needed: Microsoft ships some files with "+|" as the column separator and "&|" as the
row end (because the text inside contains tabs and newlines), a byte-order mark at the start,
and binary values (GIF images, map points) as bare hex. This turns them into tab-separated CSV
that `\\copy ... DELIMITER E'\\t' CSV` accepts. Files that are already fine are left alone.
"""

from __future__ import annotations

import sys
from pathlib import Path

WS = " \t\n\v\f\r"


def ruby_strip(s: str) -> str:
    # Ruby's String#strip drops trailing NULs as well as whitespace, but keeps a leading NUL.
    return s.lstrip(WS).rstrip(WS + "\0")


def quote_part(part: str) -> str:
    if part[:1] == "<" and part[-1:] == ">":
        return '"' + part + '"'
    if part[1:2] == "<" and part[-1:] == ">":
        return '"' + part[1:] + '"'
    if "\t" in part:
        return '"' + part + '"'
    return part


def convert(path: Path) -> bool:
    try:
        lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        return False  # the Ruby script skips files it can't read as UTF-8; so do we

    if not lines:
        return False
    first = lines[0]
    is_needed = is_pipes = is_cleaning = False
    if "+|" in first:
        is_pipes = is_needed = is_cleaning = True
    if first.startswith("\ufeff"):
        lines[0] = first = first[1:]
        is_needed = True
    if "&|" in first or "\tE6100000010C" in first:
        is_needed = is_cleaning = True
    if not is_needed:
        return False

    out: list[str] = []
    text = ""
    for line in lines:
        if is_pipes:
            line = line.replace("|474946383961", "|\\x474946383961").replace('"', '""')  # GIF data
            while (end := line.find("&|")) != -1:
                text += ruby_strip(line[:end])
                parts = []
                for i, part in enumerate(text.split("+|")):
                    # A hierarchyid can be a real NUL character; Postgres text can't hold NULs.
                    part = "00" if (i == 0 and part == "\0") else part.replace("\0", "")
                    parts.append(quote_part(part))
                out.append("\t".join(parts) + "\n")
                text = ""
                line = line[end + 2:]
            if line.strip(WS):
                text += line.replace("\r\n", "\\n").replace("\n", "\\n")
        elif is_cleaning:
            out.append(
                line.replace('"', '""')
                .replace("&|\n", "\n")
                .replace("&|\r\n", "\n")
                .replace("\tE6100000010C", "\t\\xE6100000010C")  # map points
                .replace("\r\n", "\n")
            )
        else:
            out.append(line)

    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes("".join(out).encode("utf-8"))
    tmp.replace(path)
    return True


def main() -> int:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    folder = Path(sys.argv[1])
    files = sorted(folder.glob("*.csv"))
    if not files:
        sys.exit(f"no CSV files in {folder}")
    changed = [f.name for f in files if convert(f)]
    print(f"{len(files)} CSV files checked, {len(changed)} converted: {', '.join(changed)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
