# Intégration — communications entre services et preuves de tests

## 1. Communications inter-services

Tous les échanges sont **synchrones, en REST (HTTP/JSON)**. Les appels sortants utilisent `httpx` avec des timeouts. Aucun service n'accède à la base d'un autre.

| Appelant | Appelé | Appel | But |
|---|---|---|---|
| Orders | Catalog | `GET /products/{id}` (un par produit, en parallèle) | Obtenir le nom et le **prix officiel** ; le prix du frontend est ignoré |
| Orders | Inventory | `POST /api/inventory/reserve` | Réserver toutes les lignes de façon atomique |
| Orders | Inventory | `POST /api/inventory/release` | Rendre le stock (annulation, ou échec d'enregistrement : compensation) |
| Payments | Orders | `GET /api/orders/{id}` | Vérifier que la commande existe, est `PENDING_PAYMENT` et lire le montant |
| Payments | Orders | `PATCH /api/orders/{id}/status` `{"status":"PAID"}` | Passer la commande à `PAID` |
| Shipping | Orders | `GET /api/orders/{id}` | Vérifier que la commande est `PAID` avant de créer l'expédition |

Le **frontend** appelle chaque service directement sur son port (voir `src/config/backend.js`).
Auth n'est appelé que par le frontend : les autres services ne valident pas encore le jeton (voir § 4).

### Orchestration du passage de commande

Orders est l'**orchestrateur** :

```
Catalog (prix) → Inventory (réservation atomique) → enregistrement PENDING_PAYMENT
```

Ensuite, Payments fait passer la commande à `PAID`, puis Shipping prend le relais.

### Gestion des erreurs

| Situation | Réponse |
|---|---|
| Stock insuffisant | Inventory `409`, propagé par Orders en `409` ; aucune modification de stock |
| Produit inconnu | `404` |
| Service appelé injoignable | `503` |
| Timeout | `504` (Orders) |
| Transition de statut invalide | `409` |

Les erreurs sont renvoyées au format `{"message": "..."}`, que lit `src/services/apiClient.js`.

## 2. Lancer l'ensemble

Dans six terminaux, depuis `services/<service>/` :

```bash
python -m uvicorn main:app --port 8081   # auth
python -m uvicorn main:app --port 8082   # catalog
python -m uvicorn main:app --port 8083   # inventory
python -m uvicorn main:app --port 8084   # orders
python -m uvicorn main:app --port 8085   # payments
python -m uvicorn main:app --port 8086   # shipping
```

Ensuite, passez les capacités voulues à `"rest"` dans `src/config/backend.js` et lancez `npm run dev`.

## 3. Preuves de tests

### 3.1 Tests unitaires des services

Exécutés le 12/11/2026 sur une copie des services (Python 3.12, FastAPI 0.136) :

| Service | Commande | Résultat |
|---|---|---|
| Orders | `cd services/orders && python -m pytest -q` | **6/6 OK** |
| Inventory | `cd services/inventory && python -m pytest -q` | **3/8 OK, 5 échecs** |

Les échecs d'Inventory (`test_get_stock`, `test_check_available_stock`, `test_reserve_stock`, `test_reservation_atomicity`, `test_release_stock`) renvoient 404 / `available: false`. La base de test temporaire semble ne pas être remplie par `seed.sql`. Le service lui-même fonctionne avec la base du dépôt (voir 3.2). À corriger par le responsable d'Inventory.

### 3.2 Scénario de bout en bout (6 services réels)

Les 6 services ont été lancés ensemble sur une copie, sans modifier les `.db` du dépôt, et appelés en HTTP. Résultat : **25/26 vérifications OK**.

| # | Vérification | Résultat |
|---|---|---|
| 1 | Auth : inscription → 201 | ✅ |
| 2 | Auth : e-mail déjà utilisé → 409 | ✅ |
| 3 | Auth : connexion → `user` + `token` | ✅ |
| 4 | Auth : mauvais mot de passe → 401 | ✅ |
| 5 | Auth : `GET /api/auth/me` avec le jeton | ✅ |
| 6 | Catalog : liste des produits avec `id, name, category, price, image, description` | ✅ |
| 7 | Catalog : produit inconnu → 404 | ✅ |
| 8 | Inventory : `check` d'une quantité supérieure au stock → `available: false` | ✅ |
| 9 | Orders : commande dépassant le stock → 409 | ✅ |
| 10 | Stock inchangé après ce refus (atomicité) | ✅ |
| 11 | Orders : commande créée → 201, `PENDING_PAYMENT` | ✅ |
| 12 | Total calculé avec le prix de Catalog (prix `0.01` envoyé par le client ignoré) | ✅ |
| 13 | Stock réservé (−2) | ✅ |
| 14 | `GET /api/orders?userId=` ne renvoie que les commandes de cet utilisateur | ✅ |
| 15 | Annulation d'une commande `PENDING_PAYMENT` → `CANCELLED` | ✅ |
| 16 | Stock restauré après annulation | ✅ |
| 17 | Paiement → 201 `SUCCESS` | ✅ |
| 18 | Commande passée à `PAID` | ✅ |
| 19 | Double paiement → 409 | ✅ |
| 20 | Expédition créée → `PREPARING` | ✅ |
| 21 | Saut `PREPARING → DELIVERED` → 409 | ✅ |
| 22–24 | `SHIPPED → IN_TRANSIT → DELIVERED` → 200 | ✅ |
| 25 | **Commande déjà livrée : annulation refusée (attendu 409)** | ❌ **200, commande `CANCELLED`** |
| 26 | CORS preflight depuis `http://localhost:5173` | ✅ |

## 4. Limites connues

1. **Shipping ne met pas à jour le statut de la commande** (échec n° 25). Orders reste en `PAID` pendant toute l'expédition, donc `POST /api/orders/{id}/cancel` est encore accepté pour une commande expédiée ou livrée, et le stock est rendu à tort. Cela viole le critère « une commande expédiée ne peut plus être annulée ». Correction proposée :
   - Shipping appelle `PATCH /api/orders/{id}/status` avec `SHIPPED` lors du passage à `SHIPPED`, et avec `DELIVERED` lors du passage à `DELIVERED`. Le statut `IN_TRANSIT` reste propre à Shipping.
   - Orders accepte déjà ces transitions.
2. **Le jeton Auth n'est pas vérifié par les autres services.** Orders fait confiance au `userId` reçu. Une amélioration serait que la gateway ou chaque service valide le jeton auprès d'Auth (`GET /api/auth/me`) ou via un JWT signé.
3. **Sessions Auth en mémoire.** Les jetons sont perdus au redémarrage du service.
4. **`src/config/backend.js` sur `main`** contient des restes de conflit de merge qui empêchent le frontend de compiler. À corriger avant la démonstration.
