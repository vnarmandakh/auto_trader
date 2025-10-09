#!/usr/bin/env bash
set -e
until nc -z ${POSTGRES_HOST:-db} ${POSTGRES_PORT:-5432}; do echo waiting db; sleep 1; done
python manage.py migrate --noinput
daphne -b 0.0.0.0 -p 8000 arbmon.asgi:application
