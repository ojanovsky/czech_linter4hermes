---
name: czech-text-lint
description: Use when producing or verifying Czech text — offline word-form checker (aspell-cs, 3.1M tvarů) + online sources for meaning/úzus.
---

# Kontrola českých textů

## Lokální tvarový kontrolor (offline, <1 s)

```
python3 ~/.hermes/profiles/quido/skills/czech-text-lint/scripts/czech_forms_check.py SOUBOR
# nebo text na stdin
```

## Druhá vrstva: gramatický kritik (shoda, řízení)

```
python3 ~/.hermes/profiles/quido/skills/czech-text-lint/scripts/czech_grammar_critic.py SOUBOR
```

- Druhý průchod přes lokální :8000 (q3.8-flash-next), temp 0.2, JSON nálezů — žádné nové RAM (stejné váhy). ~8 s na ~2,5 kB textu; čistý text odbaví za <1 s. Endpoint přepneš přes `CZECH_LINT_API` (výchozí `http://127.0.0.1:8000/v1`; pro serverovou vLLM nastav `http://10.193.1.181:8000/v1`).
- `chat_template_kwargs: {"enable_thinking": false}` je POVINNÝ: s myšlenkovým řetězcem model vyčerpá max_tokens rozepisováním paradigmat a vrátí prázdno (naměřeno: 98 s exit 0 bez něj, 4,3 s s nálezy s ním).
- Chytá, co kontrolor tvarů nemůže: rodová shoda (velká stůl), pádové řízení (pod ni → pod ní), chybné číslo (pod úhlem tři stupně → tří stupňů) — vše reálně zachyceno na textech, které tvarový kontrolor už propustil.
- Šum: ~1 planý poplach na delší text ("několik potvrzuje" hlášeno jako chyba, věta je správně). Typ 3 (attributiva) bývá hraniční. Brát jako varování, po opravě znovu pustit tvarový kontrolor.

- Výstup modelu se parsuje tolerantně: pole i jeden samostatný objekt (model občas vrátí `{...}` bez hranatých závorek — dříve exit 2).

Vypíše podezřelé tokeny jako `SLOVO\třádek:sloupec\tnávrhy: a, b, c` — od vrstvy 3 nabízí i nejbližší platné tvary (edit distance ≤2, fonetické přepisy q→k/w→v/x→ks, cache přes uniq tokeny; ~5 s na 200 flagů).
- Datová sada: `~/.local/share/czech-lint/cs.forms.sqlite` — lexikon kontroloru i brány (plně rozbalená paradigmat ze slovníku **aspell-cs 0.51**, zdroj KV HIL, 3,14M tvarů UTF-8; PRAGMA mmap, do RAM se jako celek neláduje). Zdrojový text `cs.forms.sorted.txt`, stažený z .deb bez roota (viz Aktualizace dat).
- **Nikdy neřeš českou morfologii přes `pip install pyMor`** — na PyPI je to knihovna model order reduction; český pyMor ani morphoita na PyPI ani GitHub nejsou. Oficiální rozbalená paradigmat existují jen v aspell-cs diktu — použij rovnou ten.
- Navrhování kandidátů: řetězec→kandidáti generuj editacemi a-membership v SQLite lexikonu (mmap); **nikdy nepoužívej filtr `all(c in it for c in ...)` přes iterátor na LCS-like heuristiku** — při neshodě spotřebuje celý kandidát a najde jen podposloupnosti (bug: vakuumový→vakuový zmizel). Větv do 2. úrovně všechny smazy + BRANCH záměn.
- Chybí-li odborný termín v diktu celou škálou tvarů (ikonoskop), je flag planý poplach i přesto, že suggestion engine vrátí vzdálenou podobu (monoskop) — řeš online (SSČ/foniie), ne přepisem. Kontrolor je bag-of-forms: neshody typu 'velká stůl' nelze chytit (potřeba vrstva 4, analyzátor s kategoriemi — na PyPI nic, et-nlp/ajthpy neexistují). Rešerše na PyPI je mrtvá větev i pro analyzátor shody (et-nlp/ajthpy/ajTH tam nejsou; distribuce těch analyzátorů je Java/C++ — před zakládáním práce na tom ověř aktuální stav).
- Tokenizace: pro česká slova používej `[^\W\d_]+` (Unicode písmena); ručně psaná třída `[A-Za-zÁa-z...]` láme tokeny na diakritice a produkuje falešné flagy. Skryté neviditelné znaky (měkká pomlčka U+00AD) token rozbijí na dva platné tvary a bránou projdou bez povšimnutí — při úpravě textu přes patch zkontroluj `grep -c $'\u00ad' SOUBOR`.
- Ručně psaná ABECEDA pro editaci kandidátů musí obsahovat ě — chybějící ě v ALPHA způsobila, že `shromazdili→shromáždili` nešlo najít (v obou skriptech bylo vynecháno, opraveno). Ověř `ě in ALPHA` při jakékoli úpravě množiny písmen.
- Kontrolor chytá i halucinované tvary generované modelem (např. *rakvací* místo *řádkovací*) — proklepni jím vlastní výstup před odesláním.
- **Text bez diakritiky kontrolorem skoro projde** — tvary bez háček/čárek jsou často platná slova, generace může diakritiku ztratit celou. Před tvarovou kontrolou proto spočítej diakritiku: `grep -o '[áčďéěíňóřšťúůýž]' SOUBOR | wc -l`; nula nebo minimum u českého textu = přepsat draft, ne flagovat jednotlivá slova.
- ignoruje čísla; velikost písmen řeší dolováním; pomlčkové složeniny díl po dílu

### Workflow po nálezu
Flagnutý tvar má tři kategorie — rozhoduj dokladem, ne dojmem:
1. překlep → návrh kontroloru sedí do kontextu → přepsat a znovu spustit, dokud exit 0
2. cizí/technický termín (`vLLM`, *RAGFlow*) nebo vlastní jméno → ponechat; opakující se nálezy dej do `allow.txt` — čtou ji nyní i kontrolor, ne jen brána
3. výmysl bez cizí stopy (český základ + česká koncovka, např. `odklapka` z 'flaps') — česky vypadající tvar není odborný termín jen proto, že vypadá česky; ani existence podobného slova v návrzích (monoskop) nic nedokazuje. Rozhodne frekvence výskytu: `czech_forms_check.py --wiki` přidá ke každému flagnutému tvaru štítek `wiki: N×` z cs.wikipedia (přesný dotaz na slovo; akronyma a camelCase se neptají). N=0 → výmysl → nahradit ustáleným názvem z článku na cs.wiki nebo ze SSČ, ponechat nelze. N>0 → termín existuje, ponechat a přidat do allow.txt. Měřeno 2026-10-13: odklapky 0×, ikonoskop 8×, Fowlerova 28×.

## Psaní rovnou pro bránu (memory, write_file/patch na *.md|*.txt)

- Skloňuj cizí termíny opatrně: pádové tvary anglických výpůjček s koncovkou `-ů` (`turnů`, `skillů`, `tasků`) a odvozeniny (`logování`, `dočitelný`, `embeddování`) v lexikonu nejsou → tvrdý flag. Použij český ekvivalent (výměn, úkolů, výstupy příkazů) nebo ponech termín v prvním pádě.
- Přídavná jména s cizím základem za pomlčkou (`RSA-šifrovaným`) padají na znaku mimo české písmo → rozepiš na předložkový opis (heslo šifrované RSA).
- Kritický kontext kontroluje i víceslovní shodu: „ne ve prahu“ → ne až na prahu.
- Nahrazuješ-li starší záznam paměti (pořízený před bránou), musí nový text projít celý — hovorové tvary z originálu (`lézení`) při konsolidaci přepiš.
- Zamítnutý zápis nezanechá částečný soubor: patch na soubor, který write_file nevytvořil, selže na čtení → oprav slova a přepiš soubor celý znovu.
- Samotný text skillu podléhá bráně taky — záměrně chybné příklady piš vždy do uvozovek nebo do kódového formátování, kurzíva je nechrania.
- Veřejné texty (README, doc) pouštěj bránou PŘED commitem — očekávej opakované zamítnutí vlastního textu: brána chytala chyby v našem README (chybějící čárka před vedlejší větou „jen to, co…“, pasivum složeného množného podmětu). Náraz do zdi znamená překlep v mém textu, nikoli vadnou bránu.
- Řídká cizí slova a jejich tvary (`negační`, `repozitáře`) v aspell diktu nejsou → tvrdý flag; přepis na obecnější český ekvivalent nebo doplnění do `allow.txt`.
- Sporná slova (významově zaměnitelná, tvarově platná — `rozchod` ve smyslu zprovoznění) NEMAJÍ být odrážkou v tomto skillu, ale záznamem v `references/sporna-slova.md`. Kritik je načítá do promptu jako pravidlo 5. Záznam musí mít rozepsané kolokace (zakázané / legitimní / náhrada): pouhé sémantické pravidlo („posuzuj význam") model na této mašině ignoroval a flagoval i legitimní použití; rozepsané kolokace daly 3/3 správně, 0/3 planě (2026-10-13). Nové opravy uživatelova slova tedy: najít rozdíl významů → zapsat záznam do seznamu, ne odrážku.
- Adresář skillu je git repo s remote na GitHubu — po úpravě skriptů, SKILL.md i doc/ udělej commit a push; snapshot dokumentu v `doc/` se řídí pravidlem: zdroj pravdy je SilverBullet poznámka, git kopie je obecná veřejná verze bez strojových identifikátorů.

## Online ověřování významu a úzu (jen na vyžádání / po flagu)

- **ÚJČ Internetová jazyková příručka** — https://prirucka.ujc.cas.cz (kanonické řešení pochybností o tvaru i pravopisu)
- **SSČ výkladový slovník** — kodex.cz (význam, kolokace)
- **foniie.cz** — https://foniie.cz/1/hledat?q=WORD (úplné paradigma: skloňování/časování ke každému heslu; nejlepší na 'existuje vůbec tenhle tvar?')

Použij web_extract, jen když lokální kontrolor flagne slovo, u kterého nejsi jistý, nebo když jde o význam/výslovnostní otázku.

- **České odborné názvy cizích pojmů** (localizer → kurzový maják/lokalizér, glideslope → sestupový maják): obecné slovníky je neobsahují — ověřit na cs.wikipedia.org (článek k tématu). Flagnutý odborný termín ≠ chyba; halucinovaný výmysl (kluzáve) se nahradí ustáleným názvem z článku. Obsah textu piš z modelu, na web jen pro ověření termínu/čísla — user schvaluje jako křížovou kontrolu, ne jako zdroj pravdy.

## Aktivní vynucení — rozdělené vrstvy (Hermes hooks, nasazeno 2026-10-13 na tomto stroji)
- **Chat (každá odpověď, <1 s):** plugin `~/.hermes/profiles/quido/plugins/czech-lint-chat/` na `transform_llm_output` — tvrdé nálezy připojí tag `⚠ Kontrola češtiny:` za odpověď, měkké jen log `$HERMES_HOME/logs/czech-lint-chat.log` (JSONL). Žádný model navíc. Kopie pro repozitář: `plugins/czech-lint-chat/` ve skillu. Bloky kódu, inline kód a URL se maskují.
- **Dokument (blokuje do čistého):** shell hook `pre_tool_call` → `~/.hermes/agent-hooks/czech-doc-gate.py` (config: hooks.pre_tool_call, matcher `write_file|patch|memory|terminal`, timeout 240, fail_closed false — lexikon/chybějící DB blokuje přes exit 2, nedostupný kritik pouští s varováním). Cílí write_file/patch na *.md|*.txt, memory operace a `curl --data-binary @soubor(.md|.txt)` / redirect do .md|.txt v terminalu. Obě vrstvy čtou text s vynechaným obsahem citací („…“, `…`, "…", '…'). Kopie ve skillu: `hooks/czech-doc-gate.py`.
- **Test hooku:** `hermes hooks test pre_tool_call --payload-file X` — v payload souboru se argumenty píší pod klíčem `args` (ne `tool_input`). `hermes hooks doctor` ověří existenci, executable bit a allowlist. Změna configu nabíhá až v nové session. `CZECH_LINT_API` se v `hooks test` nenačítá z .env — exportuj ručně, live session ji má z .env profilu.
- **Brána `scripts/czech_lint_gate.py`:** SQLite lexikon `~/.local/share/czech-lint/cs.forms.sqlite` (64 MB, `INSERT` z .txt trvá 2 s, PRAGMA mmap 64 MB — rezidentní proces tak platí jen page cache, reclaimable; namísto frozenset 300+ MB). Třídí: znak mimo české písmo / tvar s diakritikou mimo lexikon / ASCII kořen+`orem|ourem|olem` = tvrdé; ASCII mimo lexikon = měkké (technický termín). Výjimky na plané poplachy: `~/.hermes/profiles/quido/skills/czech-text-lint/allow.txt` (jméno na řádek, malými písmeny).
- Consent: `~/.hermes/profiles/quido/shell-hooks-allowlist.json` (event+command přesně); na netty lze záznam napsat ručně s `approved_at` ISO, jinak TTY prompt při prvním startu.
- Ochranu citací implementovat maskováním obsahu na mezery (pozice, řádky i délka zůstávají), ne výběrem mimo citace — pozici `řádek:sloupec` generuje model a bývá posunutá; maskování je pozicově nezávislé a chrání obě vrstvy stejně.
- Známa dira: `open(..., "w")` uvnitř `execute_code` bránou neprojde — hook visí na volání nástrojů, ne na Pythonu samotném. Přesměrování `echo … > soubor.md` v terminalu už detekována je (stejně tak curl -T/-d/--upload-file). Dokumenty proto piš přes write_file/patch; zapisuješ-li přesto mimo hook (kernel, skript), ověř výsledek ručně oběma vrstvami (tvary + kritik).

## Negation check

- `czech_forms_check.py --negace`: warns when a sentence has a negative pronoun (nikdy/nic/nikdo/nikde/nikam/nijak/ničeho) and no `ne-` word anywhere. Deterministic, <0.1 ms, opt-in (NOT in the gate — verbless sentences warn falsely).
- Works because mandatory double negation is order-independent: presence of `ne-` is a necessary condition, no parsing needed. Order-dependent rules (agreement, government) need the LLM critic.
- Critic rule type 4 flags negation calques ("VĚT se DĚLÁ nikdy" ← "is never VĚD") — BEST-EFFORT only: measured ~2/3 recall on a single calque sentence (temp 0.2) and occasional false positives on long docs (word-order nitpicks in correct double-negation sentences). `--negace` is the reliable detector for this class; treat critic type-4 hits as leads, not verdicts.
- Critic output guards (added after hallucination observed): findings whose error text is absent from the input are dropped, as are no-op findings (error == suggestion). Backtick spans are stripped from critic input before the model call.

## Známé limity
- Negace: obě vrstvy byly původně slepé k anglickému kalibru ("mažou nikdy" z "are never deleted") — od 2026-10-13 chytají: kritik má pravidlo typu 4 (záporné zájmeno bez negovaného slovesa, posuzuje se každý díl věty zvlášť, i za pomlčkou) a `czech_forms_check.py --negace` dává deterministické varování (zájmeno + žádné ne- slovo ve větě; výjimky bez/ani, dvojí negace čistá). FP pozor: nominální věty typu "Nic nového." varují planě — proto volitelný přepínač, mimo bránu.
- Negace: tvarový kontrolor i gramatický kritik to chytit neumí (měřeno 2026-10-13: "mažou nikdy" kritikem prošlo za 0,4 s čistě, přitom tentýž kritik chytá rodovou shodu a řízení) — anglický kalibr typu "mažou nikdy" (z "are never deleted") projde celou branou. Negativní zájmena (nikdy, nic, nikdo, nikde) vyžadují negovaný slovesný tvar: "nikdy se nemažou". Při překladu z angličtiny auditovat každou větu s never/no/none ručně.
- Chybí vlastní jména a čerstvé neologismy → plané poplachy, viz workflow.
- Jednotky a římské číslice (MHz, Hz, II, III) procházejí tokenizací jako slova → vždy plané flagy, ignoruj.
- Kontrolor je bag-of-forms: ověří tvar proti lexikonu, ne shodu — 'velká stůl' projde, protože oba tvary zvlášť existují; rodovou a číslovnou shodu posuzuj ručně (nebo druhým nízkoteplotním průchodem modelu).
- Aktualizace dat (bez roota): `apt-get download aspell-cs && dpkg -x aspell-cs*.deb dir` → uvnitř je `usr/lib/aspell/cs.cwl` = gzip prezip-bin proudu; `.rws` master v debu není (build vyžaduje root). Rozbal `gunzip -c cs.cwl | prezip-bin -d > tvary` (pozor: `preunzip` selže s 'unknown format' — nepoužívat), pak `iconv -f ISO-8859-2 -t UTF-8`, `sort -u` a nahraď cs.forms.sorted.txt; z něj pak přestav i SQLite lexikon — kontrolor i brána čtou jen z něj (ověřeno: 3,14M řádků za ~1,5 s):
  ```
  rm ~/.local/share/czech-lint/cs.forms.sqlite
  sqlite3 ~/.local/share/czech-lint/cs.forms.sqlite "CREATE TABLE forms(form TEXT PRIMARY KEY) WITHOUT ROWID;"
  sqlite3 ~/.local/share/czech-lint/cs.forms.sqlite ".import --csv ~/.local/share/czech-lint/cs.forms.sorted.txt forms"
  ```
  `.import --raw` tato verze sqlite3 nezná (unknown option) — `--csv` je pro tvary bez čárek bezpečné; po importu ověř `SELECT count(*)` a přítomnost tvaru s diakritikou. Nesnaž se o `aspell create master` bez roota — boří se přes chybějící .cset/.cmap v data-dir.
