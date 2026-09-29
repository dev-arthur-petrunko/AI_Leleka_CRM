# -*- coding: utf-8 -*-
"""Точка входу: /start з deep-link, колбеки кнопок, дайджести за розкладом."""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import notify
from bot.config import BOT_TOKEN, DIGEST_EVENING, DIGEST_MORNING

logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


@dp.message(CommandStart())
async def start(msg: Message):
    # Deep link: t.me/<bot>/app?startapp=deal_123
    arg = (msg.text or "").split(maxsplit=1)
    extra = f"\nВідкриваю: {arg[1]}" if len(arg) > 1 else ""
    await msg.answer(f"🪶 Leleka на звʼязку! Сповіщення про лідів, завислі угоди і фіди — сюди.{extra}")


@dp.callback_query(F.data.in_({"take", "call", "later", "open", "write", "move"}))
async def buttons(cb: CallbackQuery):
    # Прод: дернути CRM API (взяти в роботу / перенести) з JWT сервісу
    await cb.answer(f"Прийнято: {cb.data} (прод: виклик CRM API)")
    await cb.message.reply(f"✅ Дія «{cb.data}» записана (демо).")


async def digest(kind: str):
    logging.info("digest %s: прод — забрати з CRM API і розіслати підписаним", kind)


async def main():
    bot = Bot(BOT_TOKEN)
    sched = AsyncIOScheduler()
    h_m, m_m = map(int, DIGEST_MORNING.split(":"))
    h_e, m_e = map(int, DIGEST_EVENING.split(":"))
    sched.add_job(digest, "cron", hour=h_m, minute=m_m, args=["morning"])
    sched.add_job(digest, "cron", hour=h_e, minute=m_e, args=["evening"])
    sched.start()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
