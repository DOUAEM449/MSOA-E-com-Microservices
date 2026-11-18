# Contrat d'API - Orders

- URL de base : `http://localhost:8084`
- Format : JSON UTF-8
- Version : `1.0.0`
- Documentation : `/docs`

## En-tetes

| En-tete | Valeur |
|---|---|
| `Content-Type` | `application/json` pour les requetes avec corps |
| `Authorization` | `Bearer <token>` recommande pour les integrations futures |

Toutes les erreurs sont actuellement de structure :

```json
{"message":"Description lisible de l'erreur"}
```

## Endpoints

### `GET /api/orders?userId={id}`

Liste les commandes d'un utilisateur, de la plus recente a la plus ancienne.

Parametre requis : `userId` string non vide.

Reponse `200` : tableau d'objets Order.

### `GET /api/orders/{orderId}`

Recupere une commande avec ses lignes.

Reponse `200` :

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

Erreur `404` : `Order not found.`

### `POST /api/orders`

Corps requis :

```json
{
  "userId":"user-1",
  "customer":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca","email":"demo@example.com"},
  "items":[{"productId":1,"quantity":2}]
}
```

Succes `201`.

Le service relit les produits chez Catalog et reserve le stock chez Inventory.
Les prix fournis par le navigateur ne sont pas acceptes comme source de verite.

Erreurs : `400` validation, `404` produit absent, `409` stock insuffisant,
`502` reponse invalide ou indisponibilite Catalog, `503` service indisponible,
`504` timeout.

### `PATCH /api/orders/{orderId}/status`

Corps :

```json
{"status":"PAID"}
```

Etats autorises : `PENDING_PAYMENT -> PAID -> SHIPPED -> DELIVERED`.
Le statut `CANCELLED` est traite par le workflow d'annulation.

Erreurs : `404` commande absente, `409` transition invalide.

### `POST /api/orders/{orderId}/cancel`

Annule seulement `PENDING_PAYMENT` ou `PAID`, puis libere le stock reserve.

Reponse `200` : objet Order avec `"status":"CANCELLED"`.

Erreurs : `404` commande absente, `409` commande deja expediee/livree,
`503` Inventory indisponible, `500` echec de compensation.
