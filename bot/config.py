# -*- coding: utf-8 -*-
"""Telegram-бот Leleka (aiogram 3). Сповіщення з inline-кнопками + дайджести.

Запуск ТІЛЬКИ з токеном BotFather:
  BOT_TOKEN=... python -m bot.main
Без токена — чесно падає зі зрозумілою помилкою (секрети не зберігаємо в репо).
Прод: окремий сервіс у docker-compose (див. README), токен — з env сервера.
"""
import os

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CRM_API = os.environ.get("CRM_API", "http://api:8000")
DIGEST_MORNING = os.environ.get("DIGEST_MORNING", "09:00")
DIGEST_EVENING = os.environ.get("DIGEST_EVENING", "19:00")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задано. Створіть бота через @BotFather і покладіть токен у env.")
