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

-- Migrations additives (bases déjà créées) — incrémenter SCHEMA_VERSION dans db.py
ALTER TABLE listings ADD COLUMN IF NOT EXISTS is_demo BOOLEAN NOT NULL DEFAULT FALSE;

-- ============================================================ v3 : carte, référentiel, messagerie
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT,
                  ADD COLUMN IF NOT EXISTS avatar_key TEXT,
                  ADD COLUMN IF NOT EXISTS suspended_at TIMESTAMPTZ;

-- Référentiel hiérarchique : province > ville > commune > quartier > avenue (une avenue peut aussi
-- dépendre directement d'une commune quand le découpage en quartiers est inconnu).
CREATE TABLE IF NOT EXISTS places (
  id          BIGSERIAL PRIMARY KEY,
  kind        TEXT NOT NULL CHECK (kind IN ('province','city','commune','quartier','avenue')),
  name        TEXT NOT NULL,
  parent_id   BIGINT REFERENCES places(id) ON DELETE CASCADE,
  lat         DOUBLE PRECISION,
  lng         DOUBLE PRECISION,
  source      TEXT NOT NULL DEFAULT 'seed' CHECK (source IN ('seed','osm','user')),
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','pending','rejected')),
  created_by  BIGINT REFERENCES users(id) ON DELETE SET NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_places_name ON places (COALESCE(parent_id, 0), kind, lower(name));
CREATE INDEX IF NOT EXISTS ix_places_children ON places (parent_id, kind, status);

ALTER TABLE listings ADD COLUMN IF NOT EXISTS province TEXT,
                     ADD COLUMN IF NOT EXISTS quartier TEXT,
                     ADD COLUMN IF NOT EXISTS avenue TEXT,
                     ADD COLUMN IF NOT EXISTS house_number TEXT,
                     ADD COLUMN IF NOT EXISTS unit TEXT,
                     ADD COLUMN IF NOT EXISTS province_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
                     ADD COLUMN IF NOT EXISTS city_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
                     ADD COLUMN IF NOT EXISTS commune_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
                     ADD COLUMN IF NOT EXISTS quartier_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
                     ADD COLUMN IF NOT EXISTS avenue_id BIGINT REFERENCES places(id) ON DELETE SET NULL,
                     ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION,
                     ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION,
                     ADD COLUMN IF NOT EXISTS cover_url TEXT,
                     ADD COLUMN IF NOT EXISTS rating_sum INT NOT NULL DEFAULT 0,
                     ADD COLUMN IF NOT EXISTS rating_count INT NOT NULL DEFAULT 0,
                     ADD COLUMN IF NOT EXISTS fav_count INT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS ix_listings_province ON listings (status, province_id);
CREATE INDEX IF NOT EXISTS ix_listings_city ON listings (status, city_id);
CREATE INDEX IF NOT EXISTS ix_listings_commune ON listings (status, commune_id);
CREATE INDEX IF NOT EXISTS ix_listings_quartier ON listings (status, quartier_id);
CREATE INDEX IF NOT EXISTS ix_listings_avenue ON listings (status, avenue_id);
CREATE INDEX IF NOT EXISTS ix_listings_geo ON listings (lat, lng) WHERE status = 'active';
CREATE INDEX IF NOT EXISTS ix_listings_recent ON listings (status, created_at DESC);
-- Une adresse (commune + avenue + numéro + logement) ne peut figurer que dans UNE annonce en ligne ou
-- en modération : garanti par la base, même en cas de publications simultanées.
DROP INDEX IF EXISTS ix_listings_addr;
CREATE UNIQUE INDEX IF NOT EXISTS ux_listings_address ON listings (addr_key) WHERE status IN ('active','pending');

-- Compteurs dénormalisés (tri « meilleures maisons » sans agrégats à chaque requête)
UPDATE listings l SET rating_sum = COALESCE(r.s, 0), rating_count = COALESCE(r.n, 0)
  FROM (SELECT listing_id, SUM(rating) AS s, COUNT(*) AS n FROM reviews GROUP BY 1) r WHERE r.listing_id = l.id;
UPDATE listings l SET fav_count = f.n FROM (SELECT listing_id, COUNT(*) AS n FROM favorites GROUP BY 1) f
  WHERE f.listing_id = l.id;
UPDATE listings l SET cover_url = i.url FROM images i
  WHERE l.cover_url IS NULL AND i.listing_id = l.id AND i.position = 0;

-- Messagerie : une conversation par (annonce, client) ; la demande de visite ouvre la discussion.
CREATE TABLE IF NOT EXISTS conversations (
  id               BIGSERIAL PRIMARY KEY,
  listing_id       BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  client_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  host_id          BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_message_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  client_read_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  host_read_at     TIMESTAMPTZ NOT NULL DEFAULT 'epoch',
  blocked_by       BIGINT REFERENCES users(id) ON DELETE SET NULL,
  UNIQUE (listing_id, client_id),
  CHECK (client_id <> host_id)
);
CREATE INDEX IF NOT EXISTS ix_conv_client ON conversations (client_id, last_message_at DESC);
CREATE INDEX IF NOT EXISTS ix_conv_host ON conversations (host_id, last_message_at DESC);

CREATE TABLE IF NOT EXISTS messages (
  id               BIGSERIAL PRIMARY KEY,
  conversation_id  BIGINT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  sender_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind             TEXT NOT NULL DEFAULT 'text' CHECK (kind IN ('text','visit','contact')),
  body             TEXT NOT NULL,
  meta             JSONB NOT NULL DEFAULT '{}',
  flagged          BOOLEAN NOT NULL DEFAULT FALSE,     -- mention de paiement : avertissement anti-arnaque
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_messages_conv ON messages (conversation_id, id);

-- Reprise des anciennes demandes de visite dans la messagerie
INSERT INTO conversations (listing_id, client_id, host_id, created_at, last_message_at)
  SELECT q.listing_id, q.user_id, l.owner_id, MIN(q.created_at), MAX(q.created_at)
  FROM inquiries q JOIN listings l ON l.id = q.listing_id WHERE q.user_id <> l.owner_id GROUP BY 1, 2, 3
  ON CONFLICT (listing_id, client_id) DO NOTHING;
INSERT INTO messages (conversation_id, sender_id, kind, body, meta, created_at)
  SELECT c.id, q.user_id, 'visit', q.message,
         CASE WHEN q.preferred_date IS NULL THEN '{}'::jsonb ELSE jsonb_build_object('date', q.preferred_date) END,
         q.created_at
  FROM inquiries q JOIN conversations c ON c.listing_id = q.listing_id AND c.client_id = q.user_id
  WHERE NOT EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.sender_id = q.user_id
                    AND m.created_at = q.created_at);

-- Signalements : catégories + suivi par la modération ; signalement d'utilisateurs depuis la messagerie
ALTER TABLE reports ADD COLUMN IF NOT EXISTS category TEXT NOT NULL DEFAULT 'autre',
                    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'open';
CREATE TABLE IF NOT EXISTS user_reports (
  id               BIGSERIAL PRIMARY KEY,
  reporter_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  target_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  conversation_id  BIGINT REFERENCES conversations(id) ON DELETE SET NULL,
  category         TEXT NOT NULL,
  reason           TEXT NOT NULL,
  status           TEXT NOT NULL DEFAULT 'open',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (reporter_id, target_id)
);

-- ============================================================ v4 : position publique (arrondie ~110 m)
-- La recherche par zone de carte filtre sur ces colonnes : impossible de retrouver la position exacte
-- en réduisant la zone de recherche (dichotomie).
ALTER TABLE listings ADD COLUMN IF NOT EXISTS lat_pub NUMERIC(8,3) GENERATED ALWAYS AS (round(lat::numeric, 3)) STORED,
                     ADD COLUMN IF NOT EXISTS lng_pub NUMERIC(8,3) GENERATED ALWAYS AS (round(lng::numeric, 3)) STORED;
DROP INDEX IF EXISTS ix_listings_geo;
CREATE INDEX IF NOT EXISTS ix_listings_geo_pub ON listings (lat_pub, lng_pub) WHERE status = 'active';

-- ============================================================ v5 : qualité des services, confiance, agenda, alertes
-- Qualité déclarée par l'hôte (1 = très mauvais … 10 = parfait) et accès à la maison
ALTER TABLE listings ADD COLUMN IF NOT EXISTS elec_score SMALLINT CHECK (elec_score BETWEEN 1 AND 10),
                     ADD COLUMN IF NOT EXISTS water_score SMALLINT CHECK (water_score BETWEEN 1 AND 10),
                     ADD COLUMN IF NOT EXISTS access_score SMALLINT CHECK (access_score BETWEEN 1 AND 10),
                     ADD COLUMN IF NOT EXISTS access_type TEXT,
                     ADD COLUMN IF NOT EXISTS rain_access BOOLEAN,
                     ADD COLUMN IF NOT EXISTS views INT NOT NULL DEFAULT 0,
                     ADD COLUMN IF NOT EXISTS alerted_at TIMESTAMPTZ;

ALTER TABLE users ADD COLUMN IF NOT EXISTS notify_email BOOLEAN NOT NULL DEFAULT TRUE,
                  ADD COLUMN IF NOT EXISTS notify_sms BOOLEAN NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS notify_whatsapp BOOLEAN NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS host_rating_sum INT NOT NULL DEFAULT 0,
                  ADD COLUMN IF NOT EXISTS host_rating_count INT NOT NULL DEFAULT 0,
                  -- SMS/WhatsApp seulement vers un numéro prouvé par code (sinon : envoi de SMS à un tiers)
                  ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN NOT NULL DEFAULT FALSE,
                  ADD COLUMN IF NOT EXISTS phone_code_hash TEXT,
                  ADD COLUMN IF NOT EXISTS phone_code_expires TIMESTAMPTZ;
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS client_notified_at TIMESTAMPTZ,
                          ADD COLUMN IF NOT EXISTS host_notified_at TIMESTAMPTZ;

-- Vues uniques par jour (statistiques hôte) : l'identifiant du visiteur est haché, jamais stocké en clair
CREATE TABLE IF NOT EXISTS listing_views (
  listing_id  BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  day         DATE NOT NULL DEFAULT CURRENT_DATE,
  viewer      TEXT NOT NULL,
  PRIMARY KEY (listing_id, day, viewer)
);

-- Vérification d'identité : documents stockés en base (jamais servis publiquement), effacés après décision
CREATE TABLE IF NOT EXISTS id_verifications (
  id           BIGSERIAL PRIMARY KEY,
  user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  id_type      TEXT NOT NULL,
  id_doc       BYTEA,
  selfie       BYTEA,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
  note         TEXT NOT NULL DEFAULT '',
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  decided_at   TIMESTAMPTZ,
  decided_by   BIGINT REFERENCES users(id) ON DELETE SET NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_idv_pending ON id_verifications (user_id) WHERE status = 'pending';

-- Alertes de recherche (critères en colonnes pour un appariement SQL direct)
CREATE TABLE IF NOT EXISTS search_alerts (
  id            BIGSERIAL PRIMARY KEY,
  user_id       BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  label         TEXT NOT NULL,
  deal          TEXT, ptype TEXT,
  province_id   BIGINT, city_id BIGINT, commune_id BIGINT, quartier_id BIGINT,
  min_price     NUMERIC(14,2), max_price NUMERIC(14,2), min_bedrooms INT,
  furnished     BOOLEAN NOT NULL DEFAULT FALSE,
  min_elec      SMALLINT, min_water SMALLINT,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_alerts_user ON search_alerts (user_id);

-- Notifications (cloche) ; l'envoi e-mail/SMS/WhatsApp est en plus, selon les préférences
CREATE TABLE IF NOT EXISTS notifications (
  id          BIGSERIAL PRIMARY KEY,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  kind        TEXT NOT NULL,
  title       TEXT NOT NULL,
  body        TEXT NOT NULL DEFAULT '',
  link        TEXT NOT NULL DEFAULT '',
  read_at     TIMESTAMPTZ,
  ext_pending BOOLEAN NOT NULL DEFAULT FALSE,   -- relais e-mail/SMS/WhatsApp encore à envoyer (envoi différé)
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_notif_user ON notifications (user_id, created_at DESC);
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS ext_pending BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_notif_pending ON notifications (created_at) WHERE ext_pending;

-- Agenda de visites : l'hôte ouvre des créneaux, un client en réserve un
CREATE TABLE IF NOT EXISTS visit_slots (
  id               BIGSERIAL PRIMARY KEY,
  listing_id       BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
  starts_at        TIMESTAMPTZ NOT NULL,
  ends_at          TIMESTAMPTZ NOT NULL CHECK (ends_at > starts_at),
  status           TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','booked','cancelled')),
  booked_by        BIGINT REFERENCES users(id) ON DELETE SET NULL,
  booked_at        TIMESTAMPTZ,
  conversation_id  BIGINT REFERENCES conversations(id) ON DELETE SET NULL,
  UNIQUE (listing_id, starts_at)
);
CREATE INDEX IF NOT EXISTS ix_slots_listing ON visit_slots (listing_id, starts_at);

-- Avis sur les hôtes (en plus des avis sur les biens)
CREATE TABLE IF NOT EXISTS host_reviews (
  id          BIGSERIAL PRIMARY KEY,
  host_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating      INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment     TEXT NOT NULL,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (host_id, user_id),
  CHECK (host_id <> user_id)
);

-- ============================================================ v6 : avis modifiables
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;
ALTER TABLE host_reviews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- ============================================================ v7 : modérateurs et journal
-- Modérateur : un client/hôte à qui l'administrateur confie la modération (annonces, signalements, lieux),
-- sans accès aux pièces d'identité, au journal ni à la gestion des comptes.
ALTER TABLE users ADD COLUMN IF NOT EXISTS moderator BOOLEAN NOT NULL DEFAULT FALSE;
CREATE INDEX IF NOT EXISTS ix_events_time ON security_events (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_events_user ON security_events (user_id, created_at DESC);
