"""czech-lint-chat — kontrola češtiny v odpovědích agenta (tvrdá vrstva, bez modelu navíc).

``transform_llm_output``: text odpovědi projde tvarovou bránou (lexikon aspell-cs).
Tvrdé nálezy (chybný tvar s diakritikou, znak mimo češtinu) připnou za odpověď
jednorázový štítek; měkké (ASCII mimo lexikon = technický termín) se logují mlčky
do ``$HERMES_HOME/logs/czech-lint-chat.log`` (JSONL).

Bloky kódu, inline kód a URL se před kontrolou maskují — odpověď se posuzuje jako
psaný text, ne jako technický výpis. Fail-open: žádné výjimky, žádný zásah.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

SKILL = Path(os.environ.get(
    "CZECH_LINT_SKILL",
    os.path.expanduser("~/.hermes/profiles/quido/skills/czech-text-lint")))

_gate = None
_gate_failed_at = 0.0


def _get_gate():
    """Lenivý singleton brány; selhání lexikonu zkoušíme znovu nejdřív za 60 s."""
    global _gate, _gate_failed_at
    if _gate is not None:
        return _gate
    if time.time() - _gate_failed_at < 60:
        return None
    try:
        import sys
        sys.path.insert(0, str(SKILL / "scripts"))
        _gate = __import__("czech_lint_gate").Gate()
    except Exception as e:  # lexikon neexistuje -> fail-open
        _gate_failed_at = time.time()
        logger.debug("czech-lint-chat: brána nedostupná: %s", e)
        _gate = None
    return _gate


_PROTECT = (r"```[\s\S]*?```", r"`[^`\n]*`", r"https?://\S+", r"\s{4,}\S[^\n]*")


def _mask(text):
    chars = list(text)
    for pat in _PROTECT:
        for m in re.finditer(pat, text):
            for i in range(m.start(), m.end()):
                if chars[i] != "\n":
                    chars[i] = " "
    return "".join(chars)


def _log_soft(findings, session_id):
    try:
        from hermes_constants import get_hermes_home
        home = get_hermes_home()
    except Exception:
        home = Path.home() / ".hermes"
    try:
        log = home / "logs" / "czech-lint-chat.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as f:
            for w, ln, col in findings:
                f.write(json.dumps({"ts": time.time(), "session": session_id,
                                    "word": w, "line": ln, "col": col},
                                   ensure_ascii=False) + "\n")
    except OSError:
        pass


def _on_transform(response_text=None, session_id="", **kw):
    if not isinstance(response_text, str) or len(response_text) < 40:
        return None
    gate = _get_gate()
    if gate is None:
        return None
    try:
        hard, soft = gate.classify(_mask(response_text))
    except Exception as e:
        logger.debug("czech-lint-chat: classify selhalo: %s", e)
        return None
    if soft:
        _log_soft(soft, session_id)
    if not hard:
        return None
    seen = list(dict.fromkeys(w for w, _ln, _c, _why in hard))
    tag = ("⚠ Kontrola češtiny: neznámé tvary "
           + ", ".join(f"„{w}“" for w in seen[:8])
           + (f" (+{len(seen) - 8})" if len(seen) > 8 else "")
           + " — ověř proti lexikonu nebo SSČ.")
    return response_text + "\n\n" + tag


def register(ctx) -> None:
    ctx.register_hook("transform_llm_output", _on_transform)
