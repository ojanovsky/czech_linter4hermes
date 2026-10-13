# Příklad kontroly češtiny (czech-text-lint)

> Snapshot SilverBullet stránky `czech_lint_example` (space `notes`), pořízen
> 2026-10-13. Text ukazuje reálný průběh kontroly: strojem vygenerovaný článek
> s chybami, tabulku nálezů a opravenou verzi. Chybné úseky jsou pro přehlednost
> obaleny do `backticku` — brána češtiny záměrné příklady v kódu neblokuje.

Původní text obsahoval chyby, které zachytil tvarový kontrolor a gramatický kritik. Chybné úseky jsou níže pro přehlednost obaleny backticky; mimo ně je text ponechán přesně tak, jak padl na poprvé.

## Původní (neopravený) text

**Wafery a výroba polovodičů**

**Wafer (deska)** je tenký `plotýzkový` řez z monokrystalického křemíku, typicky 200 mm (8") nebo 300 mm (12") v průměru, silný jen ~0,7 mm. Je to základní „plátno", na kterém se vyrábí čipy — z jednoho waferu vzniknou stovky až tisíce identických obvodů najednou.

### Jak se wafer získá

1. **Tavení a krystalizace** — křemík (z křemene, SiO₂) se taví při ~1420 °C a metodou Czochralského se z taveniny vytahuje monokrystalická tyč (ingot) o čistotě 99,9999999 % (tzv. „`elekttronická` kvalita", nečistoty v jednotkách ppb).
2. **Broušení a leštění** — tyč se ořeže diamantovou pilou na plátky (~1 mm), ty se zbrousí a `vyleštují` do zrcadlové hladkosti (CMP — chemical mechanical polishing), protože struktury čipů se kreslí v měřítkách menších než vlnová délka světla.

### Co se děje na waferu (výroba čipu)

Probíhá v čistírně (cleanroomu, třída čistoty do ISO 1) v cyklech, které se opakují `stovkykrát`:

1. **Oxidace** — na povrch se vypěstuje tenká vrstva SiO₂ (isolant, maska).
2. **Fotolithografie** — wafer se `potrvá` `foto odpornou` vrstvou (fotorezist), exponuje se UV/EUV světlem přes masku (retikulum) — jako „fotografie" vzoru obvodu. Nejdražší stroje: EUV skenery od ASML (~150 mil. USD kus).
3. **leptání (etching)** — místa bez fotorezistu se vyleptají (plazmatem nebo chemicky), tím se přenesen vzor do vrstvy pod ním.
4. **Implantace / difuze** — do křemíku se urychlenými ionty „vystřílí" příměs (bor, fosfor), čímž vzniknou polovodičové oblasti typu P a N — základy tranzistorů.
5. **Depozice** — `napáří` se nebo `naroste` tenké vrstvy kovů (měď, wolfram) a dielektrik (CVD, PVD, ALD) — propojení a izolace.

Tyto kroky se opakují vrstvu po vrstvě (u moderních `nodeů` 20+ litografických vrstev), až vznikne struktura s miliardami tranzistorů (FinFET, dnes GAA nanosheet, velikosti kritických rozměrů jednotky nm).

### Po dokončení

- **Testování na waferu (wafer sort)** — `each` čip se elektricky otestuje `sONDICÍ` (prober), označí se dobré a špatné.
- **Řezání (dicing)** — wafer se rozřeže na jednotlivé čipy (die).
- **Balení (packaging)** — die se připevní do pouzdra, propojí zlatými drátky nebo TSV průrazy na vývody, případně se skládá více die na sebe (chiplety, 3D IC).
- **Finální test** — čip se otestuje za provozních podmínek a jde do prodeje.

Zajímavost: celý proces od křemíkového písku po hotový čip trvá 8–12 týdnů a moderní CPU obsahuje přes 10 miliard tranzistorů, z nichž každý je menší než vlnová délka viditelného světla.

## Nalezené chyby

| Nález | Typ | Oprava |
|---|---|---|
| `plotýzkový` | tvar mimo lexikon | plotýnka / wafer |
| `elekttronická` | překlep | elektronická |
| `vyleštují` | tvar mimo lexikon | vyleští |
| `potrvá` | chybné sloveso | potáhne |
| `foto odpornou` | rozepsané přídavné jméno | světlo citlivou / fotoodpudivou |
| `stovkykrát` | tvar mimo lexikon | stokrát |
| `napáří`, `naroste` | tvar mimo lexikon / shoda podmětu s přísudkem | napaří, narostou |
| `each` čip | jazykový únik | každý čip |
| `sONDICÍ` | rozhozený token | hrotem (prober) |
| `monokrystalický`, Czochralského | planý poplach (odborný termín mimo dikta) | ponecháno, přidáno do allow.txt |

## Opravený text

Wafer (česky také plotýnka, odborně substrátový disk) je tenký kotouč nařezaný z monokrystalu křemíku, obvykle 200 mm (8 palců) nebo 300 mm (12 palců) v průměru a jen asi 0,7 mm silný. Je to základní deska, na níž se vyrábějí čipy — z jednoho waferu jich najednou vzniknou stovky až tisíce.

### Jak se wafer získá

1. **Tavení a růst krystalu** — křemík se získá redukcí křemene SiO₂ na vysokou čistotu a metodou Czochralského se z taveniny vytahuje svisle rostoucí tyč (ingot) monokrystalického křemíku; nečistoty se měří na jednotky ppb.
2. **Řezání a leštění** — tyč se diamantovou pilou rozřeže na plátky silné asi 1 mm, ta se zbrousí a vyleští do zrcadlové hladkosti (CMP), protože vzory obvodů se kreslí v měřítkách menších než vlnová délka světla.

### Co se děje na waferu

Celé procesy probíhají v čistírně (cleanroomu) a stejné cykly se opakují i stokrát:

1. **Oxidace** — na povrch se vypěstuje tenká vrstva oxidu křemičitého SiO₂, která slouží jako izolant i maska.
2. **Fotolitografie** — wafer se potáhne světlo citlivou vrstvou (fotorezistem) a exponuje se UV nebo EUV světlem přes masku zvanou retikulum; princip je jako fotografie vzoru obvodu. Nejdražší stroje jsou EUV skenery od ASML, stojí kolem 150 milionů USD kus.
3. **Leptání** — místa bez fotorezistu se vyleptají plazmatem nebo chemicky a vzor se tak přenese do vrstvy pod nimi.
4. **Implantace** — do křemíku se urychlenými ionty vpraví příměs (bor, fosfor), čímž vzniknou polovodičové oblasti typu P a N, základy tranzistorů.
5. **Depozice** — napaří se nebo narostou tenké vrstvy kovů (měď, wolfram) a izolantů metodami CVD, PVD a ALD; tak vznikají propojení a izolace mezi vrstvami.

Tyto kroky se opakují vrstvu po vrstvě; u moderních výrobních uzlů je více než dvacet litografických masek a výsledkem je struktura s miliardami tranzistorů typu FinFET, dnes GAA, jejichž kritické rozměry činí jednotky nanometrů.

### Od waferu ke čipu

1. **Test na waferu** — každý čip se elektricky změří hrotem zvaným prober a dobré kusy se oddělí od vadných.
2. **Řezání (dicing)** — wafer se rozřeže na jednotlivé čipy zvané die.
3. **Balení (packaging)** — die se připevní do pouzdra a spojí zlatými drátky nebo průrazy TSV s vývody; někdy se několik die skládá na sebe (chiplety, 3D integrace).
4. **Finální test** — čip se prověří za provozních podmínek a jde do prodeje.

Celá cesta od křemene po hotový čip trvá osm až dvanáct týdnů a moderní procesor obsahuje přes deset miliard tranzistorů, z nichž každý je menší než vlnová délka viditelného světla.
