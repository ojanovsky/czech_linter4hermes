#!/usr/bin/env python3
"""Gramatický kritik češtiny — druhý průchod lokálním modelem (:8000).

Hledá jen to, co tvarový kontrolor nemůže: shodu (rod/číslo/pád), pádové
řízení a neshodná atributiva. Nepoužívá novou RAM — jen request na už
nahrané váhy, teplota 0.2 per-request.

Použití: czech_grammar_critic.py SOUBOR | text z stdin
Výstup: JSON čtenářsky přehledný řádky; exit 0 žádné nálezy, 1 nalezeno, 2 chyba.
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

API = os.environ.get("CZECH_LINT_API", "http://127.0.0.1:8000/v1/chat/completions").rstrip("/")
if not API.endswith("/chat/completions"):
    API += "/chat/completions"
MODEL = "q3.8-flash-next"
MAX_CHARS = 12000  # délka textu na jeden request (kontrola KV usage)
SPORNE = Path(__file__).resolve().parent.parent / "references" / "sporna-slova.md"

SYSTEM_BASE = (
    "Jsi korektor češtiny. V zadaném textu hledej JEN tyto chyby:\n"
    "1) porušená shoda (podmět-přísudek, přídavné jméno-podstatné: rod/číslo/pád),\n"
    "2) chybné pádové řízení (sloveso, předložka),\n"
    "3) neshodné atributivní určení a rodově nesprávné zájmeno (např. 'kniha... jeho'),\n"
    "4) chybná negace: české negativní zájmeno (nikdy, nic, nikdo, nikde, nikam, nijak) musí být spojeno se ZÁPORNOU formou slovesa s předponou ne-. Sloveso bez ne- spolu s 'nikdy/nic' za ním je anglický kalibr z 'never/no' a je chybný: tvar 'VĚT se DĚLÁ nikdy' → správně 'VĚT se nikdy NEDĚLÁ' (sloveso v negaci). Posuzuj KAŽDOU větu/díl věty samostatně — i za pomlčkou nebo čárkou; kladné sloveso + nikdy v témž dílu je chyba, i když sousední díl obsahuje 'ne' nebo 'nikdy nemažou'. Věta s dvojí negací v témž dílu ('nikdo nic neztratil') je správně.\n"
    "Nehledej: překlepy bez významu, styl, fakta, cizí slova, terminologii"
    " (výjimkou je jen seznam z pravidla 5).\n"
    'Vrať POUZE JSON pole objektů {"chyba": "...", "správně": "...", "typ": 1|2|3|4|5, "kde": "řádek:sloupec"}. '
    "Pokud nenajdeš nic, vrať []."
)


def _sporne_rule():
    """Pravidlo 5 generované ze seznamu sporných slov; prázdný soubor = žádné pravidlo."""
    try:
        seznam = SPORNE.read_text(encoding="utf-8").strip()
    except OSError:
        seznam = ""
    if not seznam:
        return ""
    return (
        "5) sporná slova: seznam níže uvádí slova s zakázanými a legitimními kolokacemi.\n"
        "   Flaguj (typ 5) POUZE výskyt padnoucí do zakázané kolokace; výskyt v legitimní\n"
        "   kolokaci nebo jinde nijak neopravovat. Rozhoduj podle sousedních slov,\n"
        "   ne podle pocitu. U každého nálezu uveď náhradu ze seznamu.\n"
        "SEZNAM SPORNÝCH SLOV:\n" + seznam + "\n"
    )


SYSTEM = SYSTEM_BASE.replace("Vrať POUZE", _sporne_rule() + "\nVrať POUZE")


def call(text):
    payload = {
        "model": MODEL,
        "temperature": 0.2,
        "max_tokens": 2048,
        # režim myšlení by rozepisováním paradigmat vyčerpal rozpočet bez
        # odpovědi; úzká korektorská úloha myšlenkový řetězec nepotřebuje
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": text[:MAX_CHARS]},
        ],
    }
    req = urllib.request.Request(
        API,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        msg = json.load(resp)["choices"][0]["message"]
    # reasoning model může vyčerpat rozpočet v řetězci 'reasoning'
    out = msg.get("content") or msg.get("reasoning") or ""
    # model může JSON obalit markdownem; najdi první [ ... ]
    start, end = out.find("["), out.rfind("]")
    if start != -1 and end > start:
        return json.loads(out[start:end + 1])
    # občas vrátí JEDEN objekt bez pole — tolerantní cesta
    start, end = out.find("{"), out.rfind("}")
    if start != -1 and end > start:
        return [json.loads(out[start:end + 1])]
    raise ValueError("model nevrátil JSON: " + out[:200])


def main():
    if len(sys.argv) > 1:
        try:
            text = open(sys.argv[1], encoding="utf-8").read()
        except OSError as e:
            print(f"chyba: {e}", file=sys.stderr)
            return 2
    else:
        text = sys.stdin.read()
    # záměrné příklady v backtickech jsou data, ne souvislý text — model je nesmí vidět
    # (bez vynechání je jeho mlčení jen štěstí; viz skill, claim o obou vrstvách)
    # náhrada jedním mezerovým znakem (ne mezerami na délku): dlouhé mezery model
    # čte jako vynechané slovo a hlásí je jako chybu shody
    text = re.sub(r"`[^`]*`", " ", text)
    try:
        findings = call(text)
    except Exception as e:
        print(f"chyba kritika: {e}", file=sys.stderr)
        return 2
    kept = []
    for f in findings:
        err = str(f.get("chyba", ""))
        # model občas zopakuje exemplář ze systémového promptu místo skutečnosti;
        # nálezy, jejichž text se ve vstupu nevyskytuje, zahazujeme
        if err and err.replace(" ", "") not in text.replace(" ", ""):
            print(f"zahozeno (není ve vstupu): {err!r}", file=sys.stderr)
            continue
        # no-op návrh (chyba a oprava jsou týž text) = model jen potvrdil, ne nález
        if err.strip() == str(f.get("správně", "")).strip():
            print(f"zahozeno (no-op): {err!r}", file=sys.stderr)
            continue
        kept.append(f)
    for f in kept:
        print(f"[{f.get('typ','?')}] {f.get('chyba','?')} → {f.get('správně','?')}  {f.get('kde','')}")
    return 1 if kept else 0


if __name__ == "__main__":
    sys.exit(main())
