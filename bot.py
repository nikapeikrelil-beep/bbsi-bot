import asyncio
import sqlite3
import re
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.enums import ParseMode, ChatType
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ════════════ ДАННЫЕ ════════════
BOT_TOKEN = "ТВОЙ_НОВЫЙ_ТОКЕН"
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
        warnings INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, ban_reason TEXT,
        level INTEGER DEFAULT 1, xp INTEGER DEFAULT 0, messages_count INTEGER DEFAULT 0,
        coins INTEGER DEFAULT 100, last_daily TEXT, last_loot TEXT,
        achievement TEXT DEFAULT '', join_date TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER, type TEXT, article TEXT,
        chat_id INTEGER, timestamp TEXT
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

def is_banned(uid):
    u = get_user(uid)
    return u and u[10] == 1

def add_violation(uid, vtype, article, chat_id):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("INSERT INTO violations (user_id, type, article, chat_id, timestamp) VALUES (?, ?, ?, ?, ?)",
              (uid, vtype, article, chat_id, datetime.now().isoformat()))
    c.execute("UPDATE users SET warnings = warnings + 1 WHERE user_id=?", (uid,))
    conn.commit()
    conn.close()
    return get_warnings(uid)

def get_warnings(uid):
    u = get_user(uid)
    return u[9] if u else 0

def get_pending_count():
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE status='pending'")
    r = c.fetchone()[0]
    conn.close()
    return r

# ════════════ КАРТА ТБИЛИСИ ════════════
TBILISI_MAP = """
🗺️ <b>ЗАБРОШКИ, САДИКИ, ШКОЛЫ И МОСТЫ ТБИЛИСИ</b>

👻 <b>Заброшенный садик в Ваке</b>
📍 Рядом с парком Ваке
<a href='https://maps.google.com/?q=41.709981,44.745398'>🗺️ Карта</a>

🏚️ <b>Старая школа в Дидубе</b>
📍 За стадионом Динамо
<a href='https://maps.google.com/?q=41.732561,44.782356'>🗺️ Карта</a>

🏗️ <b>Дом «Призрак» в Сололаки</b>
📍 Старый особняк на горе
<a href='https://maps.google.com/?q=41.693809,44.795631'>🗺️ Карта</a>

🌉 <b>Заброшенный мост через Куру</b>
📍 Пешеходный мост в районе Чугурети
<a href='https://maps.google.com/?q=41.695412,44.813245'>🗺️ Карта</a>

🏭 <b>Заброшенный завод в Глдани</b>
📍 Огромная территория
<a href='https://maps.google.com/?q=41.756123,44.795412'>🗺️ Карта</a>

🏫 <b>Старая школа №23 в Сабуртало</b>
📍 Заброшенное здание
<a href='https://maps.google.com/?q=41.722345,44.731256'>🗺️ Карта</a>

🌳 <b>Заброшенный ботанический сад</b>
📍 Верхний парк
<a href='https://maps.google.com/?q=41.686678,44.805678'>🗺️ Карта</a>

🏰 <b>Крепость Нарикала (ночью)</b>
📍 Старый город
<a href='https://maps.google.com/?q=41.688112,44.809345'>🗺️ Карта</a>

🏗️ <b>Недостроенный мост в Самгори</b>
📍 Район Самгори
<a href='https://maps.google.com/?q=41.701234,44.856789'>🗺️ Карта</a>

👻 <b>Заброшенный детский лагерь</b>
📍 Окрестности Тбилиси
<a href='https://maps.google.com/?q=41.650000,44.750000'>🗺️ Карта</a>
"""

# ════════════ КЛАВИАТУРЫ ════════════
def main_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Подать заявку", callback_data="apply")],
        [InlineKeyboardButton(text="📜 Правила (80 статей)", callback_data="rules")],
        [InlineKeyboardButton(text="👑 Админ-панель", callback_data="apanel")],
        [InlineKeyboardButton(text="📊 Мой профиль", callback_data="myprofile")],
        [InlineKeyboardButton(text="🗺️ Карта Тбилиси", callback_data="map")],
    ])

def rules_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ ПРИНИМАЮ ВСЕ 80 СТАТЕЙ", callback_data="accept_rules")],
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

def violation_buttons(uid, vtype):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 БАН", callback_data=f"vban_{uid}_{vtype}"),
         InlineKeyboardButton(text="⚠️ ПРЕДУПРЕДИТЬ", callback_data=f"vwarn_{uid}_{vtype}")],
        [InlineKeyboardButton(text="👀 ИГНОРИРОВАТЬ", callback_data=f"vignore_{uid}")]
    ])

def admin_approve_buttons(uid):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⭐ ОДОБРИТЬ В ЧАТ", callback_data=f"appr_{uid}")],
        [InlineKeyboardButton(text="⏳ ПОДОЖДАТЬ", callback_data=f"wait_{uid}"),
         InlineKeyboardButton(text="❌ ОТКАЗАТЬ", callback_data=f"deny_{uid}")],
    ])

def admin_panel_kb():
    pending = get_pending_count()
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📥 Заявки ({pending})", callback_data="apanel_requests")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="apanel_stats")],
        [InlineKeyboardButton(text="🏆 Топ-10", callback_data="apanel_top")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_main")],
    ])

def back_kb():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data="apanel")]])

# ════════════ /start ════════════
@dp.message(Command("start"), F.chat.type == ChatType.PRIVATE)
async def start_cmd(message: types.Message):
    uid = message.from_user.id
    if is_banned(uid):
        await message.answer("⛔ ВЫ ЗАБАНЕНЫ!")
        return
    user = get_user(uid)
    if not user:
        add_user(uid, message.from_user.username, message.from_user.full_name)
    await message.answer(
        "👋 ДОБРО ПОЖАЛОВАТЬ В BBSI!\n\n"
        "⚖️ 80 статей УК | ⭐ Уровни | 🎰 Игры\n"
        "🗺️ /map — карта Тбилиси\n\n"
        "Выберите действие:",
        reply_markup=main_kb()
    )

@dp.message(Command("start"), F.chat.type.in_([ChatType.GROUP, ChatType.SUPERGROUP]))
async def start_group(message: types.Message):
    pass

# ════════════ КОМАНДА /map ════════════
@dp.message(Command("map"))
async def cmd_map(message: types.Message):
    await message.answer(TBILISI_MAP, disable_web_page_preview=False)

@dp.callback_query(F.data == "map")
async def btn_map(callback: types.CallbackQuery):
    await callback.message.answer(TBILISI_MAP, disable_web_page_preview=False)
    await callback.answer("🗺️ Карта отправлена!")

# ════════════ ПРИКОЛЮХИ: /daily, /loot, /duel ════════════
@dp.message(Command("daily"))
async def cmd_daily(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    
    last = user[17]  # last_daily
    if last:
        last_date = datetime.fromisoformat(last)
        if datetime.now() - last_date < timedelta(hours=24):
            await message.reply("⏰ Ежедневный бонус уже получен! Приходи завтра.")
            return
    
    bonus_xp = random.randint(50, 200)
    bonus_coins = random.randint(10, 50)
    update_user(uid, xp=(user[13] or 0) + bonus_xp, coins=(user[16] or 0) + bonus_coins, last_daily=datetime.now().isoformat())
    
    await message.reply(f"🎁 <b>ЕЖЕДНЕВНЫЙ БОНУС!</b>\n\n⭐ XP: +{bonus_xp}\n💰 Монет: +{bonus_coins}")

@dp.message(Command("loot"))
async def cmd_loot(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    
    last = user[18]  # last_loot
    if last:
        last_date = datetime.fromisoformat(last)
        if datetime.now() - last_date < timedelta(hours=24):
            await message.reply("⏰ Лутбокс уже открыт! Следующий через 24 часа.")
            return
    
    loots = [
        ("🔥 Эпический буст XP!", random.randint(100, 500), 0),
        ("💰 Мешок монет!", 0, random.randint(50, 200)),
        ("💎 Джекпот!", random.randint(200, 1000), random.randint(50, 500)),
        ("🍀 Удача!", random.randint(50, 150), random.randint(20, 80)),
        ("👻 Пусто...", 0, 0),
        ("🎯 Точное попадание!", random.randint(150, 300), random.randint(30, 120)),
        ("💀 Проклятие! Минус XP!", -random.randint(50, 100), 0),
    ]
    
    item = random.choice(loots)
    update_user(uid, xp=max(0, (user[13] or 0) + item[1]), coins=max(0, (user[16] or 0) + item[2]), last_loot=datetime.now().isoformat())
    
    await message.reply(f"🎰 <b>ЛУТБОКС!</b>\n\n{item[0]}\n⭐ XP: {'+' if item[1] >= 0 else ''}{item[1]}\n💰 Монет: {'+' if item[2] >= 0 else ''}{item[2]}")

@dp.message(Command("duel"))
async def cmd_duel(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение противника! /duel в ответе")
        return
    
    target = message.reply_to_message.from_user.id
    if target == uid:
        await message.reply("❌ Нельзя драться с собой!")
        return
    
    u1 = user
    u2 = get_user(target)
    if not u2:
        await message.reply("❌ Противник не найден в базе!")
        return
    
    p1 = (u1[13] or 0) + random.randint(1, 100)
    p2 = (u2[13] or 0) + random.randint(1, 100)
    
    winner = uid if p1 > p2 else target
    loser = target if winner == uid else uid
    prize = random.randint(20, 80)
    
    update_user(winner, xp=(get_user(winner)[13] or 0) + prize)
    update_user(loser, xp=max(0, (get_user(loser)[13] or 0) - prize//2))
    
    w_name = message.from_user.full_name if winner == uid else message.reply_to_message.from_user.full_name
    
    await message.answer(
        f"⚔️ <b>ДУЭЛЬ!</b>\n\n"
        f"🗡 {message.from_user.full_name}: {p1} силы\n"
        f"🛡 {message.reply_to_message.from_user.full_name}: {p2} силы\n\n"
        f"👑 Победитель: <b>{w_name}</b> (+{prize} XP)!"
    )

# ════════════ ПРИКОЛЮХИ В ЧАТЕ ════════════
@dp.message(Command("slap"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_slap(message: types.Message):
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение!")
        return
    target = message.reply_to_message.from_user.full_name
    slaps = ["звонкую пощёчину", "мощный подзатыльник", "удар тапком", "хлопок по лицу", "удар подушкой"]
    await message.answer(f"👋 {message.from_user.full_name} дал {random.choice(slaps)} {target}!")

@dp.message(Command("hug"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_hug(message: types.Message):
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение!")
        return
    target = message.reply_to_message.from_user.full_name
    hugs = ["крепко обнял(а)", "заключил(а) в тёплые объятия", "прижал(а) к сердцу"]
    await message.answer(f"🤗 {message.from_user.full_name} {random.choice(hugs)} {target}!")

@dp.message(Command("kiss"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_kiss(message: types.Message):
    if not message.reply_to_message:
        await message.reply("❌ Ответьте на сообщение!")
        return
    target = message.reply_to_message.from_user.full_name
    await message.answer(f"💋 {message.from_user.full_name} поцеловал(а) {target}!")

@dp.message(Command("rage"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_rage(message: types.Message):
    rages = ["🤬 в ярости крушит всё вокруг!", "😡 РРРРРРР! Кровь кипит!", "💢 взрывается от злости!"]
    await message.answer(f"{message.from_user.full_name} {random.choice(rages)}")

@dp.message(Command("facepalm"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_facepalm(message: types.Message):
    await message.answer(f"🤦 {message.from_user.full_name} делает фейспалм...")

@dp.message(Command("coin"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_coin(message: types.Message):
    result = random.choice(["Орёл 🦅", "Решка 💰"])
    await message.answer(f"🪙 {message.from_user.full_name} подбрасывает монету...\n\n<b>{result}!</b>")

@dp.message(Command("slot"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_slot(message: types.Message):
    emojis = ["🍒", "🍋", "🔔", "💎", "7️⃣", "🍀"]
    s = [random.choice(emojis) for _ in range(3)]
    win = s[0] == s[1] == s[2]
    await message.answer(f"🎰 <b>СЛОТ-МАШИНА</b>\n\n[{s[0]}] [{s[1]}] [{s[2]}]\n\n{'🎉 ДЖЕКПОТ!!!' if win else '😔 Мимо...'}")

@dp.message(Command("guess"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_guess(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        await message.reply("❌ /guess число (от 1 до 10)")
        return
    try:
        num = int(parts[1])
    except:
        await message.reply("❌ Введите число!")
        return
    answer = random.randint(1, 10)
    if num == answer:
        uid = message.from_user.id
        user = get_user(uid)
        update_user(uid, xp=(user[13] or 0) + 50, coins=(user[16] or 0) + 25)
        await message.reply(f"🎉 УГАДАЛ! +50 XP +25 монет\nЧисло: {answer}")
    else:
        await message.reply(f"😔 Мимо... Число было: {answer}")

# ════════════ ЗАЩИТА: ПЕРЕСЫЛКА ════════════
@dp.message(F.forward_from | F.forward_from_chat)
async def detect_forward(message: types.Message):
    uid = message.from_user.id
    w = add_violation(uid, "forward", "17.8", message.chat.id)
    try: await message.delete()
    except: pass
    warn = await message.answer(f"🚫 @{message.from_user.username} — ПЕРЕСЫЛКА! | Ст.17.8 | {w}/3")
    await bot.send_message(ADMIN_GROUP, f"🚨 ПЕРЕСЫЛКА!\n👤 @{message.from_user.username} (ID:{uid})\n⚠️ {w}/3", reply_markup=violation_buttons(uid, "forward"))
    await asyncio.sleep(10)
    try: await warn.delete()
    except: pass

# ════════════ ЗАЩИТА: СКРИНШОТЫ ════════════
@dp.message(F.photo, F.chat.id.in_([GROUP_MAIN, GROUP_RULES]))
async def detect_screenshot(message: types.Message):
    uid = message.from_user.id
    caption = (message.caption or "").lower()
    suspicious = ["скрин", "screenshot", "screen", "снимок", "переписка", "чат"]
    if not caption or any(s in caption for s in suspicious):
        w = add_violation(uid, "screenshot", "12.3", message.chat.id)
        await bot.send_message(ADMIN_GROUP, f"📸 СКРИНШОТ!\n👤 @{message.from_user.username}\n⚠️ {w}/3", reply_markup=violation_buttons(uid, "screenshot"))

# ════════════ СИСТЕМА УРОВНЕЙ ════════════
@dp.message(F.chat.id.in_([GROUP_MAIN]), F.text)
async def xp_text(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    xp_gain = 5 if len(message.text) < 20 else 10 if len(message.text) < 50 else 15
    new_xp = (user[13] or 0) + xp_gain
    new_msgs = (user[12] or 0) + 1
    new_level = int((new_xp / 100) ** 0.5) + 1
    update_user(uid, xp=new_xp, messages_count=new_msgs, level=new_level, coins=(user[16] or 0) + 1)
    if new_level > (user[12] or 1):
        await message.reply(f"⬆️ @{message.from_user.username} → {new_level} уровень!")

@dp.message(F.chat.id.in_([GROUP_MAIN]), F.photo | F.video | F.document)
async def xp_media(message: types.Message):
    uid = message.from_user.id
    user = get_user(uid)
    if not user: return
    new_xp = (user[13] or 0) + 15
    new_level = int((new_xp / 100) ** 0.5) + 1
    update_user(uid, xp=new_xp, messages_count=(user[12] or 0) + 1, level=new_level, coins=(user[16] or 0) + 3)
    if new_level > (user[12] or 1):
        await message.reply(f"⬆️ @{message.from_user.username} → {new_level} уровень!")

# ════════════ КОМАНДЫ В ЧАТЕ ════════════
@dp.message(Command("top"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_top(message: types.Message):
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, level, xp FROM users WHERE status='approved' ORDER BY level DESC, xp DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    txt = "🏆 <b>ТОП-10</b>\n\n"
    for i, r in enumerate(rows):
        txt += f"{medals[i]} {r[1]} — Ур.{r[2]} | XP:{r[3]}\n"
    await message.answer(txt)

@dp.message(Command("me"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_me(message: types.Message):
    uid = message.from_user.id
    await show_profile(message, uid)

async def show_profile(message, uid):
    user = get_user(uid)
    if not user: return
    lvl = user[12] or 1
    xp = user[13] or 0
    msgs = user[11] or 0
    coins = user[16] or 0
    warns = user[9] or 0
    xp_next = (lvl * lvl) * 100
    achievements = user[19] or ""
    
    # Достижения
    if msgs >= 100 and "🗣" not in achievements:
        achievements += "🗣"
        update_user(uid, achievement=achievements)
        await bot.send_message(uid, "🏆 ДОСТИЖЕНИЕ: Болтун (100 сообщений)!")
    if msgs >= 500 and "💀" not in achievements:
        achievements += "💀"
        update_user(uid, achievement=achievements)
        await bot.send_message(uid, "🏆 ДОСТИЖЕНИЕ: Машина (500 сообщений)!")
    if lvl >= 10 and "👑" not in achievements:
        achievements += "👑"
        update_user(uid, achievement=achievements)
        await bot.send_message(uid, "🏆 ДОСТИЖЕНИЕ: Легенда (10 уровень)!")
    
    ach_text = " ".join(achievements) if achievements else "Нет"
    
    await message.answer(
        f"📊 <b>ПРОФИЛЬ</b>\n\n"
        f"👤 {user[2]}\n"
        f"⭐ Уровень: {lvl} | XP: {xp}/{xp_next}\n"
        f"💬 Сообщений: {msgs}\n"
        f"💰 Монет: {coins}\n"
        f"⚠️ Предупр: {warns}/3\n"
        f"🏆 Достижения: {ach_text}\n"
        f"🌍 {user[5]}, {user[6]}"
    )

@dp.message(Command("info"), F.chat.id.in_([GROUP_MAIN]))
async def cmd_info(message: types.Message):
    if message.reply_to_message:
        await show_profile(message, message.reply_to_message.from_user.id)
    else:
        await message.reply("❌ Ответьте на сообщение пользователя!")

# ════════════ АДМИН-ПАНЕЛЬ ════════════
@dp.callback_query(F.data == "apanel")
async def admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    await callback.message.edit_text("👑 АДМИН-ПАНЕЛЬ", reply_markup=admin_panel_kb())
    await callback.answer()

@dp.callback_query(F.data == "back_main")
async def back_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 Главное меню:", reply_markup=main_kb())
    await callback.answer()

@dp.callback_query(F.data == "apanel_requests")
async def panel_requests(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT user_id, full_name, country, city FROM users WHERE status IN ('pending', 'on_hold') LIMIT 15")
    rows = c.fetchall()
    conn.close()
    if not rows: await callback.message.edit_text("📥 Нет заявок.", reply_markup=back_kb())
    else:
        txt = f"📥 ЗАЯВКИ ({len(rows)}):\n\n"
        kb = [[InlineKeyboardButton(text=f"📋 {r[1]}", callback_data=f"info_{r[0]}")] for r in rows]
        kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="apanel")])
        await callback.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
    await callback.answer()

@dp.callback_query(F.data == "apanel_stats")
async def panel_stats(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END), SUM(CASE WHEN status='approved' THEN 1 ELSE 0 END), SUM(CASE WHEN banned=1 THEN 1 ELSE 0 END), SUM(messages_count) FROM users")
    r = c.fetchone()
    conn.close()
    txt = f"📊 СТАТИСТИКА\n\n👥 Всего: {r[0]}\n📥 Заявок: {r[1]}\n✅ В чате: {r[2]}\n🔨 Забанено: {r[3]}\n💬 Сообщений: {r[4] or 0}"
    await callback.message.edit_text(txt, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "apanel_top")
async def panel_top(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    conn = sqlite3.connect('empire.db')
    c = conn.cursor()
    c.execute("SELECT full_name, level, xp, messages_count, coins FROM users WHERE status='approved' ORDER BY level DESC, xp DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    medals = ["🥇", "🥈", "🥉"] + [f"{i}." for i in range(4, 11)]
    txt = "🏆 ТОП-10\n\n"
    for i, r in enumerate(rows):
        txt += f"{medals[i]} {r[0]} — Ур.{r[1]} | XP:{r[2]} | 💬{r[3]} | 💰{r[4]}\n"
    await callback.message.edit_text(txt, reply_markup=back_kb())
    await callback.answer()

@dp.callback_query(F.data == "myprofile")
async def my_profile(callback: types.CallbackQuery):
    await show_profile(callback.message, callback.from_user.id)
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
    await callback.message.edit_text("📝 Шаг 1/6 — Введите ПОЛНОЕ ФИО:")
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
    await message.answer("✅ Шаг 6/6 — Пол:", reply_markup=gender_kb())
    await state.set_state(Reg.gender)

@dp.message(Reg.gender)
async def s_gender(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    d = await state.get_data()
    update_user(uid, full_name=d['fio'], birth_date=d['birth'], phone=d['phone'],
                country=d['country'], city=d['city'], gender=message.text.strip(), status="pending")
    txt = f"📥 ЗАЯВКА #{uid}\n\n👤 {d['fio']}\n🎂 {d['birth']}\n📞 {d['phone']}\n🌍 {d['country']}, {d['city']}\n⚧ {message.text.strip()}"
    await bot.send_message(GROUP_REQUESTS, txt, reply_markup=request_buttons(uid))
    await bot.send_message(ADMIN_GROUP, f"📥 Заявка #{uid}", reply_markup=request_buttons(uid))
    await message.answer("✅ ЗАЯВКА ОТПРАВЛЕНА!", reply_markup=rules_kb())
    await state.clear()

# ════════════ КНОПКИ ЗАЯВОК ════════════
@dp.callback_query(F.data.startswith("acc_"))
async def btn_accept(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    link = await bot.create_chat_invite_link(GROUP_RULES, member_limit=1)
    await bot.send_message(uid, f"✅ ПРИНЯТ В ПРАВИЛА\n{link.invite_link}", reply_markup=rules_kb())
    update_user(uid, status="rules")
    await callback.message.edit_text(callback.message.text + "\n\n✅ ПРИНЯТ")
    await callback.answer()

@dp.callback_query(F.data.startswith("direct_"))
async def btn_direct(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    link = await bot.create_chat_invite_link(GROUP_MAIN, member_limit=1)
    await bot.send_message(uid, f"🎉 ВЫ В BBSI ЧАТ!\n{link.invite_link}")
    update_user(uid, status="approved")
    await callback.message.edit_text(callback.message.text + "\n\n⭐ В ЧАТЕ")
    await callback.answer()

@dp.callback_query(F.data.startswith("hold_"))
async def btn_hold(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    update_user(uid, status="on_hold")
    await callback.message.edit_text(callback.message.text + "\n\n⏳ ОТЛОЖЕНО")
    await callback.answer()

@dp.callback_query(F.data.startswith("rej_"))
async def btn_reject(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    update_user(uid, status="rejected")
    await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКЛОНЁН")
    await callback.answer()

@dp.callback_query(F.data.startswith("info_"))
async def btn_info(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    user = get_user(uid)
    if user:
        txt = f"📋 #{uid}\n👤 {user[2]}\n🎂 {user[3]}\n📞 {user[4]}\n🌍 {user[5]}, {user[6]}\n⚧ {user[7]}\n⚠️ {user[9]}"
        await callback.message.answer(txt)
    await callback.answer()

# ════════════ ПРАВИЛА ════════════
@dp.callback_query(F.data == "rules")
async def show_rules(callback: types.CallbackQuery):
    await callback.message.edit_text("📜 УК BBSI — 80 статей\n\n12.3 Скриншот → бан\n17.8 Пересылка → $5000\n23.1 Запись → вечный бан", reply_markup=rules_kb())
    await callback.answer()

@dp.callback_query(F.data == "accept_rules")
async def accept_rules(callback: types.CallbackQuery):
    uid = callback.from_user.id
    update_user(uid, rules_accepted=1)
    await callback.message.edit_text("✅ 80 СТАТЕЙ ПРИНЯТЫ!")
    await bot.send_message(ADMIN_GROUP, f"✅ @{callback.from_user.username} принял УК!", reply_markup=admin_approve_buttons(uid))
    await callback.answer()

@dp.callback_query(F.data.startswith("appr_"))
async def btn_approve(callback: types.CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS: return await callback.answer("⛔")
    uid = int(callback.data.split("_")[1])
    link = await bot.create_chat_invite_link(GROUP_MAIN, member_limit=1)
    await bot.send_message(uid, f"🎉 ВЫ В BBSI ЧАТ!\n{link.invite_link}")
    update_user(uid, status="approved")
    await callback.message.edit_text(callback.message.text + "\n\n✅ В ЧАТЕ")
    await callback.answer()

@dp.callback_query(F.data.startswith("wait_"))
async def btn_wait(callback: types.CallbackQuery):
    await callback.message.edit_text(callback.message.text + "\n\n⏳ ОЖИДАЕТ")
    await callback.answer()

@dp.callback_query(F.data.startswith("deny_"))
async def btn_deny(callback: types.CallbackQuery):
    uid = int(callback.data.split("_")[1])
    update_user(uid, status="denied")
    await callback.message.edit_text(callback.message.text + "\n\n❌ ОТКАЗАНО")
    await callback.answer()

# ════════════ ЗАПУСК ════════════
async def main():
    init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
