#!/usr/bin/env bash
# Regrese czech-text-lint. Deterministická vrstva: přísné assert.
# Kritik (LLM, temp 0.2): informativně — nespoléhat se na recall, jen varovat.
set -u
S="$(cd "$(dirname "$0")/.." && pwd)"
D="$S/tests/data"
FAIL=0
ck() { # ck POPIS OCEKAVANY_EXIT_SKUTECNY podmineny
  local desc="$1" want="$2" file="$3" extra="${4:-}"
  out=$(python3 "$S/scripts/czech_forms_check.py" $extra "$file" 2>/dev/null)
  rc=$?
  if [ "$want" = "flag" ]; then
    echo "$out" | grep -q NEGACE && echo "  OK  $desc" || { echo "  CHYBA $desc: očekáván varování"; FAIL=1; }
  elif [ "$want" = "clean" ]; then
    echo "$out" | grep -q NEGACE && { echo "  CHYBA $desc: plané varování"; FAIL=1; } || echo "  OK  $desc"
  fi
}
echo "== deterministická vrstva (--negace)"
ck "default vypnuta"            clean "$D/t1_kalibr.txt" ""          # bez flagu: žádný NEGACE výstup
ck "kalibr zachycen"            flag  "$D/t1_kalibr.txt" "--negace"
ck "kalibr za pomlčkou"         flag  "$D/t6_dash.txt"   "--negace"
ck "správná dvojí negace čistá" clean "$D/t3_fp_double.txt" "--negace" 2>/dev/null || true
ck "výjimka bez čistá"          clean "$D/t5_bez.txt"    "--negace"
ck "backtick mlčí"              clean "$D/t4_bt.txt"     "--negace"
echo "== kritik (informativně)"
for f in t1_kalibr t6_dash; do
  python3 "$S/scripts/czech_grammar_critic.py" "$D/$f.txt" >/dev/null 2>&1 \
    && echo "  POZOR kritik nenašel kalibr v $f.txt (LLM nestabilita, viz skill)" \
    || echo "  OK  kritik nalezl kalibr v $f.txt"
done
python3 "$S/scripts/czech_grammar_critic.py" "$D/neg2.txt" >/dev/null 2>&1 \
  && echo "  POZOR kritik flagl korektní text" || echo "  OK  korektní text čistý"
exit $FAIL
