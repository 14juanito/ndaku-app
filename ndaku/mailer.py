"""Envoi d'e-mails transactionnels via Resend (https://resend.com) ; journalisés en développement."""
import json
import logging
import urllib.request

log = logging.getLogger("ndaku.mail")


def send(cfg, to, subject, text):
    if not cfg.RESEND_API_KEY:
        # En production, ne jamais journaliser le contenu (il contient des jetons secrets).
        log.warning("E-mail non envoyé (RESEND_API_KEY absent) → %s : %s%s", to, subject,
                    "" if cfg.ON_VERCEL else "\n" + text)
        return False
    req = urllib.request.Request(
        "https://api.resend.com/emails", method="POST",
        data=json.dumps({"from": cfg.MAIL_FROM, "to": [to], "subject": subject, "text": text}).encode(),
        headers={"Authorization": f"Bearer {cfg.RESEND_API_KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=1.5):
            return True
    except OSError as e:
        log.error("Échec d'envoi d'e-mail : %s", e)
        return False
