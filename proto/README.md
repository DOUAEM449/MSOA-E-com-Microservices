# LAB 4 — Scénario 1 : communication haute performance (gRPC)

**Responsables :** Youssef et Taha
**Services concernés :** Orders (client gRPC) → Inventory (serveur gRPC)

## 1. Analyse (Q1)

**a. Orders a-t-il besoin d'une réponse immédiate d'Inventory ?**
Oui. Une commande ne peut être ni enregistrée ni confirmée tant qu'Orders ne sait pas si le stock est suffisant et s'il a bien été réservé. Le client attend la réponse de `POST /api/orders`. La communication doit donc rester **synchrone** (requête → réponse), avec un délai court.

**b. Limites de REST pour des appels fréquents à faible latence**
- **JSON textuel** : messages plus gros, et sérialisation / désérialisation plus coûteuse que le binaire.
- **HTTP/1.1** : une seule requête à la fois par connexion. Sous charge, il faut ouvrir plusieurs connexions, et les en-têtes HTTP sont répétés et non compressés à chaque appel.
- **Contrat faible** : la structure des messages n'est vérifiée qu'à l'exécution, et une incohérence de nom ou de type entre les deux services n'est détectée qu'en production.
- **Validation et parsing manuels** côté client (vérifier les champs, convertir les types).

**c. Caractéristiques attendues d'une alternative**
Elle doit rester **synchrone** (requête / réponse, avec délai maximal), et offrir :
- une **sérialisation binaire compacte** ;
- un **transport multiplexé et persistant** (plusieurs appels sur une même connexion) ;
- un **contrat fortement typé** partagé, qui génère le code client et serveur ;
- des **codes d'erreur standard** ;
- des **deadlines** natives.

## 2. Décision (Q4) : gRPC

| Critère | REST/JSON | **gRPC** | Message broker (RabbitMQ / Kafka) |
|---|---|---|---|
| Réponse immédiate (synchrone) | oui | **oui** | non (asynchrone) |
| Taille des messages | JSON texte | **Protobuf binaire** | dépend |
| Connexion | HTTP/1.1 | **HTTP/2 multiplexé, persistant** | connexion au broker |
| Contrat typé, code généré | non (OpenAPI facultatif) | **oui (`.proto`)** | schéma à part |
| Deadlines / codes d'erreur standard | à la main | **natifs** | non pertinent |

Un broker est écarté parce qu'Orders a besoin de la réponse **avant** de continuer : mettre la demande dans une file ne permettrait pas de confirmer la commande. gRPC garde le modèle synchrone de REST tout en corrigeant ses limites (b).

REST reste en place pour le **frontend**, qui ne parle pas gRPC. Seule l'interaction Orders → Inventory change, comme le demande l'énoncé.

## 3. Contrat : [`inventory.proto`](inventory.proto)

| RPC | Requête | Réponse | Erreurs |
|---|---|---|---|
| `CheckAvailability` | `AvailabilityRequest {productId: string, quantity: int32}` | `AvailabilityResponse {available: bool, availableQuantity: int32}` | `INVALID_ARGUMENT`, `NOT_FOUND` |
| `ReserveStock` | `StockRequest {items: [StockItem {productId, quantity}]}` | `StockResponse {success: bool}` | `INVALID_ARGUMENT`, `FAILED_PRECONDITION` (stock insuffisant : rien n'est modifié) |
| `ReleaseStock` | `StockRequest` | `StockResponse` | `INVALID_ARGUMENT`, `NOT_FOUND` |

`CheckAvailability` reprend exactement le contrat du support de cours. `ReserveStock` et `ReleaseStock` remplacent les appels REST `reserve` / `release` qu'Orders faisait déjà.

Code généré : `services/inventory/inventory_pb2*.py` et `services/orders/inventory_pb2*.py`. Pour le régénérer après une modification du `.proto` :

```bash
pip install grpcio-tools
python proto/generate.py
```

## 4. Implémentation

**Serveur — Inventory** ([`grpc_server.py`](../services/inventory/grpc_server.py))
- Il démarre automatiquement avec `uvicorn main:app --port 8083` et écoute sur **50051**. Le port est configurable avec `INVENTORY_GRPC_PORT`, et `INVENTORY_GRPC_ENABLED=0` le désactive.
- Il utilise la même base SQLite que l'API REST. La réservation est atomique (`BEGIN IMMEDIATE` : tout ou rien).
- Chaque appel est journalisé dans la console d'Inventory.

**Client — Orders** ([`inventory_client.py`](../services/orders/inventory_client.py))
- Un canal HTTP/2 persistant est ouvert au démarrage, puis réutilisé (`INVENTORY_GRPC_ADDR`, par défaut `127.0.0.1:50051`).
- Création d'une commande :
  1. `CheckAvailability` pour chaque produit, en parallèle → `409` si le stock est insuffisant, avec la quantité disponible ;
  2. `ReserveStock`.
- Annulation : `ReleaseStock`.
- **Deadline** de 2 s par appel (`INVENTORY_GRPC_TIMEOUT`).
- **Retry** : un seul, et uniquement pour `CheckAvailability` (lecture). Pas de retry automatique pour `ReserveStock` / `ReleaseStock`, qui modifient le stock.
- Conversion des codes gRPC vers l'API REST d'Orders :

| Code gRPC | HTTP | Message |
|---|---|---|
| `FAILED_PRECONDITION` | 409 | message du serveur |
| `INVALID_ARGUMENT` | 400 | message du serveur |
| `NOT_FOUND` | 404 | message du serveur |
| `UNAVAILABLE` | 503 | `The inventory service is unavailable.` |
| `DEADLINE_EXCEEDED` | 504 | `The inventory service timed out.` |

- `INVENTORY_TRANSPORT=rest` permet de revenir aux anciens appels REST (repli, et comparaison des performances).

L'API REST d'Orders et celle d'Inventory sont **inchangées**.

## 5. Lancer et vérifier

```bash
pip install -r services/inventory/requirements.txt -r services/orders/requirements.txt
cd services/catalog   && python -m uvicorn main:app --port 8082
cd services/inventory && python -m uvicorn main:app --port 8083   # REST 8083 + gRPC 50051
cd services/orders    && python -m uvicorn main:app --port 8084
python proto/demo_grpc.py
```

Avec grpcurl (étape 4 du support) :

```bash
grpcurl -plaintext -proto proto/inventory.proto -d '{"productId":"3","quantity":3}' localhost:50051 inventory.InventoryService/CheckAvailability
```

## 6. Résultats

**Tests automatisés**
- `services/inventory/tests/test_grpc_server.py` : 10 tests (stock suffisant / insuffisant, produit inconnu, quantité invalide, réservation atomique, libération).
- `services/orders/tests/test_inventory_grpc.py` : 3 tests (commande via gRPC, refus sans réservation, Inventory arrêté).
- Les tests existants passent toujours (Inventory 8/8, Orders 6/6).

**Démonstration** (`proto/demo_grpc.py`, services réels, 19/11/2026)

| Scénario (support, étapes 4 et 6) | Résultat |
|---|---|
| Produit 3, quantité 3 | `available: true, availableQuantity: 8` |
| Produit 3, quantité 10000 | `available: false, availableQuantity: 8` |
| Produit 999 | `NOT_FOUND` |
| Quantité 0 | `INVALID_ARGUMENT` |
| Commande de 2 × produit 3 via Orders | `201`, stock 8 → 6 (`ReserveStock`) ; annulation → stock 8 (`ReleaseStock`) |
| Commande de 10000 × produit 3 | `409`, aucune réservation |
| Inventory arrêté | Orders répond `504` en 2,4 s, sans planter et sans enregistrer de commande |
| Inventory redémarré | La commande suivante passe (`201`), le canal se reconnecte seul |

**Latence** : 500 vérifications de disponibilité, en local, REST avec connexion keep-alive.

| | moyenne | médiane | p95 | taille requête + réponse |
|---|---|---|---|---|
| REST (JSON) | 2,04 ms | 1,93 ms | 2,78 ms | 62 octets |
| **gRPC (Protobuf)** | **1,37 ms** | **1,29 ms** | **1,92 ms** | **9 octets** |

gRPC est environ **1,5 fois plus rapide**, et ses messages sont **7 fois plus petits**, en local et sur une seule machine. L'écart augmente avec la charge et sur un vrai réseau, où le multiplexage HTTP/2 et la taille des messages comptent davantage.
