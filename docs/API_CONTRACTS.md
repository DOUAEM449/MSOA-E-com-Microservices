# LAB 3 - API Contracts des six microservices

- Format commun : JSON UTF-8
- Header commun pour les corps : `Content-Type: application/json`
- Header recommande pour la session : `Authorization: Bearer <token>`
- Les identifiants des Catalog/Inventory sont des integers
- Les identifiants des Orders/Payments/Shipping sont des strings

## 1. Auth Service

- Responsable : Youssef
- URL de base : `http://localhost:8081`
- Prefixe : `/api/auth`
- Contrat detaille : [Auth API_CONTRACT.md](../services/auth/API_CONTRACT.md)

### `POST /api/auth/register`

Creer un compte client.

Request :

```json
{"name":"Youssef","email":"youssef@example.com","password":"Secret123"}
```

| Champ | Type | Obligatoire | Regle |
|---|---|---|---|
| name | string | oui | non vide |
| email | string | oui | format e-mail valide, unique |
| password | string | oui | 1 a 72 bytes |

Headers : `Content-Type: application/json`

Success `201` :

```json
{"id":"user-uuid","name":"Youssef","email":"youssef@example.com","role":"CUSTOMER"}
```

Errors :

| Code | Message |
|---|---|
| 400 | Champ absent, vide ou mot de passe trop long |
| 409 | `Email already registered.` |
| 500 | Erreur interne |

### `POST /api/auth/login`

Request :

```json
{"email":"demo@msoa.shop","password":"demo123"}
```

Headers : `Content-Type: application/json`

Success `200` :

```json
{
  "user":{"id":"user-1","name":"Demo Customer","email":"demo@msoa.shop","role":"CUSTOMER"},
  "token":"token-opaque"
}
```

Errors : `400` champ absent ou vide ; `401` `Invalid email or password.`

### `GET /api/auth/me`

Headers : `Authorization: Bearer <token>`

Alternative compatible : `?token=<token>`.

Success `200` : objet User.

Erreur `401` : token absent, invalide ou expire.

### `POST /api/auth/logout`

Headers : `Authorization: Bearer <token>`

Success `200` :

```json
{"success":true}
```

Cette operation est idempotente.

## 2. Catalog Service

- Responsable : Salma
- URL de base : `http://localhost:8082`
- Contrat detaille : [Catalog API_CONTRACT.md](../services/catalog/API_CONTRACT.md)

### Contrat legacy v1

| Methode | Endpoint | Success |
|---|---|---|
| GET | `/products` | 200 |
| GET | `/products/{productId}` | 200 |
| GET | `/api/v1/products` | 200 |
| GET | `/api/v1/products/{productId}` | 200 |

Headers : `Accept: application/json` recommande.

Response produit v1 :

```json
{
  "id":1,
  "name":"Lenovo ThinkPad E14",
  "category":"Laptops",
  "price":8499,
  "image":"",
  "description":"Reliable 14-inch business laptop"
}
```

`price` est un nombre.

### Contrat currency-aware v2

| Methode | Endpoint | Success |
|---|---|---|
| GET | `/api/v2/products` | 200 |
| GET | `/api/v2/products/{productId}` | 200 |

Response produit v2 :

```json
{
  "id":1,
  "name":"Lenovo ThinkPad E14",
  "category":"Laptops",
  "price":{"amount":8499,"currency":"MAD"},
  "image":"",
  "description":"Reliable 14-inch business laptop"
}
```

Errors : `404 {"detail":"Product not found"}` ; `422` parametre invalide.

## 3. Inventory Service

- Responsable : Amal
- URL de base : `http://localhost:8083`
- Contrat detaille : [Inventory API_CONTRACT.md](../services/inventory/API_CONTRACT.md)

### `GET /api/inventory/{productId}`

Success `200` :

```json
{"productId":1,"stock":12}
```

Errors : `400 Invalid product ID` ; `404 Product not found`.

### `POST /api/inventory/check`

Request :

```json
{"items":[{"productId":1,"quantity":2},{"productId":2,"quantity":1}]}
```

Success `200` :

```json
{"available":true}
```

Les champs `productId` et `quantity` sont des integers strictement positifs.

### `POST /api/inventory/reserve`

Request identique a `/check`.

Success `200` :

```json
{"success":true}
```

La reservation est atomique : tout est reserve ou rien ne l'est.
Errors : `409 Insufficient stock for product {id}` ; `422` validation ;
`500 Internal inventory error`.

### `POST /api/inventory/release`

Request identique a `/check`.

Success `200` :

```json
{"success":true}
```

Errors : `404 Product {id} not found` ; `422` validation ; `500 Internal inventory error`.

## 4. Orders Service

- Responsable : Douae
- URL de base : `http://localhost:8084`
- Contrat detaille : [Orders API_CONTRACT.md](../services/orders/API_CONTRACT.md)

Structure d'erreur commune :

```json
{"message":"Description lisible"}
```

### `GET /api/orders?userId={id}`

Parametre requis : `userId` string non vide.

Success `200` : tableau d'objets Order.

### `GET /api/orders/{orderId}`

Success `200` :

```json
{
  "id":"order-uuid",
  "userId":"user-1",
  "customer":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca"},
  "items":[{"productId":1,"name":"Lenovo ThinkPad E14","price":8499,"quantity":2}],
  "total":16998,
  "status":"PENDING_PAYMENT",
  "createdAt":"2026-11-18T12:00:00.000Z"
}
```

Error `404` : `Order not found.`

### `POST /api/orders`

Request :

```json
{
  "userId":"user-1",
  "customer":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca","email":"demo@example.com"},
  "items":[{"productId":1,"quantity":2}]
}
```

Success `201` : objet Order complet.

Le service relit les prix chez Catalog et reserve chez Inventory.
Le navigateur ne fournit jamais le prix ou le total.

Errors : `400` validation ; `404` produit absent ; `409` stock insuffisant ;
`502` reponse upstream invalide ; `503` service indisponible ; `504` timeout.

### `PATCH /api/orders/{orderId}/status`

Request :

```json
{"status":"PAID"}
```

Transitions : `PENDING_PAYMENT -> PAID -> SHIPPED -> DELIVERED`.

Errors : `404` commande absente ; `409` transition invalide.

### `POST /api/orders/{orderId}/cancel`

Annule `PENDING_PAYMENT` ou `PAID`, puis libere Inventory.

Success `200` : objet Order avec `"status":"CANCELLED"`.

Errors : `404` commande absente ; `409` commande deja expediee/livree ;
`503` Inventory indisponible ; `500` echec de compensation.

## 5. Payments Service

- Responsable : Taha
- URL de base : `http://localhost:8085`
- Contrat detaille : [Payments API_CONTRACT.md](../services/payments/API_CONTRACT.md)

Structure d'erreur commune :

```json
{"message":"Description lisible"}
```

### `GET /api/payments`

Success `200` : tableau de Payment.

### `GET /api/payments/order/{orderId}`

Success `200` :

```json
{
  "id":"payment-uuid",
  "orderId":"order-uuid",
  "amount":16998,
  "method":"CARD",
  "status":"SUCCESS",
  "createdAt":"2026-11-18T12:00:00.000Z"
}
```

Error `404` : `No payment found for order {orderId}`.

### `POST /api/payments`

Request :

```json
{"orderId":"order-uuid","method":"CARD"}
```

| Champ | Type | Obligatoire |
|---|---|---|
| orderId | string | oui |
| method | string | oui |

Success `201` : Payment avec `"status":"SUCCESS"`.

Le service relit la commande chez Orders, accepte seulement `PENDING_PAYMENT`,
puis demande le passage au statut `PAID`.

Errors : `400` champ requis ; `404` commande absente ; `409` deja payee ou en double ;
`502` reponse Orders invalide ; `503` Orders indisponible ; `500` erreur interne.

## 6. Shipping Service

- Responsable : Imane
- URL de base : `http://localhost:8086`
- Contrat detaille : [Shipping API_CONTRACT.md](../services/shipping/API_CONTRACT.md)

Structure d'erreur commune :

```json
{"message":"Description lisible"}
```

### `GET /api/shipments`

Success `200` : tableau de Shipment.

### `GET /api/shipments/order/{orderId}`

Success `200` :

```json
{
  "id":"shipment-uuid",
  "orderId":"order-uuid",
  "address":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca"},
  "trackingNumber":"TRACK-...",
  "status":"PREPARING",
  "createdAt":"2026-11-18T12:00:00.000Z",
  "updatedAt":"2026-11-18T12:00:00.000Z"
}
```

Error `404` : `No shipment found for order {orderId}`.

### `POST /api/shipments`

Request :

```json
{
  "orderId":"order-uuid",
  "address":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca"}
}
```

Success `201` : Shipment avec `"status":"PREPARING"`.

La commande doit exister au statut `PAID`. Une expedition duplicate retourne `409`.

### `PATCH /api/shipments/{shipmentId}/status`

Request :

```json
{"status":"SHIPPED"}
```

Transitions : `PREPARING -> SHIPPED -> IN_TRANSIT -> DELIVERED`.

Errors : `400` champ requis ou statut invalide ; `404` expedition absente ;
`409` transition ou statut de commande invalide ; `502` reponse invalide ;
`503` Orders indisponible.

## Evolution de l'API Catalog

Les clients anciens ne doivent pas recevoir une structure d'objet a la place du nombre
numerique `price`. La strategie retenue est le versionnement explicite :

- `/products` et `/api/v1/products` : `price` numerique
- `/api/v2/products` : `price.amount` plus `price.currency`

Approches ecartées :

1. Remplacer directement `price` : casse les calculs frontend et Orders.
2. Conserver seulement `price` plus `currency` : ambigu pour plusieurs devises.
3. Modifier sans version : rend incompatible toute integratio déployée en retard.

Orders accepte temporairement les deux formes chez Catalog. Le frontend reste v1 pendant
sa migration vers v2. L'ancien contrat sera deprecie seulement apres inventaire des
consommateurs et une periode de transition.
