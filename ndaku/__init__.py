"""Ndaku — API (web + futures apps mobiles). Point d'entrée : create_app()."""
import logging
import os

from flask import Flask, abort, g, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

from . import db as dbm
from .config import Config
from .security import apply_session_cookie, csrf_check
from .storage import Storage

PUBLIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "public")
CSP = ("default-src 'self'; "
       "script-src 'self' https://accounts.google.com/gsi/client https://appleid.cdn-apple.com; "
       "style-src 'self' 'unsafe-inline' https://accounts.google.com/gsi/style; "
       "img-src 'self' data: blob: https://*.public.blob.vercel-storage.com https://*.googleusercontent.com; "
       "connect-src 'self' https://accounts.google.com/gsi/; "
       "frame-src https://accounts.google.com/gsi/ https://appleid.apple.com; "
       "object-src 'none'; base-uri 'none'; form-action 'self' https://appleid.apple.com; frame-ancestors 'none'")
_migrated = set()


def create_app(**overrides):
    cfg = Config(**overrides)
    # En local on sert aussi le front ; sur Vercel, public/ est servi par le CDN.
    app = Flask(__name__, static_folder=None if cfg.ON_VERCEL else PUBLIC_DIR, static_url_path="")
    app.config.update(NDAKU=cfg, STORAGE=Storage(cfg), MAX_CONTENT_LENGTH=4_400_000, JSON_SORT_KEYS=False)
    app.json.ensure_ascii = False
    logging.basicConfig(level=logging.INFO)

    if cfg.DATABASE_URL not in _migrated:
        dbm.migrate(cfg.DATABASE_URL)
        _migrated.add(cfg.DATABASE_URL)

    from . import admin, auth, listings
    for bp in (auth.bp, listings.bp, admin.bp):
        app.register_blueprint(bp)

    app.before_request(csrf_check)

    if cfg.ON_VERCEL:
        from vercel.headers import set_headers

        @app.before_request
        def vercel_oidc_context():
            # Le SDK Blob (mode OIDC) lit le jeton de la requête courante ; on ne lui transmet que cet en-tête.
            tok = request.headers.get("x-vercel-oidc-token")
            set_headers({"x-vercel-oidc-token": tok} if tok else None)
    app.teardown_appcontext(dbm.close)

    @app.after_request
    def finish(resp):
        apply_session_cookie(resp)
        h = resp.headers
        h["X-Content-Type-Options"] = "nosniff"
        h["X-Frame-Options"] = "DENY"
        h["Referrer-Policy"] = "strict-origin-when-cross-origin"
        h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        h["Cross-Origin-Opener-Policy"] = "same-origin-allow-popups"  # popups Google/Apple
        h.setdefault("Content-Security-Policy", CSP)
        if cfg.SECURE_COOKIES:
            h["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if request.path.startswith("/api/"):
            h["Cache-Control"] = "no-store"
        if g.get("retry_after"):
            h["Retry-After"] = str(g.retry_after)
        return resp

    @app.errorhandler(Exception)
    def on_error(e):
        g.db_rollback = True
        if isinstance(e, HTTPException):
            if e.code == 404 and not request.path.startswith(("/api/", "/uploads/", "/media/")) and not cfg.ON_VERCEL:
                return app.send_static_file("index.html")
            return jsonify(error=e.description if e.code != 500 else "Erreur serveur"), e.code
        app.logger.exception("Erreur non gérée")
        return jsonify(error="Erreur serveur"), 500

    @app.get("/uploads/<name>")
    def local_upload(name):
        path = app.config["STORAGE"].local_path(name)
        if not path or not os.path.exists(path):
            abort(404)
        resp = send_file(path, mimetype="image/jpeg", max_age=31536000)
        resp.headers["Content-Security-Policy"] = "default-src 'none'"
        return resp

    @app.get("/media/<name>")
    def private_media(name):
        """Photos d'un store Blob privé, servies par l'app puis mises en cache par le CDN Vercel
        (nom de fichier aléatoire et immuable)."""
        data = app.config["STORAGE"].get_private(name)
        if data is None:
            abort(404)
        resp = app.response_class(data, mimetype="image/jpeg")
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        resp.headers["CDN-Cache-Control"] = "public, max-age=31536000, immutable"
        resp.headers["Content-Security-Policy"] = "default-src 'none'"
        return resp

    if not cfg.ON_VERCEL:
        @app.get("/")
        def index():
            return app.send_static_file("index.html")

    @app.get("/api/health")
    def health():
        dbm.one("SELECT 1 AS ok")
        st = app.config["STORAGE"]
        return jsonify(ok=True, storage=st.mode, blob_access=cfg.BLOB_ACCESS if st.blob else None)

    return app
