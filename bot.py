import asyncio
import sqlite3
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ════════════ ДАННЫЕ ════════════
BOT_TOKEN = "8523252259:AAGShQCJzPfJZGNojgQ9r3w7G6CwcUrBz9E"
GROUP_REQUESTS = -1003988760349
GROUP_RULES = -1003934127071
GROUP_MAIN = -1003938419933
ADMIN_GROUP = -1003944645878
ADMIN_IDS = [7440989311]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ════════════ БД ════════════
def init_db():
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
        birth_date TEXT, phone TEXT, country TEXT, city TEXT,
        gender TEXT, status TEXT DEFAULT 'new', rules_accepted INTEGER DEFAULT 0,
        warnings INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, ban_reason TEXT
    )''')
    conn.commit()
    conn.close()

def get_user(uid):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    u = c.fetchone()
    conn.close()
    return u

def update_user(uid, **kw):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    sets = ", ".join(f"{k}=?" for k in kw)
    vals = list(kw.values()) + [uid]
    c.execute(f"UPDATE users SET {sets} WHERE user_id=?", vals)
    conn.commit()
    conn.close()

def add_user(uid, uname, fname):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)", (uid, uname, fname))
    conn.commit()
    conn.close()

def is_banned(uid):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT banned FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r and r[0] == 1

def get_pending_count():
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE status='pending'")
    r = c.fetchone()[0]
    conn.close()
    return r

# ════════════ КЛАВИАТУРЫ ════════════
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Подать заявку", callback_data="apply")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="👑 Админ-панель", callback_data="apanel")],
    ])

def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНИМАЮ ВСЕ СТАТЬИ УК", callback_data="accept_rules")],
    ])

def gender_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")],
        [KeyboardButton(text="⚧ Другой")]
    ], resize_keyboard=True, one_time_keyboard=True)

def request_buttons(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНЯТЬ В ПРАВИЛА", callback_data=f"acc_{uid}")],
        [InlineKeyboardButton(text="⭐ СРАЗУ В ЧАТ", callback_data=f"direct_{uid}")],
        [
            InlineKeyboardButton(text="⏳ ОТЛОЖИТЬ", callback_data=f"hold_{uid}"),
            InlineKeyboardButton(text="❌ ОТКЛОНИТЬ", callback_data=f"rej_{uid}")
        ],
        [
            InlineKeyboardButton(text="📋 АНКЕТА", callback_data=f"info_{uid}"),
            InlineKeyboardButton(text="💬 НАПИСАТЬ", url=f"tg://user?id={uid}")
        ]
    ])

def admin_approve_buttons(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ ОДОБРИТЬ В ЧАТ", callback_data=f"appr_{uid}")],
        [
            InlineKeyboardButton(text="⏳ ПОДОЖДАТЬ", callback_data=f"wait_{uid}"),
            InlineKeyboardButton(text="❌ ОТКАЗАТЬ", callback_data=f"deny_{uid}")
        ],
        [InlineKeyboardButton(text="📋 АНКЕТА", callback_data=f"info_{uid}")],
    ])

def admin_panel_kb():
    pending = get_pending_count()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📥 Заявки ({pending})", callback_data="apanel_requests")],
        [InlineKeyboardButton(text="👤 Пользователи", callback_data="apanel_users")],
        [InlineKeyboardButton(text="🔨 Забаненные", callback_data="apanel_banned")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="apanel_stats")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="apanel")],
    ])

# ════════════ /start ТОЛЬКО В ЛИЧКЕ ════════════
@dp.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def start_cmd(message: types.Message):
    uid = message.from_user.id
    if is_banned(uid):
        await message.answer("⛔ ВЫ ЗАБАНЕНЫ!")
        return
    user = get_user(uid)
    if not user:
        add_user(uid, message.from_user.username, message.from_user.full_name)
    await message.answer("👋 ДОБРО ПОЖАЛОВАТЬ В BBSI!\n\n⚖️ 80 статей УК\n💀 Слив = приговор", reply_markup=main_kb())

@dp.message(Command("start"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def start_group(message: types.Message):
    pass

# ════════════ АДМИН-ПАНЕЛЬ ════════════
@dp.callback_query(F.data == "apanel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!")
        return
    await callback.message.edit_text("👑 АДМИН-ПАНЕЛЬ\n\nВыберите раздел:", reply_markup=admin_panel_kb())
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 Главное меню:", reply_markup=main_kb())
    await callback.answer()

@dp.callback_query(F.data == "apanel_requests")
async def panel_requests(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!")
        return
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, country, city, status FROM users WHERE status IN ('pending', 'on_hold') ORDER BY rowid DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.edit_text("📥 Нет активных заявок.", reply_markup=back_kb())
        return
    
    txt = "📥 АКТИВНЫЕ ЗАЯВКИ:\n\n"
    kb = []
    for r in rows:
        txt += f"🆔 {r[0]} | {r[1]} | {r[3]}\n"
        kb.append([InlineKeyboardButton(text=f"📋 {r[1]}", callback_data=f"info_{r[0]}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="apanel")])
    
    await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data == "apanel_users")
async def panel_users(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!")
        return
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, status FROM users WHERE status='approved' LIMIT 20")
    rows = c.fetchall()
    conn.close()
    
    if not rows:
        await callback.message.edit_text("👤 Нет пользователей.", reply_markup=back_kb())
        return
    
    txt = "👤 ПОЛЬЗОВАТЕЛИ:\n\n"
    for r in rows:
        txt += f"🆔 {r[0]} | {r[1]} | ✅\n"
    
    await callback.message.edit_text(txt, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "apanel_stats")
async def panel_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("⛔ Нет прав!")
        return
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE status='pending'")
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE status='approved'")
    approved = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned = c.fetchone()[0]
    conn.close()
    
    txt = (f"📊 СТАТИСТИКА\n\n"
           f"👥 Всего: {total}\n"
           f"📥 Заявок: {pending}\n"
           f"✅ В чате: {approved}\n"
           f"🔨 Забанено: {banned}")
    
    await callback.message.edit_text(txt, reply_markup=back_kb())
    await callback.answer()

# ════════════ РЕГИСТРАЦИЯ ════════════
class Reg(StatesGroup):
    fio = State()
    birth = State()
    phone = State()
    country = State()
    city = State()
    gender = State()

@dp.callback_query(F.data == "apply")
async def apply_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 Шаг 1/6 — Введите ПОЛНОЕ ФИО (Фамилия Имя Отчество):")
    await state.set_state(Reg.fio)
    await callback.answer()

@dp.message(Reg.fio)
async def s_fio(message: types.Message, state: FSMContext):
    if len(message.text.split()) < 2:
        await message.answer("❌ Минимум Фамилия и Имя:")
        return
    await state.update_data(fio=message.text.strip())
    await message.answer("✅ Шаг 2/6 — Дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(Reg.birth)

@dp.message(Reg.birth)
async def s_birth(message: types.Message, state: FSMContext):
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', message.text.strip()):
        await message.answer("❌ ДД.ММ.ГГГГ:")
        return
    await state.update_data(birth=message.text.strip())
    await message.answer("✅ Шаг 3/6 — Телефон:")
    await state.set_state(Reg.phone)

@dp.message(Reg.phone)
async def s_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip())
    await message.answer("✅ Шаг 4/6 — Страна:")
    await state.set_state(Reg.country)

@dp.message(Reg.country)
async def s_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("✅ Шаг 5/6 — Город:")
    await state.set_state(Reg.city)

@dp.message(Reg.city)
async def s_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("✅ Шаг 6/6 — Выберите пол:", reply_markup=gender_kb())
    await state.set_state(Reg.gender)

@dp.message(Reg.gender)
async def s_gender(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    d = await state.get_data()
    uname = message.from_user.username or "нет"
    
    update_user(uid, full_name=d['fio'], birth_date=d['birth'], phone=d['phone'],
                country=d['country'], city=d['city'], gender=message.text.strip(), status="pending")
    
    txt = (f"📥 ЗАЯВКА #{uid}\n\n"
           f"👤 {d['fio']}\n🎂 {d['birth']}\n📞 {d['phone']}\n"
           f"🌍 {d['country']}, {d['city']}\n⚧ {message.text.strip()}\n"
           f"🆔 {uid}\n📛 @{uname}")
    
    await bot.send_message(GROUP_REQUESTS, txt, reply_markup=request_buttons(uid))
    await bot.send_message(ADMIN_GROUP, f"📥 Заявка #{uid}\n{d['fio']}", reply_markup=request_buttons(uid))
    
    await message.answer("✅ ЗАЯВКА ОТПРАВЛЕНА!\n\nОжидайте решения.", reply_markup=rules_kb())
    await state.clear()

# ════════════ КНОПКИ УПРАВЛЕНИЯ ════════════
@dp.callback_query(F.data.startswith("acc_"))
async def btn_accept(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    try:
        link = await bot.create_chat_invite_link(GROUP_RULES, member_limit=1)
        await bot.send_message(uid, f"✅ ПРИНЯТ В BBSI ПРАВИЛА\n\n{link.invite_link}\n\n📜 Примите УК:", reply_markup=rules_kb())
        update_user(uid, status="rules")
        await callback.message.edit_text(callback.message.text + "\n\n✅ ПРИНЯТ В ПРАВИЛА")
    except Exception as e: await callback.answer(str(e))
    await callback.answer()

@dp.callback_query(F.data.startswith("direct_"))
async def btn_direct(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    try:
        link = await bot.create_chat_invite_link(GROUP_MAIN, member_limit=1)
        await bot.send_message(uid, f"🎉 ВЫ В BBSI ЧАТ!\n\n{link.invite_link}\n\n⚖️ УК действует!")
        update_user(uid, status="approved")
        await callback.message.edit_text(callback.message.text + "\n\n⭐ В ЧАТЕ")
    except Exception as e: await callback.answer(str(e))
    await callback.answer()

@dp.callback_query(F.data.startswith("hold_"))
async def btn_hold(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    update_user(uid, status="on_hold")
    await bot.send_message(uid, "⏳ Ваша заявка на рассмотрении.")
    await callback.message.edit_text(callback.message.text + "\n\n⏳ ОТЛОЖЕНО")
    await callback.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def btn_reject(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    await bot.send_message(uid, "❌ Заявка отклонена.")
    update_user(uid, status="rejected")
    await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКЛОНЁН")
    await callback.answer()

@dp.callback_query(F.data.startswith("info_"))
async def btn_info(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    user = get_user(uid)
    if user:
        age = "?"
        if user[3]:
            try:
                d = datetime.strptime(user[3], "%d.%m.%Y")
                age = datetime.now().year - d.year
            except: pass
        txt = (f"📋 АНКЕТА #{uid}\n\n"
               f"👤 {user[2]}\n🎂 {user[3]} ({age} лет)\n📞 {user[4]}\n"
               f"🌍 {user[5]}, {user[6]}\n⚧ {user[7]}\n"
               f"📊 Статус: {user[8]}\n⚠️ Предупреждений: {user[9]}")
        await callback.message.answer(txt)
    await callback.answer()

# ════════════ ПРИНЯТИЕ УК ════════════
@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    await callback.message.edit_text("📜 УК BBSI — 80 статей\n\n12.3 Скриншот → бан\n17.8 Пересылка → $5000\n23.1 Запись → вечный бан", reply_markup=rules_kb())
    await callback.answer()

@dp.callback_query(F.data == "accept_rules")
async def accept_rules(callback: types.CallbackQuery):
    uid = callback.from_user.id
    update_user(uid, rules_accepted=1)
    await callback.message.edit_text("✅ ВСЕ 80 СТАТЕЙ ПРИНЯТЫ!\nОжидайте одобрения в чат.")
    await bot.send_message(ADMIN_GROUP, f"✅ @{callback.from_user.username} принял УК!", reply_markup=admin_approve_buttons(uid))
    await callback.answer()

# ════════════ ОДОБРЕНИЕ В ЧАТ ════════════
@dp.callback_query(F.data.startswith("appr_"))
async def btn_approve(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    try:
        link = await bot.create_chat_invite_link(GROUP_MAIN, member_limit=1)
        await bot.send_message(uid, f"🎉 ВЫ В BBSI ЧАТ!\n\n{link.invite_link}")
        update_user(uid, status="approved")
        await callback.message.edit_text(callback.message.text + "\n\n✅ В ЧАТЕ")
    except Exception as e: await callback.answer(str(e))
    await callback.answer()

@dp.callback_query(F.data.startswith("wait_"))
async def btn_wait(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    await callback.message.edit_text(callback.message.text + "\n\n⏳ ОЖИДАЕТ")
    await callback.answer()

@dp.callback_query(F.data.startswith("deny_"))
async def btn_deny(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    await bot.send_message(uid, "❌ Отказано.")
    update_user(uid, status="denied")
    await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКАЗАНО")
    await callback.answer()

# ════════════ ЗАПУСК ════════════
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
