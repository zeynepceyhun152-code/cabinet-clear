"""
lang_ctx.py - which language the current request wants ("en" or "tr").

The page sends an X-Lang header on every server call. app.py reads it once per request (middleware)
and stores it here, so the AI prompts and the PDF can follow it without changing every function.
"""
import contextvars

_lang = contextvars.ContextVar("cc_lang", default="en")


def set_lang(value):
    code = "tr" if str(value or "").strip().lower().startswith("tr") else "en"
    return _lang.set(code)


def reset_lang(token):
    _lang.reset(token)


def get_lang():
    return _lang.get()


_TURKISH = (
    "\n\nLANGUAGE: Write every plain-language field in Turkish (Türkçe), in clear, formal wording a patient "
    "can understand. The document itself may be in English or Turkish; read it either way. Keep medication "
    "names, strengths, doses, numbers, dates and units exactly as written in the document. Keep the JSON "
    "keys, and any fixed values (such as high, medium, low, immediate, urgent, monitor), in English."
)


def language_instruction():
    """Extra prompt text for the AI. Empty in English, so English behaves exactly as before."""
    return _TURKISH if get_lang() == "tr" else ""
