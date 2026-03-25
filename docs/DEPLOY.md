# 🚀 Инструкция по деплою на VPS (Ubuntu 22.04+)

## 1. Подготовка сервера

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip postgresql postgresql-contrib git
```

## 2. Создание системного пользователя

```bash
sudo useradd -m -s /bin/bash botuser
sudo mkdir -p /opt/anon_bot
sudo chown botuser:botuser /opt/anon_bot
```

## 3. Клонирование / загрузка кода

```bash
sudo -u botuser git clone https://github.com/your-repo/anon_bot /opt/anon_bot
# или загрузите через scp:
# scp -r ./anon_bot botuser@your_vps:/opt/
```

## 4. Python-окружение и зависимости

```bash
sudo -u botuser bash -c "
  cd /opt/anon_bot
  python3.11 -m venv venv
  venv/bin/pip install --upgrade pip
  venv/bin/pip install -r requirements.txt
"
```

## 5. База данных PostgreSQL

```bash
sudo systemctl enable --now postgresql
sudo bash scripts/init_db.sh   # создаёт пользователя и БД
```

## 6. Конфигурация `.env`

```bash
sudo -u botuser cp /opt/anon_bot/.env.example /opt/anon_bot/.env
sudo -u botuser nano /opt/anon_bot/.env
```

Заполните:
| Переменная | Описание |
|---|---|
| `BOT_TOKEN` | Токен от @BotFather |
| `ADMIN_GROUP_ID` | chat_id группы модераторов (отрицательное число) |
| `CHANNEL_ID` | chat_id вашего канала |
| `DATABASE_URL` | строка подключения asyncpg |

### Получение chat_id группы / канала

1. Добавьте бота в группу/канал как администратора.
2. Отправьте любое сообщение и откройте:  
   `https://api.telegram.org/bot<TOKEN>/getUpdates`
3. Найдите поле `"chat": {"id": -100...}`.

## 7. Папка для логов

```bash
sudo -u botuser mkdir -p /opt/anon_bot/logs
```

## 8. Systemd-сервис

```bash
sudo cp /opt/anon_bot/scripts/anon_bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable anon_bot
sudo systemctl start anon_bot
```

### Управление сервисом

```bash
sudo systemctl status anon_bot      # статус
sudo journalctl -u anon_bot -f      # live-логи
sudo systemctl restart anon_bot     # перезапуск
sudo systemctl stop anon_bot        # остановка
```

## 9. Обновление бота

```bash
sudo -u botuser bash -c "
  cd /opt/anon_bot
  git pull
  venv/bin/pip install -r requirements.txt
"
sudo systemctl restart anon_bot
```

## 10. Первичный запуск и проверка

1. Отправьте `/start` своему боту — получите приветствие.
2. Отправьте тестовое сообщение — оно должно появиться в админ-группе с кнопками.
3. Нажмите ✅ Одобрить — сообщение публикуется в канале анонимно.

---

## Масштабирование до 50k пользователей

### Текущая архитектура (single instance)
- Одна машина + PostgreSQL — выдерживает **тысячи** одновременных пользователей.
- `MemoryStorage` для FSM — хранится в RAM процесса.

### При горизонтальном масштабировании

| Компонент | Решение |
|---|---|
| FSM Storage | Заменить `MemoryStorage` на `RedisStorage` из `aiogram-redis` |
| Anti-spam | Перенести счётчики в Redis (атомарные операции) |
| Несколько воркеров | Запустить несколько процессов за балансировщиком (webhook-режим) |
| Webhook | Использовать `aiogram` webhook + nginx/caddy |
| Мониторинг | Prometheus + Grafana |

### Webhook-режим (рекомендуется для нагрузки)

```python
# В main.py замените start_polling на:
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

WEBHOOK_URL = "https://your-domain.com/webhook"

async def on_startup(bot: Bot) -> None:
    await bot.set_webhook(WEBHOOK_URL)

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
setup_application(app, dp, bot=bot)
web.run_app(app, host="0.0.0.0", port=8080)
```

---

## Безопасность

- Никогда не коммитьте `.env` в git — добавьте его в `.gitignore`.
- Ограничьте доступ к PostgreSQL файрволом: `ufw allow from 127.0.0.1 to any port 5432`.
- Включите SSL для PostgreSQL при необходимости удалённого подключения.
- Telegram ID авторов постов хранится в БД, но **никогда не публикуется** в канале.
