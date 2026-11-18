# Contrat d'API — Service Catalog

- **Responsable :** Salma
- **URL de base :** `http://localhost:8082`
- **Format :** JSON (UTF-8)
- **Version courante :** 2.0.0
- **Documentation interactive :** `http://localhost:8082/docs`

## Contrat retrocompatible v1

| Opération | Méthode | Endpoint | Succès |
|---|---|---|---|
| Liste des produits | GET | `/products` | 200 |
| Produit par ID | GET | `/products/{product_id}` | 200 |
| Liste des produits (versionnée) | GET | `/api/v1/products` | 200 |
| Produit par ID (versionné) | GET | `/api/v1/products/{product_id}` | 200 |

En-têtes : aucune authentification requise. `Accept: application/json` est recommandé.

Schéma v1 :

| Champ | Type | Obligatoire |
|---|---|---|
| id | integer | oui |
| name | string | oui |
| category | string | oui |
| price | number | oui |
| image | string | oui |
| description | string | oui |

```json
{
  "id": 1,
  "name": "Lenovo ThinkPad E14",
  "category": "Laptops",
  "price": 8499,
  "image": "",
  "description": "Reliable 14-inch business laptop"
}
```

## Contrat avec devises v2

| Opération | Méthode | Endpoint | Succès |
|---|---|---|---|
| Liste des produits | GET | `/api/v2/products` | 200 |
| Produit par ID | GET | `/api/v2/products/{product_id}` | 200 |

Schéma v2 :

| Champ | Type | Obligatoire |
|---|---|---|
| id | integer | oui |
| name | string | oui |
| category | string | oui |
| price.amount | number | oui |
| price.currency | string ISO-4217 | oui |
| image | string | oui |
| description | string | oui |

```json
{
  "id": 1,
  "name": "Lenovo ThinkPad E14",
  "category": "Laptops",
  "price": {
    "amount": 8499,
    "currency": "MAD"
  },
  "image": "",
  "description": "Reliable 14-inch business laptop"
}
```

## Erreurs

FastAPI utilise `{ "detail": "..." }` pour les erreurs.

| Code | Signification |
|---|---|
| 404 Not Found | `{ "detail": "Product not found" }` |
| 422 Unprocessable Entity | Paramètre de chemin ou requête invalide |
| 500 Internal Server Error | Erreur interne inattendue |

## Stratégie d'évolution

Le champ v1 `price` reste numérique. La structure objet est réservée aux endpoints v2.
Cette séparation évite les changements de type qui cassent les clients qui font des opérations
arithmétiques directement sur `price`. Les nouveaux clients doivent lire `price.amount` et
`price.currency`; les anciens clients restent sur v1 jusqu'à leur migration.
