"""Données de développement LOCAL uniquement (refuse de tourner contre une base distante).

    python scripts/seed_local.py            # annonces d'illustration + comptes de test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ndaku import create_app  # noqa: E402
from ndaku.db import one, run  # noqa: E402
from ndaku.demo import create_demo  # noqa: E402
from ndaku.security import hash_password  # noqa: E402

PASSWORD = os.environ.get("NDAKU_DEV_PASSWORD", "Ndaku-Dev-2026")

app = create_app()
url = app.config["NDAKU"].DATABASE_URL
if "localhost" not in url and "127.0.0.1" not in url:
    sys.exit("Refus : ce script ne tourne que sur une base locale (comptes de test à mot de passe connu).")
with app.app_context():
    for name, email, role in (("Admin Local", "admin@local.test", "admin"), ("Hôte Local", "hote@local.test", "host"),
                              ("Client Local", "client@local.test", "client")):
        if not one("SELECT 1 FROM users WHERE email=%s", (email,)):
            run("INSERT INTO users (name, email, email_verified, pw_hash, role, verified) VALUES (%s,%s,TRUE,%s,%s,TRUE)",
                (name, email, hash_password(PASSWORD), role))
    while True:
        res = create_demo(app.config["STORAGE"], source="illustrations", max_listings=4)
        print(res["created"], res["skipped"])
        if res["done"]:
            break
    from ndaku.db import close
    close(None)
print(f"OK — comptes admin@ / hote@ / client@local.test, mot de passe : {PASSWORD}")
