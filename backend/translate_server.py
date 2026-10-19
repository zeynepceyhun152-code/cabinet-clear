"""
translate_server.py - Turkish text for things the SERVER writes itself (used by the PDF).

It reads the same tr.json the page uses, so the two always agree. Text the AI writes is not handled here:
the AI is asked to write in Turkish directly (see lang_ctx.py).
"""
import json
import re
from pathlib import Path

from lang_ctx import get_lang

_HERE = Path(__file__).resolve().parent
_PATHS = [_HERE / "tr.json", _HERE.parent / "frontend" / "tr.json"]
_data = None
_rx = None


def _load():
    global _data, _rx
    if _data is not None:
        return
    _data = {"strings": {}, "patterns": [], "freq": []}
    for p in _PATHS:
        if p.exists():
            _data = json.loads(p.read_text(encoding="utf-8"))
            break
    _rx = [(re.compile(p["re"]), p["tr"]) for p in _data.get("patterns", [])]


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip()


def _freq(s):
    for a, b in _data.get("freq", []):
        s = s.replace(a, b)
    return s


def translate(text, depth=0):
    """Turkish text, or None when there is nothing to translate."""
    _load()
    if depth > 3:
        return None
    key = norm(text)
    if not key:
        return None
    if key in _data["strings"]:
        return _data["strings"][key]
    for rx, tr in _rx:
        m = rx.search(key)
        if not m:
            continue

        def fill(g):
            kind, n = g.group(1), int(g.group(2))
            val = m.group(n) if n <= len(m.groups()) and m.group(n) is not None else ""
            if kind == "t":
                t = translate(val, depth + 1)
                return val if t is None else t
            if kind == "f":
                t = translate(val, depth + 1)
                return _freq(val) if t is None else t
            if kind == "ts":
                parts = []
                for part in val.split("; "):
                    t = translate(part, depth + 1)
                    parts.append(part if t is None else t)
                return "; ".join(parts)
            return val

        return re.sub(r"\{(t|f|ts)?(\d)\}", fill, tr)
    return None


def tx(text, lang=None):
    """Turkish when the request asked for Turkish; otherwise the text unchanged."""
    if text is None:
        return text
    if (lang or get_lang()) != "tr":
        return text
    t = translate(str(text))
    return str(text) if t is None else t
