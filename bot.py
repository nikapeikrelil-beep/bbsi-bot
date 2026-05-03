import asyncio
import sqlite3
import re
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ════════════ ТВОИ ДАННЫЕ ════════════
BOT_TOKEN = "8523252259:AAGShQCJzPfJZGNojgQ9r3w7G6CwcUrBz9E"
GROUP_REQUESTS = -1003988760349
GROUP_RULES = -1003934127071
GROUP_MAIN = -1003938419933
ADMIN_GROUP = -1003944645878
SUPREME_ADMIN = 7440989311
ADMIN_LEVELS = {7440989311: 3}

# Уровни админов: {user_id: уровень}
# 1 - младший админ, 2 - старший, 3 - верховный (ты)
ADMIN_LEVELS = {7440989311: 3}

# Авто-банк: True = бот сам банит, False = спрашивает тебя
AUTO_BAN = False  # Поменяй на True когда захочешь автобаны

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# ════════════ БАЗА ДАННЫХ ════════════
def init_db():
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT,
        birth_date TEXT, phone TEXT, country TEXT, city TEXT,
        gender TEXT, level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0,
        status TEXT DEFAULT 'new', rules_accepted INTEGER DEFAULT 0,
        language TEXT DEFAULT 'RU', join_date TEXT,
        admin_level INTEGER DEFAULT 0, warnings INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0, ban_reason TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, type TEXT, article TEXT,
        chat_id INTEGER, auto_action TEXT, timestamp TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS blacklist (
        user_id INTEGER PRIMARY KEY, username TEXT,
        reason TEXT, banned_by INTEGER, ban_date TEXT
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
    c.execute("INSERT OR IGNORE INTO users (user_id, username, full_name, join_date) VALUES (?, ?, ?, ?)",
              (uid, uname, fname, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def add_violation(uid, vtype, article, chat_id, action=""):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("INSERT INTO violations (user_id, type, article, chat_id, auto_action, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
              (uid, vtype, article, chat_id, action, datetime.now().isoformat()))
    # Увеличиваем счётчик предупреждений
    c.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return get_warnings(uid)

def get_warnings(uid):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT warnings FROM users WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r[0] if r else 0

def is_banned(uid):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT * FROM blacklist WHERE user_id=?", (uid,))
    r = c.fetchone()
    conn.close()
    return r is not None

def ban_user(uid, reason, banned_by):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO blacklist (user_id, username, reason, banned_by, ban_date) VALUES (?, ?, ?, ?, ?)",
              (uid, f"user_{uid}", reason, banned_by, datetime.now().isoformat()))
    c.execute("UPDATE users SET banned=1, ban_reason=? WHERE user_id=?", (reason, uid))
    conn.commit()
    conn.close()

def unban_user(uid):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("DELETE FROM blacklist WHERE user_id=?", (uid,))
    c.execute("UPDATE users SET banned=0, ban_reason=NULL, warnings=0 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()

def get_admin_level(uid):
    return ADMIN_LEVELS.get(uid, 0)

# ════════════ ЯЗЫКИ ════════════
ALL_LANGUAGES = {
    "RU": "🇷🇺 Русский", "EN": "🇬🇧 English", "DE": "🇩🇪 Deutsch",
    "FR": "🇫🇷 Français", "ES": "🇪🇸 Español", "IT": "🇮🇹 Italiano",
    "PT": "🇵🇹 Português", "PL": "🇵🇱 Polski", "UA": "🇺🇦 Українська",
    "CS": "🇨🇿 Čeština", "HU": "🇭🇺 Magyar", "RO": "🇷🇴 Română",
    "BG": "🇧🇬 Български", "SR": "🇷🇸 Српски", "HR": "🇭🇷 Hrvatski",
    "SQ": "🇦🇱 Shqip", "EL": "🇬🇷 Ελληνικά", "SV": "🇸🇪 Svenska",
    "DA": "🇩🇰 Dansk", "NO": "🇳🇴 Norsk", "FI": "🇫🇮 Suomi",
    "ET": "🇪🇪 Eesti", "LV": "🇱🇻 Latviešu", "LT": "🇱🇹 Lietuvių",
    "ZH": "🇨🇳 中文", "JA": "🇯🇵 日本語", "KO": "🇰🇷 한국어",
    "HI": "🇮🇳 हिन्दी", "BN": "🇧🇩 বাংলা", "UR": "🇵🇰 اردو",
    "AR": "🇸🇦 العربية", "HE": "🇮🇱 עברית", "FA": "🇮🇷 فارسی",
    "TR": "🇹🇷 Türkçe", "TH": "🇹🇭 ไทย", "VI": "🇻🇳 Tiếng Việt",
    "ID": "🇮🇩 Indonesia", "TL": "🇵🇭 Tagalog",
    "KA": "🇬🇪 ქართული", "HY": "🇦🇲 Հայերեն", "AZ": "🇦🇿 Azərbaycan",
    "KK": "🇰🇿 Қазақша", "UZ": "🇺🇿 O'zbek", "KY": "🇰🇬 Кыргызча",
    "SW": "🇹🇿 Kiswahili", "ZU": "🇿🇦 isiZulu", "AF": "🇿🇦 Afrikaans",
    "AM": "🇪🇹 አማርኛ", "SO": "🇸🇴 Soomaali",
    "TO": "🇹🇴 Faka-Tonga", "MI": "🇳🇿 Māori", "EO": "🟢 Esperanto",
}

RULES_TEXT = """
⚖️ УГОЛОВНЫЙ КОДЕКС СООБЩЕСТВА

Статья 12.3 — Скриншот чата. Пожизненный бан. 1M ⭐
Статья 17.8 — Пересылка контента. Бан + $5000 нал.
Статья 23.1 — Запись экрана. Вечный бан без амнистии.
Статья 19.2 — Доксинг. Вечный бан. 25M ⭐
Статья 15.1 — Оскорбление. Бан 1 месяц. 100K ⭐
Статья 25.4 — Угрозы жизни. Вечный бан + полиция.
Статья 27.1 — Слив интимных фото. Вечный бан + дело.
Статья 34.9 — Шпионаж. GLOBAL BLACKLIST.
Статья 35.2 — Слив БД. $100K или 1B ⭐
Статья 30.0 — Уничтожение чата. $100K + суд.

Всего 80 статей. При входе - принимаешь всё.
"""

class Reg(StatesGroup):
    fio = State()
    birth = State()
    phone = State()
    country = State()
    city = State()
    gender = State()

# ════════════ КЛАВИАТУРЫ ════════════
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Подать заявку", callback_data="apply")],
        [InlineKeyboardButton(text="📜 Правила", callback_data="rules")],
        [InlineKeyboardButton(text="🌐 Язык", callback_data="lang")],
    ])

def admin_kb(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ В правила", callback_data=f"acc_{uid}")],
        [InlineKeyboardButton(text="⭐ В основную", callback_data=f"main_{uid}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rej_{uid}")],
    ])

def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНИМАЮ ВСЕ СТАТЬИ", callback_data="accept_rules")],
    ])

def gender_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👨 Мужской"), KeyboardButton(text="👩 Женский")],
        [KeyboardButton(text="⚧ Другой")]
    ], resize_keyboard=True, one_time_keyboard=True)

def violation_kb(uid, vtype):
    """Клавиатура для админа при нарушении"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔨 БАН", callback_data=f"vban_{uid}_{vtype}"),
            InlineKeyboardButton(text="⚠️ Предупредить", callback_data=f"vwarn_{uid}_{vtype}")
        ],
        [
            InlineKeyboardButton(text="👀 Игнорировать", callback_data=f"vignore_{uid}_{vtype}"),
            InlineKeyboardButton(text="📊 Статистика", callback_data=f"vstats_{uid}")
        ]
    ])

def lang_kb(page=0):
    langs = list(ALL_LANGUAGES.items())
    per_page = 6
    total = len(langs) // per_page + 1
    start = page * per_page
    kb = []
    for code, name in langs[start:start+per_page]:
        kb.append([InlineKeyboardButton(text=name, callback_data=f"setlang_{code}")])
    nav = []
    if page > 0: nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"langpg_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="noop"))
    if page < total - 1: nav.append(InlineKeyboardButton(text="➡️", callback_data=f"langpg_{page+1}"))
    kb.append(nav)
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ════════════ /start ════════════
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    uid = message.from_user.id
    if is_banned(uid):
        await message.answer("⛔ ВЫ ЗАБАНЕНЫ!\n\nДля аппеляции обратитесь к администратору.")
        return
    user = get_user(uid)
    if not user:
        add_user(uid, message.from_user.username, message.from_user.full_name)
    await message.answer(
        "👋 ДОБРО ПОЖАЛОВАТЬ В THE EMPIRE!\n\n"
        "⚖️ Уголовный Кодекс — 80 статей\n"
        "💀 Слив = приговор\n\n"
        "📝 Подайте заявку для вступления:",
        reply_markup=main_kb()
    )

# ════════════ АДМИН-КОМАНДЫ ════════════
@dp.message(Command("ban"))
async def cmd_ban(message: types.Message):
    uid = message.from_user.id
    if get_admin_level(uid) < 1:
        await message.answer("⛔ Нет прав!")
        return
    
    # Формат: /ban ID причина
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("❌ Формат: /ban ID причина\nНапример: /ban 123456789 скриншот")
        return
    
    target_id = int(parts[1])
    reason = parts[2]
    
    ban_user(target_id, reason, uid)
    
    # Баним в группах
    for gid in [GROUP_REQUESTS, GROUP_RULES, GROUP_MAIN]:
        try:
            await bot.ban_chat_member(gid, target_id)
        except:
            pass
    
    await message.answer(f"✅ Пользователь {target_id} забанен!\nПричина: {reason}")
    await bot.send_message(ADMIN_GROUP, f"🔨 @{message.from_user.username} забанил {target_id}\nПричина: {reason}")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message):
    uid = message.from_user.id
    if get_admin_level(uid) < 1:
        await message.answer("⛔ Нет прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Формат: /unban ID\nНапример: /unban 123456789")
        return
    
    target_id = int(parts[1])
    unban_user(target_id)
    
    # Разбаниваем в группах
    for gid in [GROUP_REQUESTS, GROUP_RULES, GROUP_MAIN]:
        try:
            await bot.unban_chat_member(gid, target_id)
        except:
            pass
    
    await message.answer(f"✅ Пользователь {target_id} разбанен!")
    await bot.send_message(ADMIN_GROUP, f"✅ @{message.from_user.username} разбанил {target_id}")

@dp.message(Command("BOTBBSI"))
async def cmd_promote_admin(message: types.Message):
    """Повышение до админа после обзвона. Только старший админ (уровень 2+)."""
    uid = message.from_user.id
    if get_admin_level(uid) < 2:
        await message.answer("⛔ Только старшие админы могут повышать!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("❌ Формат: /BOTBBSI ID уровень\nУровни: 1-младший, 2-старший\nПример: /BOTBBSI 123456789 1")
        return
    
    target_id = int(parts[1])
    level = int(parts[2])
    
    if level not in [1, 2]:
        await message.answer("❌ Уровень должен быть 1 или 2!")
        return
    
    ADMIN_LEVELS[target_id] = level
    update_user(target_id, admin_level=level)
    
    await message.answer(f"✅ Пользователь {target_id} повышен до админа уровня {level}!")
    await bot.send_message(target_id, f"🎉 ПОЗДРАВЛЯЕМ!\n\nВы стали администратором уровня {level}!\n\nДоступные команды:\n/ban - забанить\n/unban - разбанить\n/warnings - предупреждения")
    await bot.send_message(ADMIN_GROUP, f"👑 @{message.from_user.username} повысил {target_id} до админа уровня {level}")

@dp.message(Command("demote"))
async def cmd_demote(message: types.Message):
    """Понижение админа. Только верховный (уровень 3)."""
    uid = message.from_user.id
    if get_admin_level(uid) < 3:
        await message.answer("⛔ Только Верховный Админ может понижать!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("❌ Формат: /demote ID")
        return
    
    target_id = int(parts[1])
    if target_id == SUPREME_ADMIN:
        await message.answer("❌ Нельзя понизить Верховного Админа!")
        return
    
    ADMIN_LEVELS.pop(target_id, None)
    update_user(target_id, admin_level=0)
    
    await message.answer(f"✅ Админ {target_id} понижен!")
    await bot.send_message(target_id, "⚠️ Вы были понижены. Админ-права отозваны.")

@dp.message(Command("admins"))
async def cmd_admins(message: types.Message):
    """Список всех админов."""
    if not ADMIN_LEVELS:
        await message.answer("Нет админов.")
        return
    
    txt = "👑 СПИСОК АДМИНОВ:\n\n"
    for aid, level in ADMIN_LEVELS.items():
        lvl_name = {1: "Младший", 2: "Старший", 3: "Верховный"}
        txt += f"🆔 {aid} — {lvl_name.get(level, 'Неизвестно')}\n"
    
    await message.answer(txt)

@dp.message(Command("warnings"))
async def cmd_warnings(message: types.Message):
    """Проверить предупреждения пользователя."""
    uid = message.from_user.id
    if get_admin_level(uid) < 1:
        # Обычный пользователь смотрит свои
        w = get_warnings(message.from_user.id)
        await message.answer(f"⚠️ Ваши предупреждения: {w}/3\nПри 3 = БАН")
        return
    
    parts = message.text.split()
    target_id = int(parts[1]) if len(parts) > 1 else message.from_user.id
    w = get_warnings(target_id)
    await message.answer(f"⚠️ Предупреждения пользователя {target_id}: {w}/3")

@dp.message(Command("autoban"))
async def cmd_autoban(message: types.Message):
    """Включить/выключить авто-бан. Только верховный."""
    global AUTO_BAN
    uid = message.from_user.id
    if get_admin_level(uid) < 3:
        await message.answer("⛔ Только Верховный Админ!")
        return
    
    AUTO_BAN = not AUTO_BAN
    status = "ВКЛЮЧЕН" if AUTO_BAN else "ВЫКЛЮЧЕН"
    await message.answer(f"🤖 Авто-бан: {status}")
    await bot.send_message(ADMIN_GROUP, f"⚙️ Верховный Админ изменил режим банов:\nАвто-бан: {status}")

# ════════════ РЕГИСТРАЦИЯ ════════════
@dp.callback_query(F.data == "apply")
async def apply_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("📝 РЕГИСТРАЦИЯ\n\nШаг 1/6 — Введите ПОЛНОЕ ФИО:")
    await state.set_state(Reg.fio)
    await callback.answer()

@dp.message(Reg.fio)
async def step_fio(message: types.Message, state: FSMContext):
    if len(message.text.split()) < 2:
        await message.answer("❌ Минимум Фамилия и Имя:")
        return
    await state.update_data(fio=message.text.strip())
    await message.answer("✅ Шаг 2/6 — Дата рождения (ДД.ММ.ГГГГ):")
    await state.set_state(Reg.birth)

@dp.message(Reg.birth)
async def step_birth(message: types.Message, state: FSMContext):
    if not re.match(r'^\d{2}\.\d{2}\.\d{4}$', message.text.strip()):
        await message.answer("❌ Формат: ДД.ММ.ГГГГ")
        return
    await state.update_data(birth=message.text.strip())
    await message.answer("✅ Шаг 3/6 — Телефон:")
    await state.set_state(Reg.phone)

@dp.message(Reg.phone)
async def step_phone(message: types.Message, state: FSMContext):
    p = message.text.strip().replace(' ','').replace('-','')
    if len(p) < 10:
        await message.answer("❌ Неверный формат:")
        return
    await state.update_data(phone=message.text.strip())
    await message.answer("✅ Шаг 4/6 — Страна:")
    await state.set_state(Reg.country)

@dp.message(Reg.country)
async def step_country(message: types.Message, state: FSMContext):
    await state.update_data(country=message.text.strip())
    await message.answer("✅ Шаг 5/6 — Город:")
    await state.set_state(Reg.city)

@dp.message(Reg.city)
async def step_city(message: types.Message, state: FSMContext):
    await state.update_data(city=message.text.strip())
    await message.answer("✅ Шаг 6/6 — Пол:", reply_markup=gender_kb())
    await state.set_state(Reg.gender)

@dp.message(Reg.gender)
async def step_gender(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    d = await state.get_data()
    update_user(uid, full_name=d['fio'], birth_date=d['birth'], phone=d['phone'],
                country=d['country'], city=d['city'], gender=message.text.strip(), status="pending")
    txt = (f"📥 ЗАЯВКА\n\n👤 {d['fio']}\n🎂 {d['birth']}\n📞 {d['phone']}\n"
           f"🌍 {d['country']}, {d['city']}\n⚧ {message.text.strip()}\n"
           f"🆔 {uid}\n📛 @{message.from_user.username}")
    await bot.send_message(GROUP_REQUESTS, txt, reply_markup=admin_kb(uid))
    await bot.send_message(ADMIN_GROUP, txt)
    await message.answer(f"✅ ГОТОВО!\n\n{txt}\n\nОжидайте решения.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📜 Правила", callback_data="rules")]]))
    await state.clear()

# ════════════ АДМИН-КНОПКИ ЗАЯВОК ════════════
@dp.callback_query(F.data.startswith("acc_"))
async def admin_acc(callback: types.CallbackQuery):
    if get_admin_level(callback.from_user.id) < 1:
        await callback.answer("⛔ Нет прав!")
        return
    uid = int(callback.data.split("_")[1])
    try:
        link = await bot.create_chat_invite_link(GROUP_RULES, member_limit=1)
        await bot.send_message(uid, f"✅ ВЫ ПРИНЯТЫ В ГРУППУ ПРАВИЛ\n{link.invite_link}\n\nИзучите Кодекс и примите все статьи.")
        update_user(uid, status="rules")
        await callback.message.edit_text(callback.message.text + "\n\n✅ В ПРАВИЛАХ")
    except Exception as e:
        await callback.answer(str(e))
    await callback.answer()

@dp.callback_query(F.data.startswith("main_"))
async def admin_main(callback: types.CallbackQuery):
    if get_admin_level(callback.from_user.id) < 1:
        await callback.answer("⛔ Нет прав!")
        return
    uid = int(callback.data.split("_")[1])
    u = get_user(uid)
    if not u or u[10] != 1:
        await callback.answer("❌ Не принял правила!")
        return
    try:
        link = await bot.create_chat_invite_link(GROUP_MAIN, member_limit=1)
        await bot.send_message(uid, f"🎉 ВЫ В ОСНОВНОЙ ГРУППЕ!\n{link.invite_link}\n\n⚖️ УК действует!")
        update_user(uid, status="approved")
        await callback.message.edit_text(callback.message.text + "\n\n✅ В ОСНОВНОЙ")
    except Exception as e:
        await callback.answer(str(e))
    await callback.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def admin_rej(callback: types.CallbackQuery):
    if get_admin_level(callback.from_user.id) < 1:
        await callback.answer("⛔ Нет прав!")
        return
    uid = int(callback.data.split("_")[1])
    await bot.send_message(uid, "❌ Заявка отклонена.")
    update_user(uid, status="rejected")
    await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКЛОНЁН")
    await callback.answer()

# ════════════ ПРАВИЛА ════════════
@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    await callback.message.edit_text(RULES_TEXT, reply_markup=rules_kb())
    await callback.answer()

@dp.callback_query(F.data == "accept_rules")
async def accept_rules(callback: types.CallbackQuery):
    uid = callback.from_user.id
    update_user(uid, rules_accepted=1)
    await callback.message.edit_text("✅ ВСЕ 80 СТАТЕЙ ПРИНЯТЫ!\n\n⚖️ Вы под юрисдикцией Суда.\nОжидайте одобрения.")
    await bot.send_message(ADMIN_GROUP, f"✅ @{callback.from_user.username} принял статьи!")
    await callback.answer()

# ════════════ ЗАЩИТА ОТ НАРУШЕНИЙ ════════════
@dp.message(F.forward_from | F.forward_from_chat)
async def detect_forward(message: types.Message):
    """Обнаружение пересылки"""
    uid = message.from_user.id
    w = add_violation(uid, "forward", "17.8", message.chat.id)
    
    try:
        await message.delete()
    except:
        pass
    
    if AUTO_BAN and w >= 3:
        await execute_ban(uid, "Пересылка (3 нарушения)")
        return
    
    # Отправляем админам
    await bot.send_message(
        ADMIN_GROUP,
        f"🚨 ПЕРЕСЫЛКА!\n👤 @{message.from_user.username} (ID:{uid})\n"
        f"📜 Статья 17.8\n⚠️ Нарушений: {w}/3\n"
        f"🤖 Авто-бан: {'ВКЛ' if AUTO_BAN else 'ВЫКЛ'}",
        reply_markup=violation_kb(uid, "forward")
    )
    
    warn_msg = await message.answer(f"🚫 @{message.from_user.username} — ПЕРЕСЫЛКА ЗАПРЕЩЕНА!\nНарушение {w}/3")
    await asyncio.sleep(10)
    try:
        await warn_msg.delete()
    except:
        pass

async def execute_ban(uid, reason):
    """Выполнить бан пользователя"""
    ban_user(uid, reason, 0)
    for gid in [GROUP_REQUESTS, GROUP_RULES, GROUP_MAIN]:
        try:
            await bot.ban_chat_member(gid, uid)
        except:
            pass
    await bot.send_message(uid, f"⛔ ВЫ ЗАБАНЕНЫ!\nПричина: {reason}")
    await bot.send_message(ADMIN_GROUP, f"🔨 АВТО-БАН: {uid}\nПричина: {reason}")

# ════════════ ОБРАБОТКА КНОПОК АДМИНА ════════════
@dp.callback_query(F.data.startswith("vban_"))
async def violation_ban(callback: types.CallbackQuery):
    if get_admin_level(callback.from_user.id) < 1:
        await callback.answer("⛔ Нет прав!")
        return
    parts = callback.data.split("_")
    uid = int(parts[1])
    vtype = parts[2]
    await execute_ban(uid, f"Нарушение: {vtype}")
    await callback.message.edit_text(callback.message.text + f"\n\n🔨 ЗАБАНЕН админом @{callback.from_user.username}")
    await callback.answer("✅ Забанен!")

@dp.callback_query(F.data.startswith("vwarn_"))
async def violation_warn(callback: types.CallbackQuery):
    if get_admin_level(callback.from_user.id) < 1:
        await callback.answer("⛔ Нет прав!")
        return
    parts = callback.data.split("_")
    uid = int(parts[1])
    w = get_warnings(uid)
    await bot.send_message(uid, f"⚠️ ПРЕДУПРЕЖДЕНИЕ {w}/3\nПри 3 нарушениях — БАН.")
    await callback.message.edit_text(callback.message.text + f"\n\n⚠️ Предупреждён админом @{callback.from_user.username}")
    await callback.answer()

@dp.callback_query(F.data.startswith("vignore_"))
async def violation_ignore(callback: types.CallbackQuery):
    await callback.message.edit_text(callback.message.text + "\n\n👀 Игнорировано")
    await callback.answer()

@dp.callback_query(F.data.startswith("vstats_"))
async def violation_stats(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    w = get_warnings(uid)
    user = get_user(uid)
    await callback.answer(f"📊 ID:{uid} | Нарушений: {w}/3 | Статус: {user[5] if user else '?'}", show_alert=True)

# ════════════ ЯЗЫКИ ════════════
@dp.callback_query(F.data == "lang")
async def show_lang(callback: types.CallbackQuery):
    await callback.message.edit_text("🌐 ВЫБЕРИТЕ ЯЗЫК:", reply_markup=lang_kb())
    await callback.answer()

@dp.callback_query(F.data.startswith("langpg_"))
async def lang_page(callback: types.CallbackQuery):
    page = int(callback.data.split("_")[1])
    await callback.message.edit_text("🌐 ЯЗЫК:", reply_markup=lang_kb(page))
    await callback.answer()

@dp.callback_query(F.data.startswith("setlang_"))
async def set_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    update_user(callback.from_user.id, language=lang)
    await callback.message.edit_text(f"✅ Язык: {ALL_LANGUAGES.get(lang, lang)}\n/start — меню")
    await callback.answer()

@dp.callback_query(F.data == "back")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 Главное меню:", reply_markup=main_kb())
    await callback.answer()

@dp.callback_query(F.data == "noop")
async def noop(callback: types.CallbackQuery):
    await callback.answer()

# ════════════ ЗАПУСК ════════════
async def main():
    init_db()
    print("🤖 БОТ ЗАПУЩЕН!")
    print(f"👑 Верховный Админ: {SUPREME_ADMIN}")
    print(f"🤖 Авто-бан: {'ВКЛЮЧЕН' if AUTO_BAN else 'ВЫКЛЮЧЕН (ручной режим)'}")
    print(f"⚖️ УК активирован")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())