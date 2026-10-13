#!/usr/bin/env python3
"""Ověří české textové tvary proti rozbalené morphologické mřížce aspell-cs.

Použití: czech_forms_check.py SOUBOR | text z stdin
Výstup: jeden řádek na každý podezřelý token:
  'SLOVO\třádek:sloupec\tnávrhy: a, b, c'  (návrhy jsou reálné tvary z diktu)
Návratový kód: 0 = vše ok, 1 = nalezeny neznámé tvary, 2 = chyba.
"""
import difflib
import re
import sqlite3
import sys

import os

FORMS = os.path.expanduser("~/.local/share/czech-lint/cs.forms.sqlite")


class Forms:
    """Množina tvarů přes mmap SQLite — do RAM neláduje nic (srov. gate)."""

    def __init__(self, path):
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.db.execute("PRAGMA mmap_size=67108864")  # 64MB líné mapování

    def __contains__(self, word):
        return self.db.execute(
            "SELECT 1 FROM forms WHERE form=?", (word,)).fetchone() is not None
# token = posloupnost Unicode písmen (2+), volitelně s vnitřními pomlčkami (např. 'ne-jsem')
TOKEN_RE = re.compile(r"[^\W\d_]{2,}(?:-[^\W\d_]+)*", re.UNICODE)

# abeceda pro editaci: běžná písmena; fonetické záměny řeší předpis (_variants)
ALPHA = "abcdefghijklmnopqrstuvwxyzábcčdďeéěfghiíjklmnňoopqrŕřsstťuúůvwyýzž"
PHON = [("q", "k"), ("w", "v"), ("x", "ks")]
MAX_SUGG = 5
BRANCH = 400         # kolik kandidátů 1. úrovně rozvětvit do 2. úrovně
_SUGG_CACHE = {}


def _variants(word):
    """Foneticky přepsaná podoby slova (q→k atd.), jinak identické slovo."""
    out = {word}
    for bad, good in PHON:
        if bad in word:
            out.add(word.replace(bad, good))
    return out


def _edits(w):
    """Všechny jedné editace od w (smazání, záměna, transpozice, vložení)."""
    n = len(w)
    seen = set()
    for i in range(n):
        seen.add(w[:i] + w[i + 1:])
        for c in ALPHA:
            seen.add(w[:i] + c + w[i + 1:])
        if i + 1 < n:
            seen.add(w[:i] + w[i + 1] + w[i] + w[i + 2:])
    for i in range(n + 1):
        for c in ALPHA:
            seen.add(w[:i] + c + w[i:])
    seen.discard(w)
    return seen


def suggest(word, forms):
    """Nejbližší platné tvary v editdistanci 1, pak 2; přes fonetické přepisy.

    Do 2. úrovně rozvětvíme kandidáty 1. úrovně: všemi smazy (kryjou cestu
    dva smazy nebo smaz+záměna, např. vakuumový→vakumový→vakuový) a omezenou
    dávkou záměn (BRANCH), aby expanze nenarostla na miliony.
    """
    low = word.lower()
    if low in _SUGG_CACHE:
        return _SUGG_CACHE[low]
    seeds = {s for s in _variants(low) if s}
    cur = seeds
    res = []
    for level in (1, 2):
        nxt = set()
        for s in cur:
            nxt |= _edits(s)
        nxt -= seeds
        hits = [f for f in nxt if f in forms]
        if hits:
            res = sorted(
                hits,
                key=lambda f: (-difflib.SequenceMatcher(None, low, f).ratio(), len(f)),
            )[:MAX_SUGG]
            break
        if level == 1 and nxt:
            n = len(low)
            dels = [s for s in nxt if len(s) == n - 1]
            subs = [s for s in nxt if len(s) == n][:BRANCH]
            cur = dels + subs
    _SUGG_CACHE[low] = res
    return res


def check_text(text, forms):
    problems = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for m in TOKEN_RE.finditer(line):
            word = m.group(0)
            low = word.lower()
            ok = low in forms
            # pomlčkové složeniny (např. 'ne-jsem') zkusit díl po dílu
            parts = [p for p in low.split("-") if p]
            if not ok and len(parts) > 1:
                ok = all(p in forms for p in parts)
            if not ok:
                sug = suggest(word, forms)
                if word[0].isupper() and sug:
                    sug = [s.capitalize() for s in sug]
                problems.append((word, lineno, m.start() + 1, sug))
    return problems


def check_negation(text):
    """Deterministická pojistka proti negačnímu kalibru z angličtiny.

    Věta obsahující negativní zájmeno (nikdy/nic/nikdo/nikde/nikam/nijak/nikoli)
    a žádný token s předponou ne- (ani výjimky 'bez'/'ani') bývá presunutá
    anglická stavba 'are never X' místo české 'X se nikdy neděje'. Varování,
    ne rozsudek — dvojí negace a nominální věty ('Nikdy bez tebe') mají nízké
    FP díky výjimkám; jistotu dává až kontext.
    """
    NEG_PRON = {"nikdy", "nic", "nikdo", "nikoho", "nikde", "nikam", "nijak",
                "ničeho"}  # 'nikoli' záměrně ne — je to sám záporovací spojovací výraz
    findings = []
    for lineno, line in enumerate(text.splitlines(), 1):
        for sent_start, sentence in _sentences(line):
            # záměrné příklady v backtickech jsou data, ne proza — nemůžou triggerovat
            sentence = re.sub(r"`[^`]*`", " ", sentence)
            toks = [m.group(0).lower() for m in TOKEN_RE.finditer(sentence)]
            if not any(t in NEG_PRON for t in toks):
                continue
            if any(t.startswith("ne") and len(t) > 2 for t in toks):
                continue
            if any(t in ("bez", "ani") for t in toks):
                continue
            col = line.lower().find(sentence.strip()[:12]) if sentence.strip() else 0
            findings.append((lineno, max(col, 1) + sent_start, sentence.strip()[:80]))
    return findings


def _sentences(line):
    """Hrubé dělení na věty; vrací (offset, věta) pro pozici v řádce."""
    parts = re.split(r"([.!?])", line)
    out, pos, buf = [], 0, ""
    for p in parts:
        if p and len(p) == 1 and p in ".!?":
            buf += p
            if buf.strip():
                out.append((pos, buf))
            pos += len(buf)
            buf = ""
        else:
            buf += p
    if buf.strip():
        out.append((pos, buf))
    return out


def main():
    argv = [a for a in sys.argv[1:] if a != "--negace"]
    neg_on = "--negace" in sys.argv[1:]
    try:
        forms = Forms(FORMS)
    except sqlite3.Error as e:
        print(f"chyba: nelze načíst slovní tvarů: {e}", file=sys.stderr)
        return 2
    if argv:
        try:
            text = open(argv[0], encoding="utf-8").read()
        except OSError as e:
            print(f"chyba: {e}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()
    problems = check_text(text, forms)
    for word, lineno, col, sug in problems:
        tail = "\tnávrhy: " + ", ".join(sug) if sug else "\tnávrhy: (žádný v distanci 2)"
        print(f"{word}\t{lineno}:{col}{tail}")
    if neg_on:
        for lineno, col, sent in check_negation(text):
            print(f"NEGACE\t{lineno}:{col}\tvarování: zájmeno bez negovaného slovesa — zkontroluj větu: {sent!r}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
