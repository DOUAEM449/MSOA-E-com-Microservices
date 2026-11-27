# Lab 5 · API Gateway & Service Discovery · Réponses

Équipe : Douae (leader), Youssef, Taha, Imane, Amal, Salma.
Chacun complète **uniquement sa section** (ne pas modifier celles des autres, pour éviter les conflits).

| Partie | Responsable | Statut |
|---|---|---|
| P1 Part I · Q1, Q2, Q3 | Youssef | à faire |
| P1 Q4, 5a, 5b | Douae | ✅ fait |
| P1 5c (transparence HTTP) | Youssef | à faire |
| P1 5d (frontend) | Taha | à faire |
| P1 5e (vérification direct vs gateway) | Youssef + Taha | à faire |
| P2 Part I · Q1 | Imane | à faire |
| P2 Part I · Q2, Q3 | Amal | à faire |
| P2 Part II · 4a–4d (registry) | Imane | à faire |
| P2 Part III · 5a–5e (discovery dynamique) | Amal | à faire |
| P2 Q6 | Douae | ✅ fait |
| P3 a–d (Analytics + interception) | Salma | à faire |
| P3 e (accès desktop uniquement) | Imane | à faire |
| P3 f (vérification Edge) | Taha | à faire |

---

## Problem 1 · Too Many Entry Points

### PART I · Analyse

#### Q1. Communication directe vs intermédiaire commun (Youssef)

_À compléter._

#### Q2. L'intermédiaire doit-il porter la logique métier ? (Youssef)

_À compléter._

#### Q3. Pattern architectural retenu (Youssef)

_À compléter._

### PART II · Implémentation

#### Q4. Mise en place de la solution retenue (Douae)

La solution retenue en Part I est le pattern **API Gateway** : un point d'entrée unique placé entre le
frontend et les six microservices. Nous l'avons ajouté sous la forme d'une **application indépendante**,
`services/api-gateway/`, sans modifier aucun microservice existant.

```
               ┌──────────────────────────────┐
 Frontend ───► │  API Gateway  :8080          │
 (5173)        │  1. routage (préfixe → nom)  │
               │  2. adresse du service       │
               │  3. forward transparent      │
               └──────┬───────────────────────┘
        ┌─────────┬───┴─────┬──────────┬───────────┬───────────┐
        ▼         ▼         ▼          ▼           ▼           ▼
     Auth      Catalog  Inventory   Orders     Payments    Shipping
     :8081     :8082    :8083       :8084      :8085       :8086

  gRPC (Orders → Inventory), RabbitMQ (Payments → Shipping) et Kafka (→ Analytics :8087)
  restent des communications internes : elles ne passent pas par la gateway.
```

Choix de conception :

- **Rôle limité à la coordination de l'accès.** La gateway ne contient aucune règle métier
  (pas de calcul de prix, pas de vérification de stock) : elle reçoit, choisit le service, transmet,
  et renvoie la réponse telle quelle. La logique métier reste dans chaque microservice, qui garde
  son indépendance (règle fondamentale du lab).
- **Technologie : Python + FastAPI** (et non Express.js). Toute la plateforme est déjà en
  FastAPI : même langage, mêmes outils de test (`pytest`, `httpx.MockTransport`), même script de
  lancement. FastAPI est asynchrone (ASGI) : une requête qui attend un service ne bloque pas les
  autres. Les appels sortants passent par **un seul `httpx.AsyncClient`** créé au démarrage
  (`lifespan`), qui réutilise les connexions (pool) au lieu d'en ouvrir une par requête.
- **Contrats REST inchangés.** La gateway ne réécrit pas les chemins : `/api/orders/123` est transmis
  tel quel au service Orders. Les endpoints existants n'ont donc pas eu à changer.
- **Noms logiques dès le départ.** Le routage associe un préfixe à un **nom logique**
  (`catalog-service`), puis le nom à une adresse. En Problem 1 l'adresse vient d'une table statique ;
  en Problem 2 seule cette étape est remplacée par le registry, sans toucher au routage.
- **Points d'extension prévus** dans `main.py` pour le registry (`/registry/*`), la découverte
  dynamique, le middleware d'activité et le contrôle desktop (Problem 3).

Fichiers : `main.py` (application), `config.py` (configuration), `routes.py` (table de routage),
`proxy.py` (transmission), `tests/test_gateway.py` (26 tests).

#### 5a. Initialisation de la gateway (Douae)

- Application dédiée : `services/api-gateway/`, avec son propre environnement Python (`.venv`) et
  son `requirements.txt` (`fastapi`, `uvicorn[standard]`, `httpx`, `user-agents`, `pytest`).
- Serveur HTTP **uvicorn** sur le port **8080** :

  ```powershell
  cd services\api-gateway
  .\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8080
  ```

  Le script `scripts/start-services.ps1` la lance automatiquement **en dernier**, après les services
  vers lesquels elle route, et vérifie `GET /health`.
- Route propre à la gateway : `GET /health` → `200 {"status": "UP", "service": "api-gateway"}`.
  Elle est déclarée avant la route « attrape-tout », donc elle n'est jamais transmise à un service.
- Configuration externalisée (`config.py`) : port (`GATEWAY_PORT`), délai d'attente vers les
  services (`GATEWAY_UPSTREAM_TIMEOUT`, 5 s par défaut) et adresses (`<NOM>_URL`) se changent par
  variables d'environnement, sans modifier le code.

Preuve : [lab5-evidence/p1-gateway-douae.md §1](lab5-evidence/p1-gateway-douae.md).

#### 5b. Routage des requêtes, adresses statiques (Douae)

Une route « attrape-tout » (`/{path:path}`, toutes méthodes) reçoit chaque requête, puis :

1. **Choix du service** (`routes.match`) selon le préfixe du chemin :

   | Préfixe | Nom logique | Adresse statique |
   |---|---|---|
   | `/api/auth` | `auth-service` | `http://127.0.0.1:8081` |
   | `/products`, `/api/v1/products`, `/api/v2/products` | `catalog-service` | `http://127.0.0.1:8082` |
   | `/api/inventory` | `inventory-service` | `http://127.0.0.1:8083` |
   | `/api/orders` | `orders-service` | `http://127.0.0.1:8084` |
   | `/api/payments` | `payments-service` | `http://127.0.0.1:8085` |
   | `/api/shipments` | `shipping-service` | `http://127.0.0.1:8086` |
   | `/api/analytics` | `events-analytics-service` (Kafka, Lab 4) | `http://127.0.0.1:8087` |
   | `/activity` | `analytics-service` (Problem 3) | `ANALYTICS_SERVICE_URL` |

   Le préfixe le plus long est testé en premier, et il doit correspondre à un segment complet :
   `/products/3` va vers Catalog, `/productsX` ne correspond à rien.
2. **Adresse du service** : lue dans la table statique (`config.static_services()`), surchargeable
   par variable d'environnement (ex. `CATALOG_SERVICE_URL=http://127.0.0.1:9192`).
3. **Transmission** (`proxy.forward`) : même méthode, même chemin, mêmes paramètres de requête,
   mêmes en-têtes utiles et même corps ; la réponse du service (code, corps, en-têtes dont CORS) est
   renvoyée au client.

Erreurs propres à la gateway :

| Cas | Réponse |
|---|---|
| Aucun préfixe ne correspond | `404 {"error": "No route for /xyz"}` |
| Le service n'a pas d'adresse | `503 {"error": "<nom> is not registered"}` |
| Toute réponse d'un service (201, 400, 401, 404, 409…) | renvoyée sans modification |

Vérification (services + gateway lancés) : 10 requêtes vers les 7 services donnent **exactement la
même réponse** (code et corps) en direct et via la gateway, y compris les erreurs métier (401 Auth,
400 Orders, 404 Payments/Shipping) et le preflight CORS du frontend.
Détails : [lab5-evidence/p1-gateway-douae.md §2–§4](lab5-evidence/p1-gateway-douae.md).
Tests automatisés : `26 passed`.

#### 5c. Transparence HTTP (Youssef)

_À compléter._

#### 5d. Intégration frontend (Taha)

_À compléter._

#### 5e. Vérification (Youssef + Taha)

_À compléter._

---

## Problem 2 · When Services Change Addresses

### PART I · Analyse

#### Q1. Liste statique vs registry (Imane)

_À compléter._

#### Q2. Découverte côté client ou côté intermédiaire (Amal)

_À compléter._

#### Q3. Conception du mécanisme d'enregistrement et de découverte (Amal)

_À compléter._

### PART II · Registry (Imane)

#### 4a–4d

_À compléter._

### PART III · Découverte dynamique (Amal)

#### 5a–5e

_À compléter._

### Q6. Le pattern qui aurait évité les valeurs codées en dur (Douae)

**Pattern : Externalized Configuration** (facteur III « Config » de la méthode *12-Factor App*).
Le principe : **tout ce qui change d'un environnement à l'autre** (adresses, ports, URL des brokers,
chemins de base de données, origines CORS, délais, secrets) **ne doit pas être écrit dans le code**,
mais fourni au service au démarrage, par variables d'environnement ou par un serveur de
configuration. Le même code (le même artefact) tourne alors en local, en test et en production ;
seule la configuration change.

**Ce que nous avons vécu sans ce pattern :**

- Le frontend contient six adresses (`src/config/backend.js`, ports 8081 à 8086) : passer par la
  gateway oblige à modifier ce fichier, et chaque déplacement d'un service aussi.
- La même liste d'origines CORS (`localhost:5173`, `5174`, `5175`, puis la même chose en
  `127.0.0.1`) est recopiée dans le `main.py` de chacun des six services : ajouter une origine
  impose six modifications.
- Les ports sont figés dans `scripts/start-services.ps1`, et Catalog lit un chemin de base fixe.
  Le scénario du Problem 2 (Catalog déplacé de 8082 vers 9192) casse alors tout client qui connaît
  l'ancienne adresse.

Les Labs 3 et 4 montrent déjà la bonne direction : `ORDERS_URL`, `CATALOG_URL`, `INVENTORY_URL`,
`INVENTORY_GRPC_ADDR`, `RABBITMQ_URL`, `KAFKA_BOOTSTRAP_SERVERS` se lisent avec `os.getenv(...)` et
une valeur par défaut pour le développement. La gateway suit la même règle (`config.py`). Le problème
vient de ce qui est resté codé en dur à côté.

**Comment l'appliquer dès le début :**

1. **Un module de configuration par service** (`config.py`), seul endroit qui lit l'environnement,
   avec des valeurs par défaut pour le développement local et une validation au démarrage (par
   exemple `pydantic-settings`) : le service refuse de démarrer si une valeur obligatoire manque,
   au lieu d'échouer plus tard.
2. **Externaliser chaque valeur dépendante de l'environnement** : `PORT`, URL des services appelés,
   `RABBITMQ_URL`, `KAFKA_BOOTSTRAP_SERVERS`, chemin de la base, `CORS_ORIGINS` (une liste), délais.
3. **Documenter sans divulguer** : un `.env.example` versionné par service, le vrai `.env` ignoré
   par Git ; les secrets (mots de passe des brokers, clés JWT) ne sont jamais dans le dépôt.
4. **Frontend** : une seule variable (`VITE_API_URL`, l'adresse de la gateway) au lieu d'une adresse
   par service.
5. **Par environnement** : `docker-compose` (`environment:` / `env_file:`), puis, à plus grande
   échelle, un serveur de configuration centralisé (Spring Cloud Config, Consul KV, Kubernetes
   ConfigMaps et Secrets).

Externalized Configuration et Service Discovery se complètent : la configuration indique à chaque
composant **où trouver le registry ou la gateway** ; la découverte fournit ensuite, à chaque
requête, **l'adresse actuelle** des instances, qui peut changer sans redémarrer personne.

---

## Problem 3 · Client-Aware Analytics (Bonus)

#### a–d. Déploiement, enregistrement, interception, journalisation (Salma)

_À compléter._

#### e. Accès desktop uniquement à `GET /activity` (Imane)

_À compléter._

#### f. Vérification avec Microsoft Edge (Taha)

_À compléter._
