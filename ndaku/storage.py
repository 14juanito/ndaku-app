"""Stockage des photos : Vercel Blob en production, disque local en développement/tests."""
import os
import re
import uuid

_SAFE = re.compile(r"^[a-f0-9]{32}\.jpg$")
FOLDERS = {"listings": "", "avatars": "a/"}  # dossier du store → préfixe d'URL /media/


class StorageUnavailable(Exception):
    """Aucun stockage de photos configuré (BLOB_READ_WRITE_TOKEN absent sur Vercel)."""


class Storage:
    def __init__(self, cfg):
        self.cfg = cfg
        self.blob = bool(cfg.BLOB_TOKEN or cfg.BLOB_STORE_ID)
        # Le SDK lit ces noms exacts : on y recopie les valeurs trouvées sous un préfixe personnalisé.
        if cfg.BLOB_TOKEN and cfg.ON_VERCEL:
            os.environ.setdefault("BLOB_READ_WRITE_TOKEN", cfg.BLOB_TOKEN)
        if cfg.BLOB_STORE_ID and cfg.ON_VERCEL:
            os.environ.setdefault("BLOB_STORE_ID", cfg.BLOB_STORE_ID)
        self.mode = ("blob-oidc" if cfg.BLOB_STORE_ID else "blob-token") if self.blob else (
            "none" if cfg.ON_VERCEL else "local")
        # Sur Vercel le disque est en lecture seule : pas de repli local, il faut un store Blob.
        self.available = self.blob or not cfg.ON_VERCEL

    def put(self, jpeg: bytes, folder="listings"):
        """Retourne (url à afficher, clé de stockage). folder : listings (photos) ou avatars."""
        name = f"{uuid.uuid4().hex}.jpg"
        if folder not in FOLDERS:
            raise ValueError(folder)
        if not self.available:
            raise StorageUnavailable()
        if self.blob:
            from vercel.blob.sync import put_blob
            if self.cfg.BLOB_ACCESS == "private":
                put_blob(f"{folder}/{name}", jpeg, access="private", content_type="image/jpeg")
                return f"/media/{FOLDERS[folder]}{name}", f"{folder}/{name}"
            r = put_blob(f"{folder}/{name}", jpeg, access="public", content_type="image/jpeg",
                         cache_control_max_age=31536000)
            return r.url, r.url
        os.makedirs(self.cfg.LOCAL_UPLOADS, exist_ok=True)
        with open(os.path.join(self.cfg.LOCAL_UPLOADS, name), "wb") as f:
            f.write(jpeg)
        return f"/uploads/{name}", name

    def delete(self, keys):
        keys = [k for k in keys if k]
        if not keys:
            return
        if self.blob:
            from vercel.blob.sync import delete_blob
            try:
                delete_blob(keys)
            except Exception:  # noqa: BLE001 — une suppression ratée ne doit pas casser la requête
                pass
            return
        for k in keys:
            if _SAFE.match(k):
                try:
                    os.remove(os.path.join(self.cfg.LOCAL_UPLOADS, k))
                except OSError:
                    pass

    def get_private(self, name, folder="listings"):
        """Octets d'une photo d'un store privé, ou None (nom validé : pas de traversée de chemin)."""
        if not self.blob or not _SAFE.match(name or "") or folder not in FOLDERS:
            return None
        from vercel.blob.sync import BlobNotFoundError, get_blob
        try:
            return get_blob(f"{folder}/{name}", access="private").body
        except BlobNotFoundError:
            return None

    def local_path(self, name):
        """Chemin local sûr (anti path traversal) ou None."""
        if self.blob or not _SAFE.match(name or ""):
            return None
        return os.path.join(self.cfg.LOCAL_UPLOADS, name)
