"""Configuration lue depuis l'environnement (Vercel → Settings → Environment Variables)."""
import os


def _list(name):
    return [x.strip() for x in os.environ.get(name, "").split(",") if x.strip()]


def _bool(name, default=False):
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


class Config:
    def __init__(self, **overrides):
        env = os.environ
        self.DATABASE_URL = env.get("DATABASE_URL") or env.get("POSTGRES_URL") or "postgresql://postgres@localhost:5433/ndaku"
        self.ON_VERCEL = bool(env.get("VERCEL"))
        # Cookies `Secure` + préfixe __Host- dès qu'on est en HTTPS (toujours le cas sur Vercel).
        self.SECURE_COOKIES = _bool("NDAKU_SECURE_COOKIES", self.ON_VERCEL)
        self.PUBLIC_URL = env.get("NDAKU_PUBLIC_URL") or (f"https://{env['VERCEL_PROJECT_PRODUCTION_URL']}"
                                                          if env.get("VERCEL_PROJECT_PRODUCTION_URL") else "http://localhost:5000")
        # OAuth : plusieurs audiences possibles (client web + iOS + Android).
        self.GOOGLE_CLIENT_IDS = _list("GOOGLE_CLIENT_IDS")
        self.APPLE_CLIENT_IDS = _list("APPLE_CLIENT_IDS")  # Services ID (web) + Bundle ID (iOS)
        self.APPLE_REDIRECT_URI = env.get("APPLE_REDIRECT_URI", self.PUBLIC_URL)
        self.ADMIN_EMAILS = {e.lower() for e in _list("ADMIN_EMAILS")}
        self.RESEND_API_KEY = env.get("RESEND_API_KEY")
        self.MAIL_FROM = env.get("MAIL_FROM", "Ndaku <no-reply@ndaku.app>")
        self.REQUIRE_EMAIL_VERIFICATION = _bool("REQUIRE_EMAIL_VERIFICATION", bool(self.RESEND_API_KEY))
        self.BLOB_TOKEN = env.get("BLOB_READ_WRITE_TOKEN")
        self.CRON_SECRET = env.get("CRON_SECRET")
        self.SESSION_DAYS = int(env.get("SESSION_DAYS", "30"))
        self.LOCAL_UPLOADS = env.get("NDAKU_UPLOADS", os.path.join(os.path.dirname(os.path.dirname(__file__)), "instance", "uploads"))
        self.TRUST_PROXY = self.ON_VERCEL or _bool("NDAKU_TRUST_PROXY")
        for k, v in overrides.items():
            setattr(self, k, v)

    @property
    def cookie_name(self):
        return "__Host-ndaku_session" if self.SECURE_COOKIES else "ndaku_session"
