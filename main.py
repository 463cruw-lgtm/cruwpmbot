import os
import asyncio
import sqlite3

import bot_status
from flask import Flask
from threading import Thread

from aiogram import Bot, Dispatcher, F, BaseMiddleware
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    BotCommandScopeAllPrivateChats,
    MenuButtonCommands
)

from config import (
    TOKEN,
    ADMIN_ID,
    CARD_NUMBER,
    CARD_OWNER
)

from database import (
    db,
    sql
)

from balance import (
    register_balance,
    check_payments_loop,
    expire_payments_loop
)

from subscription import (
    check_subscription,
    subscription_check_message,
    subscription_keyboard
)

from ban_middleware import BanMiddleware
from otzif import send_otzif

# --- RENDER UCHUN FLASK WEB-SERVER QISMI ---
app = Flask('')

@app.route('/')
def home():
    return "Bot muvaffaqiyatli ishlamoqda!"

def run():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -------------------------------------------

# Bot va Dispatcher obyektlarini yaratish
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher()

# Kerakli middleware'larni ulash (Agar mavjud bo'lsa)
# dp.message.middleware(BanMiddleware())


async def main():
    # 1. Render uxlab qolmasligi uchun Flask veb-serverini alohida oqimda ishga tushiramiz
    keep_alive()
    print("Veb-server (Flask) ishga tushdi!")
    
    # 2. Boshqa fon sikllarini ishga tushirish (masalan, to'lovlarni tekshirish)
    asyncio.create_task(check_payments_loop(bot))
    asyncio.create_task(expire_payments_loop(bot))

    # 3. Botni ishga tushirish
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi!")
# =========================
# UC STATES 
# ========================= 

class AddUCCode(StatesGroup):
    name = State()
    count = State()
    codes = State()


class EditUC(StatesGroup):
    product_id = State()
    name = State()
    price = State()


# =========================
# UC XARID STATE
# =========================

class BuyUC(StatesGroup):
    amount = State()


# =========================
# BOT
# =========================

bot = Bot(
    TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)


# =========================
# DISPATCHER
# =========================

dp = Dispatcher()



# =========================
# GURUH CHATDAGI TUGMALARNI OLIB TASHLASH
# =========================

@dp.message(Command("remove_keyboard"))
async def remove_keyboard(message: Message):

    # Faqat admin ishlata oladi
    if message.from_user.id != ADMIN_ID:
        return

    # Faqat guruh/superguruhda ishlaydi
    if message.chat.type not in ("group", "supergroup"):
        return

    await message.answer(
        "🔕 Bot tugmalari olib tashlandi.",
        reply_markup=ReplyKeyboardRemove()
    )


# =========================
# BOT PAUZA MIDDLEWARE
# =========================

class PauseMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler,
        event,
        data
    ):

        user = event.from_user

        # User bo'lmasa
        if not user:
            return await handler(event, data)

        # =========================
        # GURUHDA BOT UMUMAN JAVOB BERMAYDI
        # =========================

        if isinstance(event, Message):

            if event.chat.type in ("group", "supergroup"):

                # Faqat admin /remove_keyboard ishlata oladi
                if (
                    event.text == "/remove_keyboard"
                    and user.id == ADMIN_ID
                ):
                    return await handler(event, data)

                # Guruhdagi barcha boshqa xabarlarni bloklash
                return

        # =========================
        # BOT PAUZA HOLATI
        # =========================

        if user.id != ADMIN_ID:

            if bot_status.BOT_PAUSED:

                if isinstance(event, Message):

                    await event.answer(
                        "⛔ <b>BOT VAQTINCHA TO'XTATILGAN</b>\n\n"
                        "⚠️ Hozircha botdan foydalanib bo'lmaydi.\n"
                        "🔄 Keyinroq qaytadan urinib ko'ring.",
                        parse_mode="HTML"
                    )

                elif isinstance(event, CallbackQuery):

                    await event.answer(
                        "⛔ Bot vaqtincha to'xtatilgan!",
                        show_alert=True
                    )

                return

        # =========================
        # HANDLERGA O'TKAZISH
        # =========================

        return await handler(event, data)


# =========================
# USERNAME AVTOMATIK YANGILASH
# =========================

class UsernameMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler,
        event,
        data
    ):

        user = event.from_user

        # User bo'lmasa
        if not user:
            return await handler(event, data)

        try:

            current_username = (
                user.username or "NoUsername"
            )

            # =========================
            # USER BAZADA BORMI?
            # =========================

            sql.execute(
                """
                SELECT username
                FROM users
                WHERE id=?
                """,
                (user.id,)
            )

            user_row = sql.fetchone()

            # =========================
            # USER BAZADA BOR
            # =========================

            if user_row:

                old_username = user_row[0]

                # Username o'zgargan bo'lsa
                if old_username != current_username:

                    sql.execute(
                        """
                        UPDATE users
                        SET username=?
                        WHERE id=?
                        """,
                        (
                            current_username,
                            user.id
                        )
                    )

                    db.commit()

            # =========================
            # USER BAZADA YO'Q
            # =========================

            else:

                sql.execute(
                    """
                    INSERT INTO users(
                        id,
                        username,
                        balance,
                        total,
                        orders,
                        ban
                    )
                    VALUES(?,?,?,?,?,?)
                    """,
                    (
                        user.id,
                        current_username,
                        0,
                        0,
                        0,
                        0
                    )
                )

                db.commit()

        except Exception as e:

            print(
                f"❌ UsernameMiddleware xatosi: {e}"
            )

        # =========================
        # HANDLERGA O'TKAZISH
        # =========================

        return await handler(event, data)

                           
# =========================
# MIDDLEWARELARNI YOQISH
# =========================

dp.message.middleware(
    PauseMiddleware()
)

dp.callback_query.middleware(
    PauseMiddleware()
)

dp.message.middleware(
    BanMiddleware()
)

dp.callback_query.middleware(
    BanMiddleware()
)

dp.message.middleware(
    UsernameMiddleware()
)

dp.callback_query.middleware(
    UsernameMiddleware()
)

register_balance(dp)

# =========================
# DATABASE
# =========================

from database import db, sql


# =========================
# USERS
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    total INTEGER DEFAULT 0,
    orders INTEGER DEFAULT 0,
    ban INTEGER DEFAULT 0
)
""")

try:

    sql.execute(
        "ALTER TABLE users ADD COLUMN ban INTEGER DEFAULT 0"
    )

    db.commit()

except Exception:
    pass




# =========================
# ADMIN STATE
# =========================

class AdminState(StatesGroup):
    bot_paused = State()

    # PM
    edit_pm_id = State()
    edit_pm_data = State()

    # UC
    edit_uc_id = State()
    edit_uc_data = State()

    # BAN / UNBAN
    ban = State()
    unban = State()

    # BALANCE +
    balance_add = State()
    balance_add_amount = State()

    # BALANCE -
    balance_minus = State()
    balance_minus_amount = State()

    # USER INFO
    user_info = State()

    # BROADCAST / XABAR YUBORISH
    broadcast = State()

# =========================
# 📢 ADMIN XABAR YUBORISH
# =========================

@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.broadcast)

    await message.answer(
        "📢 <b>XABAR YUBORISH</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan "
        "xabaringizni yuboring.\n\n"
        "📝 Matn, rasm, video yoki fayl yuborishingiz mumkin.\n\n"
        "❌ Bekor qilish: 🔙 Orqaga",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.broadcast)
async def broadcast_send(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    # Barcha foydalanuvchilarni olish
    sql.execute("SELECT id FROM users")
    users = sql.fetchall()

    if not users:
        await state.clear()

        await message.answer(
            "❌ Foydalanuvchilar topilmadi.",
            reply_markup=admin_menu
        )
        return

    sent = 0
    failed = 0

    await message.answer(
        f"📤 Xabar yuborilmoqda...\n\n"
        f"👥 Jami: {len(users)} ta"
    )

    for user in users:
        user_id = user[0]

        try:
            await message.copy_to(chat_id=user_id)
            sent += 1

            await asyncio.sleep(0.05)

        except Exception as e:
            failed += 1
            print(f"❌ {user_id}: {e}")

    await state.clear()

    await message.answer(
        f"✅ <b>XABAR YUBORISH YAKUNLANDI</b>\n\n"
        f"📤 Yuborildi: {sent} ta\n"
        f"❌ Yuborilmadi: {failed} ta\n"
        f"👥 Jami: {len(users)} ta",
        parse_mode="HTML",
        reply_markup=admin_menu
    )
# PRODUCTS
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price INTEGER NOT NULL,
    stock INTEGER DEFAULT 0
)
""")

# =========================
# PUBG UC PRODUCTS
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS uc_products(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price INTEGER NOT NULL,
    stock INTEGER DEFAULT 0
)
""")

# =========================
# PUBG UC CODES
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS uc_codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    code TEXT,
    used INTEGER DEFAULT 0
)
""")

db.commit()
# =========================
# UC_CODES UNIQUE NI OLIB TASHLASH
# =========================

try:
    sql.execute("""
        CREATE TABLE IF NOT EXISTS uc_codes_new(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            code TEXT,
            used INTEGER DEFAULT 0
        )
    """)

    sql.execute("""
        INSERT INTO uc_codes_new(id, product_name, code, used)
        SELECT id, product_name, code, used
        FROM uc_codes
    """)

    sql.execute("DROP TABLE uc_codes")

    sql.execute("""
        ALTER TABLE uc_codes_new
        RENAME TO uc_codes
    """)

    db.commit()

except Exception as e:
    print("UC_CODES jadval xatosi:", e)
    db.rollback()
# =========================
# STANDART 5 TA UC
# =========================

sql.execute("SELECT COUNT(*) FROM uc_products")

if sql.fetchone()[0] == 0:
    sql.executemany(
        """
        INSERT INTO uc_products(name, price, stock)
        VALUES(?,?,?)
        """,
        [
            ("60 UC", 0, 0),
            ("120 UC", 0, 0),
            ("325 UC", 0, 0),
            ("660 UC", 0, 0),
            ("1800 UC", 0, 0)
        ]
    )
    db.commit()


# =========================
# PM CODES
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS pm_codes(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_name TEXT,
    code TEXT,
    used INTEGER DEFAULT 0
)
""")


# =========================
# ORDERS
# =========================

sql.execute("""
CREATE TABLE IF NOT EXISTS orders(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    product_name TEXT,
    count INTEGER,
    price INTEGER,
    status TEXT
)
""")

db.commit()
# =========================
# STANDART PM
# =========================

sql.execute("SELECT COUNT(*) FROM products")

if sql.fetchone()[0] == 0:
    sql.executemany(
        """
        INSERT INTO products(name, price, stock)
        VALUES(?,?,?)
        """,
        [
            ("42 PM", 3000, 0),
            ("79 PM", 5000, 0),
            ("99 PM", 8000, 0),
            ("299 PM", 23000, 0)
        ]
    )
    db.commit()


# =========================
# STATES
# =========================

class BuyPM(StatesGroup):
    amount = State()


class AddPMCode(StatesGroup):
    name = State()
    count = State()
    codes = State()
    # =========================
# ADD UC CODE STATE
# =========================

class AddUCCode(StatesGroup):
    name = State()
    count = State()
    codes = State()
    # =========================
# ASOSIY MENU
# =========================

menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🛒 BULL PM XARID"),
            KeyboardButton(text="🎮 PUBG UC XARID")
        ],
        [
            KeyboardButton(text="💰 Balansni to'ldirish")
        ],
        [
            KeyboardButton(text="👤 Profil"),
            KeyboardButton(text="📞 Qo'llab-quvvatlash")
        ]
    ],
    resize_keyboard=True
)


# =========================
# ORQAGA MENU
# =========================

back_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔙 Orqaga")
        ]
    ],
    resize_keyboard=True
)


# =========================
# ADMIN MENU
# =========================

admin_menu = ReplyKeyboardMarkup(
    keyboard=[

        [
            KeyboardButton(text="➕ PM qo'shish"),
            KeyboardButton(text="📦 PM qoldiq"),
            KeyboardButton(text="✏️ PM nomi/narxini o'zgartirish")
        ],

        [
            KeyboardButton(text="➕ UC qo'shish"),
            KeyboardButton(text="📦 UC qoldiq"),
            KeyboardButton(text="✏️ UC nomi/narxini o'zgartirish")
        ],

        [
            KeyboardButton(text="🔑 Kodlar soni"),
            KeyboardButton(text="👥 Statistika")
        ],

        [
            KeyboardButton(text="📢 Xabar yuborish")
        ],

        [
            KeyboardButton(text="📢 Obuna kanallari")
        ],

        [
            KeyboardButton(text="💰 Balans +"),
            KeyboardButton(text="💸 Balans -")
        ],

        [
            KeyboardButton(text="👤 User ma'lumot"),
            KeyboardButton(text="🚫 Ban")
        ],

        [
            KeyboardButton(text="✅ Unban")
        ],

        [
            KeyboardButton(text="⛔ Botni to'xtatish"),
            KeyboardButton(text="▶️ Botni ishga tushirish")
        ],

        [
            KeyboardButton(text="🏠 Bosh menyu")
        ]

    ],
    resize_keyboard=True
)


async def check_bot_pause(message: Message) -> bool:
    if message.from_user.id == ADMIN_ID:
        return False

    import bot_status

    if bot_status.BOT_PAUSED:
        await message.answer(
            "⛔ <b>BOT VAQTINCHA TO'XTATILGAN</b>\n\n"
            "Iltimos, keyinroq qayta urinib ko'ring."
        )
        return True

    return False
# =========================
# START
# =========================

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(call: CallbackQuery):
    if await check_subscription(bot, call.from_user.id):
        await call.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "Botdan foydalanishingiz mumkin."
        )
        await call.message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )
        await call.answer("✅ Obuna tasdiqlandi!")
    else:
        await call.answer(
            "❌ Siz hali barcha majburiy chat va kanallarga a'zo bo'lmagansiz!",
            show_alert=True
        )

@dp.message(Command("start"), F.chat.type == "private")
async def start_handler(message: Message):
    ...

    if await check_bot_pause(message):
        return

    # MAJBURIY CHAT A'ZOLIGI
    if not await subscription_check_message(message, bot):
        return

    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"

    sql.execute(
        "SELECT id FROM users WHERE id=?",
        (user_id,)
    )

    user = sql.fetchone()

    if user is None:
        sql.execute(
            """
            INSERT INTO users(
                id,
                username,
                balance,
                total,
                orders
            )
            VALUES(?,?,?,?,?)
            """,
            (
                user_id,
                username,
                0,
                0,
                0
            )
        )
    else:
        sql.execute(
            """
            UPDATE users
            SET username=?
            WHERE id=?
            """,
            (
                username,
                user_id
            )
        )

    db.commit()

    await message.answer(
        """
👋 Assalomu alaykum!

🎮 BULL PM BOT ga xush kelibsiz.

Quyidagi menyudan kerakli bo'limni tanlang.
""",
        reply_markup=menu
    )
    
# =========================
# PROFIL
# =========================

@dp.message(F.text == "👤 Profil")
async def profile(message: Message):

    # Faqat private chat
    if message.chat.type != "private":
        return

    # Majburiy obuna
    if not await subscription_check_message(message, bot):
        return

    user_id = message.from_user.id
    username = message.from_user.username or "NoUsername"

    # Foydalanuvchi bazada bormi?
    sql.execute(
        """
        SELECT balance, total, orders
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    user = sql.fetchone()

    # Agar /start bosmagan bo'lsa, avtomatik yaratamiz
    if user is None:
        sql.execute(
            """
            INSERT INTO users(
                id,
                username,
                balance,
                total,
                orders,
                ban
            )
            VALUES(?,?,?,?,?,?)
            """,
            (
                user_id,
                username,
                0,
                0,
                0,
                0
            )
        )

        db.commit()

        # Qaytadan olamiz
        sql.execute(
            """
            SELECT balance, total, orders
            FROM users
            WHERE id=?
            """,
            (user_id,)
        )

        user = sql.fetchone()

    # Username
    username_text = (
        f"@{message.from_user.username}"
        if message.from_user.username
        else "Username mavjud emas"
    )

    await message.answer(
        f"""
👤 <b>SIZNING PROFILINGIZ</b>

🆔 ID:
<code>{user_id}</code>

🌐 Username:
{username_text}

💰 Balans:
<b>{user[0]:,} so'm</b>

💳 Jami to'ldirilgan:
<b>{user[1]:,} so'm</b>

📦 Xaridlar:
<b>{user[2]} ta</b>
""",
        parse_mode="HTML"
    )

    # =========================
# ADMIN PANEL
# =========================

@dp.message(Command("admin"))
async def admin_panel(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "👑 Admin panelga xush kelibsiz.",
        reply_markup=admin_menu
    )
    # =========================
# BULL PM XARID
# =========================

@dp.message(F.text == "🛒 BULL PM XARID")
async def bull_pm(message: Message):

    if not await subscription_check_message(message, bot):
        return

    text = """❗ <b>Muhim xarid qoidasi!</b>

📹 Xarid qilish tugmasini bosishdan oldin uzluksiz ekran videosini (Screen Record) yoqing!

Videoda botdan kod olinishi, nusxalanib (Copy) darhol Bulldrop saytiga qo'yilishi (Paste) va faollashtirilishi kesilmasdan ko'rinishi shart.

⚠️ Aks holda "ishlamadi" yoki "ishlatilgan" degan e'tirozlar ko'rib chiqilmaydi va pul qaytarilmaydi.

👇 Qoidaga rozilik bildirsangiz, quyidagi tugmani bosing:"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ROZIMAN",
                    callback_data="bull_pm_rules_accept"
                )
            ]
        ]
    )

    await message.answer(
        text,
        reply_markup=keyboard
    )

@dp.callback_query(F.data == "bull_pm_rules_accept")
async def bull_pm_rules_accept(call: CallbackQuery):

    await call.answer()

    sql.execute("""
        SELECT
            p.id,
            p.name,
            p.price,
            (
                SELECT COUNT(*)
                FROM pm_codes pc
                WHERE pc.product_name = p.name
                AND pc.used = 0
            ) AS stock
        FROM products p
        ORDER BY p.id
    """)

    products = sql.fetchall()

    if not products:
        await call.message.answer("❌ Hozircha PM mavjud emas.")
        return

    keyboard = []

    for product in products:
        keyboard.append([
            InlineKeyboardButton(
                text=f"💎 {product[1]} | {product[2]:,} so'm | {product[3]} ta",
                callback_data=f"buy:{product[0]}"
            )
        ])

    await call.message.answer(
        "💎 <b>PM XARID</b>\n\nXarid qilmoqchi bo'lgan PM paketini tanlang:",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )

# =========================
# PM TANLASH
# =========================

@dp.callback_query(F.data.startswith("buy:"))
async def buy_pm(call: CallbackQuery, state: FSMContext):

    product_id = int(call.data.split(":")[1])

    sql.execute(
        """
        SELECT id, name, price
        FROM products
        WHERE id=?
        """,
        (product_id,)
    )

    product = sql.fetchone()

    if product is None:
        await call.answer(
            "❌ Mahsulot topilmadi.",
            show_alert=True
        )
        return

    # HAQIQIY QOLDIQNI pm_codes DAN OLAMIZ
    sql.execute(
        """
        SELECT COUNT(*)
        FROM pm_codes
        WHERE product_name=?
        AND used=0
        """,
        (product[1],)
    )

    real_stock = sql.fetchone()[0]

    if real_stock <= 0:
        await call.answer(
            "❌ Ushbu PM tugagan.",
            show_alert=True
        )
        return

    await state.update_data(
        product_id=product[0],
        pm_name=product[1],
        price=product[2]
    )

    await state.set_state(BuyPM.amount)

    await call.message.answer(
        f"""
💎 PM: {product[1]}

💰 Narxi: {product[2]:,} so'm

📦 Omborda: {real_stock} ta

✍️ Nechta olmoqchisiz?

(1 - 10)
""",
        reply_markup=back_menu
    )

    await call.answer()
    # =========================
# PM SONINI QABUL QILISH
# =========================

@dp.message(BuyPM.amount)
async def pm_count(message: Message, state: FSMContext):

    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting.")
        return

    count = int(message.text)

    if count < 1 or count > 10:
        await message.answer("❌ 1 dan 10 gacha kiriting.")
        return

    data = await state.get_data()

    product_id = data["product_id"]
    pm_name = data["pm_name"]
    price = data["price"]

    total = price * count

    # =========================
    # HAQIQIY PM KODLAR QOLDIG'INI TEKSHIRISH
    # =========================

    sql.execute(
        """
        SELECT COUNT(*)
        FROM pm_codes
        WHERE product_name=?
        AND used=0
        """,
        (pm_name,)
    )

    available_codes = sql.fetchone()[0]

    if available_codes < count:
        await message.answer(
            f"❌ Faqat {available_codes} ta {pm_name} kodi mavjud.\n"
            f"📦 Maksimal {available_codes} ta olishingiz mumkin."
        )
        return

    # Balansni tekshirish
    sql.execute(
        "SELECT balance FROM users WHERE id=?",
        (message.from_user.id,)
    )

    balance = sql.fetchone()[0]

    if balance < total:
        await message.answer(
            f"""❌ Balans yetarli emas!

💰 Kerak: {total:,} so'm
💳 Balans: {balance:,} so'm"""
        )
        await state.clear()
        return

    await state.update_data(
        count=count,
        total=total
    )

    await message.answer(
        f"""✅ Tasdiqlandi

💎 PM: {pm_name}
📦 Soni: {count} ta
💰 Jami: {total:,} so'm

⏳ Xarid amalga oshirilmoqda..."""
    )
        # =========================
    # BALANSDAN PUL YECHISH
    # =========================

    sql.execute(
        """
        UPDATE users
        SET balance = balance - ?,
            orders = orders + 1
        WHERE id=?
        """,
        (
            total,
            message.from_user.id
        )
    )


    # =========================
    # PM KODLARNI OLISH
    # =========================

    sql.execute(
        """
        SELECT id, code
        FROM pm_codes
        WHERE product_name=?
        AND used=0
        LIMIT ?
        """,
        (
            pm_name,
            count
        )
    )

    codes = sql.fetchall()

    if len(codes) < count:
        db.rollback()
        await message.answer("❌ Yetarli PM kod mavjud emas.")
        await state.clear()
        return

    text = "🔑 Sizning PM kodlaringiz:\n\n"

    for i, code in enumerate(codes, start=1):
        text += f"{i}) `{code[1]}`\n"

        sql.execute(
            """
            UPDATE pm_codes
            SET used=1
            WHERE id=?
            """,
            (code[0],)
        )

    db.commit()

    # =========================
    # BUYURTMANI SAQLASH
    # =========================

    sql.execute(
        """
        INSERT INTO orders(
            user_id,
            product_name,
            count,
            price,
            status
        )
        VALUES(?,?,?,?,?)
        """,
        (
            message.from_user.id,
            pm_name,
            count,
            total,
            "completed"
        )
    )

    db.commit()

    await message.answer(
        text,
        parse_mode="Markdown"
    )

    await message.answer(
        f"""
✅ Xarid muvaffaqiyatli!

💎 PM: {pm_name}
📦 Soni: {count} ta
💰 To'lov: {total:,} so'm

💳 Qolgan balans: {balance - total:,} so'm

🎉 Xaridingiz uchun rahmat!
""",
        reply_markup=menu
    )
        # =========================
    # OTZIF KANALGA YUBORISH
    # =========================

    await send_otzif(
        bot=bot,
        user_id=message.from_user.id,
        username=message.from_user.username,
        product_name=pm_name,
        count=count,
        total=total,
        product_type="PM"
    )

    await state.clear()

    # Keyingi qismda xarid yakunlanadi
    # =========================
# ADMIN - PM QO'SHISH
# =========================

@dp.message(F.text == "➕ PM qo'shish")
async def add_pm_start(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    await state.clear()
    await state.set_state(AddPMCode.name)

    await message.answer(
        """
➕ PM KOD QO'SHISH

Kerakli PM turini yozing.

Misol:
42 PM
79 PM
99 PM
299 PM
""",
        reply_markup=back_menu
    )
    # =========================
# BULL UC XARID
# =========================

@dp.message(F.text == "🎮 PUBG UC XARID")
async def bull_uc(message: Message):

    if not await subscription_check_message(message, bot):
        return

    text = """❗️ <b>Muhim xarid qoidasi!</b>

📹 Xarid qilish tugmasini bosishdan oldin uzluksiz ekran videosini (Screen Record) yoqing!

Videoda botdan redem olinishi, nusxalanib (Copy) darhol Midasby saytiga qo'yilishi (Paste) va faollashtirilishi kesilmasdan ko'rinishi shart.

⚠️ Aks holda "ishlamadi" yoki "ishlatilgan" degan e'tirozlar ko'rib chiqilmaydi va pul qaytarilmaydi.

👇 Qoidaga rozilik bildirsangiz, quyidagi tugmani bosing:"""

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ ROZIMAN",
                    callback_data="bull_uc_rules_accept"
                )
            ]
        ]
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=keyboard
    )


# =========================
# UC QOIDAGA ROZILIK
# =========================

@dp.callback_query(F.data == "bull_uc_rules_accept")
async def bull_uc_rules_accept(
    call: CallbackQuery
):

    await call.answer()

    sql.execute("""
        SELECT
            p.id,
            p.name,
            p.price,
            (
                SELECT COUNT(*)
                FROM uc_codes uc
                WHERE uc.product_name = p.name
                AND uc.used = 0
            ) AS stock
        FROM uc_products p
        ORDER BY p.id
    """)

    products = sql.fetchall()

    if not products:
        await call.message.answer(
            "❌ Hozircha UC mavjud emas."
        )
        return

    keyboard = []

    for product in products:

        keyboard.append([
            InlineKeyboardButton(
                text=f"💎 {product[1]} | {product[2]:,} so'm | {product[3]} ta",
                callback_data=f"buy_uc:{product[0]}"
            )
        ])

    await call.message.answer(
        "💎 <b>UC XARID</b>\n\n"
        "Xarid qilmoqchi bo'lgan UC paketini tanlang:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=keyboard
        )
    )


# =========================
# UC TANLASH
# =========================

@dp.callback_query(F.data.startswith("buy_uc:"))
async def buy_uc(
    call: CallbackQuery,
    state: FSMContext
):

    product_id = int(
        call.data.split(":")[1]
    )

    sql.execute(
        """
        SELECT id, name, price
        FROM uc_products
        WHERE id=?
        """,
        (product_id,)
    )

    product = sql.fetchone()

    if product is None:

        await call.answer(
            "❌ Mahsulot topilmadi.",
            show_alert=True
        )
        return

    # HAQIQIY UC QOLDIQ
    sql.execute(
        """
        SELECT COUNT(*)
        FROM uc_codes
        WHERE product_name=?
        AND used=0
        """,
        (product[1],)
    )

    real_stock = sql.fetchone()[0]

    if real_stock <= 0:

        await call.answer(
            "❌ Ushbu UC tugagan.",
            show_alert=True
        )
        return

    await state.update_data(
        uc_product_id=product[0],
        uc_name=product[1],
        price=product[2]
    )

    await state.set_state(
        BuyUC.amount
    )

    await call.message.answer(
        f"""
💎 UC: {product[1]}

💰 Narxi: {product[2]:,} so'm

📦 Omborda: {real_stock} ta

✍️ Nechta olmoqchisiz?

(1 - 10)
""",
        reply_markup=back_menu
    )

    await call.answer()


# =========================
# UC SONINI QABUL QILISH
# =========================

@dp.message(BuyUC.amount)
async def uc_count(message: Message, state: FSMContext):

    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting.")
        return

    count = int(message.text)

    if count < 1 or count > 10:
        await message.answer("❌ 1 dan 10 gacha kiriting.")
        return

    data = await state.get_data()

    uc_name = data.get("uc_name")
    price = data.get("price")
    product_id = data.get("uc_product_id")

    if not uc_name or price is None or not product_id:
        await message.answer(
            "❌ UC ma'lumotlari topilmadi.\n"
            "Iltimos, xaridni boshidan boshlang."
        )
        await state.clear()
        return

    total = price * count

    # =========================
    # UC QOLDIG'INI TEKSHIRISH
    # =========================

    sql.execute(
        """
        SELECT COUNT(*)
        FROM uc_codes
        WHERE product_name=?
        AND used=0
        """,
        (uc_name,)
    )

    available_codes = sql.fetchone()[0]

    if available_codes < count:
        await message.answer(
            f"❌ Faqat {available_codes} ta "
            f"{uc_name} kodi mavjud.\n\n"
            f"📦 Maksimal {available_codes} ta olishingiz mumkin."
        )
        return

    # =========================
    # BALANS
    # =========================

    sql.execute(
        "SELECT balance FROM users WHERE id=?",
        (message.from_user.id,)
    )

    result = sql.fetchone()

    if result is None:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        await state.clear()
        return

    balance = result[0]

    if balance < total:
        await message.answer(
            f"""❌ Balans yetarli emas!

💰 Kerak: {total:,} so'm
💳 Balans: {balance:,} so'm"""
        )
        await state.clear()
        return

    # =========================
    # UC KODLARNI OLISH
    # =========================

    sql.execute(
        """
        SELECT id, code
        FROM uc_codes
        WHERE product_name=?
        AND used=0
        LIMIT ?
        """,
        (uc_name, count)
    )

    codes = sql.fetchall()

    if len(codes) < count:
        await message.answer(
            "❌ Yetarli UC kod mavjud emas."
        )
        await state.clear()
        return

    # =========================
    # BALANSDAN YECHISH
    # =========================

    sql.execute(
        """
        UPDATE users
        SET balance = balance - ?,
            orders = orders + 1
        WHERE id=?
        """,
        (total, message.from_user.id)
    )

    # =========================
    # KODLARNI ISHLATILGAN QILISH
    # =========================

    text = "🔑 Sizning redem kodlaringiz:\n\n"

    for i, code in enumerate(codes, start=1):

        text += f"{i}) `{code[1]}`\n"

        sql.execute(
            """
            UPDATE uc_codes
            SET used=1
            WHERE id=?
            """,
            (code[0],)
        )

    # =========================
    # UC QOLDIG'INI YANGILASH
    # =========================

    sql.execute(
        """
        SELECT COUNT(*)
        FROM uc_codes
        WHERE product_name=?
        AND used=0
        """,
        (uc_name,)
    )

    new_stock = sql.fetchone()[0]

    sql.execute(
        """
        UPDATE uc_products
        SET stock=?
        WHERE id=?
        """,
        (new_stock, product_id)
    )

    # =========================
    # BUYURTMANI SAQLASH
    # =========================

    sql.execute(
        """
        INSERT INTO orders(
            user_id,
            product_name,
            count,
            price,
            status
        )
        VALUES(?,?,?,?,?)
        """,
        (
            message.from_user.id,
            uc_name,
            count,
            total,
            "completed"
        )
    )

    db.commit()

    # =========================
    # REDEM KODLAR
    # =========================

    await message.answer(
        text,
        parse_mode="Markdown"
    )

       # =========================
    # YAKUNIY XABAR
    # =========================

    await message.answer(
        f"""
✅ Xarid muvaffaqiyatli!

🎮 UC: {uc_name}
📦 Soni: {count} ta
💰 To'lov: {total:,} so'm

💳 Qolgan balans: {balance - total:,} so'm

🎉 Xaridingiz uchun rahmat!
""",
        reply_markup=menu
    )

    # =========================
    # OTZIF KANALGA UC XARID
    # =========================

    await send_otzif(
        bot=bot,
        user_id=message.from_user.id,
        username=message.from_user.username,
        product_name=uc_name,
        count=count,
        total=total,
        product_type="UC"
    )

    await state.clear()
    # =========================
# ADMIN - UC QOLDIQ
# =========================

@dp.message(F.text == "📦 UC qoldiq")
async def uc_stock(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    sql.execute("""
        SELECT id, name, price
        FROM uc_products
        ORDER BY id
    """)

    products = sql.fetchall()

    if not products:
        await message.answer(
            "❌ UC mahsulotlari topilmadi.",
            reply_markup=admin_menu
        )
        return

    text = "📦 <b>UC QOLDIQ</b>\n\n"

    for product_id, name, price in products:

        sql.execute("""
            SELECT COUNT(*)
            FROM uc_codes
            WHERE product_name=?
            AND used=0
        """, (name,))

        stock = sql.fetchone()[0]

        text += (
            f"🆔 ID: <code>{product_id}</code>\n"
            f"💎 UC: <b>{name}</b>\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n"
            f"📦 Qoldiq: <b>{stock} ta</b>\n\n"
        )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu
    )
# =========================
# ADMIN - UC QO'SHISH
# =========================

@dp.message(F.text == "➕ UC qo'shish")
async def add_uc_start(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    await state.clear()

    sql.execute("""
        SELECT id, name, price
        FROM uc_products
        ORDER BY id
    """)

    products = sql.fetchall()

    if not products:
        await message.answer(
            "❌ UC mahsulotlari topilmadi.",
            reply_markup=admin_menu
        )
        return

    text = "➕ <b>PUBG UC KOD QO'SHISH</b>\n\n"

    for product_id, name, price in products:
        text += (
            f"🆔 ID: <code>{product_id}</code>\n"
            f"💎 UC: <b>{name}</b>\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n\n"
        )

    text += (
        "✍️ Kod qo'shmoqchi bo'lgan UC ID sini yuboring.\n\n"
        "Masalan: <code>1</code>"
    )

    await state.set_state(AddUCCode.name)

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=back_menu
    )


# =========================
# UC ID QABUL QILISH
# =========================

@dp.message(AddUCCode.name)
async def add_uc_name(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "❌ UC ID son bo'lishi kerak.\n\n"
            "Masalan: 1"
        )
        return

    product_id = int(message.text)

    sql.execute(
        """
        SELECT id, name, price
        FROM uc_products
        WHERE id=?
        """,
        (product_id,)
    )

    product = sql.fetchone()

    if product is None:
        await message.answer(
            "❌ Bunday UC mahsulot topilmadi."
        )
        return

    await state.update_data(
        uc_product_id=product[0],
        uc_name=product[1]
    )

    await state.set_state(AddUCCode.count)

    await message.answer(
        f"""
✅ <b>UC TANLANDI</b>

💎 Mahsulot:
<b>{product[1]}</b>

💰 Narxi:
<b>{product[2]:,} so'm</b>

📦 Nechta kod qo'shmoqchisiz?

Masalan:
<code>10</code>
""",
        parse_mode="HTML"
    )


# =========================
# UC KOD SONI
# =========================

@dp.message(AddUCCode.count)
async def add_uc_count(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "❌ Faqat son kiriting."
        )
        return

    count = int(message.text)

    if count < 1 or count > 1000:
        await message.answer(
            "❌ 1 dan 1000 gacha kiriting."
        )
        return

    await state.update_data(
        count=count
    )

    await state.set_state(
        AddUCCode.codes
    )

    await message.answer(
        f"""
✅ <b>TAYYOR</b>

💎 UC:
<b>{(await state.get_data())["uc_name"]}</b>

🔢 Kodlar soni:
<b>{count} ta</b>

🔑 Endi <b>{count} ta UC kodni</b> yuboring.

Har bir kodni yangi qatordan yozing.

Masalan:

<code>UC123456</code>
<code>UC789012</code>
<code>UC345678</code>
""",
        parse_mode="HTML"
    )


# =========================
# UC KODLARNI SAQLASH
# =========================

@dp.message(AddUCCode.codes)
async def save_uc_codes(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()

    uc_name = data.get("uc_name")
    count = data.get("count")

    if not uc_name or not count:
        await state.clear()

        await message.answer(
            "❌ Ma'lumot topilmadi.",
            reply_markup=admin_menu
        )
        return

    if not message.text:
        await message.answer(
            "❌ UC kodlarni yuboring."
        )
        return

    codes = [
        code.strip()
        for code in message.text.splitlines()
        if code.strip()
    ]

    if len(codes) != count:
        await message.answer(
            f"❌ {count} ta kod kerak.\n\n"
            f"📥 Siz {len(codes)} ta yubordingiz."
        )
        return

    try:

        for code in codes:

            sql.execute(
                """
                INSERT INTO uc_codes(
                    product_name,
                    code,
                    used
                )
                VALUES(?, ?, 0)
                """,
                (
                    uc_name,
                    code
                )
            )

        # HAQIQIY QOLDIQ
        sql.execute(
            """
            SELECT COUNT(*)
            FROM uc_codes
            WHERE product_name=?
            AND used=0
            """,
            (uc_name,)
        )

        stock = sql.fetchone()[0]

        # PRODUCTS STOCK YANGILASH
        sql.execute(
            """
            UPDATE uc_products
            SET stock=?
            WHERE name=?
            """,
            (
                stock,
                uc_name
            )
        )

        db.commit()

        await state.clear()

        await message.answer(
            f"""
✅ <b>UC KODLAR QO'SHILDI!</b>

💎 Mahsulot:
<b>{uc_name}</b>

🔑 Qo'shilgan:
<b>{count} ta</b>

📦 Hozirgi qoldiq:
<b>{stock} ta</b>
""",
            parse_mode="HTML",
            reply_markup=admin_menu
        )

    except sqlite3.IntegrityError:

        db.rollback()

        await message.answer(
            "❌ Kodlardan biri allaqachon mavjud.\n\n"
            "Kodlar qo'shilmadi."
        )

    except Exception as e:

        db.rollback()

        print(
            "UC KOD QO'SHISH XATOSI:",
            repr(e)
        )

        await message.answer(
            "❌ UC kodlarni qo'shishda xatolik yuz berdi."
        )
# =========================
# ADMIN - UC NOMI/NARXINI O'ZGARTIRISH
# =========================

@dp.message(F.text == "✏️ UC nomi/narxini o'zgartirish")
async def edit_uc_start(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()

    sql.execute("""
        SELECT id, name, price
        FROM uc_products
        ORDER BY id
    """)

    products = sql.fetchall()

    if not products:
        await message.answer(
            "❌ UC mahsulotlari topilmadi.",
            reply_markup=admin_menu
        )
        return

    text = "✏️ <b>UC NOMI/NARXINI O'ZGARTIRISH</b>\n\n"

    for product_id, name, price in products:
        text += (
            f"🆔 ID: <code>{product_id}</code>\n"
            f"💎 UC: <b>{name}</b>\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n\n"
        )

    text += (
        "✍️ O'zgartirmoqchi bo'lgan UC ID sini yuboring.\n\n"
        "Masalan: <code>1</code>"
    )

    await state.set_state(EditUC.product_id)

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=back_menu
    )


# =========================
# UC ID TANLASH
# =========================

@dp.message(EditUC.product_id)
async def edit_uc_product_id(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "❌ Faqat UC ID raqamini yuboring.\n\n"
            "Masalan: 1"
        )
        return

    product_id = int(message.text)

    sql.execute("""
        SELECT id, name, price
        FROM uc_products
        WHERE id=?
    """, (product_id,))

    product = sql.fetchone()

    if product is None:
        await message.answer(
            "❌ Bunday UC mahsulot mavjud emas."
        )
        return

    await state.update_data(
        product_id=product[0],
        old_name=product[1],
        old_price=product[2]
    )

    await state.set_state(EditUC.name)

    await message.answer(
        f"""
✏️ <b>UC NOMINI O'ZGARTIRISH</b>

💎 Hozirgi nom:
<b>{product[1]}</b>

✍️ Yangi UC nomini yuboring.

Masalan:
<code>60 UC</code>
""",
        parse_mode="HTML"
    )


# =========================
# YANGI UC NOMI
# =========================

@dp.message(EditUC.name)
async def edit_uc_name(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    if not message.text or not message.text.strip():
        await message.answer(
            "❌ UC nomini kiriting."
        )
        return

    new_name = message.text.strip()

    data = await state.get_data()

    await state.update_data(
        new_name=new_name
    )

    await state.set_state(EditUC.price)

    await message.answer(
        f"""
💎 Yangi UC nomi:
<b>{new_name}</b>

💰 Yangi narxni yuboring.

Masalan:
<code>5000</code>
""",
        parse_mode="HTML"
    )


# =========================
# YANGI NARX
# =========================

@dp.message(EditUC.price)
async def edit_uc_price(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":
        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )
        return

    if not message.text or not message.text.isdigit():
        await message.answer(
            "❌ Narx faqat son bo'lishi kerak.\n\n"
            "Masalan: 5000"
        )
        return

    new_price = int(message.text)

    if new_price < 1:
        await message.answer(
            "❌ Narx 0 dan katta bo'lishi kerak."
        )
        return

    data = await state.get_data()

    product_id = data.get("product_id")
    old_name = data.get("old_name")
    new_name = data.get("new_name")

    if not product_id or not new_name:
        await state.clear()

        await message.answer(
            "❌ Ma'lumot topilmadi.",
            reply_markup=admin_menu
        )
        return

    try:

        # UC mahsulotini yangilash
        sql.execute("""
            UPDATE uc_products
            SET name=?, price=?
            WHERE id=?
        """, (
            new_name,
            new_price,
            product_id
        ))

        # Eski nomdagi kodlarni yangi nomga o'tkazish
        sql.execute("""
            UPDATE uc_codes
            SET product_name=?
            WHERE product_name=?
        """, (
            new_name,
            old_name
        ))

        db.commit()

        await state.clear()

        await message.answer(
            f"""
✅ <b>UC MAHSULOTI O'ZGARTIRILDI!</b>

💎 Eski nom:
<b>{old_name}</b>

💎 Yangi nom:
<b>{new_name}</b>

💰 Yangi narx:
<b>{new_price:,} so'm</b>
""",
            parse_mode="HTML",
            reply_markup=admin_menu
        )

    except Exception as e:

        db.rollback()

        print(
            "UC O'ZGARTIRISH XATOSI:",
            repr(e)
        )

        await message.answer(
            "❌ UC ma'lumotlarini o'zgartirishda xatolik yuz berdi."
        )
# =========================
# PM NOMINI QABUL QILISH
# =========================

@dp.message(AddPMCode.name)
async def add_pm_name(message: Message, state: FSMContext):

    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )
        return

    pm_name = message.text.strip()

    sql.execute(
        """
        SELECT name
        FROM products
        WHERE name=?
        """,
        (pm_name,)
    )

    product = sql.fetchone()

    if product is None:
        await message.answer(
            """
❌ Bunday PM topilmadi.

Faqat:
42 PM
79 PM
99 PM
299 PM
"""
        )
        return

    await state.update_data(pm_name=pm_name)
    await state.set_state(AddPMCode.count)

    await message.answer(
        f"""
✅ PM tanlandi

💎 {pm_name}

📦 Nechta kod qo'shmoqchisiz?
"""
    )
    # =========================
# KOD SONINI QABUL QILISH
# =========================

@dp.message(AddPMCode.count)
async def add_pm_count(message: Message, state: FSMContext):

    if message.text == "🔙 Orqaga":
        await state.clear()
        await message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )
        return

    if not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting.")
        return

    count = int(message.text)

    if count < 1 or count > 1000:
        await message.answer("❌ 1 dan 1000 gacha kiriting.")
        return

    await state.update_data(count=count)

    await state.set_state(AddPMCode.codes)

    await message.answer(
        f"""
✅ Tayyor

🔢 Kodlar soni:
{count} ta

🔑 Endi {count} ta PM kodni yuboring.

Har bir kodni yangi qatordan yozing.

Misol:

ABC123
XYZ456
PM789
"""
    )
# =========================
# PM KODLARNI SAQLASH
# =========================

@dp.message(AddPMCode.codes)
async def save_pm_codes(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    data = await state.get_data()

    pm_name = data["pm_name"]
    count = data["count"]

    if not message.text:
        await message.answer("❌ Kodlarni yuboring.")
        return

    codes = [
        code.strip()
        for code in message.text.splitlines()
        if code.strip()
    ]

    if len(codes) != count:
        await message.answer(
            f"❌ {count} ta kod kerak.\n"
            f"Siz {len(codes)} ta yubordingiz."
        )
        return

    try:
        for code in codes:
            sql.execute(
                """
                INSERT INTO pm_codes (
                    product_name,
                    code,
                    used
                )
                VALUES (?, ?, 0)
                """,
                (pm_name, code)
            )

        sql.execute(
            """
            SELECT COUNT(*)
            FROM pm_codes
            WHERE product_name = ?
            AND used = 0
            """,
            (pm_name,)
        )

        stock = sql.fetchone()[0]

        sql.execute(
            """
            UPDATE products
            SET stock = ?
            WHERE name = ?
            """,
            (stock, pm_name)
        )

        db.commit()

        await state.clear()

        await message.answer(
            f"✅ Tayyor!\n\n"
            f"💎 Mahsulot: {pm_name}\n"
            f"🔑 Qo‘shilgan kodlar: {count} ta\n"
            f"📦 Hozirgi qoldiq: {stock} ta"
        )

    except sqlite3.IntegrityError:
        db.rollback()
        await message.answer(
            "❌ Bu kodlardan biri allaqachon mavjud."
        )

    except Exception as e:
        db.rollback()
        await message.answer(
            f"❌ Xatolik:\n`{e}`",
            parse_mode="Markdown"
        )
       # =========================
# PM QOLDIQ
# =========================

@dp.message(F.text == "📦 PM qoldiq")
async def pm_stock(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    sql.execute("""
        SELECT
            p.name,
            (
                SELECT COUNT(*)
                FROM pm_codes pc
                WHERE pc.product_name = p.name
                AND pc.used = 0
            )
        FROM products p
        ORDER BY p.id
    """)

    products = sql.fetchall()

    if not products:
        await message.answer(
            "❌ Mahsulotlar mavjud emas.",
            reply_markup=admin_menu
        )
        return

    text = "📦 <b>PM QOLDIQLAR</b>\n\n"

    for name, stock in products:
        text += f"💎 <b>{name}</b>\n"
        text += f"📦 Qoldiq: <b>{stock} ta</b>\n\n"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu
    )
    # =========================
# PM NOMI / NARXINI O'ZGARTIRISH
# =========================

@dp.message(F.text == "✏️ PM nomi/narxini o'zgartirish")
async def edit_pm_start(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    await state.clear()

    sql.execute("""
        SELECT id, name, price
        FROM products
        ORDER BY id
    """)

    products = sql.fetchall()

    if not products:

        await message.answer(
            "❌ PM mahsulotlar topilmadi.",
            reply_markup=admin_menu
        )

        return

    text = "✏️ <b>PM NOMI / NARXINI O'ZGARTIRISH</b>\n\n"

    for product_id, name, price in products:

        text += (
            f"🆔 ID: <code>{product_id}</code>\n"
            f"💎 PM: <b>{name}</b>\n"
            f"💰 Narxi: <b>{price:,} so'm</b>\n\n"
        )

    text += "✍️ O'zgartirmoqchi bo'lgan PM ID sini yuboring."

    await state.set_state(
        AdminState.edit_pm_id
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=back_menu
    )


# =========================
# PM ID QABUL QILISH
# =========================

@dp.message(AdminState.edit_pm_id)
async def edit_pm_id(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":

        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )

        return

    if not message.text or not message.text.isdigit():

        await message.answer(
            "❌ PM ID son bo'lishi kerak."
        )

        return

    product_id = int(message.text)

    sql.execute("""
        SELECT id, name, price
        FROM products
        WHERE id=?
    """, (product_id,))

    product = sql.fetchone()

    if not product:

        await message.answer(
            "❌ Bunday PM topilmadi."
        )

        return

    await state.update_data(
        edit_product_id=product[0],
        old_name=product[1]
    )

    await state.set_state(
        AdminState.edit_pm_data
    )

    await message.answer(
        f"""
✏️ <b>PM NI O'ZGARTIRISH</b>

💎 Hozirgi nomi:
<b>{product[1]}</b>

💰 Hozirgi narxi:
<b>{product[2]:,} so'm</b>

📝 Yangi nom va narxni quyidagicha yuboring:

<code>YANGI NOM | NARX</code>

Masalan:

<code>42 PM | 3500</code>
""",
        parse_mode="HTML"
    )


# =========================
# YANGI NOM VA NARXNI SAQLASH
# =========================

@dp.message(AdminState.edit_pm_data)
async def edit_pm_data(
    message: Message,
    state: FSMContext
):

    if message.from_user.id != ADMIN_ID:
        return

    if message.text == "🔙 Orqaga":

        await state.clear()

        await message.answer(
            "👑 Admin panel",
            reply_markup=admin_menu
        )

        return

    if not message.text:

        await message.answer(
            "❌ Nom va narxni yuboring."
        )

        return

    if "|" not in message.text:

        await message.answer(
            """
❌ Format noto'g'ri.

Quyidagicha yuboring:

42 PM | 3500
"""
        )

        return

    try:

        new_name, new_price = (
            message.text.split("|", 1)
        )

        new_name = new_name.strip()

        new_price = int(
            new_price.strip()
            .replace(" ", "")
            .replace(",", "")
        )

    except Exception:

        await message.answer(
            "❌ Narx noto'g'ri."
        )

        return

    if not new_name:

        await message.answer(
            "❌ PM nomini kiriting."
        )

        return

    if new_price <= 0:

        await message.answer(
            "❌ Narx 0 dan katta bo'lishi kerak."
        )

        return

    data = await state.get_data()

    product_id = data.get(
        "edit_product_id"
    )

    old_name = data.get(
        "old_name"
    )

    if not product_id or not old_name:

        await state.clear()

        await message.answer(
            "❌ Ma'lumot topilmadi.",
            reply_markup=admin_menu
        )

        return

    try:

        # PRODUCTS JADVALINI O'ZGARTIRISH
        sql.execute("""
            UPDATE products
            SET name=?, price=?
            WHERE id=?
        """, (
            new_name,
            new_price,
            product_id
        ))


        # PM KODLAR NOMINI HAM O'ZGARTIRISH
        sql.execute("""
            UPDATE pm_codes
            SET product_name=?
            WHERE product_name=?
        """, (
            new_name,
            old_name
        ))

        db.commit()

        await state.clear()

        await message.answer(
            f"""
✅ <b>PM MUVAFFAQIYATLI O'ZGARTIRILDI</b>

💎 Yangi nom:
<b>{new_name}</b>

💰 Yangi narx:
<b>{new_price:,} so'm</b>
""",
            parse_mode="HTML",
            reply_markup=admin_menu
        )

    except sqlite3.IntegrityError:

        db.rollback()

        await message.answer(
            "❌ Bu nomdagi PM allaqachon mavjud."
        )

    except Exception as e:

        db.rollback()

        print(
            "PM O'ZGARTIRISH XATOSI:",
            repr(e)
        )

        await message.answer(
            "❌ PM o'zgartirishda xatolik yuz berdi."
        )


# =========================
# KODLAR SONI
# =========================

@dp.message(F.text == "🔑 Kodlar soni")
async def pm_codes_count(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    sql.execute("""
        SELECT product_name, COUNT(*)
        FROM pm_codes
        WHERE used = 0
        GROUP BY product_name
    """)

    codes = sql.fetchall()

    if not codes:
        await message.answer(
            "❌ Ishlatilmagan PM kodlar mavjud emas.",
            reply_markup=admin_menu
        )
        return

    text = "🔑 <b>PM KODLAR SONI</b>\n\n"

    for name, count in codes:
        text += f"💎 <b>{name}</b>\n"
        text += f"🔢 Kodlar: <b>{count} ta</b>\n\n"

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=admin_menu
    )


# =========================
# BALANS +
# =========================

@dp.message(F.text == "💰 Balans +")
async def balance_add_menu(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.balance_add)

    await message.answer(
        "💰 <b>Balans qo'shish</b>\n\n"
        "👤 User ID yoki @username yuboring.",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.balance_add)
async def balance_add_user(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.text:
        await message.answer("❌ User ID yoki @username yuboring.")
        return

    value = message.text.strip()

    if value.startswith("@"):
        username = value[1:].strip()

        if not username:
            await message.answer("❌ @username noto'g'ri.")
            return

        sql.execute(
            "SELECT id, username, balance FROM users WHERE username=?",
            (username,)
        )

    elif value.isdigit():
        sql.execute(
            "SELECT id, username, balance FROM users WHERE id=?",
            (int(value),)
        )

    else:
        await message.answer("❌ ID yoki @username yuboring.")
        return

    user = sql.fetchone()

    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    await state.update_data(target_user_id=user[0])
    await state.set_state(AdminState.balance_add_amount)

    username_text = f"@{user[1]}" if user[1] else "Username yo'q"

    await message.answer(
        f"👤 User: <b>{username_text}</b>\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"💰 Hozirgi balans: <b>{user[2]:,} so'm</b>\n\n"
        "💵 Qancha balans qo'shishni yuboring:",
        parse_mode="HTML"
    )


@dp.message(AdminState.balance_add_amount)
async def balance_add_amount(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.text or not message.text.isdigit():
        await message.answer("❌ Faqat son kiriting.")
        return

    amount = int(message.text)

    if amount <= 0:
        await message.answer("❌ Summa 0 dan katta bo'lishi kerak.")
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")

    if not user_id:
        await state.clear()
        await message.answer(
            "❌ User topilmadi.",
            reply_markup=admin_menu
        )
        return

    sql.execute(
        "UPDATE users SET balance = balance + ? WHERE id=?",
        (amount, user_id)
    )

    db.commit()

    sql.execute(
        "SELECT id, username, balance FROM users WHERE id=?",
        (user_id,)
    )

    user = sql.fetchone()

    await state.clear()

    if not user:
        await message.answer(
            "❌ Foydalanuvchi topilmadi.",
            reply_markup=admin_menu
        )
        return

    username = f"@{user[1]}" if user[1] else "Username yo'q"

    await message.answer(
        f"✅ <b>BALANS QO'SHILDI</b>\n\n"
        f"👤 User: <b>{username}</b>\n"
        f"🆔 ID: <code>{user[0]}</code>\n\n"
        f"➕ Qo'shildi: <b>{amount:,} so'm</b>\n"
        f"💰 Yangi balans: <b>{user[2]:,} so'm</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


# =========================
# BALANS -
# =========================

@dp.message(F.text == "💸 Balans -")
async def balance_minus_menu(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.balance_minus)

    await message.answer(
        "💸 <b>Balans ayirish</b>\n\n"
        "👤 User ID yoki @username yuboring.",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.balance_minus)
async def balance_minus_user(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.text:
        await message.answer("❌ ID yoki @username yuboring.")
        return

    data = await state.get_data()

    if data.get("wait_amount"):
        if not message.text.isdigit():
            await message.answer("❌ Faqat summa son bo'lishi kerak.")
            return

        amount = int(message.text)

        if amount <= 0:
            await message.answer("❌ Summa 0 dan katta bo'lishi kerak.")
            return

        user_id = data.get("target_user_id")

        sql.execute(
            "SELECT username, balance FROM users WHERE id=?",
            (user_id,)
        )

        user = sql.fetchone()

        if not user:
            await state.clear()
            await message.answer(
                "❌ Foydalanuvchi topilmadi.",
                reply_markup=admin_menu
            )
            return

        if amount > user[1]:
            await message.answer(
                f"❌ Balansda yetarli mablag' yo'q.\n\n"
                f"💰 Hozirgi balans: {user[1]:,} so'm"
            )
            return

        sql.execute(
            "UPDATE users SET balance = balance - ? WHERE id=?",
            (amount, user_id)
        )

        db.commit()

        sql.execute(
            "SELECT username, balance FROM users WHERE id=?",
            (user_id,)
        )

        user = sql.fetchone()

        await state.clear()

        username = f"@{user[0]}" if user and user[0] else "Username yo'q"
        new_balance = user[1] if user else 0

        await message.answer(
            f"✅ <b>BALANS AYIRILDI</b>\n\n"
            f"👤 User: <b>{username}</b>\n"
            f"🆔 ID: <code>{user_id}</code>\n\n"
            f"➖ Ayirildi: <b>{amount:,} so'm</b>\n"
            f"💰 Yangi balans: <b>{new_balance:,} so'm</b>",
            parse_mode="HTML",
            reply_markup=admin_menu
        )
        return

    value = message.text.strip()

    if value.startswith("@"):
        username = value[1:].strip()

        sql.execute(
            "SELECT id, username, balance FROM users WHERE username=?",
            (username,)
        )

    elif value.isdigit():
        sql.execute(
            "SELECT id, username, balance FROM users WHERE id=?",
            (int(value),)
        )

    else:
        await message.answer("❌ ID yoki @username yuboring.")
        return

    user = sql.fetchone()

    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    await state.update_data(
        target_user_id=user[0],
        wait_amount=True
    )

    username_text = f"@{user[1]}" if user[1] else "Username yo'q"

    await message.answer(
        f"👤 User: <b>{username_text}</b>\n"
        f"🆔 ID: <code>{user[0]}</code>\n"
        f"💰 Hozirgi balans: <b>{user[2]:,} so'm</b>\n\n"
        "💵 Qancha ayirishni yuboring:",
        parse_mode="HTML"
    )


# =========================
# USER MA'LUMOT
# =========================

@dp.message(F.text == "👤 User ma'lumot")
async def user_info_menu(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.user_info)

    await message.answer(
        "👤 <b>User ma'lumotlari</b>\n\n"
        "🆔 User ID yoki @username yuboring.",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.user_info)
async def user_info(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    if not message.text:
        await message.answer("❌ ID yoki @username yuboring.")
        return

    value = message.text.strip()

    if value.startswith("@"):
        username = value[1:].strip()

        sql.execute(
            """
            SELECT id, username, balance, total, orders
            FROM users
            WHERE username=?
            """,
            (username,)
        )

    elif value.isdigit():

        sql.execute(
            """
            SELECT id, username, balance, total, orders
            FROM users
            WHERE id=?
            """,
            (int(value),)
        )

    else:
        await message.answer("❌ ID yoki @username yuboring.")
        return

    user = sql.fetchone()

    if not user:
        await message.answer("❌ Foydalanuvchi topilmadi.")
        return

    user_id, username, balance, total, orders = user

    sql.execute(
        """
        SELECT product_name, count, price
        FROM orders
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 1
        """,
        (user_id,)
    )

    last_order = sql.fetchone()

    if last_order:
        last_order_text = (
            f"💎 {last_order[0]}\n"
            f"📦 Soni: {last_order[1]} ta\n"
            f"💰 Narxi: {last_order[2]:,} so'm"
        )
    else:
        last_order_text = "❌ Hali xarid qilmagan"

    await state.clear()

    await message.answer(
        f"👤 <b>USER MA'LUMOTLARI</b>\n\n"
        f"👤 User: <b>{('@' + username) if username else 'Username yo‘q'}</b>\n"
        f"🆔 ID: <code>{user_id}</code>\n\n"
        f"💰 Balans: <b>{balance or 0:,} so'm</b>\n"
        f"💳 Jami to'ldirilgan: <b>{total or 0:,} so'm</b>\n"
        f"📦 Jami PM xaridi: <b>{orders or 0} ta</b>\n\n"
        f"🛒 <b>Oxirgi xarid:</b>\n"
        f"{last_order_text}",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


# =========================
# BAN
# =========================

@dp.message(F.text == "🚫 Ban")
async def ban_menu(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.ban)

    await message.answer(
        "🚫 <b>Ban qilinadigan foydalanuvchi</b>\n\n"
        "Username yoki ID yuboring.\n\n"
        "Masalan:\n"
        "@username\n"
        "123456789",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.ban)
async def do_ban(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    value = (message.text or "").strip()

    if value.startswith("@"):
        username = value[1:].strip()

        sql.execute(
            "SELECT id, username FROM users WHERE username=?",
            (username,)
        )

    elif value.isdigit():

        sql.execute(
            "SELECT id, username FROM users WHERE id=?",
            (int(value),)
        )

    else:
        await message.answer(
            "❌ Username yoki ID noto'g'ri.\n\n"
            "Masalan: @username yoki 123456789"
        )
        return

    user = sql.fetchone()

    if not user:
        await message.answer(
            "❌ Bunday foydalanuvchi topilmadi."
        )
        return

    user_id = user[0]
    username = user[1]

    # BAN
    sql.execute(
        "UPDATE users SET ban=1 WHERE id=?",
        (user_id,)
    )

    db.commit()
    await state.clear()

    username_text = f"@{username}" if username else "Username yo'q"

    # ADMIN'GA
    await message.answer(
        f"🚫 <b>Foydalanuvchi ban qilindi!</b>\n\n"
        f"👤 {username_text}\n"
        f"🆔 ID: <code>{user_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )

    # USERGA
    try:
        await bot.send_message(
            user_id,
            "🚫 <b>Siz botdan ban oldingiz.</b>\n\n"
            "❌ Hozircha botdan foydalanishingiz mumkin emas.",
            parse_mode="HTML"
        )
    except Exception:
        pass


# =========================
# UNBAN
# =========================

@dp.message(F.text == "✅ Unban")
async def unban_menu(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    await state.set_state(AdminState.unban)

    await message.answer(
        "✅ <b>Ban'dan chiqariladigan foydalanuvchi</b>\n\n"
        "Username yoki ID yuboring.\n\n"
        "Masalan:\n"
        "@username\n"
        "123456789",
        parse_mode="HTML",
        reply_markup=back_menu
    )


@dp.message(AdminState.unban)
async def do_unban(message: Message, state: FSMContext):

    if message.from_user.id != ADMIN_ID:
        return

    value = (message.text or "").strip()

    if value.startswith("@"):
        username = value[1:].strip()

        sql.execute(
            "SELECT id, username FROM users WHERE username=?",
            (username,)
        )

    elif value.isdigit():

        sql.execute(
            "SELECT id, username FROM users WHERE id=?",
            (int(value),)
        )

    else:
        await message.answer(
            "❌ Username yoki ID noto'g'ri.\n\n"
            "Masalan: @username yoki 123456789"
        )
        return

    user = sql.fetchone()

    if not user:
        await message.answer(
            "❌ Bunday foydalanuvchi topilmadi."
        )
        return

    user_id = user[0]
    username = user[1]

    # UNBAN
    sql.execute(
        "UPDATE users SET ban=0 WHERE id=?",
        (user_id,)
    )

    db.commit()
    await state.clear()

    username_text = f"@{username}" if username else "Username yo'q"

    # ADMIN'GA
    await message.answer(
        f"✅ <b>Foydalanuvchi ban'dan chiqarildi!</b>\n\n"
        f"👤 {username_text}\n"
        f"🆔 ID: <code>{user_id}</code>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )

    # USERGA
    try:
        await bot.send_message(
            user_id,
            "✅ <b>Siz ban'dan chiqarildingiz.</b>\n\n"
            "🎉 Endi botdan yana foydalanishingiz mumkin.",
            parse_mode="HTML"
        )
    except Exception:
        pass
# =========================
# ADMIN BOSH MENYU
# =========================

@dp.message(F.text == "🏠 Bosh menyu")
async def admin_home(message: Message):

    if message.from_user.id != ADMIN_ID:
        await message.answer("❌ Siz admin emassiz.")
        return

    await message.answer(
        "🏠 Bosh menyuga qaytdingiz.",
        reply_markup=menu
    )


# =========================
# QO'LLAB-QUVVATLASH
# =========================

@dp.message(F.text == "📞 Qo'llab-quvvatlash")
async def support(message: Message):

    if not await subscription_check_message(message, bot):
        return

    await message.answer(
        """
📞 <b>QO'LLAB-QUVVATLASH</b>

Muammo yoki savol bo'lsa admin bilan bog'laning.

👤 Admin:
@SIGMA_OKELA

🕒 Ish vaqti:
10:00 - 22:00
""",
        parse_mode="HTML"
    )


# =========================
# ORQAGA
# =========================

@dp.message(F.text == "🔙 Orqaga")
async def back(message: Message, state: FSMContext):

    await state.clear()

    await message.answer(
        "🏠 Bosh menyu",
        reply_markup=menu
    )


# =========================
# STATISTIKA
# =========================

@dp.message(F.text == "👥 Statistika")
async def statistics(message: Message):

    if message.from_user.id != ADMIN_ID:
        return

    sql.execute("SELECT COUNT(*) FROM users")
    users = sql.fetchone()[0]

    sql.execute("SELECT COUNT(*) FROM users WHERE ban=1")
    bans = sql.fetchone()[0]

    sql.execute("SELECT SUM(balance) FROM users")
    total_balance = sql.fetchone()[0] or 0

    sql.execute("SELECT SUM(total) FROM users")
    total_payment = sql.fetchone()[0] or 0

    await message.answer(
        f"📊 <b>BOT STATISTIKASI</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{users}</b>\n"
        f"🚫 Ban qilinganlar: <b>{bans}</b>\n"
        f"💰 Umumiy balans: <b>{total_balance:,} so'm</b>\n"
        f"💳 Umumiy to'lov: <b>{total_payment:,} so'm</b>",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


import os
import asyncio
from aiogram import F
from aiogram.types import Message, BotCommand, BotCommandScopeAllPrivateChats

# =========================
# BOTNI PAUZA QILISH
# =========================

@dp.message(F.text == "⛔ Botni to'xtatish")
async def pause_bot(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    bot_status.BOT_PAUSED = True

    await message.answer(
        "⛔ <b>BOT VAQTINCHA TO'XTATILDI</b>\n\n"
        "Oddiy foydalanuvchilar botdan foydalana olmaydi.\n"
        "👑 Admin panel ishlaydi.",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

@dp.message(F.text == "▶️ Botni ishga tushirish")
async def resume_bot(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    bot_status.BOT_PAUSED = False

    await message.answer(
        "▶️ <b>BOT QAYTA ISHGA TUSHDI</b>\n\n"
        "Foydalanuvchilar botdan yana foydalanishi mumkin.",
        parse_mode="HTML",
        reply_markup=admin_menu
    )


async def main():
    # 1. Render uxlab qolmasligi uchun Flask veb-serverini ishga tushiramiz
    keep_alive()
    print("Veb-server (Flask) ishga tushdi!")

    print("✅ BOT ISHGA TUSHDI")
    print("🔄 HAMYON AVTO TEKSHIRUV ISHGA TUSHDI")

    asyncio.create_task(check_payments_loop(bot))
    asyncio.create_task(expire_payments_loop(bot))

    await bot.delete_my_commands()

    await bot.set_my_commands(
        commands=[
            BotCommand(
                command="start",
                description="🚀 Botni qayta ishga tushirish"
            )
        ],
        scope=BotCommandScopeAllPrivateChats()
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot to'xtatildi!")
