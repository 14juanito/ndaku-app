"""Accès PostgreSQL (Neon) : pool de connexions + migration idempotente au démarrage."""
import atexit
import os
import threading

from flask import current_app, g
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")
_pools = {}
_lock = threading.Lock()


def pool(url, side=False):
    """side=True : pool séparé pour les écritures hors transaction (committed), afin qu'une requête
    qui tient déjà une connexion n'attende jamais une seconde connexion du même pool."""
    key = (url, side)
    with _lock:
        p = _pools.get(key)
        if p is None:
            # prepare_threshold=None : compatible avec le pooler PgBouncer de Neon (mode transaction).
            p = ConnectionPool(url, min_size=0, max_size=int(os.environ.get("DB_POOL_MAX", "5")),
                               kwargs={"row_factory": dict_row, "prepare_threshold": None, "autocommit": False},
                               check=ConnectionPool.check_connection, open=True)
            _pools[key] = p
            atexit.register(p.close)
        return p


SCHEMA_VERSION = 7  # à incrémenter à chaque modification de schema.sql


def migrate(url):
    """Rejoue schema.sql seulement si la base est en retard : un démarrage à froid ne coûte qu'un SELECT
    et ne prend aucun verrou DDL sur les tables."""
    with pool(url).connection() as con:
        if con.execute("SELECT to_regclass('public.schema_meta') AS t").fetchone()["t"]:
            row = con.execute("SELECT version FROM schema_meta").fetchone()
            if row and row["version"] >= SCHEMA_VERSION:
                return
        con.execute("SELECT pg_advisory_xact_lock(424242)")
        con.execute(open(_SCHEMA).read())
        from .places_seed import seed
        seed(con)
        con.execute("CREATE TABLE IF NOT EXISTS schema_meta (version INT NOT NULL)")
        con.execute("DELETE FROM schema_meta")
        con.execute("INSERT INTO schema_meta VALUES (%s)", (SCHEMA_VERSION,))


def db():
    """Connexion de la requête courante (transaction validée à la fin si pas d'erreur)."""
    if "db" not in g:
        g._db_pool = pool(current_app.config["NDAKU"].DATABASE_URL)
        g.db = g._db_pool.getconn()
    return g.db


def close(exc):
    con = g.pop("db", None)
    if con is None:
        return
    try:
        if exc is None and not g.get("db_rollback"):
            con.commit()
        else:
            con.rollback()
    finally:
        g._db_pool.putconn(con)


def one(sql, args=()):
    return db().execute(sql, args).fetchone()


def all_(sql, args=()):
    return db().execute(sql, args).fetchall()


def run(sql, args=()):
    return db().execute(sql, args)


def committed(sql, args=()):
    """Écriture validée immédiatement, hors transaction de la requête : survit à un abort()
    (compteurs anti-brute-force, journal d'audit)."""
    with pool(current_app.config["NDAKU"].DATABASE_URL, side=True).connection() as con:
        cur = con.execute(sql, args)
        return cur.fetchone() if cur.description else None
