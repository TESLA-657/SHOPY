#!/usr/bin/env bash
# Build script pour Render - exécuté automatiquement au déploiement
set -o errexit

echo "=== Installation des dépendances ==="
pip install -r requirements.txt

echo "=== Collecte des fichiers statiques ==="
python manage.py collectstatic --no-input

echo "=== Application des migrations ==="
python manage.py migrate

echo "=== Build terminé avec succès ==="
