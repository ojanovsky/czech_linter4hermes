# Kontrola češtiny pro LLM agenty (czech-text-lint)

Tvarová a gramatická brána českého textu — navržená tak, aby ji mohl používat
autonomní agent i člověk v terminálu. Offline, bez volaných API, bez nové RAM
navíc (kritik využívá ten samý lokální model, na kterém agent běží).

## ⚠️ Původ realizace

Tento kód, dokumentace i testy **realizoval autonomní agent Hermes** na modelu
Qwen3.8-Flash-Next (lokální vLLM), nikoli člověk. Postup byl průběžně měřen a
opravován — deterministické části mají regresní testy (`tests/run_tests.sh`),
gramatický kritik je z podstaty věci pravděpodobnostní — jeho výstupy jsou
vodítko, nikoli rozsudek. Berejte to jako funkční nástroj s dokumentovanými
limity, ne jako ručně broušený software.

## Tři vrstvy

| Vrstva | Co dělá | Cena |
|---|---|---|
| `scripts/czech_forms_check.py` | každý token proti lexikonu 3,14M platných českých tvarů (aspell-cs), výjimky z `allow.txt`; s `--negace` deterministicky hlídá povinnou dvojí negaci, s `--wiki` doplní frekvenci tvaru na cs.wikipedia (0× = výmysl modelu, ne termín) | <1 s offline, --wiki sítově |
| `scripts/czech_grammar_critic.py` | druhý průchod lokálním modelem: shoda, pádové řízení, atributiva, kalibry záporu z angličtiny | ~2–8 s, jen to, co kontrolor nemůže |
| `scripts/czech_lint_gate.py` | hook do Hermes `pre_tool_call`: blokuje zápis `.md`/`.txt`, dokud text neprošel oběma vrstvami | fail-closed |

Lexikon se staví z oficiálního balíku `aspell-cs` (návod v `doc/`), do RAM se
neláduje celý — SQLite se mapuje přes mmap.

## Rychlý start

```bash
# 1. postavit datovou sadu tvarů (viz doc/Kontrola češtiny.md, krok za krokem)
# 2. vyzkoušet na vlastním textu:
python3 scripts/czech_forms_check.py --negace muj-text.md
python3 scripts/czech_grammar_critic.py muj-text.md   # chce běžící model na :8000
# 3. regrese:
bash tests/run_tests.sh
```

## Struktura

```
SKILL.md            návod pro agenty (načítá se do Hermesu jako dovednost)
scripts/            kontrolor tvarů, kritik, brána
tests/              regresní sada + testovací věty
doc/                obsáhlejší návod ke zprovoznění a údržbě (snapshot)
allow.txt           výjimky pro plané poplachy (vlastní jména, termíny)
```

## Licence

MIT — viz [LICENSE](LICENSE). Datová sada tvarů se staví lokálně ze zdroje
`aspell-cs` a řídí se jeho licenčními podmínkami; samotné databázové soubory
součástí tohoto adresáře nejsou.
