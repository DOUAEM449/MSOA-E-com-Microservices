# Part I — Analyse

## Q1 — 3 arguments pour MSOA

### Argument 1 — Scalabilité indépendante par capacité métier

**Problème.** Pendant les campagnes promotionnelles, la consultation des produits reçoit un trafic très élevé, alors que les paiements et les expéditions ont une charge différente. Dans le monolithe, on ne peut faire monter en charge que l'application entière : on duplique aussi le code des paiements, des commandes, etc., même s'ils ne sont pas sollicités.

**Apport de MSOA.** Chaque capacité est déployée comme un processus séparé. On peut lancer plusieurs instances de **Catalog** derrière un répartiteur de charge pendant une promotion, sans toucher à **Payments** ni **Shipping**. Les ressources suivent la charge réelle de chaque service, et une saturation du catalogue ne fait pas tomber le paiement.

### Argument 2 — Isolation des changements et des pannes

**Problème.** Une modification de la gestion des stocks peut casser le traitement des commandes, parce que les deux partagent le même backend, le même modèle de données et le même cycle de build. Chaque changement oblige à reconstruire et redéployer toute l'application.

**Apport de MSOA.** **Inventory** possède sa propre base et n'est accessible qu'à travers un contrat REST (`/api/inventory/check`, `/reserve`, `/release`). Tant que ce contrat est respecté, l'implémentation interne peut changer (schéma, règles de réservation) sans impact sur **Orders**. Le service est testé et redéployé seul, et une panne reste locale : Orders répond `503` au lieu de planter.

### Argument 3 — Autonomie des équipes et intégration de nouvelles fonctionnalités

**Problème.** Plusieurs équipes travaillent sur des capacités différentes et se gênent dans une même base de code. L'entreprise veut aussi ajouter des fonctionnalités et intégrer des services externes (passerelle de paiement, transporteur) sans modifier tout le backend.

**Apport de MSOA.** Chaque équipe possède un service de bout en bout : code, base de données, déploiement et choix technologique. Dans notre projet, chaque membre a développé un service et peut choisir sa stack. Une nouvelle intégration externe (par exemple un vrai prestataire de paiement) se fait **dans** Payments, sans toucher aux autres services, puisque le contrat `POST /api/payments` reste le même.

## Q2 — Décomposition en microservices

**Stratégie utilisée : décomposition par capacité métier (*business capability*)**, affinée par les **sous-domaines DDD** (*bounded contexts*). Chaque service correspond à une chose que l'entreprise *fait* et possède les données de ce domaine. Nous n'avons pas découpé par couche technique (UI / logique / données), car cela recrée le couplage du monolithe.

| Service | Port | Responsabilité métier | Données possédées | Pourquoi une frontière indépendante |
|---|---|---|---|---|
| **Auth** | 8081 | Comptes clients, inscription, connexion, sessions | Utilisateurs, hachés des mots de passe, jetons | Sous-domaine générique et sensible (sécurité). Il change rarement et doit être isolé pour limiter l'exposition des données d'identification. |
| **Catalog** | 8082 | Consultation des produits (nom, catégorie, prix, image, description) | Produits et prix | Le plus sollicité (lecture intensive, pics promotionnels). Il doit pouvoir être mis à l'échelle seul. C'est la **source de vérité des prix**. |
| **Inventory** | 8083 | Disponibilité et réservation atomique des stocks | Quantités en stock | Règles propres (réservation atomique, libération) qui changent indépendamment des commandes. C'est le problème explicitement cité dans l'énoncé. |
| **Orders** | 8084 | Création et cycle de vie des commandes, orchestration du scénario d'achat | Commandes, lignes de commande, statuts | Cœur du domaine. Il coordonne les autres services mais ne possède ni les prix ni les stocks. |
| **Payments** | 8085 | Enregistrement des paiements et passage de la commande à `PAID` | Paiements | Charge différente du catalogue. Point d'intégration naturel d'une passerelle externe, avec des exigences propres (idempotence, compensation). |
| **Shipping** | 8086 | Création et suivi des expéditions (`PREPARING → SHIPPED → IN_TRANSIT → DELIVERED`) | Expéditions, statuts de livraison | Cycle de vie propre, après le paiement. Point d'intégration d'un transporteur externe. |

**Panier.** Le panier n'est pas un service backend : dans le frontend fourni, il est géré côté client (`CartContext`) et aucun contrat REST n'est défini pour lui. Il ne devient une donnée serveur qu'au moment du `POST /api/orders`. Un service *Cart* pourrait être ajouté plus tard (panier persistant multi-appareils) sans changer les autres frontières.

**Database-per-service.** Chaque service a sa propre base SQLite dans `services/<service>/db/`. Aucun service ne lit la base d'un autre : toute donnée externe passe par l'API REST de son propriétaire.

## Q3 — Évaluation (cohésion, couplage, autonomie, data ownership)

Pour vérifier que le découpage est bon, on évalue chaque service selon les quatre principes du cours.

| Principe | Question posée | Évaluation de notre architecture |
|---|---|---|
| **Cohésion forte** | Les opérations d'un service changent-elles pour la même raison métier ? | Oui. Toutes les opérations d'Inventory concernent le stock. Celles de Shipping concernent le suivi de livraison. Un changement de règle de stock ne touche qu'Inventory. |
| **Couplage faible** | Peut-on modifier un service sans modifier les autres ? | Oui, tant que le contrat REST est respecté. Les services ne partagent ni code ni base. Orders ne connaît d'Inventory que trois endpoints. |
| **Autonomie** | Le service peut-il être développé, testé, déployé et mis à l'échelle seul ? | Oui. Chaque service a son port, sa base, ses dépendances et ses tests (par exemple `services/orders/tests`). Chaque membre a pu choisir sa stack. |
| **Propriété des données** | Chaque donnée a-t-elle un seul propriétaire ? | Oui. Les prix appartiennent à Catalog : Orders les **relit** au moment de la commande au lieu de faire confiance au frontend. Le stock appartient à Inventory. Le statut de commande appartient à Orders : Payments le modifie via `PATCH /api/orders/{id}/status`, jamais directement. |

**Autres signaux vérifiés :**
- Un scénario métier courant ne nécessite pas une cascade d'appels synchrones : la commande appelle Catalog, puis Inventory, et c'est tout.
- Aucune transaction distribuée n'est nécessaire : les incohérences sont gérées par compensation (voir Q4).

**Problème potentiel en cas de mauvais découpage : le « monolithe distribué ».**
Si l'on avait séparé *Orders* et *Inventory* tout en gardant une **base de données partagée** (Orders décrémentant directement la table `stock`), ou si l'on avait découpé par couche technique, chaque changement de schéma casserait plusieurs services à la fois. On cumulerait alors les inconvénients des deux mondes : la latence et la complexité réseau des microservices, plus le couplage et les déploiements coordonnés du monolithe. Un découpage trop fin produit le même effet. Par exemple, un service séparé pour les « lignes de commande » imposerait des appels réseau constants (*chatty services*) et une cohérence difficile à garantir.

## Q4 — Scénario : commande multi-produits

**Services impliqués :** Orders (coordinateur), Catalog, Inventory, puis Payments et Shipping pour la suite du cycle de vie.

**Coordination : orchestration par le service Orders.** Orders est l'orchestrateur du workflow : c'est lui qui reçoit la commande et appelle les autres services dans l'ordre. Nous avons choisi l'orchestration plutôt que la chorégraphie parce que le scénario est court et séquentiel, et que la logique reste visible et testable à un seul endroit. Les appels sont **synchrones en REST** (HTTP/JSON, `httpx` avec timeouts).

```
Frontend ──POST /api/orders──► Orders
                                 │ 1. GET /products/{id}  (pour chaque produit) ─► Catalog
                                 │      → nom + prix officiels, calcul du total
                                 │ 2. POST /api/inventory/reserve {items[]} ─────► Inventory
                                 │      → réservation atomique de TOUTES les lignes
                                 │ 3. Enregistre la commande (PENDING_PAYMENT)
                                 ◄── 201 { id, items, total, status, createdAt }
Frontend ──POST /api/payments──► Payments ─GET + PATCH status=PAID─► Orders
Frontend ──POST /api/shipments─► Shipping ─GET (commande PAID ?)──► Orders
```

**Déroulement :**
1. Orders regroupe les quantités par produit, puis interroge **Catalog** pour chaque produit afin d'obtenir le prix officiel. Le prix envoyé par le frontend n'est jamais utilisé.
2. Orders demande à **Inventory** de réserver l'ensemble des lignes en **un seul appel**. Inventory vérifie toutes les lignes dans une transaction (`BEGIN IMMEDIATE`) avant de modifier quoi que ce soit : c'est *tout ou rien*.
3. Si la réservation réussit, Orders enregistre la commande avec le statut `PENDING_PAYMENT`.
4. Le paiement (Payments) fait passer la commande à `PAID`, puis Shipping peut créer l'expédition.

**Si le stock demandé n'est pas disponible :**
- Inventory **annule toute la transaction** (`ROLLBACK`) : aucun stock n'est modifié, même pour les produits disponibles, et il répond `409 Conflict` avec le produit en cause.
- Orders **n'enregistre pas la commande** et renvoie `409` au frontend avec le message d'Inventory. Le client peut alors ajuster son panier.
- Si Catalog ou Inventory est injoignable, Orders répond `503` (ou `504` en cas de timeout) au lieu d'accepter une commande incohérente.
- **Compensation (pattern Saga) :** si la réservation a réussi mais que l'enregistrement de la commande échoue, Orders appelle `POST /api/inventory/release` pour rendre le stock. De même, une annulation autorisée (`PENDING_PAYMENT` ou `PAID`) libère le stock. Côté paiement, si le passage à `PAID` échoue, Payments supprime le paiement enregistré.

# Part II

## Q6 — Stratégie de migration

**Stratégie proposée : le pattern *Strangler Fig* (étrangleur).** On construit les nouveaux services **autour** de l'application existante et on leur redirige le trafic **une capacité à la fois**, jusqu'à ce que l'ancien backend ne serve plus rien et puisse être retiré. On ne fait jamais de *big bang*.

**Mise en œuvre dans notre projet.** Le frontend passe déjà par une couche d'aiguillage : `src/config/backend.js` définit pour chaque capacité un mode `"mock"` (ancien backend simulé) ou `"rest"` (nouveau microservice), et chaque fichier `src/services/*Service.js` choisit en conséquence entre les données simulées et un appel REST (via `apiClient.js`). Cette couche joue le rôle de **façade / routeur** du Strangler Fig. En production, ce serait une **API Gateway** ou un reverse proxy (Nginx, Kong) qui route `/api/inventory/*` vers l'ancien ou le nouveau backend.

**Étapes :**

1. **Façade d'abord.** Tout le trafic passe par la façade, qui renvoie au début 100 % des appels vers l'existant. Aucun changement visible pour les clients.
2. **Extraire les capacités les moins risquées en premier.** Par exemple Catalog (lecture seule) et Auth : on bascule leur mode à `"rest"`, on valide, puis on passe à la suivante.
3. **Puis les capacités transactionnelles**, dans l'ordre des dépendances : Inventory, puis Orders (qui dépend de Catalog et Inventory), puis Payments et Shipping.
4. **Pour chaque bascule :** tests de contrat (mêmes chemins, mêmes JSON), déploiement en parallèle de l'ancien, bascule progressive (*canary* : quelques % du trafic, puis 100 %) et surveillance des erreurs.
5. **Migration des données par capacité.** On copie les données dans la base du nouveau service et on les synchronise pendant la transition (double écriture ou capture de changements). La base du nouveau service devient ensuite la source de vérité.
6. **Retrait.** Quand plus aucun appel n'atteint une fonction de l'ancien backend, on supprime ce code. Le monolithe « rétrécit » jusqu'à disparaître.

**Pourquoi cette approche répond aux contraintes :**
- **Interruption minimale.** L'ancien système reste en service pendant toute la migration. Chaque bascule est un simple changement de routage, **réversible instantanément** (retour à `"mock"` / à l'ancien backend) en cas de problème.
- **Validation incrémentale.** Une seule capacité change à la fois, ce qui permet d'isoler et de corriger chaque problème. Le critère de passage est mesurable : contrat respecté, tests passés, taux d'erreur stable.
- **Pas de réécriture complète.** On réutilise le frontend tel quel : les composants React ne sont pas modifiés, seuls les contrats REST sont respectés. Les fonctionnalités sont remplacées une par une, et les parties qui fonctionnent bien peuvent rester dans l'existant aussi longtemps que nécessaire.
