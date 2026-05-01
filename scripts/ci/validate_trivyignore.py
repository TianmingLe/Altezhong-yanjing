from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_EXPIRES_RE = re.compile(r"^#\s*expires:\s*(\d{4}-\d{2}-\d{2})\s*$")
_REASON_RE = re.compile(r"^#\s*reason:\s*(.+?)\s*$")


@dataclass(frozen=True)
class IgnoreBlock:
    reason_line: int
    expires_line: int
    expires: date
    entry_line: int
    entry: str


def _parse_date(s: str, line_no: int) -> date:
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise ValueError(f"Invalid expires date at line {line_no}: {s}") from e


def _is_entry(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith("#"):
        return False
    return True


def parse_blocks(lines: list[str]) -> list[IgnoreBlock]:
    blocks: list[IgnoreBlock] = []
    last_reason: tuple[int, str] | None = None
    last_expires: tuple[int, date] | None = None

    for i, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        m_reason = _REASON_RE.match(line)
        if m_reason:
            last_reason = (i, m_reason.group(1))
            continue

        m_expires = _EXPIRES_RE.match(line)
        if m_expires:
            last_expires = (i, _parse_date(m_expires.group(1), i))
            continue

        if not _is_entry(line):
            continue

        if last_reason is None or last_expires is None:
            raise ValueError(
                f"Ignore entry at line {i} must be preceded by # reason: and # expires:"
            )

        blocks.append(
            IgnoreBlock(
                reason_line=last_reason[0],
                expires_line=last_expires[0],
                expires=last_expires[1],
                entry_line=i,
                entry=line.strip(),
            )
        )
        last_reason = None
        last_expires = None

    return blocks


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(".trivyignore")
    if not path.exists():
        return 0

    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks = parse_blocks(lines)
    today = date.today()

    expired = [b for b in blocks if b.expires < today]
    if expired:
        msg_lines = ["Expired .trivyignore entries:"]
        for b in expired:
            msg_lines.append(
                f"- line {b.entry_line} ({b.entry}) expired at {b.expires.isoformat()} (expires line {b.expires_line})"
            )
        sys.stderr.write("\n".join(msg_lines) + "\n")
        return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
