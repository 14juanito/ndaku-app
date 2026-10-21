-- Ndaku — schéma PostgreSQL (Neon). Idempotent : rejouable à chaque démarrage.
CREATE TABLE IF NOT EXISTS users (
  id              BIGSERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  email           TEXT NOT NULL,
  email_verified  BOOLEAN NOT NULL DEFAULT FALSE,
  pw_hash         TEXT,                                  -- NULL : compte Google/Apple uniquement
  role            TEXT NOT NULL CHECK (role IN ('client','host','admin')),
  phone           TEXT NOT NULL DEFAULT '',
  verified        BOOLEAN NOT NULL DEFAULT FALSE,        -- badge « hôte vérifié » (modération)
  failed_logins   INT NOT NULL DEFAULT 0,
  locked_until    TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_users_email ON users (lower(email));

CREATE TABLE IF NOT EXISTS identities (               -- comptes Google / Apple liés
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider    TEXT NOT NULL CHECK (provider IN ('google','apple')),
  subject     TEXT NOT NULL,
  email       TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (provider, subject)
);

CREATE TABLE IF NOT EXISTS sessions (                 -- jetons opaques, stockés hachés (SHA-256)
  id          BIGSERIAL PRIMARY KEY,
  token_hash  BYTEA NOT NULL UNIQUE,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL CHECK (kind IN ('web','mobile')),
  user_agent  TEXT NOT NULL DEFAULT '',
  ip          TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_seen   TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions (user_id);

CREATE TABLE IF NOT EXISTS email_tokens (             -- vérification d'e-mail / réinitialisation
  token_hash  BYTEA PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  purpose     TEXT NOT NULL CHECK (purpose IN ('verify','reset')),
  expires_at  TIMESTAMPTZ NOT NULL,
  used_at     TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS oauth_nonces (             -- anti-rejeu des ID tokens
  nonce_hash  BYTEA PRIMARY KEY,
  expires_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS rate_limits (
  key           TEXT NOT NULL,
  window_start  TIMESTAMPTZ NOT NULL,
  count         INT NOT NULL,
  PRIMARY KEY (key, window_start)
);

CREATE TABLE IF NOT EXISTS listings (
  id            BIGSERIAL PRIMARY KEY,
  owner_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title         TEXT NOT NULL,
  description   TEXT NOT NULL,
  deal          TEXT NOT NULL CHECK (deal IN ('location','vente')),
  ptype         TEXT NOT NULL,
  city          TEXT NOT NULL,
  commune       TEXT NOT NULL,
  address       TEXT NOT NULL,
  price         NUMERIC(14,2) NOT NULL CHECK (price > 0),
  bedrooms      INT NOT NULL,
  bathrooms     INT NOT NULL,
  surface       INT NOT NULL,
  furnished     BOOLEAN NOT NULL DEFAULT FALSE,
  amenities     JSONB NOT NULL DEFAULT '[]',
  status        TEXT NOT NULL CHECK (status IN ('active','pending','rejected','closed')),
  risk_score    INT NOT NULL DEFAULT 0,
  risk_reasons  JSONB NOT NULL DEFAULT '[]',
  addr_key      TEXT NOT NULL,
  is_demo       BOOLEAN NOT NULL DEFAULT FALSE,     -- annonces d'illustration (affichées comme telles)
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_listings_search ON listings (status, city, deal);
CREATE INDEX IF NOT EXISTS ix_listings_owner ON listings (owner_id);
CREATE INDEX IF NOT EXISTS ix_listings_addr ON listings (addr_key);

-- Une photo est d'abord « en attente » (listing_id NULL), puis rattachée à une annonce.
-- sha UNIQUE : deux annonces ne peuvent jamais partager la même photo, même en concurrence.
CREATE TABLE IF NOT EXISTS images (
  id          BIGSERIAL PRIMARY KEY,
  owner_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  listing_id  BIGINT REFERENCES listings(id) ON DELETE CASCADE,
  url         TEXT NOT NULL,
  storage_key TEXT NOT NULL,
  sha         TEXT NOT NULL UNIQUE,
  dhash       BIGINT NOT NULL,
  phash       BIGINT NOT NULL,
  dhash_m     BIGINT NOT NULL,
  phash_m     BIGINT NOT NULL,
  position    INT NOT NULL DEFAULT 0,
  credit      JSONB,                                  -- auteur / licence pour les photos importées
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_images_listing ON images (listing_id, position);
CREATE INDEX IF NOT EXISTS ix_images_pending ON images (owner_id) WHERE listing_id IS NULL;

CREATE TABLE IF NOT EXISTS favorites (
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, listing_id)
);

CREATE TABLE IF NOT EXISTS inquiries (
  id              BIGSERIAL PRIMARY KEY,
  listing_id      BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  message         TEXT NOT NULL,
  preferred_date  DATE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_inquiries_listing ON inquiries (listing_id);

CREATE TABLE IF NOT EXISTS reviews (
  id          BIGSERIAL PRIMARY KEY,
  listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (listing_id, user_id)
);

CREATE TABLE IF NOT EXISTS reports (
  id          BIGSERIAL PRIMARY KEY,
  listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  reason      TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (listing_id, user_id)
);

CREATE TABLE IF NOT EXISTS security_events (          -- journal d'audit (connexions, liaisons OAuth…)
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT REFERENCES users(id) ON DELETE SET NULL,
  event       TEXT NOT NULL,
  detail      JSONB NOT NULL DEFAULT '{}',
  ip          TEXT NOT NULL DEFAULT '',
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Migrations additives (bases déjà créées)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;
