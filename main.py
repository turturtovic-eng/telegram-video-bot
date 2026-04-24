import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils import executor

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

conn = sqlite3.connect("data.db")
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS videos(
id INTEGER PRIMARY KEY AUTOINCREMENT,
user_id INTEGER,
username TEXT,
file_id TEXT
)""")

cur.execute("""CREATE TABLE IF NOT EXISTS balance(
user_id INTEGER PRIMARY KEY,
amount INTEGER DEFAULT 0
)""")

conn.commit()


# --- ДОБАВЛЕНИЕ БАЛАНСА ---
def add_balance(user_id, amount):
    cur.execute("INSERT OR IGNORE INTO balance(user_id, amount) VALUES(?,0)", (user_id,))
    cur.execute("UPDATE balance SET amount = amount + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()


# --- КОМАНДА СТАРТ ---
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("Отправь видео (до 60 сек). Максимум 10 видео.")


# --- ПОЛУЧЕНИЕ ВИДЕО ---
@dp.message_handler(content_types=types.ContentType.VIDEO)
async def video(msg: types.Message):
    user_id = msg.from_user.id
    username = msg.from_user.username or "no_username"

    cur.execute("SELECT COUNT(*) FROM videos WHERE user_id=?", (user_id,))
    count = cur.fetchone()[0]

    if count >= 10:
        return await msg.answer("Лимит 10 видео достигнут.")

    cur.execute("INSERT INTO videos(user_id, username, file_id) VALUES(?,?,?)",
                (user_id, username, msg.video.file_id))
    conn.commit()

    await msg.answer("Видео отправлено стримеру")


# --- ОЧЕРЕДЬ ДЛЯ СТРИМЕРА ---
@dp.message_handler(commands=['queue'])
async def queue(msg: types.Message):
    if msg.from_user.id != ADMIN_ID:
        return

    cur.execute("SELECT * FROM videos ORDER BY id LIMIT 1")
    data = cur.fetchone()

    if not data:
        return await msg.answer("Очередь пуста")

    video_id, user_id, username, file_id = data

    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("➕ +50 грн", callback_data=f"add_{user_id}_{video_id}"),
        InlineKeyboardButton("❌ пропустить", callback_data=f"skip_{video_id}"),
        InlineKeyboardButton("▶️ следующее", callback_data="next")
    )

    await bot.send_video(msg.chat.id, file_id,
        caption=f"@{username} (ID: {user_id})",
        reply_markup=kb)


# --- КНОПКИ ---
@dp.callback_query_handler()
async def call(cb: types.CallbackQuery):
    data = cb.data

    if data.startswith("add"):
        _, user_id, video_id = data.split("_")
        add_balance(int(user_id), 50)

        cur.execute("DELETE FROM videos WHERE id=?", (video_id,))
        conn.commit()

        await cb.answer("Добавлено +50 грн")

    elif data.startswith("skip"):
        _, video_id = data.split("_")
        cur.execute("DELETE FROM videos WHERE id=?", (video_id,))
        conn.commit()

        await cb.answer("Пропущено")

    elif data == "next":
        await queue(cb.message)


# --- БАЛАНС ---
@dp.message_handler(commands=['balance'])
async def balance(msg: types.Message):
    cur.execute("SELECT amount FROM balance WHERE user_id=?", (msg.from_user.id,))
    res = cur.fetchone()
    await msg.answer(f"Баланс: {res[0] if res else 0} грн")


executor.start_polling(dp)
