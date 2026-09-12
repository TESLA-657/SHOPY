#!/usr/bin/env bash
# Build script pour Render - exécuté automatiquement au déploiement
set -o errexit

echo "=== Installation des dépendances ==="
pip install -r requirements.txt

echo "=== Collecte des fichiers statiques ==="
python manage.py collectstatic --no-input

echo "=== Application des migrations ==="
python manage.py migrate

echo "=== Création / vérification du superutilisateur admin ==="
# Utilise les variables DJANGO_SUPERUSER_USERNAME / EMAIL / PASSWORD
# à configurer dans le dashboard Render (Environment).
# La commande est idempotente : elle n'échoue pas si le user existe déjà.
python manage.py ensure_superuser || echo "Avertissement: ensure_superuser a échoué (variables DJANGO_SUPERUSER_* non définies ?)"

echo "=== Import des données de référence (catégories, plans) ==="
# Idempotent : n'insère que ce qui manque (catégories + plans d'abonnement).
python manage.py seed_data

echo "=== Build terminé avec succès ==="
