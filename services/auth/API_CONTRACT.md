# Contrat d'API — Service Auth

- **Responsable :** Youssef
- **URL de base :** `http://localhost:8081`
- **Préfixe :** `/api/auth`
- **Format :** JSON (UTF-8)
- **Version du contrat :** 1.0.0
- **Spécification OpenAPI :** générée par FastAPI sur `GET /openapi.json` (copie dans [`openapi.json`](openapi.json)). Interface Swagger : `/docs`.
- **Collection Postman :** [`postman/auth.postman_collection.json`](postman/auth.postman_collection.json)

## a. Opérations exposées

| Opération | Méthode | Endpoint |
|---|---|---|
| Créer un compte client | `POST` | `/api/auth/register` |
| Se connecter et obtenir un jeton | `POST` | `/api/auth/login` |
| Obtenir l'utilisateur connecté | `GET` | `/api/auth/me` |
| Se déconnecter (invalider le jeton) | `POST` | `/api/auth/logout` |

## En-têtes HTTP communs (f)

| En-tête | Quand | Valeur |
|---|---|---|
| `Content-Type` | Requêtes avec corps (`register`, `login`) | `application/json` |
| `Authorization` | `me`, `logout` | `Bearer <token>` (le jeton reçu au `login`) |
| `Content-Type` (réponse) | Toujours | `application/json` |

Le jeton peut aussi être passé en paramètre de requête `?token=<token>` (compatibilité). L'en-tête `Authorization` est la forme recommandée.

## Schéma d'erreur commun (j)

Toutes les erreurs, quel que soit l'endpoint, ont la même structure :

```json
{ "message": "string" }
```

| Code | Signification |
|---|---|
| `400 Bad Request` | Champ manquant ou vide, format invalide, JSON mal formé |
| `401 Unauthorized` | Identifiants incorrects, ou jeton absent / invalide / expiré |
| `404 Not Found` | Route inconnue |
| `409 Conflict` | E-mail déjà utilisé |
| `500 Internal Server Error` | Erreur inattendue du service |

## Schémas de données

**User** (réponse) :

| Champ | Type | Description |
|---|---|---|
| `id` | string | Identifiant unique (UUID, ou `user-1` pour le compte démo) |
| `name` | string | Nom complet |
| `email` | string | E-mail, en minuscules |
| `role` | string | `CUSTOMER` (ou `ADMIN`) |

Le mot de passe et son haché ne sont **jamais** renvoyés.

---

## 1. `POST /api/auth/register`

- **b.** `POST /api/auth/register`
- **c. But :** créer un compte client. Le mot de passe est stocké haché avec bcrypt.
- **d. Paramètres d'URL :** aucun.
- **e. Paramètres de données :** corps JSON.
- **f. En-têtes :** `Content-Type: application/json`.
- **g. Corps de la requête :**

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| `name` | string | oui | non vide (espaces retirés) |
| `email` | string | oui | format `x@domaine.tld`, unique sans tenir compte de la casse, stocké en minuscules |
| `password` | string | oui | non vide, 72 octets au maximum (limite de bcrypt) |

```json
{ "name": "Youssef", "email": "youssef@example.com", "password": "Secret123" }
```

- **h. Succès :** `201 Created`
- **i. Réponse :** un objet **User**.

```json
{ "id": "5b0c…", "name": "Youssef", "email": "youssef@example.com", "role": "CUSTOMER" }
```

- **j. Erreurs :**

| Code | `message` |
|---|---|
| 400 | `name is required.` / `email is required.` / `password is required.` (champ absent) |
| 400 | `All fields are required.` (champ vide) |
| 400 | `Invalid email format.` |
| 400 | `Password must be at most 72 bytes.` |
| 409 | `Email already registered.` |

## 2. `POST /api/auth/login`

- **b.** `POST /api/auth/login`
- **c. But :** vérifier les identifiants et ouvrir une session. Renvoie l'utilisateur et un jeton.
- **d. Paramètres d'URL :** aucun.
- **e. Paramètres de données :** corps JSON.
- **f. En-têtes :** `Content-Type: application/json`.
- **g. Corps de la requête :**

| Champ | Type | Obligatoire |
|---|---|---|
| `email` | string | oui (non vide, sans tenir compte de la casse) |
| `password` | string | oui (non vide) |

```json
{ "email": "demo@msoa.shop", "password": "demo123" }
```

- **h. Succès :** `200 OK`
- **i. Réponse :**

| Champ | Type |
|---|---|
| `user` | **User** |
| `token` | string (jeton de session opaque) |

```json
{
  "user": { "id": "user-1", "name": "Demo Customer", "email": "demo@msoa.shop", "role": "CUSTOMER" },
  "token": "token-3f1c2a9e-8b7d-4c1e-9f0a-1234567890ab"
}
```

- **j. Erreurs :**

| Code | `message` |
|---|---|
| 400 | `email is required.` / `password is required.` / `Email and password are required.` |
| 401 | `Invalid email or password.` (même message si l'e-mail n'existe pas, pour ne pas révéler quels comptes existent) |

## 3. `GET /api/auth/me`

- **b.** `GET /api/auth/me`
- **c. But :** retrouver l'utilisateur correspondant au jeton. Le frontend l'utilise pour restaurer la session.
- **d. Paramètres d'URL :** aucun (option : `?token=<token>`).
- **e. Paramètres de données :** aucun corps.
- **f. En-têtes :** `Authorization: Bearer <token>`.
- **g. Corps de la requête :** aucun.
- **h. Succès :** `200 OK`
- **i. Réponse :** un objet **User**.
- **j. Erreurs :**

| Code | `message` |
|---|---|
| 401 | `Missing or invalid token.` (pas de jeton) |
| 401 | `Session expired or invalid token.` (jeton inconnu ou déconnecté) |

## 4. `POST /api/auth/logout`

- **b.** `POST /api/auth/logout`
- **c. But :** invalider le jeton. Après cet appel, `GET /me` avec ce jeton renvoie `401`.
- **d. Paramètres d'URL :** aucun (option : `?token=<token>`).
- **e. Paramètres de données :** aucun corps.
- **f. En-têtes :** `Authorization: Bearer <token>`.
- **g. Corps de la requête :** aucun.
- **h. Succès :** `200 OK`. L'opération est **idempotente** : la réponse est la même si le jeton est déjà invalide ou absent.
- **i. Réponse :**

```json
{ "success": true }
```

- **j. Erreurs :** aucune erreur métier.

---

## Vérification

- **Tests automatisés :** `python -m pytest -q tests` (14 tests). Ils vérifient les codes, la forme des réponses et le schéma d'erreur `{"message"}` pour chaque cas ci-dessus.
- **Postman :** importer `postman/auth.postman_collection.json`, lancer le service, puis exécuter la collection avec *Run collection*. Chaque requête contient des tests sur le code et la structure de la réponse.
