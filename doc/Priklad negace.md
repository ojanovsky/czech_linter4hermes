# Příklad: kalibr záporu z angličtiny

Vzniklo v SilverBullet poznámce „Kontrola češtiny" — původem oprava věty
z diskuse o kompresi kontextu v Hermesu.

## Špatně (doslovný překlad anglického „your messages are never deleted")

```
Tvoje zprávy se kompresí mažou nikdy.
```

Chyba je ve stavbě věty, ne ve tvaru slov — všechna slova jsou platná,
kontrolor tvarů nemá co hlásit. Čeština vyžaduje dvojí negaci: negativní
zájmeno (`nikdy`, `nic`, `nikdo`, …) musí doprovázet negované sloveso
(`nemazou`, ne `mažou`). Pořadí slov roli nehraje.

## Správně

```
Tvoje zprávy se kompresí nikdy nemažou.
```

## Co na to vrstvy

| Vrstva | Výsledek na špatné verzi |
|---|---|
| `czech_forms_check.py` | projde (tvarově je vše v pořádku) |
| `czech_forms_check.py --negace` | flagne deterministicky, <0,1 ms, spolehlivě |
| `czech_grammar_critic.py` | najde přibližně ze dvou třetin (LLM, teplota 0,2) — vodítko, ne rozsudek |

Regresní data: `tests/data/t1_kalibr.txt` (špatně), `tests/data/neg2.txt`
(správně), `tests/data/t6_dash.txt` (varianta za pomlčkou).
