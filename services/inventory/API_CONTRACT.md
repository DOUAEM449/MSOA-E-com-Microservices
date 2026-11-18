# Contrat d'API - Inventory

- URL de base : `http://localhost:8083`
- Format : JSON UTF-8
- Version : `1.0.0`
- Documentation : `/docs`

## Communications communes

| Cas | En-tete |
|---|---|
| Requetes avec corps | `Content-Type: application/json` |
| Reponses | `Content-Type: application/json` |

## Endpoints

### `GET /api/inventory/{productId}`

Recupere le stock actuel d'un produit.

Reponse `200` :

```json
{"productId": 1, "stock": 12}
```

Erreurs : `400 Invalid product ID`, `404 Product not found`, `500` au besoin.

### `POST /api/inventory/check`

Verifie sans modifier le stock.

Corps :

```json
{"items":[{"productId":1,"quantity":2},{"productId":2,"quantity":1}]}
```

Reponse `200` :

```json
{"available": true}
```

Une quantite inexistante ou insuffisante retourne `{"available": false}`.
Les champs utilisent les types `integer` strictement positifs.

### `POST /api/inventory/reserve`

Reserve atomiquement tous les articles. Aucune modification n'est appliquee si un article manque de stock.

Reponse `200` :

```json
{"success": true}
```

Erreurs : `409 Insufficient stock for product {id}`, `422` pour un corps invalide,
`500 Internal inventory error`.

### `POST /api/inventory/release`

Restaure le stock reserve pour une annulation autorisee.

Reponse `200` :

```json
{"success": true}
```

Erreurs : `404 Product {id} not found`, `422` pour un corps invalide,
`500 Internal inventory error`.

## Schemas communs

Les erreurs FastAPI peuvent etre `{"detail":"..."}`. Toutes les operations utilisent
`productId` en `integer` et `quantity` en `integer` strictement positif.
