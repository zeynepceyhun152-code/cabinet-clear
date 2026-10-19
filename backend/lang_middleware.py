"""lang_middleware.py - read the X-Lang header once per request and remember it (see lang_ctx.py)."""
from lang_ctx import set_lang, reset_lang


def install(app):
    @app.middleware("http")
    async def language_middleware(request, call_next):
        token = set_lang(request.headers.get("x-lang"))
        try:
            return await call_next(request)
        finally:
            reset_lang(token)
