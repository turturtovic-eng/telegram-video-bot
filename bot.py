import os
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage

# Настройки берем из Render
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

bot = Bot(token=API_TOKEN, parse_mode="HTML")
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

queue = [] 
scores = {} 
current_index = 0

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer("<b>📺 ПАНЕЛЬ ПРИЕМА ВИДЕО</b>\n\nПрисылай видео до 60 сек.\nЛимит: 10 видео от одного человека.")

@dp.message_handler(content_types=['video'])
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    
    # Красиво определяем имя пользователя
    if message.from_user.username:
        user_name = f"@{message.from_user.username}"
    else:
        user_name = f"<a href='tg://user?id={user_id}'>{message.from_user.full_name}</a>"
    
    user_video_count = sum(1 for v in queue if v['user_id'] == user_id)
    
    if message.video.duration > 60:
        return await message.answer("❌ Видео длиннее 60 секунд не принимаются.")
    
    if user_video_count >= 10:
        return await message.answer("❌ Ты уже прислал свой лимит (10 видео).")

    queue.append({
        'video_id': message.video.file_id,
        'user_name': user_name,
        'user_id': user_id
    })
    await message.answer(f"✅ Видео получено! Ты в очереди под номером <b>{len(queue)}</b>")

@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    await send_next_video(message.from_user.id)

async def send_next_video(chat_id):
    global current_index
    if current_index >= len(queue):
        await bot.send_message(chat_id, "🏁 <b>Все видео в очереди просмотрены!</b>\nИспользуй /results для итогов.")
        return
    
    item = queue[current_index]
    
    # Создаем удобные кнопки
    kb = InlineKeyboardMarkup(row_width=1) # Кнопки одна под другой, чтобы было легче попадать
    btn_add = InlineKeyboardButton(text="💰 ПРИБАВИТЬ +50 ГРН", callback_data=f"add_50_{item['user_id']}")
    btn_next = InlineKeyboardButton(text="➡️ СЛЕДУЮЩЕЕ ВИДЕО", callback_data="skip")
    kb.add(btn_add, btn_next)
    
    caption = f"👤 Отправитель: <b>{item['user_name']}</b>\n🎥 Видео в очереди: {current_index + 1} из {len(queue)}"
    
    await bot.send_video(
        chat_id, 
        item['video_id'], 
        caption=caption, 
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith('add_50_') or c.data == 'skip')
async def process_callback(call: types.CallbackQuery):
    global current_index
    
    if call.data.startswith('add_50_'):
        u_id = int(call.data.split('_')[2])
        name = queue[current_index]['user_name']
        
        if u_id not in scores:
            scores[u_id] = {'name': name, 'balance': 0}
        
        scores[u_id]['balance'] += 50
        await call.answer("Начислено 50 грн!", show_alert=False)
    else:
        await call.answer("Пропущено")

    current_index += 1
    # Удаляем текущее сообщение, чтобы не захламлять чат
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    # Вызываем следующее
    await send_next_video(call.message.chat.id)

@dp.message_handler(commands=['results'])
async def show_results(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    if not scores:
        return await message.answer("Список пуст. Никто еще не получил бонусы.")
    
    res = "🏆 <b>ИТОГИ ВЫПЛАТ:</b>\n\n"
    for data in scores.values():
        res += f"▪️ {data['name']}: <b>{data['balance']} грн</b>\n"
    
    await message.answer(res)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
