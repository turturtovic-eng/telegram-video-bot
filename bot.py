import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web

# --- НАСТРОЙКИ (берутся из Environment Variables на Render) ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Хранилище данных (в памяти)
queue = [] 
scores = {} 
current_index = 0

# --- ВЕБ-СЕРВЕР ДЛЯ БЕСПЛАТНОГО ТАРИФА RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get("/", handle)

async def on_startup(dp):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())

# --- ЛОГИКА БОТА ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("<b>📺 ПАНЕЛЬ ПРИЕМА ВИДЕО</b>\n\nПрисылай видео до 60 сек. Я передам его стримеру!")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    
    # Исправленное определение имени (чтобы не было "292")
    if message.from_user.username:
        user_name = f"@{message.from_user.username}"
    else:
        full_name = message.from_user.full_name.strip()
        user_name = full_name if full_name else f"User {user_id}"
    
    # Проверка длительности
    if message.video.duration > 60:
        return await message.answer("❌ Видео слишком длинное (макс. 60 сек).")
    
    # Проверка лимита (10 видео)
    user_video_count = sum(1 for v in queue if v['user_id'] == user_id)
    if user_video_count >= 10:
        return await message.answer("❌ Ты уже прислал максимум (10 видео).")

    # Добавление в очередь
    queue.append({
        'video_id': message.video.file_id,
        'user_name': user_name,
        'user_id': user_id
    })
    
    await message.answer(f"✅ Видео от <b>{user_name}</b> принято!\nМесто в очереди: <b>{len(queue)}</b>")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await send_next_video(message.from_user.id)

async def send_next_video(chat_id):
    global current_index
    
    if current_index >= len(queue):
        await bot.send_message(chat_id, "🏁 <b>Видео в очереди закончились!</b>\nНапиши /results для итогов.")
        return
    
    item = queue[current_index]
    
    # Кнопки в столбик для удобства на стриме
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="💰 ПРИБАВИТЬ +50 ГРН", callback_data=f"add_50_{item['user_id']}"),
        InlineKeyboardButton(text="➡️ СЛЕДУЮЩЕЕ ВИДЕО", callback_data="skip")
    )
    
    caption = f"👤 От: <b>{item['user_name']}</b>\n🎥 Видео №{current_index + 1} из {len(queue)}"
    
    try:
        await bot.send_video(chat_id, item['video_id'], caption=caption, reply_markup=kb)
    except Exception as e:
        await bot.send_message(chat_id, f"Ошибка при загрузке видео: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'skip')
async def process_decision(call: types.CallbackQuery):
    global current_index
    
    if call.data.startswith('add_50_'):
        u_id = int(call.data.split('_')[2])
        # Сохраняем имя для итоговой таблицы
        u_name = queue[current_index]['user_name']
        
        if u_id not in scores:
            scores[u_id] = {'name': u_name, 'balance': 0}
        
        scores[u_id]['balance'] += 50
        await call.answer("Начислено +50 грн!")
    else:
        await call.answer("Пропущено")

    current_index += 1
    # Удаляем сообщение с видео, чтобы не путаться
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    # Показываем следующее
    await send_next_video(call.message.chat.id)

@dp.message_handler(commands=['results'])
async def show_results(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    
    if not scores:
        return await message.answer("Пока никто ничего не заработал.")
    
    res = "🏆 <b>ИТОГИ СТРИМА:</b>\n\n"
    for data in scores.values():
        res += f"▪️ {data['name']}: <b>{data['balance']} грн</b>\n"
    
    await message.answer(res)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
