"""Notifications : toujours dans l'application (cloche), et selon les préférences de l'utilisateur
par e-mail (Resend), SMS ou WhatsApp (Twilio). Les canaux externes ne reçoivent jamais le contenu
d'un message privé, seulement une invitation à ouvrir Ndaku."""
import base64
import logging
import time
import urllib.parse
import urllib.request

from . import mailer
from .db import all_, one, run
from .security import cfg

log = logging.getLogger("ndaku.notify")


def _twilio(to, text, whatsapp=False):
    c = cfg()
    sender = c.TWILIO_WHATSAPP_FROM if whatsapp else c.TWILIO_FROM
    if not (c.TWILIO_ACCOUNT_SID and c.TWILIO_AUTH_TOKEN and sender and to):
        return False
    dest = f"whatsapp:{to}" if whatsapp else to
    src = f"whatsapp:{sender}" if whatsapp and not sender.startswith("whatsapp:") else sender
    req = urllib.request.Request(
        f"https://api.twilio.com/2010-04-01/Accounts/{urllib.parse.quote(c.TWILIO_ACCOUNT_SID)}/Messages.json",
        data=urllib.parse.urlencode({"To": dest, "From": src, "Body": text[:600]}).encode(), method="POST",
        headers={"Authorization": "Basic " + base64.b64encode(f"{c.TWILIO_ACCOUNT_SID}:{c.TWILIO_AUTH_TOKEN}".encode()).decode()})
    try:
        with urllib.request.urlopen(req, timeout=2):
            return True
    except OSError as e:
        log.error("Échec d'envoi Twilio : %s", e)
        return False


def e164(phone):
    """+243 81 234 5678 → +243812345678 (les SMS exigent le format international)."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return None
    if (phone or "").strip().startswith("+"):
        return "+" + digits
    if digits.startswith("0") and len(digits) == 10:  # numéro congolais local 08…
        return "+243" + digits[1:]
    return "+" + digits


def _relay(user_id, title, body, link):
    u = one("SELECT email, phone, notify_email, notify_sms, notify_whatsapp, suspended_at FROM users WHERE id=%s",
            (user_id,))
    if not u or u["suspended_at"]:
        return
    url = f"{cfg().PUBLIC_URL}/{link.lstrip('/')}" if link else cfg().PUBLIC_URL
    text = f"Ndaku : {title}. {url}"
    if u["notify_email"] and not u["email"].endswith(".invalid"):
        mailer.send(cfg(), u["email"], f"Ndaku — {title}", f"{title}\n\n{body}\n\nOuvrir Ndaku : {url}")
    if u["notify_sms"]:
        _twilio(e164(u["phone"]), text)
    if u["notify_whatsapp"]:
        _twilio(e164(u["phone"]), text, whatsapp=True)


def notify(user_id, kind, title, body="", link="", external=True, defer=False):
    """Crée la notification et, si external, la relaie par les canaux choisis par l'utilisateur.
    defer=True : le relais externe est laissé à flush_pending() (envois en masse, ex. alertes)."""
    title, body, link = title[:140], body[:500], link[:200]
    run("INSERT INTO notifications (user_id, kind, title, body, link, ext_pending) VALUES (%s,%s,%s,%s,%s,%s)",
        (user_id, kind, title, body, link, bool(external and defer)))
    if external and not defer:
        _relay(user_id, title, body, link)


def flush_pending(limit=50, budget=4.0):
    """Relaie les notifications différées, dans une limite de temps (fonctions serverless)."""
    t0, sent = time.monotonic(), 0
    rows = all_("""UPDATE notifications SET ext_pending=FALSE WHERE id IN (
                     SELECT id FROM notifications WHERE ext_pending ORDER BY created_at LIMIT %s FOR UPDATE SKIP LOCKED)
                   RETURNING id, user_id, title, body, link""", (limit,))
    for i, r in enumerate(rows):
        if time.monotonic() - t0 > budget:
            run("UPDATE notifications SET ext_pending=TRUE WHERE id = ANY(%s)", ([x["id"] for x in rows[i:]],))
            break
        _relay(r["user_id"], r["title"], r["body"], r["link"])
        sent += 1
    return sent


def channels():
    c = cfg()
    twilio = bool(c.TWILIO_ACCOUNT_SID and c.TWILIO_AUTH_TOKEN)
    return {"email": bool(c.RESEND_API_KEY), "sms": twilio and bool(c.TWILIO_FROM),
            "whatsapp": twilio and bool(c.TWILIO_WHATSAPP_FROM)}

