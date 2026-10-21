"""Stockage des photos : Vercel Blob en production, disque local en développement/tests."""
import os
import re
import uuid

_SAFE = re.compile(r"^[a-f0-9]{32}\.jpg$")


class Storage:
    def __init__(self, cfg):
        self.cfg = cfg
        self.blob = bool(cfg.BLOB_TOKEN)
        if not self.blob:
            os.makedirs(cfg.LOCAL_UPLOADS, exist_ok=True)

    def put(self, jpeg: bytes):
        """Retourne (url publique, clé de stockage)."""
        name = f"{uuid.uuid4().hex}.jpg"
        if self.blob:
            from vercel.blob.sync import put_blob
            r = put_blob(f"listings/{name}", jpeg, access="public", content_type="image/jpeg",
                         cache_control_max_age=31536000)
            return r.url, r.url
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

    def local_path(self, name):
        """Chemin local sûr (anti path traversal) ou None."""
        if self.blob or not _SAFE.match(name or ""):
            return None
        return os.path.join(self.cfg.LOCAL_UPLOADS, name)
