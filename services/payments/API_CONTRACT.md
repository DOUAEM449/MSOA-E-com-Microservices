# Contrat d'API - Payments

- URL de base : `http://localhost:8085`
- Format : JSON UTF-8
- Version : `1.0.0`
- Documentation : `/docs`

## En-tetes

| En-tete | Valeur |
|---|---|
| `Content-Type` | `application/json` pour `POST /api/payments` |
| `Accept` | `application/json` recommande |

Toutes les erreurs utilisent `{"message":"..."}`.

## Endpoints

### `GET /api/payments`

Liste tous les paiements. Reponse `200` : tableau de Payment.

### `GET /api/payments/order/{orderId}`

Recupere le paiement d'une commande.

Reponse `200` :

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

Erreur `404` : `No payment found for order {orderId}`.

### `POST /api/payments`

Corps requis :

```json
{"orderId":"order-uuid","method":"CARD"}
```

Champs :

| Champ | Type | Obligatoire | Règle |
|---|---|---|---|
| orderId | string | oui | non vide |
| method | string | oui | non vide, exemples : `CARD`, `CASH` |

Succes `201` : objet Payment avec `status: "SUCCESS"`.

Le service consulte Orders pour verifier que la commande existe, son total et son statut
`PENDING_PAYMENT`. Apres paiement, il demande a Orders de passer la commande a `PAID`.

Erreurs : `400` champ requis, `404` commande absente, `409` commande deja payee ou
paiement en double, `502` reponse Orders invalide, `503` Orders indisponible,
`500` erreur interne.
