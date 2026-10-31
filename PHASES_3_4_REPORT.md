# Rapport de Fin d'Exécution Final — Phases 3 & 4

## Résumé de validation

| Composant | Résultat |
|---|---|
| Streaming Redpanda | Validé, topic `transactions` opérationnel et cluster healthy |
| Producer | Validé, 5 transactions/s avec injection de fraudes configurable |
| Consumer | Validé, appels API, persistance SQLite et commits Kafka |
| Résilience | Retries exponentiels, DLQ `transactions.dlq`, idempotence par transaction ID |
| API | Validée, santé et métriques Prometheus accessibles |
| Dashboard Streamlit | Validé sur le port 8501 et stockage live accessible |
| Docker Compose | Validé avec MLflow, API, Redpanda, Producer, Consumer et Dashboard |
| Lancement global | `docker compose up -d` validé |
| Qualité | `make lint` validé et 6 tests API unitaires validés |

## Pipeline bout en bout

1. Le Producer génère ou rejoue des transactions et les publie sur `transactions`.
2. Redpanda achemine chaque message vers le groupe `fraud-detector-consumer`.
3. Le Consumer appelle `POST /predict` avec retries exponentiels.
4. Les prédictions sont persistées une seule fois dans SQLite grâce à la clé primaire `transaction_id`.
5. Les offsets Kafka sont validés après traitement ou après routage vers la DLQ.
6. Streamlit lit les résultats depuis le volume persistant partagé.

## Métriques observées

- Cluster Redpanda : healthy.
- API `/health` : accessible et expose l'état MLflow/fallback.
- API `/metrics` : Prometheus accessible avec compteur requêtes, latence et fraudes.
- Streamlit healthcheck : HTTP `ok`, service accessible sur le port 8501.
- Volume persistant partagé : les prédictions du pipeline ont été observées en base à haute cadence pendant la validation, avec plus de 60 lignes persistées.

La version validée démarrait volontairement en mode fallback, le serveur MLflow n'étant pas accompagné d'un modèle enregistré localement. Ce comportement est attendu et sécurisé: dès qu'une version `fraud-detector` est publiée sur l'alias Production, le service bascule automatiquement vers le modèle Registry.

## Résilience

Les paramètres de retry sont configurables avec `API_RETRY_ATTEMPTS` et `API_RETRY_INITIAL_SECONDS`. Les codes HTTP 5xx et les erreurs réseau déclenchent un retry; les erreurs permanentes sont redirigées vers `transactions.dlq`. Les transactions mal formées sont également routées vers la DLQ sans bloquer le groupe.

## Monitoring et dashboard

Le module [drift.py](/home/medo/fraud-detection/src/fraud/monitoring/drift.py) calcule les écarts de distribution par feature, ainsi que le déplacement du taux de fraude pour le concept drift. Le Producer peut modifier ses distributions et simuler des pics. Evidently est ajouté aux dépendances du projet et le dashboard fournit les sections Live stream, System metrics, Explainability et Monitoring.

## Actions opérationnelles

```bash
make up
curl http://localhost:8000/health
curl http://localhost:8000/metrics
curl http://localhost:8501/_stcore/health
```

Pour déclencher la démonstration de drift:

```bash
DEMO_DRIFT=true DRIFT_STRENGTH=2.0 python -m src.fraud.monitoring.drift \
  --reference data/train.csv --current data/test.csv --output data/drift_report.json
```
