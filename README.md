# MSOA — E-commerce Microservices (Lab 2)

Lab 2 — Microservice-oriented Architectures (Master Big Data & Data Science).

Transformation d'une application e-commerce (frontend React fourni) vers une architecture microservices.

## Structure

```
frontend/            React (Vite) fourni — ne pas modifier pages/composants, seulement src/config/backend.js
services/
  auth/       :8081  Authentification et comptes
  catalog/    :8082  Consultation des produits
  inventory/  :8083  Gestion et réservation des stocks
  orders/     :8084  Création et gestion des commandes (orchestrateur)
  payments/   :8085  Simulation des paiements
  shipping/   :8086  Expédition et suivi
docs/                Réponses Part I (analyse) + Q6 (stratégie de migration)
```

Chaque service a sa propre base SQLite dans `services/<service>/db/` (database-per-service).

## Lancer le frontend

```bash
cd frontend
npm install
npm run dev
```

Compte démo (mode mock) : `demo@msoa.shop` / `demo123`

## Répartition de l'équipe

| Service | Membre | Stack |
|---|---|---|
| Auth | | |
| Catalog | | |
| Inventory | | |
| Orders | | |
| Payments | | |
| Shipping | | |
