#!/bin/bash
# docker-entrypoint.sh
# Acdante DB Inspector Docker 容器启动脚本

set -e

echo "==> Acdante DB Inspector v$(cat /app/VERSION.txt 2>/dev/null || echo 'unknown')"

# Ensure data/ and drivers/ directories exist and are writable
mkdir -p /app/data
chmod 755 /app/data
mkdir -p /app/drivers
chmod 755 /app/drivers
mkdir -p /app/pro_data
chmod 755 /app/pro_data

# Initialize database tables (create if not exist)
# This ensures inspection_template and other tables exist even on first run
echo "==> Initializing database tables..."
python -c "
from inspection_dal import init_database
init_database()
print('inspection.db tables ready.')
" 2>&1 || echo "WARNING: inspection.db init failed"

# Initialize default inspection templates (skip if already exist)
echo "==> Initializing default inspection templates..."
python /app/inspection_init_db.py 2>&1 || echo "WARNING: inspection_init_db.py failed"

# Check drivers status
DRIVER_COUNT=$(find /app/drivers -type f 2>/dev/null | wc -l)
if [ "$DRIVER_COUNT" -eq 0 ]; then
    echo "==> WARNING: /app/drivers/ is empty."
    echo "    Oracle client libs and YashanDB wheel are not included."
    echo "    To enable these databases, place driver files in /app/drivers/"
    echo "    or use '-v /path/to/drivers:/app/drivers' when running the container."
else
    echo "==> Drivers found: $DRIVER_COUNT file(s) in /app/drivers/"
fi

# Initialize RBAC user management seed data
echo "==> Initializing RBAC user management..."
python -m user_management.seed 2>&1 || echo "WARNING: RBAC seed init failed"

echo "==> Starting Acdante DB Inspector Web UI on port 5003..."
exec python /app/web_ui.py
