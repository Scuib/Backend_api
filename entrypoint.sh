#!/bin/bash
set -e

echo "Running migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
exec gunicorn scuibai.wsgi:application --bind 0.0.0.0:8000
