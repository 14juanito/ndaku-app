# Ndaku — location & vente de maisons en RDC

Marketplace style Airbnb (orange/blanc). Web aujourd'hui, apps mobiles ensuite : **le backend est une API JSON** que le site et les futures apps iOS/Android consomment de la même façon.

- Comptes **client** / **hôte** : e-mail + mot de passe, **Google**, **Apple (iCloud)**
- Annonces location ou vente, filtres ville/quartier/prix/chambres, « meilleures maisons »
- Anti-fraude : une même photo (même recadrée, en miroir, recompressée) ne peut jamais servir deux fois
- Demandes de visite, avis vérifiés, favoris, signalements, modération

## Architecture

| Élément | Choix |
|---|---|
| API | Flask (`app.py` → `ndaku/`), fonctions Python Vercel |
| Front web | `public/` (SPA sans framework) servi par le CDN Vercel |
| Base de données | PostgreSQL **Neon** (pooler PgBouncer), schéma `ndaku/schema.sql` migré au démarrage si nécessaire |
| Photos | **Vercel Blob** (public), disque local en développement |
| E-mails | Resend (optionnel) |
| Tâche planifiée | Vercel Cron → `/api/cron/cleanup` (photos orphelines, sessions expirées) |

### API pour les apps mobiles
- Connexion : `POST /api/auth/login`, `/register`, `/oauth/google`, `/oauth/apple` avec `"client": "mobile"` → la réponse contient `token` ; l'envoyer ensuite en `Authorization: Bearer <token>` (à stocker dans le Keychain / Keystore).
- Google / Apple natifs : demander un nonce (`GET /api/auth/nonce`), le passer au SDK (Apple iOS : son SHA-256), puis envoyer `id_token` + `nonce` brut au backend.
- Photos : `POST /api/uploads` (une photo par requête, champ `image`) → `id` ; puis `POST /api/listings` avec `image_ids`.

## Déploiement Vercel + Neon

1. Importer le dépôt dans Vercel (Framework : Flask, détecté automatiquement).
2. **Storage → Neon** (Marketplace) → crée `DATABASE_URL` (utiliser l'URL *pooled*).
3. **Storage → Blob** → crée `BLOB_READ_WRITE_TOKEN`.
4. Variables d'environnement :

| Variable | Rôle |
|---|---|
| `ADMIN_EMAILS` | e-mails (vérifiés) qui deviennent administrateurs |
| `GOOGLE_CLIENT_IDS` | ID(s) client OAuth Google (web, iOS, Android), séparés par des virgules |
| `APPLE_CLIENT_IDS` | Services ID (web) et Bundle ID (iOS) Sign in with Apple |
| `APPLE_REDIRECT_URI` | URL du site (ex. `https://ndaku.vercel.app`) déclarée chez Apple |
| `CRON_SECRET` | secret aléatoire pour la tâche planifiée |
| `RESEND_API_KEY`, `MAIL_FROM` | envoi des e-mails (vérification, mot de passe oublié) ; active la vérification obligatoire |
| `NDAKU_PUBLIC_URL` | URL publique utilisée dans les liens des e-mails |

**Google** : console.cloud.google.com → Identifiants → ID client OAuth « Application Web », origines JavaScript autorisées = URL du site.
**Apple** : developer.apple.com → Identifiers → Services ID avec « Sign in with Apple », domaine + Return URL = URL du site (compte Apple Developer requis).

### Vraies photos
Le conteneur de build n'est pas utilisé : une fois connecté en admin, page **Modération → Importer (photos réelles)**. Le serveur récupère des photos de maisons de Kinshasa et d'autres villes sur Wikimedia Commons (licences libres, auteur et licence affichés sur l'annonce), les passe par l'anti-fraude et crée des annonces **de démonstration** marquées comme telles, en attente : vérifier chaque photo avant d'approuver.

## Développement local
```bash
pip install -r requirements.txt
export DATABASE_URL=postgresql://postgres@localhost:5432/ndaku
python scripts/seed_local.py   # comptes de test + annonces illustrées (refuse une base distante)
python app.py                  # http://localhost:5000
TEST_DATABASE_URL=postgresql://postgres@localhost:5432/ndaku_test python -m pytest tests -q
```

## Sécurité (résumé)
| Menace | Parade |
|---|---|
| Vol de session | Jetons opaques 256 bits stockés hachés (SHA-256), cookie `__Host-` HttpOnly/Secure/SameSite=Lax, révocation à la déconnexion et au changement de mot de passe |
| CSRF | En-tête `X-Ndaku` obligatoire (pré-vol CORS impossible, aucun CORS ouvert) + contrôle `Origin` |
| Brute force | Limites par IP et par compte (Postgres, partagées entre instances), verrouillage 15 min après 5 échecs |
| Énumération de comptes | Réponses et durée identiques (connexion, mot de passe oublié), hachage factice |
| Jetons Google/Apple forgés | RS256 via JWKS, `iss`/`aud`/`exp` vérifiés, `alg=none` et confusion HS256 refusés, nonce à usage unique |
| Pré-détournement de compte | Un compte non vérifié repris via Google/Apple perd son mot de passe et toutes ses sessions |
| Élévation de privilège | Rôle admin uniquement via e-mail vérifié de `ADMIN_EMAILS` ; champs internes ignorés (mass assignment) |
| IDOR | Propriété vérifiée côté serveur (404 sinon) ; photos rattachables seulement par leur auteur |
| Upload malveillant | Décodeurs JPEG/PNG/WebP uniquement, anti-bombe de décompression, ré-encodage (EXIF/GPS et charges polyglottes supprimés) |
| XSS | Échappement systématique côté front + CSP stricte (pas de script inline) |
| SQL injection | Requêtes paramétrées, colonnes/tri en liste blanche |
| Fraude d'annonce | Photos uniques (empreintes exacte + perceptuelles, miroir inclus), adresse unique, coordonnées interdites, prix anormal, description copiée, 3 signalements = masquage, avis réservés aux clients ayant contacté l'hôte |

Tests : `tests/` — 90 tests dont attaques sur l'authentification, OAuth, CSRF, IDOR, uploads et injections.
