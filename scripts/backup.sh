#!/bin/sh
# Щоденний бекап Postgres (фаза 1.6). Cron на хості або окремий контейнер:
#   0 3 * * * /opt/leleka/scripts/backup.sh >> /var/log/leleka-backup.log 2>&1
# Змінні беруться з .env. Перевірка відновлення — розгорнути дамп у leleka_restore.
set -eu
: "${DB_USER:?}" "${DB_PASSWORD:?}" "${DB_NAME:?}"
: "${BACKUP_DIR:=/var/backups/leleka}"
mkdir -p "$BACKUP_DIR"
TS=$(date +%F_%H%M)
FILE="$BACKUP_DIR/leleka_$TS.sql.gz"
export PGPASSWORD="$DB_PASSWORD"
pg_dump -h "${DB_HOST:-localhost}" -U "$DB_USER" -d "$DB_NAME" | gzip > "$FILE"
# тримати останні 14
ls -t "$BACKUP_DIR"/leleka_*.sql.gz | tail -n +15 | xargs -r rm -f
echo "backup ok: $FILE"
