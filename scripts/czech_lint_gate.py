#!/usr/bin/env python3
"""Sdílená brána pro hooky: tvary češtiny přes SQLite, bez velkého RAM.

Klasifikuje neznámé tokeny na tvrdé (blokuj/pověz) a měkké (varování):
- měkké: ASCII slovo mimo lexikon — pravděpodobně technický termín
- tvrdé: písmo mimo češtinu (CJK, cyrilice, německé znaky), chybný tvar
  s českou diakritikou, nebo -orem přípona (halucinační instrumentál)
"""
import re
import sqlite3
from pathlib import Path

import os as _os

FORMS_DB = _os.path.expanduser("~/.local/share/czech-lint/cs.forms.sqlite")
ALLOW_TXT = Path(__file__).resolve().parent.parent / "allow.txt"
TOKEN_RE = re.compile(r"[^\W\d_]{2,}(?:-[^\W\d_]+)*", re.UNICODE)
CZECH = set("abcdefghijklmnopqrstuvwxyzábcčdďeéěfghiíjklmnňoňopqrŕřsstťuúůvwýyzž")
DIAC = CZECH - set("abcdefghijklmnopqrstuvwxyz")
# halucinační instrumentály: ASCII kořen + česká přípona, kterou lexikon nezná
MORPH_LEAK = ("orem", "ourem", "olem")


class Gate:
    def __init__(self, db_path=FORMS_DB):
        self.db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self.db.execute("PRAGMA mmap_size=67108864")  # 64MB líné mapování
        self.allow = set()
        if ALLOW_TXT.exists():
            self.allow = {l.strip().lower() for l in
                          ALLOW_TXT.read_text(encoding="utf-8").splitlines()
                          if l.strip() and not l.startswith("#")}

    def known(self, low):
        return self.db.execute(
            "SELECT 1 FROM forms WHERE form=?", (low,)).fetchone() is not None

    def classify(self, text):
        """-> (hard: [(slovo, řádek, sloupec, důvod)], soft: [(slovo, ř, s)])"""
        hard, soft = [], []
        for ln, line in enumerate(text.splitlines(), 1):
            spans = []
            for m in TOKEN_RE.finditer(line):
                spans.append((m.start(), m.end()))
                w = m.group(0)
                low = w.lower()
                if low in self.allow or self.known(low):
                    continue
                parts = [p for p in low.split("-") if p]
                if len(parts) > 1 and all(self.known(p) for p in parts):
                    continue
                alpha = {c for c in low if c.isalpha()}
                if alpha - CZECH:
                    hard.append((w, ln, m.start() + 1, "znak mimo české písmo"))
                elif alpha & DIAC:
                    hard.append((w, ln, m.start() + 1, "tvar s diakritikou mimo lexikon"))
                elif any(low.endswith(s) for s in MORPH_LEAK):
                    hard.append((w, ln, m.start() + 1, "chybný tvar s českou příponou"))
                else:
                    soft.append((w, ln, m.start() + 1))
            # jednopísmenkové úniky mimo tokeny (CJK znak sám o sobě)
            for col, ch in enumerate(line, 1):
                if ch.isalpha() and not ch.isascii() and ch.casefold() not in CZECH \
                        and not any(a <= col - 1 < b for a, b in spans):
                    hard.append((ch, ln, col, "únik znaku mimo češtinu"))
        return hard, soft
