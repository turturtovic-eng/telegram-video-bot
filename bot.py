import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web

# Настройки из Render
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

queue = [] 
scores = {} 
current_index = 0

# --- КОСТЫЛЬ ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get("/", handle)

async def on_startup(dp):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())

# --- КЛАВИАТУРА АДМИНА ---
def get_admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📺 Смотреть очередь"), KeyboardButton("🏆 Результаты"))
    kb.add(KeyboardButton("🗑 Очистить всё"))
    return kb

# --- ЛОГИКА ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("<b>👋 Привет, Стример!</b>\nТвоя админ-панель готова.", reply_markup=get_admin_kb())
    else:
        await message.answer("<b>📺 ПАНЕЛЬ ПРИЕМА ВИДЕО</b>\n\nПрисылай видео до 60 сек. Я передам его стримеру!")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    
    if message.video.duration > 60:
        return await message.answer("❌ Видео слишком длинное!")
    
    if sum(1 for v in queue if v['user_id'] == user_id) >= 10:
        return await message.answer("❌ Лимит исчерпан.")

    queue.append({'video_id': message.video.file_id, 'user_name': user_name, 'user_id': user_id})
    await message.answer(f"✅ Видео принято! Очередь: <b>{len(queue)}</b>")

# Обработка кнопок админа
@dp.message_handler(lambda message: message.from_user.id == ADMIN_ID)
async def admin_buttons(message: types.Message):
    global current_index, queue, scores
    
    if message.text == "📺 Смотреть очередь":
        await send_next_video(message.chat.id)
        
    elif message.text == "🏆 Результаты":
        if not scores:
            await message.answer("Пока никто ничего не заработал.")
        else:
            res = "🏆 <b>ТЕКУЩИЕ ВЫПЛАТЫ:</b>\n\n"
            for data in scores.values():
                res += f"▪️ {data['name']}: <b>{data['balance']} грн</b>\n"
            await message.answer(res)
            
    elif message.text == "🗑 Очистить всё":
        queue = []
        scores = {}
        current_index = 0
        await message.answer("⚠️ Все данные удалены. Очередь и результаты обнулены.")

async def send_next_video(chat_id):
    global current_index
    if current_index >= len(queue):
        await bot.send_message(chat_id, "🏁 <b>Видео закончились!</b>")
        return
    
    item = queue[current_index]
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton(text="✅ ПРИБАВИТЬ +50 ГРН", callback_data=f"add_50_{item['user_id']}"),
        InlineKeyboardButton(text="➡️ СЛЕДУЮЩЕЕ", callback_data="skip")
    )
    
    caption = f"👤 От: <b>{item['user_name']}</b>\n🎥 Видео №{current_index + 1} из {len(queue)}"
    await bot.send_video(chat_id, item['video_id'], caption=caption, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'skip')
async def process_decision(call: types.CallbackQuery):
    global current_index
    if call.data.startswith('add_50_'):
        u_id = int(call.data.split('_')[2])
        if u_id not in scores:
            scores[u_id] = {'name': queue[current_index]['user_name'], 'balance': 0}
        scores[u_id]['balance'] += 50
        await call.answer("Начислено +50 грн!")
    
    current_index += 1
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    await send_next_video(call.message.chat.id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
