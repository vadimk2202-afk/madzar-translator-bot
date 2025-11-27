import logging
import os
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
import csv
import difflib  # Для fuzzy search

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Токен и ссылка (твои данные)
BOT_TOKEN = "8417685005:AAEQ_J3-p0EdpEveDVrdlK_t-In5iVaoJJo"
CHANNEL_LINK = "https://t.me/+VE9U7WU8eXo4NGYy"
PROVIDER_TOKEN = "your_premium_bot_token"  # Замени на токен от @PremiumBot (получи бесплатно)

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Состояния FSM
class Form(StatesGroup):
    waiting_phrase = State()

# Инициализация БД
def init_db():
    conn = sqlite3.connect('phrases.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS phrases (
            id INTEGER PRIMARY KEY,
            phrase TEXT UNIQUE,
            ru TEXT,
            en TEXT,
            pl TEXT,
            explanation TEXT,
            audio TEXT
        )
    ''')
    
    # Загрузка CSV в БД (при первом запуске)
    if cursor.execute('SELECT COUNT(*) FROM phrases').fetchone()[0] == 0:
        with open('phrases.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                cursor.execute('''
                    INSERT OR IGNORE INTO phrases (phrase, ru, en, pl, explanation, audio)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (row['фраза'], row['перевод_RU'], row['перевод_EN'], row['перевод_PL'], row['объяснение'], row['аудио_ссылка']))
        conn.commit()
    conn.close()

# Fuzzy search функция
def find_phrase(query):
    conn = sqlite3.connect('phrases.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM phrases')
    all_phrases = [row[1] for row in cursor.fetchall()]  # Все фразы
    conn.close()
    
    matches = difflib.get_close_matches(query, all_phrases, n=1, cutoff=0.6)
    if matches:
        conn = sqlite3.connect('phrases.db')
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM phrases WHERE phrase = ?', (matches[0],))
        result = cursor.fetchone()
        conn.close()
        return result
    return None

# Команда /start
@dp.message(Command("start"))
async def start_handler(message: types.Message, state: FSMContext):
    await message.answer(
        "Привет! Я Галицкий словарь — переводчик западноукраинского фольклора.\n\n"
        "Введи фразу (например, 'етнічне на ніч') для перевода.\n\n"
        "Соглашаешься на обработку запросов? (Да/Нет)"
    )
    await state.set_state(Form.waiting_phrase)

# Обработка фразы
@dp.message(Form.waiting_phrase)
async def process_phrase(message: types.Message, state: FSMContext):
    user_input = message.text.lower().strip()
    
    # Согласие ПД (простая проверка)
    if user_input.lower() in ['нет', 'no']:
        await message.answer("Ок, до свидания. Без согласия не могу работать.")
        await state.clear()
        return
    
    # Поиск
    result = find_phrase(user_input)
    if result:
        phrase, ru, en, pl, explanation, audio = result[1], result[2], result[3], result[4], result[5], result[6]
        text = f"Фраза: {phrase}\n\nRU: {ru}\nEN: {en}\nPL: {pl}\n\nОбъяснение: {explanation}\nАудио: {audio}"
        await message.answer(text)
    else:
        await message.answer("Фраза не найдена. Попробуй другую или уточни. Пример: 'віхолою колись'.")
    
    # Предложить подписку после 3 запросов (логика счётчика в FSM, но упрощённо)
    await message.answer("Хочешь полный доступ (870+ фраз)? Оплати 99 ₽/мес: /subscribe")
    await state.clear()

# Подписка
@dp.message(Command("subscribe"))
async def subscribe_handler(message: types.Message):
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Галицкий словарь Premium",
        description="Полный доступ к 870 фразам + обновления",
        payload="galician_premium",
        provider_token=PROVIDER_TOKEN,
        currency="RUB",
        prices=[LabeledPrice(label="Подписка", amount=99)],
        start_parameter="galician-sub"
    )

# Pre-checkout
@dp.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_q: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_q.id, ok=True)

# Успешная оплата
@dp.message(lambda message: message.successful_payment)
async def successful_payment_handler(message: types.Message):
    # Добавляем в канал
    await bot.send_message(message.from_user.id, f"Спасибо! Вот доступ: {CHANNEL_LINK}")
    # Логика добавления в канал (через invite link)
    await message.answer("Ты в премиуме! Теперь все фразы без лимита.")

# Запуск
if __name__ == "__main__":
    init_db()  # Инициализация БД
    dp.run_polling(bot)