# Rapport de Fin d'Exécution — Phases 1 & 2

## 1. Synthèse

| Domaine | Statut | Détails |
|---|---|---|
| DVC et données | Partiel | Remote local configuré et `data/` suivi par DVC (`data.dvc`). Le répertoire source ne contenait aucune donnée au démarrage de la mission. |
| Validation Pandera | Réalisé | Schéma des colonnes `V1`–`V28`, `Time` et `Amount`, avec valeurs nulles interdites et montants négatifs refusés. |
| MLflow persistant | Réalisé | Volume nommé `mlflow_data` monté sur `/mlflow`, base SQLite et artefacts persistants configurés. |
| API FastAPI | Réalisé | Santé, métriques, prédiction unitaire et prédiction batch disponibles. |
| Registry MLflow | Réalisé | Chargement de `models:/fraud-detector/Production`; bascule automatique en fallback. |
| SHAP | Réalisé | `TreeExplainer` utilisé lorsqu'un modèle compatible est disponible, avec explication de secours sécurisée. |
| Locust | Configuré | Profil de charge fixe à 50 utilisateurs et rapport p50/p95/p99 configuré. |
| Docker API | Réalisé | Build multi-stage et exécution sous l'utilisateur non-root `frauduser`. |

## 2. Validation effectuée

- `make lint`: réussi (`ruff`, `black`).
- `make test`: réussi, 6 tests API unitaires.
- Build Docker API: réussi.
- `docker compose config`: réussi.
- `make up`: services démarrés; API vérifiée sur `/health` et `/metrics`.
- DVC: remote local opérationnel et `dvc push` réussi.
- Validation Pandera: montant négatif rejeté par `SchemaErrors`.

## 3. Endpoints

- `GET /health`: état, version du modèle, URI et URI du modèle MLflow.
- `GET /metrics`: métriques Prometheus des requêtes, de la latence et des fraudes.
- `POST /predict`: transaction unique, seuil, décision et trois explications principales.
- `POST /predict_batch`: inférence vectorisée sur une liste de transactions.

## 4. État du fallback

En absence du Registry ou du serveur MLflow, le service reste disponible en mode `fallback`, expose un modèle marqué `fallback` et produit une décision probabiliste déterministe. Le modèle entraîné est chargé automatiquement dès que MLflow redevient disponible et que l'alias/stage Production est publié.

## 5. Points à compléter par l'opérateur

- Ajouter les fichiers `train.csv` / `test.csv` réels dans `data/`, puis relancer `dvc add data && dvc push`.
- Enregistrer le modèle sous le nom `fraud-detector` avec l'alias `Production` dans MLflow.
- Lancer le scénario Locust contre un serveur démarré :
  `locust -f tests/load/locustfile.py --headless -u 50 -r 10 -t 60s`
