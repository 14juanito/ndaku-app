"""Point d'entrée Vercel (détection Flask automatique) et serveur de développement local."""
import os

from ndaku import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("NDAKU_DEBUG")))
