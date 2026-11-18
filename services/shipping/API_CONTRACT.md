# Contrat d'API - Shipping

- Responsable : Imane
- URL de base : `http://localhost:8086`
- Format : JSON UTF-8
- Version : `1.0.0`
- Documentation : `/docs`

## En-tetes

| En-tete | Valeur |
|---|---|
| `Content-Type` | `application/json` pour les requetes avec corps |
| `Accept` | `application/json` recommande |

Toutes les erreurs utilisent `{"message":"..."}`.

## Endpoints

### `GET /api/shipments`

Liste toutes les expeditions. Reponse `200` : tableau de Shipment.

### `GET /api/shipments/order/{orderId}`

Recupere l'expedition d'une commande.

Reponse `200` :

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

Erreur `404` : `No shipment found for order {orderId}`.

### `POST /api/shipments`

Corps requis :

```json
{
  "orderId":"order-uuid",
  "address":{"name":"Demo Customer","address":"123 Main Street","city":"Casablanca"}
}
```

Succes `201` : objet Shipment avec `status: "PREPARING"`.

La creation exige une commande existante au statut `PAID`. Une expedition duplicate
pour la meme commande retourne `409`.

### `PATCH /api/shipments/{shipmentId}/status`

Corps requis :

```json
{"status":"SHIPPED"}
```

Transitions autorisees :

`PREPARING -> SHIPPED -> IN_TRANSIT -> DELIVERED`

Chaque changement est valide avant execution. Une transition sautee ou retour en
arriere retourne `409`.

Erreurs : `400` champ requis ou statut invalide, `404` expedition absente,
`409` transition ou statut de commande invalide, `503` Orders indisponible,
`502` reponse invalide.
