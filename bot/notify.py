# -*- coding: utf-8 -*-
"""Тексти сповіщень з inline-кнопками (формат за ТЗ, фаза 3.1)."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

BTN_TAKE = InlineKeyboardButton(text="Взяти в роботу", callback_data="take")
BTN_CALL = InlineKeyboardButton(text="Подзвонити", callback_data="call")
BTN_LATER = InlineKeyboardButton(text="Пізніше", callback_data="later")
BTN_OPEN = InlineKeyboardButton(text="Відкрити", callback_data="open")
BTN_WRITE = InlineKeyboardButton(text="Написати", callback_data="write")
BTN_MOVE = InlineKeyboardButton(text="Перенести", callback_data="move")

KB_LEAD = InlineKeyboardMarkup(inline_keyboard=[[BTN_TAKE, BTN_CALL], [BTN_LATER, BTN_OPEN]])
KB_STUCK = InlineKeyboardMarkup(inline_keyboard=[[BTN_WRITE, BTN_MOVE]])
KB_FEED = InlineKeyboardMarkup(inline_keyboard=[[BTN_OPEN]])


def new_lead(name: str, source: str) -> tuple[str, InlineKeyboardMarkup]:
    return (f"🔥 Новий лід\n{name} · {source}", KB_LEAD)


def stuck_deal(title: str, days: int) -> tuple[str, InlineKeyboardMarkup]:
    return (f"⚠️ Угода зависла: {title}, {days} дн.", KB_STUCK)


def feed_ok(name: str, changes: int) -> tuple[str, InlineKeyboardMarkup]:
    return (f"📦 Фід {name} оновлено: {changes} змін", KB_FEED)


def feed_error(name: str, error: str) -> tuple[str, InlineKeyboardMarkup]:
    return (f"❌ Фід {name}: помилка {error[:100]}", KB_FEED)
