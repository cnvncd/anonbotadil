#!/usr/bin/env bash
# scripts/init_db.sh  –  one-time PostgreSQL setup

set -euo pipefail

DB_NAME="anon_bot"
DB_USER="bot_user"
DB_PASS="secret"   # change in production!

echo "Creating database and user…"
sudo -u postgres psql <<SQL
CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};
GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo "Done. Update .env with:"
echo "  DATABASE_URL=postgresql+asyncpg://${DB_USER}:${DB_PASS}@localhost:5432/${DB_NAME}"
