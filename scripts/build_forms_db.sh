#!/usr/bin/env bash
# Postaví databázi českých tvarů pro czech-text-lint — bez roota, na míře.
#
#   ./build_forms_db.sh            # výstup do ~/.local/share/czech-lint
#   CZECH_LINT_DATA=/cesta ./build_forms_db.sh
#
# Zdroj: oficiální deb aspell-cs (KV HIL). Bez roota: dpkg -x místo instalace,
# prezip-bin z balíku prezip-bin (umí i rozbalení .cwl ručně). POZOR: preunzip
# na cs.cwl selže hláškou 'unknown format' — nepoužívat.
set -euo pipefail

DEST="${CZECH_LINT_DATA:-$HOME/.local/share/czech-lint}"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/czech-lint-build.XXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$DEST"

echo "[1/5] stahuji aspell-cs .deb"
cd "$TMP"
if ! apt-get download aspell-cs 2>/dev/null; then
    # bez indexu universe: stáhnout napřímo z archivu (libovolná architektura —
    # deb s diktem je all)
    URL=$(curl -sL "http://archive.ubuntu.com/ubuntu/pool/universe/a/aspell-cs/" \
          | grep -oE 'aspell-cs_[^"]+all\.deb' | sort -u | tail -1)
    [ -n "$URL" ] || { echo "CHYBA: nejde najít aspell-cs .deb (apt ani archive)"; exit 1; }
    curl -sLO "http://archive.ubuntu.com/ubuntu/pool/universe/a/aspell-cs/$URL"
fi
deb=$(ls aspell-cs_*.deb | head -1)

echo "[2/5] rozbaluji dikt"
dpkg -x "$deb" unpacked
# v aktuálním debu je usr/share/aspell/cs.cwl.gz; starší popisy mluví o
# usr/lib/aspell/cs.cwl — hledáme obojí podle masky, ať skript přežije obojí
cwl=$(find unpacked -name 'cs.cwl*' | head -1)
[ -n "$cwl" ] || { echo "CHYBA: v deb nic cs.cwl*"; exit 1; }

echo "[3/5] dekomprimuji prezip proud"
if ! command -v prezip-bin >/dev/null 2>&1; then
    echo "      prezip-bin není nainstalován, stahuji z archivu"
    apt-get download prezip-bin 2>/dev/null || {
        arch=$(dpkg --print-architecture)
        purl=$(curl -sL "http://archive.ubuntu.com/ubuntu/pool/universe/p/prezip-bin/" \
               | grep -oE "prezip-bin_[^\"_]*_${arch}\.deb" | sort -u | tail -1)
        [ -n "$purl" ] || { echo "CHYBA: prezip-bin nedostupný"; exit 1; }
        curl -sLO "http://archive.ubuntu.com/ubuntu/pool/universe/p/prezip-bin/$purl"
        dpkg -x prezip-bin_*.deb prezipdir
        PREZIP="$TMP/prezipdir/usr/bin/prezip-bin"
    }
    PREZIP="${PREZIP:-$(command -v prezip-bin)}"
else
    PREZIP=$(command -v prezip-bin)
fi

echo "[4/5] konvertuji na UTF-8, třídím"
case "$cwl" in
    *.gz) gunzip -c "$cwl" | "$PREZIP" -d ;;
    *)    "$PREZIP" -d < "$cwl" ;;
esac | iconv -f ISO-8859-2 -t UTF-8 | sort -u > "$DEST/cs.forms.sorted.txt"

echo "[5/5] stavím SQLite + meta.charset"
db="$DEST/cs.forms.sqlite"
rm -f "$db"
sqlite3 "$db" "CREATE TABLE forms(form TEXT PRIMARY KEY) WITHOUT ROWID;"
sqlite3 "$db" ".import --csv $DEST/cs.forms.sorted.txt forms"
python3 - "$db" <<'PY'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1])
chars = set()
for (form,) in db.execute("SELECT form FROM forms"):
    chars.update(form.lower())
db.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT)")
db.execute("INSERT OR REPLACE INTO meta VALUES('charset', ?)", ("".join(sorted(chars)),))
db.commit()
PY

# ověření: počty a přítomnost diakritiky i metadat (selže hlasitě)
count=$(sqlite3 "$db" "SELECT count(*) FROM forms")
meta=$(sqlite3 "$db" "SELECT length(value) FROM meta WHERE key='charset'")
dia=$(sqlite3 "$db" "SELECT count(*) FROM forms WHERE form LIKE '%ě%'")
echo "hotovo: $count tvarů, charset $meta znaků, s ě: $dia"
[ "$count" -gt 2000000 ] && [ "$meta" -gt 30 ] && [ "$dia" -gt 1000 ] \
    || { echo "CHYBA: ověření neprošlo — data vypadají neúplná"; exit 1; }
