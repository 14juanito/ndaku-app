"""Vérification des ID tokens Google et Apple (« Se connecter avec Apple » = compte iCloud).

Le même flux sert le web (Google Identity Services / Sign in with Apple JS) et les apps mobiles
(SDK natifs) : le client obtient un ID token signé par le fournisseur et l'envoie au backend.
Contrôles : signature RS256 via JWKS, iss, aud, exp/iat, nonce à usage unique.
"""
import hashlib
import secrets
from datetime import timedelta

import jwt

from .db import one, run
from .security import now

PROVIDERS = {
    "google": {"jwks": "https://www.googleapis.com/oauth2/v3/certs",
               "issuers": ("accounts.google.com", "https://accounts.google.com")},
    "apple": {"jwks": "https://appleid.apple.com/auth/keys", "issuers": ("https://appleid.apple.com",)},
}
_jwks_clients = {}
GOOGLE_PICTURE = "https://lh3.googleusercontent.com/"  # seule source de photo de profil acceptée depuis un jeton


class OAuthError(Exception):
    pass


def _signing_key(provider, token):
    client = _jwks_clients.get(provider)
    if client is None:
        client = _jwks_clients[provider] = jwt.PyJWKClient(PROVIDERS[provider]["jwks"], cache_keys=True,
                                                           lifespan=3600, timeout=5)
    return client.get_signing_key_from_jwt(token).key


def issue_nonce():
    raw = secrets.token_urlsafe(24)
    run("DELETE FROM oauth_nonces WHERE expires_at < now()")
    run("INSERT INTO oauth_nonces (nonce_hash, expires_at) VALUES (%s,%s)",
        (hashlib.sha256(raw.encode()).digest(), now() + timedelta(minutes=30)))
    return raw


def _consume_nonce(raw):
    if not raw or not isinstance(raw, str) or len(raw) > 100:
        return False
    return one("DELETE FROM oauth_nonces WHERE nonce_hash=%s AND expires_at > now() RETURNING 1",
               (hashlib.sha256(raw.encode()).digest(),)) is not None


def verify(provider, token, nonce, audiences):
    """Retourne {sub, email, email_verified, name} ou lève OAuthError."""
    if provider not in PROVIDERS:
        raise OAuthError("Fournisseur inconnu.")
    if not audiences:
        raise OAuthError("Connexion via ce fournisseur non configurée.")
    if not isinstance(token, str) or len(token) > 8192 or token.count(".") != 2:
        raise OAuthError("Jeton invalide.")
    try:
        key = _signing_key(provider, token)
        claims = jwt.decode(token, key, algorithms=["RS256"], audience=audiences,
                            issuer=list(PROVIDERS[provider]["issuers"]), leeway=60,
                            options={"require": ["exp", "iat", "iss", "aud", "sub"]})
    except (jwt.PyJWTError, OSError) as e:
        raise OAuthError("Jeton refusé.") from e
    # Nonce : le client fournit la valeur brute ; le fournisseur a pu signer la valeur brute (web)
    # ou son SHA-256 (iOS natif). Le nonce n'est accepté qu'une fois.
    tok_nonce = claims.get("nonce")
    if not tok_nonce or tok_nonce not in (nonce, hashlib.sha256((nonce or "").encode()).hexdigest()):
        raise OAuthError("Nonce invalide.")
    if not _consume_nonce(nonce):
        raise OAuthError("Nonce expiré ou déjà utilisé.")
    ev = claims.get("email_verified")
    return {"sub": str(claims["sub"]), "email": (claims.get("email") or "").strip().lower() or None,
            "email_verified": ev is True or ev == "true", "name": claims.get("name"),
            "picture": claims.get("picture") if str(claims.get("picture", "")).startswith(GOOGLE_PICTURE) else None}
