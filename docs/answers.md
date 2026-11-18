# Part I — Analyse

## Q1 — 3 arguments pour MSOA

## Q2 — Décomposition en microservices

## Q3 — Évaluation (cohésion, couplage, autonomie, data ownership)

## Q4 — Scénario : commande multi-produits

# Part II

## Q6 — Stratégie de migration

# LAB 3 — Contrats API et évolution

## Questions 1 et 2 — Interactions et endpoints

| Fournisseur | Consommateur | Informations échangées |
|---|---|---|
| Auth | Frontend | Identifiants, utilisateur, jeton de session |
| Catalog | Frontend, Orders | Produit, nom, catégorie, prix, devise, image |
| Inventory | Frontend, Orders | Stock disponible, demandes de vérification/réservation/libération |
| Orders | Frontend, Payments, Shipping | Commande, client, articles, total, statut |
| Payments | Orders | Résultat du paiement et mise à jour du statut |
| Shipping | Orders, Frontend | Adresse, expédition, état de livraison |

Le détail complet des méthodes, paramètres, schémas, codes et erreurs est défini dans les fichiers `API_CONTRACT.md` des services. Les contrats déployés sont listés dans `README.md`.

## Question 4 — Cause de l'incompatibilité

Une réponse JSON reste valide syntaxiquement, mais le **type de données** de `price` change :
numeric (`8499`) vers objet (`{"amount":8499,"currency":"MAD"}`). Les anciens clients exécutent
`price * quantity`, font `toLocaleString()` ou supposent une addition numérique. Avec un objet,
cela donne `NaN`, `[object Object]`, une exception ou un total incorrect.

Composants affectés :

- **Frontend :** cartes produits, panier, checkout et affichage des totaux.
- **Orders :** lecture du prix de Catalog, calcul du total et persistance des lignes.
- **Services tiers :** toute intégration dépendant de `price` comme nombre.

## Question 5 — Approches possibles

| Approche | Avantages | Inconvénients | Décision |
|---|---|---|---|
| Remplacer directement `price` | Simple, court terme | Casse tous les anciens clients | À rejeter |
| Conserver `price` et ajouter `currency` | Compatible avec le calcul actuel | Ambiguïté sur les prix de plusieurs devises | Temporaire |
| Ajout de champs optionnels | Limite les changements | Permet encore des interprétations incohérentes | À éviter pour la devise |
| Endpoints/versionnement | Contrats explicites, coexistence et migration contrôlée | Nécessite de maintenir deux versions | Approche retenue |

La plateforme utilise une migration explicite : `/api/v1/*` ou `/products` conservent le prix
numérique, tandis que `/api/v2/*` expose `{amount,currency}`. La maintenance des versions permet
la migration indépendante des services sans déploiement simultané.

## Question 6 — Stratégie adoptée

1. Ne pas modifier `/products` ni son contrat v1 pendant la migration.
2. Publier `/api/v1/products` comme alias explicite du contrat numérique.
3. Publier `/api/v2/products` avec `price.amount` et `price.currency`.
4. Faire évoluer les nouveaux consommateurs vers v2 uniquement après mise à jour de leurs tests.
5. Faire conserver aux anciens consommateurs v1 jusqu'à leur décommissionnement.
6. Déprécier v1 seulement après inventaire des appels et période de transition.

Le service Catalog reste compatible : les anciens appels retournent toujours un nombre. Le nouveau
contrat peut être vérifié via Swagger ou Postman. `Orders` accepte également les deux formes afin
que sa lecture reste compatible pendant la transition.
