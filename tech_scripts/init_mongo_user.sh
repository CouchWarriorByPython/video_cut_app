#!/bin/bash

USER="anot_user"
PASS="anot_pass"
DB="annotator"

echo "[1/4] Створення користувача MongoDB у базі $DB..."

mongosh <<EOF
use $DB
db.createUser({
  user: "$USER",
  pwd: "$PASS",
  roles: [ { role: "readWrite", db: "$DB" } ]
})
EOF

echo "[2/4] Увімкнення авторизації в mongod.conf..."

CONFIG_FILE="/etc/mongod.conf"

# Перевіряємо чи вже є розділ security, якщо ні — додаємо
if grep -q "^security:" "$CONFIG_FILE"; then
  sudo sed -i '/^security:/,/^[^ ]/s/^ *authorization:.*$/  authorization: enabled/' "$CONFIG_FILE"
else
  echo -e "\nsecurity:\n  authorization: enabled" | sudo tee -a "$CONFIG_FILE"
fi

echo "[3/4] Перезапуск MongoDB..."

sudo systemctl restart mongod

echo "[4/4] Перевірка доступу з авторизацією..."
mongosh -u "$USER" -p "$PASS" --authenticationDatabase "$DB" --eval "db.stats()"

echo "✅ Готово. URI для підключення:"
echo "mongodb://$USER:$PASS@localhost:27017/$DB"
