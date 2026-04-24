import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Эти данные мы укажем позже в настройках сервера (Koyeb)
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

queue = [] 
scores = {} 
current_index = 0

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("📺 Присылай видео до 60 сек. Лимит: 10 штук.")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    
    count = sum(1 for v in queue if v['user_id'] == user_id)
    if message.video.duration > 60:
        return await message.answer("❌ Слишком длинное!")
    if count >= 10:
        return await message.answer("❌ Лимит 10 видео исчерпан.")

    queue.append({'video_id': message.video.file_id, 'user': username, 'user_id': user_id})
    await message.answer(f"✅ Видео принято! Место в очереди: {len(queue)}")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await send_next_video(message.from_user.id)

async def send_next_video(chat_id):
    global current_index
    if current_index >= len(queue):
        return await bot.send_message(chat_id, "🏁 Видео закончились! Жми /results")
    
    item = queue[current_index]
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ +50 грн", callback_data=f"add_50_{item['user_id']}"),
        InlineKeyboardButton("➡️ След.", callback_data="next")
    )
    await bot.send_video(chat_id, item['video_id'], caption=f"От: {item['user']}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'next')
async def process(call: types.CallbackQuery):
    global current_index
    if call.data.startswith('add_50_'):
        uid = int(call.data.split('_')[2])
        if uid not in scores: scores[uid] = {'name': queue[current_index]['user'], 'balance': 0}
        scores[uid]['balance'] += 50
    
    current_index += 1
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    await send_next_video(call.message.chat.id)

@dp.message_handler(commands=['results'])
async def results(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = "💰 Таблица выплат:\n" + "\n".join([f"{d['name']}: {d['balance']} грн" for d in scores.values()])
    await message.answer(text if scores else "Пусто.")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
