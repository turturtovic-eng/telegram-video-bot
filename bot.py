import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web # Добавили эту библиотеку

# Настройки
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

queue = [] 
scores = {} 
current_index = 0

# --- КОСТЫЛЬ ДЛЯ БЕСПЛАТНОГО RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get("/", handle)

async def on_startup(dp):
    # Запускаем веб-сервер в фоне на порту 10000 (стандарт Render)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())
# ---------------------------------------

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("<b>📺 ПАНЕЛЬ ПРИЕМА ВИДЕО</b>\n\nПрисылай видео до 60 сек.")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    user_name = f"@{message.from_user.username}" if message.from_user.username else f"<a href='tg://user?id={user_id}'>{message.from_user.full_name}</a>"
    
    if message.video.duration > 60:
        return await message.answer("❌ Слишком длинное!")
    
    if sum(1 for v in queue if v['user_id'] == user_id) >= 10:
        return await message.answer("❌ Лимит исчерпан.")

    queue.append({'video_id': message.video.file_id, 'user_name': user_name, 'user_id': user_id})
    await message.answer(f"✅ Видео получено! Номер в очереди: <b>{len(queue)}</b>")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await send_next_video(message.from_user.id)

async def send_next_video(chat_id):
    global current_index
    if current_index >= len(queue):
        await bot.send_message(chat_id, "🏁 Видео закончились!")
        return
    
    item = queue[current_index]
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("💰 ПРИБАВИТЬ +50 ГРН", callback_data=f"add_50_{item['user_id']}"),
        InlineKeyboardButton("➡️ СЛЕДУЮЩЕЕ ВИДЕО", callback_data="skip")
    )
    await bot.send_video(chat_id, item['video_id'], caption=f"От: {item['user_name']}", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'skip')
async def process(call: types.CallbackQuery):
    global current_index
    if call.data.startswith('add_50_'):
        uid = int(call.data.split('_')[2])
        if uid not in scores: scores[uid] = {'name': queue[current_index]['user_name'], 'balance': 0}
        scores[uid]['balance'] += 50
    
    current_index += 1
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    await send_next_video(call.message.chat.id)

@dp.message_handler(commands=['results'])
async def show_results(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    res = "🏆 <b>ИТОГИ:</b>\n\n" + "\n".join([f"▪️ {d['name']}: <b>{d['balance']} грн</b>" for d in scores.values()])
    await message.answer(res if scores else "Пусто.")

if __name__ == '__main__':
    # Добавили on_startup для запуска веб-сервера
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
