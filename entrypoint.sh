#!/bin/bash
set -e

echo "🔄 Running AGEB data migration..."
python migrate_to_postgis.py || echo "⚠️  Migration skipped (data may already exist)"

echo "🚀 Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
