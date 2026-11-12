# MSOA — E-commerce Microservices (Lab 2)

Lab 2 — Microservice-oriented Architectures (Master Big Data & Data Science).

Transformation d'une application e-commerce (frontend React fourni) vers une architecture microservices.

## Structure

```
Racine (comme le repo du prof)  React (Vite) — ne pas modifier pages/composants, seulement src/config/backend.js
services/
  auth/       :8081  Authentification et comptes
  catalog/    :8082  Consultation des produits
  inventory/  :8083  Gestion et réservation des stocks
  orders/     :8084  Création et gestion des commandes (orchestrateur)
  payments/   :8085  Simulation des paiements
  shipping/   :8086  Expédition et suivi
docs/                answers.md : réponses Part I (analyse) + Q6 (stratégie de migration)
                     INTEGRATION.md : communications inter-services + preuves de tests
```

Chaque service a sa propre base SQLite dans `services/<service>/db/` (database-per-service).

## Lancer le frontend

```bash

npm install
npm run dev
```

Compte démo (mode mock) : `demo@msoa.shop` / `demo123`

## Répartition de l'équipe

| Service | Membre | Stack | Base de données |
|---|---|---|---|
| Auth | Youssef | Python (FastAPI) | SQLite (`services/auth/db/auth.db`) |
| Catalog | Salma | Python (FastAPI) | SQLite (`services/catalog/db/catalog.db`) |
| Inventory | Amal | Python (FastAPI) | SQLite (`services/inventory/db/inventory.db`) |
| Orders + Intégration | Douae (leader) | Python (FastAPI, client `httpx`) | SQLite (`services/orders/db/`) |
| Payments | Taha | Python (FastAPI, client `httpx`) | SQLite (`services/payments/db/`) |
| Shipping | Taha | Python (FastAPI, client `httpx`) | SQLite (`services/shipping/db/`) |

Communications entre services et preuves de tests : voir [INTEGRATION.md](INTEGRATION.md).
Réponses Part I et Q6 : voir [answers.md](answers.md).
