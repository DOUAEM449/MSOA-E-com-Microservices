# Contrat d'API — Payments Service

- URL de base : `http://localhost:8085`
- Format : JSON UTF-8
- Version : `1.0.0`
- Documentation interactive : `/docs` (Swagger UI)

---

## En-têtes requis

| En-tête        | Valeur                                       |
|----------------|----------------------------------------------|
| `Content-Type` | `application/json` (pour `POST /api/payments`) |
| `Accept`       | `application/json` (recommandé)              |

---

## Schéma d'erreur uniforme

Toutes les erreurs retournent un objet JSON avec une seule clé :

```json
{"message": "Description lisible de l'erreur"}
```

---

## Endpoints

### 1. `GET /health`

**Objet** : Vérifier que le service est actif.

| Élément            | Valeur         |
|--------------------|----------------|
| **Méthode HTTP**   | `GET`          |
| **URL**            | `/health`      |
| **Paramètres URL** | Aucun          |
| **Corps requis**   | Aucun          |
| **En-têtes**       | Aucun          |

**Réponse succès** — `200 OK` :

```json
{"status": "UP"}
```

---

### 2. `GET /api/payments`

**Objet** : Lister tous les paiements enregistrés (du plus récent au plus ancien).

| Élément            | Valeur             |
|--------------------|--------------------|
| **Méthode HTTP**   | `GET`              |
| **URL**            | `/api/payments`    |
| **Paramètres URL** | Aucun              |
| **Corps requis**   | Aucun              |
| **En-têtes**       | Aucun              |

**Réponse succès** — `200 OK` :

```json
[
  {
    "id": "payment-a1b2c3d4",
    "orderId": "order-demo-001",
    "amount": 16998,
    "method": "CARD",
    "status": "SUCCESS",
    "createdAt": "2026-11-18T12:00:00Z"
  }
]
```

**Schéma de réponse** :

| Champ       | Type     | Description                                   |
|-------------|----------|-----------------------------------------------|
| `id`        | `string` | Identifiant unique du paiement                |
| `orderId`   | `string` | Identifiant de la commande associée           |
| `amount`    | `number` | Montant total payé (lu depuis Orders)         |
| `method`    | `string` | Méthode de paiement (`CARD`, `CASH`, etc.)    |
| `status`    | `string` | Statut : `SUCCESS`, `FAILED`, `PENDING`, `REFUNDED` |
| `createdAt` | `string` | Date de création (ISO 8601 UTC)               |

---

### 3. `GET /api/payments/order/{orderId}`

**Objet** : Récupérer le paiement associé à une commande spécifique.

| Élément            | Valeur                               |
|--------------------|--------------------------------------|
| **Méthode HTTP**   | `GET`                                |
| **URL**            | `/api/payments/order/{orderId}`      |
| **Paramètres URL** | `orderId` (string, obligatoire) — ID de la commande |
| **Corps requis**   | Aucun                                |
| **En-têtes**       | Aucun                                |

**Réponse succès** — `200 OK` :

```json
{
  "id": "payment-a1b2c3d4",
  "orderId": "order-demo-001",
  "amount": 16998,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-18T12:00:00Z"
}
```

**Erreurs** :

| Code  | Condition                       | Message exemple                              |
|-------|---------------------------------|----------------------------------------------|
| `404` | Aucun paiement pour cet orderId | `No payment found for order {orderId}`       |

---

### 4. `POST /api/payments`

**Objet** : Créer un paiement pour une commande. Le service vérifie auprès du service Orders que la commande existe et est en statut `PENDING_PAYMENT`, puis enregistre le paiement et met à jour le statut de la commande à `PAID`.

| Élément            | Valeur                |
|--------------------|-----------------------|
| **Méthode HTTP**   | `POST`                |
| **URL**            | `/api/payments`       |
| **Paramètres URL** | Aucun                 |
| **En-têtes**       | `Content-Type: application/json` |

**Schéma du corps de la requête** :

```json
{
  "orderId": "order-demo-001",
  "method": "CARD"
}
```

| Champ     | Type     | Obligatoire | Contrainte                                    |
|-----------|----------|-------------|-----------------------------------------------|
| `orderId` | `string` | Oui         | Non vide, doit correspondre à une commande existante |
| `method`  | `string` | Oui         | Non vide. Exemples : `CARD`, `CASH`           |

**Réponse succès** — `201 Created` :

```json
{
  "id": "payment-a1b2c3d4",
  "orderId": "order-demo-001",
  "amount": 16998,
  "method": "CARD",
  "status": "SUCCESS",
  "createdAt": "2026-11-18T12:01:00Z"
}
```

**Logique métier** :

1. Le service interroge Orders (`GET /api/orders/{orderId}`) pour récupérer la commande.
2. Vérifie que le statut est `PENDING_PAYMENT`.
3. Enregistre le paiement avec le montant `total` de la commande (jamais depuis le frontend).
4. Envoie un `PATCH /api/orders/{orderId}/status` avec `{"status": "PAID"}`.
5. Si le PATCH échoue, le paiement est supprimé (compensation) et une erreur est retournée.

**Erreurs** :

| Code  | Condition                                   | Message exemple                                                     |
|-------|---------------------------------------------|---------------------------------------------------------------------|
| `400` | Champ `orderId` ou `method` manquant/vide   | `orderId is required` / `method is required`                        |
| `404` | Commande introuvable dans Orders            | `Order {orderId} not found`                                         |
| `409` | Commande pas en `PENDING_PAYMENT`           | `Order {orderId} is not pending payment (current: PAID)`            |
| `409` | Paiement en double pour la même commande    | `Payment already exists for order {orderId}`                        |
| `409` | Commande annulée entre GET et PATCH         | `Order {orderId} can no longer be paid`                             |
| `502` | Réponse inattendue du service Orders        | `Unexpected response from Orders service` / `Orders service could not mark the order as PAID, payment was not recorded` |
| `503` | Service Orders indisponible                 | `Orders service is unavailable`                                     |
| `500` | Erreur interne                              | `Internal server error`                                             |

---

## Interactions avec les autres microservices

### Dépendances (Payments → Orders)

| Interaction                     | Méthode HTTP | Endpoint côté Orders              | Données échangées              |
|---------------------------------|-------------|-----------------------------------|--------------------------------|
| Récupérer une commande          | `GET`       | `/api/orders/{orderId}`           | Objet Order (total, status)    |
| Mettre à jour le statut à PAID  | `PATCH`     | `/api/orders/{orderId}/status`    | `{"status": "PAID"}`           |

### Services qui consomment Payments

| Service consommateur | Endpoint consommé                     | Usage                               |
|----------------------|---------------------------------------|--------------------------------------|
| Frontend (React)     | `GET /api/payments/order/{orderId}`   | Afficher le statut de paiement       |
| Frontend (React)     | `POST /api/payments`                  | Déclencher le paiement d'une commande |
| Frontend (React)     | `GET /api/payments`                   | Lister l'historique des paiements     |

---

## Schéma de la base de données

```sql
CREATE TABLE payments (
    id         TEXT PRIMARY KEY,
    order_id   TEXT NOT NULL UNIQUE,
    amount     REAL NOT NULL CHECK(amount >= 0),
    method     TEXT NOT NULL,
    status     TEXT NOT NULL CHECK(status IN ('SUCCESS','FAILED','PENDING','REFUNDED')),
    created_at TEXT NOT NULL
);
```

---

## Tests de contrat

Les tests automatisés se trouvent dans `tests/test_payments.py` et couvrent :

- ✅ Health check
- ✅ Liste vide des paiements
- ✅ Création d'un paiement avec succès (201)
- ✅ Récupération d'un paiement par orderId (200)
- ✅ Paiement introuvable (404)
- ✅ Paiement en double (409)
- ✅ Commande introuvable (404)
- ✅ Commande pas en PENDING_PAYMENT (409)
- ✅ Champs manquants (400)
- ✅ Service Orders indisponible (503)
- ✅ Compensation (rollback) si PATCH échoue (502)
- ✅ Compensation si PATCH retourne 409
- ✅ Format d'erreur uniforme `{"message": "..."}`
- ✅ CORS preflight

La collection Postman est disponible dans `postman/payments.postman_collection.json`.
