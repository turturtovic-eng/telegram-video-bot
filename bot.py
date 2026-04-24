import os
import asyncio
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiohttp import web

# --- ИСПРАВЛЕННЫЙ БЛОК НАСТРОЕК ---
API_TOKEN = os.getenv('BOT_TOKEN')
# Читаем строку с ID, режем её по запятой и превращаем в список чисел
raw_admins = os.getenv('ADMIN_ID', '0')
ADMIN_IDS = [int(i.strip()) for i in raw_admins.split(',') if i.strip().isdigit()]

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Данные в памяти
queue = [] 
scores = {} 
current_index = 0

# --- СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

app = web.Application()
app.router.add_get("/", handle)

async def on_startup(dp):
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 10000)
    asyncio.create_task(site.start())

# Проверка на админа
def is_admin(user_id):
    return user_id in ADMIN_IDS

# Кнопки внизу экрана
def get_admin_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📺 Смотреть очередь"), KeyboardButton("🏆 Результаты"))
    kb.add(KeyboardButton("🗑 Очистить всё"))
    return kb

# --- ОБРАБОТКА КОМАНД ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    if is_admin(message.from_user.id):
        await message.answer("<b>👋 Админ-панель активирована!</b>\nИспользуй кнопки ниже:", reply_markup=get_admin_kb())
    else:
        await message.answer("<b>📺 ПАНЕЛЬ ПРИЕМА ВИДЕО</b>\n\nПрисылай видео до 60 секунд. Я передам его стримеру!")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    # Получаем ник или имя (без странных цифр)
    user_name = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    
    if message.video.duration > 60:
        return await message.answer("❌ Видео слишком длинное (макс. 60 сек).")
    
    # Лимит 10 видео от одного человека
    if sum(1 for v in queue if v['user_id'] == user_id) >= 10:
        return await message.answer("❌ Лимит 10 видео исчерпан.")

    queue.append({'video_id': message.video.file_id, 'user_name': user_name, 'user_id': user_id})
    await message.answer(f"✅ Видео принято! В очереди: <b>{len(queue)}</b>")

# Обработка кнопок панели управления
@dp.message_handler(lambda message: is_admin(message.from_user.id))
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
        await bot.send_message(chat_id, "🏁 <b>Видео в очереди закончились!</b>")
        return
    
    item = queue[current_index]
    kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton(text="✅ ПРИБАВИТЬ +50 ГРН", callback_data=f"add_50_{item['user_id']}"),
        InlineKeyboardButton(text="➡️ СЛЕДУЮЩЕЕ", callback_data="skip")
    )
    
    caption = f"👤 От: <b>{item['user_name']}</b>\n🎥 Видео №{current_index + 1} из {len(queue)}"
    await bot.send_video(chat_id, item['video_id'], caption=caption, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'skip')
async def process_decision(call: types.CallbackQuery):
    global current_index
    if not is_admin(call.from_user.id): return
    
    if call.data.startswith('add_50_'):
        u_id = int(call.data.split('_')[2])
        if u_id not in scores:
            scores[u_id] = {'name': queue[current_index]['user_name'], 'balance': 0}
        scores[u_id]['balance'] += 50
        await call.answer("Начислено +50 грн!")
    
    # Убираем кнопки у старого видео, чтобы не нажать дважды
    await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
    
    current_index += 1
    # Сообщение НЕ удаляем, просто шлем следующее
    await send_next_video(call.message.chat.id)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
