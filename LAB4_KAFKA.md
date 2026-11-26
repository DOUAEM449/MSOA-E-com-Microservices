# LAB 4 – Intégration de Kafka dans l'architecture microservices

## 1. Objectif

L'objectif de ce travail est d'intégrer Apache Kafka dans notre architecture e-commerce basée sur des microservices afin de permettre la communication asynchrone entre les services et la centralisation des événements dans un service Analytics.

Kafka permet aux services de publier des événements sans dépendre directement du service qui les consomme.

## 2. Architecture mise en place

Les services suivants participent à l'architecture événementielle :

- **Orders** : publie les événements liés à la création et à la modification des commandes.
- **Payments** : publie les événements liés à la confirmation des paiements.
- **Shipping** : publie les événements liés à la création et à la modification des expéditions.
- **Analytics** : consomme les événements Kafka et les enregistre dans une base de données SQLite pour produire des statistiques.

Le topic Kafka utilisé est `ecommerce-events`.

Il est configuré avec 3 partitions et un facteur de réplication de 1.

## 3. Événements Kafka implémentés

Les événements publiés utilisent une structure JSON commune contenant notamment :

- `eventId` : identifiant unique de l'événement.
- `eventType` : type de l'événement.
- `source` : microservice émetteur.
- `occurredAt` : date et heure de création.
- `orderId` : identifiant de la commande.
- `data` : informations spécifiques à l'événement.

Les événements implémentés sont :

| Événement               | Service émetteur | Description                             |
| ----------------------- | ---------------- | --------------------------------------- |
| `OrderCreated`          | Orders           | Une commande a été créée.               |
| `OrderStatusChanged`    | Orders           | Le statut d'une commande a changé.      |
| `PaymentCompleted`      | Payments         | Un paiement a été effectué avec succès. |
| `ShipmentCreated`       | Shipping         | Une expédition a été créée.             |
| `ShipmentStatusChanged` | Shipping         | Le statut d'une expédition a changé.    |

La clé Kafka utilisée est `orderId`, afin de regrouper les événements d'une même commande dans la même partition.

## 4. Gestion des producteurs Kafka

Chaque service émetteur possède un module `events.py` qui gère la publication des événements.

La publication intervient après la réussite de l'opération métier correspondante et l'enregistrement des données.

La configuration utilise les variables d'environnement :

- `KAFKA_BOOTSTRAP_SERVERS` : adresse du broker Kafka.
- `KAFKA_TOPIC` : nom du topic utilisé.

La disponibilité de Kafka n'est pas une condition obligatoire pour traiter les requêtes HTTP : en cas d'erreur de publication, le service journalise un avertissement et poursuit son fonctionnement.

## 5. Service Analytics

Un nouveau microservice `analytics` a été ajouté.

Il contient notamment :

- `consumer.py` : consomme les événements depuis Kafka.
- `database.py` : gère la base de données SQLite.
- `analytics_service.py` : réalise les opérations de consultation et de statistiques.
- `routes.py` : définit les endpoints de l'API.
- `main.py` : initialise l'application FastAPI.

Les événements consommés sont enregistrés dans la base de données Analytics.

L'identifiant `eventId` permet d'éviter l'enregistrement plusieurs fois du même événement.

### Endpoints disponibles

| Méthode | Endpoint                 | Description                                    |
| ------- | ------------------------ | ---------------------------------------------- |
| GET     | `/health`                | Vérifie l'état du service.                     |
| GET     | `/api/analytics/summary` | Retourne les statistiques globales.            |
| GET     | `/api/analytics/events`  | Retourne les événements enregistrés.           |
| POST    | `/api/analytics/replay`  | Déclenche une demande de rejeu des événements. |

## 6. Configuration et lancement

### Démarrer Kafka

Depuis le dossier d'installation de Kafka :

```powershell
cd C:\kafka_2.13-4.4.0
.\bin\windows\kafka-server-start.bat .\config\server.properties
```

### Configurer les variables d'environnement

```powershell
$env:KAFKA_BOOTSTRAP_SERVERS="localhost:9092"
$env:KAFKA_TOPIC="ecommerce-events"
```

Ces variables doivent être configurées dans les terminaux utilisés pour lancer les microservices concernés.

### Démarrer Analytics

```powershell
cd services\analytics
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8087
```

La documentation interactive de l'API est accessible à l'adresse :

`http://localhost:8087/docs`

## 7. Vérifications réalisées

Les vérifications effectuées comprennent :

- Démarrage du broker Kafka.
- Publication des événements depuis Orders, Payments et Shipping.
- Consommation des événements par Analytics.
- Enregistrement des événements dans SQLite.
- Consultation des événements et des statistiques via l'API Analytics.
- Vérification des événements à l'aide d'un consommateur Kafka en ligne de commande.

Lors d'une vérification manuelle, le service Analytics a retourné les statistiques suivantes :

| Type d'événement      | Nombre |
| --------------------- | -----: |
| OrderCreated          |     12 |
| OrderStatusChanged    |      7 |
| PaymentCompleted      |      5 |
| ShipmentCreated       |      1 |
| ShipmentStatusChanged |      1 |
| **Total**             | **26** |

Ces valeurs correspondent à une exécution de test et peuvent évoluer lors de nouvelles opérations.

Les tests automatisés d'Orders ont également été exécutés avec succès : 6 tests réussis.

## 8. Conclusion

L'intégration de Kafka permet aux microservices Orders, Payments et Shipping de publier des événements métier de manière asynchrone.

Le service Analytics centralise ces événements et fournit des endpoints permettant de consulter les données et les statistiques.

Cette réalisation illustre l'utilisation d'une architecture événementielle dans une application e-commerce composée de microservices.

### Test pratique : Kafka Retention et reprise du Consumer

Un test de rétention a été réalisé afin de vérifier que les événements Kafka restent disponibles lorsque le service Analytics est temporairement arrêté.

**Étapes du test :**

1. Arrêt du service Analytics sur le port 8087, sans arrêter le broker Kafka.
2. Création de deux nouvelles commandes et réalisation de leurs paiements.
3. Vérification du Consumer Group `analytics-service` pendant l'arrêt :
   - Partition 0 : Lag = 3
   - Partition 1 : Lag = 3
   - Partition 2 : Lag = 0
   - Lag total = 6 événements.
4. Redémarrage du service Analytics.
5. Vérification de la reprise de consommation :
   - Partition 0 : Lag = 0
   - Partition 1 : Lag = 0
   - Partition 2 : Lag = 0
6. Vérification du résumé Analytics après reprise.

**Résultats obtenus :**

- Total Events : 35 → 41
- Total Orders Tracked : 16 → 18
- PaymentCompleted : 8 → 10
- Consumer Lag : 6 → 0

**Conclusion :**

Le test confirme que Kafka conserve les événements produits pendant l'indisponibilité temporaire du service Analytics. Après son redémarrage, le consumer reprend la consommation à partir des offsets enregistrés et traite les six événements en attente. Le lag revient à zéro, ce qui confirme la reprise correcte du traitement.

La configuration `retention.ms = 604800000` correspond à une durée de rétention configurée de 7 jours.

## Q5b — Analytics Consumer (Owner: Amal)

### 1. Architecture et configuration du Consumer

Le service Analytics consomme les événements publiés dans Kafka par les microservices Orders, Payments et Shipping.

Configuration utilisée :

| Paramètre          | Valeur            |
| ------------------ | ----------------- |
| Bootstrap Server   | localhost:9092    |
| Topic              | ecommerce-events  |
| Consumer Group     | analytics-service |
| Auto Offset Reset  | earliest          |
| Enable Auto Commit | false             |
| Port Analytics     | 8087              |

Le Consumer utilise les commits manuels après le traitement des événements afin de contrôler la progression des offsets.

### 2. Gestion des offsets et rétention

La rétention du topic `ecommerce-events` est configurée à 604800000 ms, soit 7 jours.

Un test pratique a été effectué :

- Arrêt temporaire du service Analytics.
- Création et paiement de deux commandes.
- Observation de six événements en attente dans Kafka (Consumer Lag = 6).
- Redémarrage du service Analytics.
- Reprise de la consommation et retour du Consumer Lag à zéro.

Ce test confirme que les événements produits pendant l'indisponibilité d'Analytics ont été conservés dans Kafka et traités après le redémarrage.

### 3. Idempotence

Le service utilise `event_id` comme clé primaire dans la table des événements.

L'insertion utilise `INSERT OR IGNORE`, ce qui empêche l'enregistrement multiple d'un événement ayant le même identifiant.

Cette approche protège les statistiques contre le double comptage lorsqu'un événement est retraité.

### 4. Replay

Un endpoint permet de demander le rejeu des événements :

`POST /api/analytics/replay`

Le rejeu permet de relancer le traitement des événements du topic. L'idempotence basée sur `event_id` évite de dupliquer les événements déjà enregistrés.

Le endpoint a été testé et la réponse a confirmé que la demande de replay a été acceptée. Les totaux sont restés identiques après le test précédent.

### 5. API Analytics

Les endpoints exposés sont :

| Méthode | Endpoint                 | Description                                     |
| ------- | ------------------------ | ----------------------------------------------- |
| GET     | `/health`                | Vérification de disponibilité                   |
| GET     | `/api/analytics/summary` | Statistiques globales                           |
| GET     | `/api/analytics/events`  | Liste des événements avec pagination et filtres |
| POST    | `/api/analytics/replay`  | Demande de rejeu                                |

### 6. Tests automatisés

Les tests couvrent notamment :

- L'initialisation de la base de données.
- L'insertion et l'idempotence des événements.
- Le calcul des statistiques.
- La pagination et le filtrage des événements.
- Les endpoints API.
- Le comportement de l'endpoint Replay.

Résultat obtenu : **14 tests passed**.

### 7. Résultat final

Après le test de rétention et le redémarrage du Consumer :

- Total Events : 41
- Total Orders Tracked : 18
- Consumer Lag : 0 sur les trois partitions.

Le service Analytics est intégré au script `scripts/start-services.ps1` et démarre sur le port 8087 avec le contrôle de santé `/health`.

**Conclusion :** Le service Analytics assure la consommation des événements Kafka, leur stockage idempotent, la consultation des statistiques et la reprise du traitement après une interruption temporaire.
