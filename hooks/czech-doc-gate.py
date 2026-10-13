#!/usr/bin/env python3
"""Brána dokumentů: Hermes pre_tool_call hook — blokuje zápis .md/.txt, dokud text není čistý.

Vrstva 1: tvrdé nálezy tvarové brány (czech_lint_gate.Gate).
Vrstva 2: gramatický kritik (czech_grammar_critic) — obě vrstvy čtou text s
vynechaným obsahem citací („…“, "…", '…', `…`); selže-li model, necháme
projít s varováním na stderr (kritik je pravděpodobnostní, brána tvrdá).

Výstup: JSON {"action": "block", "message": ...} na stdout, jinak prázdno.
"""
import ast
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

SKILL = Path(os.environ.get(
    "CZECH_LINT_SKILL",
    os.path.expanduser("~/.hermes/skills/czech-text-lint")))
GATE = SKILL / "scripts" / "czech_lint_gate.py"
CRITIC = SKILL / "scripts" / "czech_grammar_critic.py"

DOC_SUFFIXES = {".md", ".txt"}
DOC_TOOLS = {"write_file", "patch", "memory", "terminal"}
# textová hodnota v argumentu patch, pokud ji volající zapsal jako python-literal
_PY_LITERAL_RE = re.compile(r"^\s*(?:[rbfu]{0,2})(?:'''|\"\"\"|'|\\\")")


def _block(msg):
    json.dump({"action": "block", "message": msg}, sys.stdout, ensure_ascii=False)
    sys.stdout.flush()
    sys.exit(0)


def _gate():
    sys.path.insert(0, str(GATE.parent))
    return __import__("czech_lint_gate").Gate()


QUOTE_PATS = (r"„[^“”]*“", r'"[^"\n]*"', r"'[^'\n]*'",
              r"`[^`\n]*`", r"<<[^>\n]*>>")


def _mask_citations(text):
    """Znepřístupni obsah citací (mezery, délka i řádky zachovány) — uvnitř
    nich jsou záměrně chybné příklady; pozice mimo ně sedí na originál."""
    chars = list(text)
    for pat in QUOTE_PATS:
        for m in re.finditer(pat, text):
            for i in range(m.start(), m.end()):
                if chars[i] != "\n":
                    chars[i] = " "
    return "".join(chars)


def _critic_findings(text):
    """-> (nalézt, ok). ok=False znamená selhání kritika (vLLM down, timeout…)."""
    try:
        p = subprocess.run(
            [sys.executable, str(CRITIC)], input=text,
            capture_output=True, text=True, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        return [], False
    if p.returncode not in (0, 1):  # 1 = nalezeno, 0 = čisto; 2+ = chyba
        return [], False
    findings = [ln for ln in p.stdout.splitlines() if ln.strip()]
    return findings, True


def _extract(payload):
    """-> list[(path, full_text_or_None, new_text)]. full None = kontroluj jen new_text (patch)."""
    tool = payload.get("tool_name")
    args = payload.get("tool_input") or {}
    out = []
    if tool == "write_file":
        out.append((args.get("path"), args.get("content"), args.get("content")))
    elif tool == "patch":
        new = args.get("new_string")
        if isinstance(new, str) and _PY_LITERAL_RE.match(new):
            try:
                new = str(ast.literal_eval(new))
            except (ValueError, SyntaxError):
                pass
        out.append((args.get("path"), None, new))
    elif tool == "memory":
        ops = args.get("operations") or ([args] if args.get("action") in
                                         ("add", "replace") else [])
        for op in ops:
            if isinstance(op, dict) and isinstance(op.get("content"), str):
                out.append((None, None, op["content"]))
    elif tool == "terminal":
        cmd = args.get("command") or ""
        pats = (r'--data-binary[ =]@?("[^"]+\.(?:md|txt)"|\S+\.(?:md|txt))',
                r'-d[ =]@?("[^"]+\.(?:md|txt)"|\S+\.(?:md|txt))',
                r'--upload-file[ =]@?("[^"]+\.(?:md|txt)"|\S+\.(?:md|txt))',
                r'-T[ =]@?("[^"]+\.(?:md|txt)"|\S+\.(?:md|txt))',
                r'\d?>{1,2}\s*("[^"]+\.(?:md|txt)"|\S+\.(?:md|txt))')
        files = set()
        for pat in pats:
            for m in re.finditer(pat, cmd):
                f = m.group(1).strip('"')
                files.add(f if f.startswith(("/", "~", "$HOME")) else
                          os.path.join(os.getcwd(), f))
        for f in files:
            p = Path(os.path.expandvars(os.path.expanduser(f)))
            if p.is_file():
                out.append((str(p), None, None))  # čti soubor ze disku
    return out


def main():
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name")
    if tool not in DOC_TOOLS:
        return
    items = _extract(payload)
    if not items:
        return
    try:
        gate = _gate()
    except Exception as e:
        print(f"czech-doc-gate: brána nedostupná ({e})", file=sys.stderr)
        sys.exit(2)  # fail-closed na tvrdost lexikonu
    problems = []
    for path, full, new_text in items:
        if full is None and path and new_text is None:
            try:
                full = Path(path).read_text(encoding="utf-8")
            except OSError:
                continue
        text = full if full is not None else (new_text or "")
        if not text.strip():
            continue
        suffix = Path(path).suffix.lower() if path else ""
        if path and suffix not in DOC_SUFFIXES:
            continue
        bare = _mask_citations(text)
        try:
            hard, _soft = gate.classify(bare)
        except Exception as e:
            print(f"czech-doc-gate: lexikon nedostupný ({e})", file=sys.stderr)
            sys.exit(2)
        for w, ln, col, why in hard[:12]:
            problems.append(f"  {w} ({ln}:{col}) — {why}")
        if hard:
            problems.append(f"  -> přepiš na platný tvar, nebo vlastní termín "
                            f"doplň do {SKILL / 'allow.txt'}")
            continue
        findings, ok = _critic_findings(bare)
        if not ok:
            print("czech-doc-gate: kritik nedostupný, pouštím bez gramatické "
                  "vrstvy", file=sys.stderr)
        else:
            for f in findings[:12]:
                problems.append(f"  {f}")
    if problems:
        _block("⛔ Kontrola češtiny — brána nalezla chyby:\n"
               + "\n".join(problems))
    return


if __name__ == "__main__":
    main()
