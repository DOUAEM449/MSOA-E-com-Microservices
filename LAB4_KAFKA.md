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

| Événement | Service émetteur | Description |
|---|---|---|
| `OrderCreated` | Orders | Une commande a été créée. |
| `OrderStatusChanged` | Orders | Le statut d'une commande a changé. |
| `PaymentCompleted` | Payments | Un paiement a été effectué avec succès. |
| `ShipmentCreated` | Shipping | Une expédition a été créée. |
| `ShipmentStatusChanged` | Shipping | Le statut d'une expédition a changé. |

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

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/health` | Vérifie l'état du service. |
| GET | `/api/analytics/summary` | Retourne les statistiques globales. |
| GET | `/api/analytics/events` | Retourne les événements enregistrés. |
| POST | `/api/analytics/replay` | Déclenche une demande de rejeu des événements. |

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

| Type d'événement | Nombre |
|---|---:|
| OrderCreated | 12 |
| OrderStatusChanged | 7 |
| PaymentCompleted | 5 |
| ShipmentCreated | 1 |
| ShipmentStatusChanged | 1 |
| **Total** | **26** |

Ces valeurs correspondent à une exécution de test et peuvent évoluer lors de nouvelles opérations.

Les tests automatisés d'Orders ont également été exécutés avec succès : 6 tests réussis.

## 8. Conclusion

L'intégration de Kafka permet aux microservices Orders, Payments et Shipping de publier des événements métier de manière asynchrone.

Le service Analytics centralise ces événements et fournit des endpoints permettant de consulter les données et les statistiques.

Cette réalisation illustre l'utilisation d'une architecture événementielle dans une application e-commerce composée de microservices.