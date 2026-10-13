---
tags: [hermes, nástroje, čeština]
---
a dej mi 
# Kontrola češtiny — návod ke zprovoznění

Jak jsme v Hermesovi zprovoznili automatickou kontrolu českých tvarů a jak ji udržovat. Přišlo to na pochybení: model si vymýšlel hlavně přídavná jména („vakuumový“ → správně vakuový, „quitara“ → kytara, „rácovací“ → řádkovací) a paměťová poznámka na každé slovo je k ničemu — potřeba je generátor tvarů.

## Architektura

| Vrstva | Co | Kde |
|---|---|---|
| Dovednost | pravidla a workflow, načítá se k úlohám s češtinou | `~/.hermes/skills/czech-text-lint/SKILL.md` |
| Kontrolor | Python skript, <1 s, offline | `~/.hermes/skills/czech-text-lint/scripts/czech_forms_check.py` |
| Data | 3,14 mil. tvarů slov v SQLite lexikonu (mmap, do RAM se jako celek neláduje) | `~/.local/share/czech-lint/cs.forms.sqlite` (zdroj: `cs.forms.sorted.txt`) |
| Online pojistka | význam/úzus po nálezu | IJP `prirucka.ujc.cas.cz`, SSČ `kodex.cz`, `foniie.cz` |
| Gramatický kritik | shoda, pádové řízení a negace (co tvarový kontrolor nevidí) | `~/.hermes/skills/czech-text-lint/scripts/czech_grammar_critic.py` |

Zdroj dat: oficiální slovník aspell-cs (podklad KV HIL — Morfologický lexikon češtiny). Žádný balík na PyPI ani GitHubu neexistoval — pyMor na PyPI je cizí knihovna pro model order reduction, mýlka, která stála několik pokusů.

Kritik je druhý průchod tvým vlastním modelem na :8000 (temp 0.2, myšlení vypnuté per-request — jinak vyčerpá rozpočet rozebíráním paradigmat a nic nevrátí). Žádná nová RAM, ~8 s na odstavec, čistý text odbaví vteřinu. Do praxe přinesl hmatatelné nálezy i v textech, které už tvarovou kontrolou prošly: *pod úhlem tři stupně* (má být *tří stupňů*), *nad nebo pod ni* (má být *pod ní*, 7. pád). Planých poplachů dělá asi jeden na delší text („několik potvrzuje“ nabízel opravit na množné číslo — obojí je správně), takže se brát má jako varování, ne ortel.

## Jak to bylo realizováno (bez root oprávnění)

Celý postup je skript `scripts/build_forms_db.sh` — stáhne dikt, rozbalí, převede, postaví SQLite a sám ověří počty. Ruční ekvivalent krok za krokem:

```bash
# 1. stáhnout deb a rozbalit do dočasného adresáře
apt-get download aspell-cs && dpkg -x aspell-cs*.deb dir
# 2. uvnitř je dikt — aktuální deb nese usr/share/aspell/cs.cwl.gz,
#    starší měly usr/lib/aspell/cs.cwl; najít jistě: find dir -name 'cs.cwl*'
#    (POZOR: preunzip selže 'unknown format', jen prezip-bin -d)
gunzip -c "$(find dir -name 'cs.cwl*' | head -1)" | prezip-bin -d > tvary
# 3. slovník je v ISO-8859-2
iconv -f ISO-8859-2 -t UTF-8 tvary > tvary.utf8
sort -u tvary.utf8 -o ~/.local/share/czech-lint/cs.forms.sorted.txt
# 4. přestavět SQLite lexikon, který kontrolor i brána čtou
rm ~/.local/share/czech-lint/cs.forms.sqlite
sqlite3 ~/.local/share/czech-lint/cs.forms.sqlite "CREATE TABLE forms(form TEXT PRIMARY KEY) WITHOUT ROWID;"
sqlite3 ~/.local/share/czech-lint/cs.forms.sqlite ".import --csv ~/.local/share/czech-lint/cs.forms.sorted.txt forms"
# naplnit meta.charset — znaková množina odvozená z dat (kontrolor i brána
# ji čtou; ruční výčet písmen ve skriptech je jen fallback pro starou db)
python3 -c "import sqlite3,os;p=os.path.expanduser('~/.local/share/czech-lint/cs.forms.sqlite');db=sqlite3.connect(p);ch=set();[ch.update(f.lower())for(f,)in db.execute('SELECT form FROM forms')];db.execute('CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT)');db.execute(\"INSERT OR REPLACE INTO meta VALUES('charset',?)\",(''.join(sorted(ch)),));db.commit()"
```

Skript dělí text regulárním výrazem `re.compile(r"[^\W\d_]{2,}(?:-[^\W\d_]+)*")` — Unicode písmena; ručně psaná třída `[A-Za-z...]` lámala tokeny na diakritice a produkovala falešné hlášky (učeno z vlastní chyby). Kontrolor umí: velikost písmen (doluje), pomlčkové složeniny po částech, ignoruje číslice a pro každý nález nabídne nejbližší platné tvary (editace do vzdálenosti 2, s fonetickými přepisy q→k, w→v, x→ks; typicky zlomek vteřiny na slovo).

## Nastavení Hermes

V `~/.hermes/config.yaml` pro qwen38flash (Qwen3.8 Flash Next, lokální vLLM :8000):

```yaml
extra_body:
  temperature: 0.6
  top_p: 0.9
  frequency_penalty: 0.1
```

- **temperature 0.6** — nižší teplota tlumí vymyšlené tvary i únik CJK tokenů (směsky znaků z výukového korpusu). Vlastní zkušenost: vyšší teplota = víc „vakuumových“ a cizích vsuvek; nesnížit pod 0.4 bez testu, model pak ztrácí plynulost.
- **frequency_penalty 0.1** — lehce tlumí opakování, tím i znovu se vracející úniky.
- V SOUL.md je direktiva `Language: ... must be in Czech. Never emit CJK characters` — ta říká *co*, kontrolor ověří *jak*; bez kontroloru je to přání, s ním fakt.
- MTP (multi-token prediction) u Flash Next neměnit — s kontrolou nesouvisí, ale teplota na něj citlivě působí.

## SOUL.md — realizovaná úprava

`~/.hermes/SOUL.md` (osobnostní vrstva, předává se do každé relace) obsahuje od 12. 10. 2026, 19:50 tento jazykový řádek — druhý odstavec:

```
Language: all human-readable output (responses, explanations, commit
messages, user-facing comments) must be in Czech. Never emit CJK
(Chinese/Japanese/Korean) characters in your output — they are token
leakage, not words; if one surfaces during generation, discard it and
write the Czech word instead. Keep code identifiers, CLI commands,
config keys and established technical terms in English.
```

Co tím je zastaveno: (1) odpovědi v angličtině nebo jiném cizím jazyce — výstup musí být česky; (2) znaky čínštiny, japonštiny a korejštiny, které občas prorazí z výukového korpusu — to není slovo, ale únik tokenu, má se zahodit a přepsat českým ekvivalentem; (3) naopak identifikátory, CLI a zavedené termíny (vLLM, RAG, temperature) zůstávají anglicky, což je záměr, ne chyba.

Tahle direktiva řeší *co* — ale model ji občas poruší sama uprostřed generování. Proto je navrch kontrolor tvarů níže, který to po sobě umí *ověřit*. Doplňovací rada pro další rozvoj SOUL.md:

```
Delší nebo odborný český text proženu kontrolorem czech-text-lint
před odesláním; nalezené tvary ověřím, neznámé cizí termíny ponechám.
```

## Workflow použití

1. napsat text do souboru
2. `python3 ~/.hermes/skills/czech-text-lint/scripts/czech_forms_check.py soubor`
3. návratový kód 1 → každý nález posoudit: rodové jméno, cizí termín nebo citát = planý poplach; jinak přepsat a opakovat, dokud není čisto
4. nejistý tvar → foniie.cz (paradigma), IJP (úzus), kodex.cz (význam)

Reálný záchyt z prvních dní: únik `zaSOURCE` a `thanks` dovnitř české věty, vymyšlený tvar zpatientoval (kontrolor nyní rovnou nabídne patentoval), „vakuumový“ (návrh: vakuový), „quitara“ (návrh: kytara). U pojmu ikonoskop naopak selže slovník, ne kontrolor — celá forma v aspell-cs není vůbec, takže flag je planý poplach a nabídne se i vzdálený monoskop; takové termíny řeš až po flagu online (foniie/SSČ).

## Vynucování hooky (dva režimy podle ceny)

Kdyby kontrola běžela plnou vahou na každou odpověď, zpomalila by každý chat o druhý průchod modelem. Proto rozdělení:

- **Chat:** plugin `~/.hermes/plugins/czech-lint-chat` (event `transform_llm_output`) — jen tvrdá tvarová brána, bez modelu navíc, latence pod sekundu. Při nálezu připne za odpověď tag `⚠ Kontrola češtiny:`; měkké nálezy (technické termíny) jdou mlčky do logu `~/.hermes/logs/czech-lint-chat.log`.
- **Dokumenty:** shell hook `pre_tool_call` spouští `~/.hermes/agent-hooks/czech-doc-gate.py` — blokuje zápis `.md`/`.txt` přes `write_file`/`patch` i `curl PUT` na SilverBullet, dokud není čistý; zde platí i gramatický kritik a selhání brány je fail-closed. Záměrně chybné příklady musí být v citaci „…“ nebo v backticku, jinak hook zablokuje celý dokument.
- **Výjimky:** plané poplachy na vlastní jména a termíny se píší po jednom na řádek do `~/.hermes/skills/czech-text-lint/allow.txt`; lexikon tvarů pro kontrolor i bránu je `~/.local/share/czech-lint/cs.forms.sqlite` (64 MB, mapovaný přes mmap — celý se do RAM nenačítá).
- Registrace je v `config.yaml` (`hooks.pre_tool_call`, `plugins.enabled`), schválení v `~/.hermes/shell-hooks-allowlist.json`. Test bez agenta: `hermes hooks test pre_tool_call --payload-file X`, stav: `hermes hooks doctor`. Změny se projeví až nové sezení.

## Údržba

- novelizace dat: zopakovat postup výše s čerstvým deb balíkem aspell-cs (např. při přechodu na novější Ubuntu).
- kontrolor neřeší styl ani sémantiku — jen morfologii a lexikon.
- limity: chybí vlastní jména a neologismy → plané poplachy jsou řádný stav, ne chyba.


## Negace — slepé místo a jeho uzavření (13. 10. 2026)

Dnešní relace zachytila chybu, kterou obě vrstvy dříve propustily: anglickou stavbu přeloženou doslova jako `zprávy se mažou nikdy` (z anglického „are never deleted"). Každé slovo zvlášť je platný tvar — chyba sedí mezi slovy, tvarový kontrolor ji tedy vidět nemůže a kritik ji dosud neměl na seznamu pravidel. Změřeno: věta prošla za 0,4 s bez nálezu.

Správně je `zprávy se nikdy nemažou`. Čeština vyžaduje dvojí negaci: záporné zájmeno (`nikdy`, `nic`, `nikdo`, `nikde`) musí doprovázet sloveso s předponou `ne-`. Angličtina tohle pravidlo nezná — proto takový typ chyby vzniká překladem, nikoli překlepem.

Co se změnilo:
- **Kritik** má nové pravidlo typu 4 (negace) a hodnotí každý díl věty zvlášť, i za pomlčkou. Současně byl opraven jeho parser: dříve havaroval na kód 2, když model vrátil jeden JSON objekt bez pole.
- **`czech_forms_check.py --negace`** je deterministická pojistka do 0,1 ms: varuje, když věta obsahuje záporné zájmeno a žádné slovo s předponou `ne-`. Přepínač zůstává záměrně mimo bránu — nominální věty bez slovesa by varoval planě.

Proč tu počítadlo slov stačí: pravidlo dvojí negace nezávisí na pořádku slov. Věty `Nikdy se to nedělá` i `Nedělá se to nikdy` mají tutéž nutnou podmínku — přítomnost záporu ve větě. Test nutné podmínky se obejde bez syntaktického rozboru a platí jen pro pravidla na pořádku nezávislá. Pravidla na pořádku závislá (shoda, řízení) potřebují znovu kritika. Škála jde od nejlevnějšího k nejchytřejšímu: počítadlo (0,1 ms) → morfologie (<1 s) → kritik (sekundy); každá vrstva hlídá to, co předchozí nemůže.

Změřeno na reálných větách (tři opakování): deterministická vrstva zachytí kalibr spolehlivě, včetně případu za pomlčkou; kritik jej hlásí přibližně ze dvou třetin — jeho nález typu 4 je vodítko, nikoli rozsudek. Dvojí negace i věty s výjimkou `bez` zůstávají čisté, nálezy shody a řízení nedotčeny. Při ručním běhu kritik navíc vynechává příklady v backtickech a zahazuje nálezy, které se ve vstupu nevyskytují, i ty bez změny textu — obojí se objevilo při testech.

## Sporná slova — seznam, ne odrážky (13. 10. 2026)

Když opravuješ slovo, které je tvarově platné, ale bývá zaměňováno významově (rozchod ve smyslu uvedení do provozu), nepatří poučení do odrážky skillu. Patří do `references/sporna-slova.md` — kritik seznam načítá do svého promptu jako pravidlo 5, takže jím projde každý text, ne jen ty, kde agent skill zrovna četl.

Tři úložiště podle toho, co je spatřeno:
- `allow.txt` — slovo je v pořádku, jen ho dik nezná (planý poplach tvarový)
- `references/sporna-slova.md` — slovo je platné, ale bývá zaměňováno významově
- `SKILL.md` — pouze postupy a třídy poučení; slovní zásoba sem nepatří

Formát záznamu: zakázané kolokace / legitimní významy / náhrada. Rozepsané kolokace jsou nutné — čistě sémantické zadání („posuzuj význam“, „nahraď a ověř smysl“) model na této mašině porušoval a flagoval i legitimní použití; po přepsání na konkrétní sousloví měřeno 3/3 záchyt, 0/3 planý poplach. Slabší model potřebuje vzor, ne úsudek.

Postup při příští opravě slova: ověřit, že jde o záměnu významu (ne o planý poplach diktu) → přidat záznam do seznamu → ověřit kritikem na větě špatné i legitimní. Regrese: `tests/data/t7_sporne_spatne.txt` a `t7_sporne_ok.txt`.
