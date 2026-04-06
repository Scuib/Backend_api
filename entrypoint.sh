#!/bin/bash
set -e

echo "Running api migrations first (custom user model)..."
python manage.py migrate api --noinput

echo "Running remaining migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn scuibai.wsgi:application --bind 0.0.0.0:8000
