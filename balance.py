import asyncio
import time
import json
import aiohttp

from aiogram import F, Router, Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

from subscription import subscription_check_message

from config import (
    ADMIN_ID,
    CARD_NUMBER,
    CARD_OWNER,
    ELDER_API_URL,
    SHOP_ID,
    SHOP_KEY
)

from database import db, sql

router = Router()

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
back_menu = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="🔙 Orqaga")
        ]
    ],
    resize_keyboard=True
)


class FillBalance(StatesGroup):
    amount = State()


class CardReceipt(StatesGroup):
    payment_id = State()


def create_payment_table():

    sql.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at INTEGER NOT NULL,
            elder_order TEXT
        )
    """)

    try:
        sql.execute(
            "ALTER TABLE payments ADD COLUMN elder_order TEXT"
        )
    except Exception:
        pass

    db.commit()


async def elder_create_payment(amount: int, user_id: int) -> dict:

    payload = {
        "method": "create",
        "shop_id": SHOP_ID,
        "shop_key": SHOP_KEY,
        "amount": int(amount),
        "user_id": f"telegram_{user_id}"
    }

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:

            async with session.post(
                ELDER_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:

                text = await response.text()

                try:
                    result = json.loads(text)
                except Exception:
                    result = {
                        "status": "error",
                        "message": "Elder noto'g'ri JSON qaytardi"
                    }

                result["_http_status"] = response.status

                print(
                    "ELDER CREATE:",
                    response.status,
                    result
                )

                return result

    except asyncio.TimeoutError:

        print("ELDER CREATE TIMEOUT")

        return {
            "status": "error",
            "message": "Elder API timeout",
            "_http_status": 0
        }

    except aiohttp.ClientError as e:

        print(
            "ELDER CREATE HTTP XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }

    except Exception as e:

        print(
            "ELDER CREATE XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }
async def elder_check_payment(elder_order: str) -> dict:

    payload = {
        "method": "check",
        "shop_id": SHOP_ID,
        "shop_key": SHOP_KEY,
        "order": elder_order
    }

    try:

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                ELDER_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:

                text = await response.text()

                try:
                    result = json.loads(text)

                except Exception:

                    result = {
                        "status": "error",
                        "message": "Elder noto'g'ri JSON qaytardi"
                    }

                result["_http_status"] = response.status

                print(
                    "ELDER CHECK:",
                    elder_order,
                    response.status,
                    result
                )

                return result

    except asyncio.TimeoutError:

        print("ELDER CHECK TIMEOUT")

        return {
            "status": "error",
            "message": "Elder API timeout",
            "_http_status": 0
        }

    except aiohttp.ClientError as e:

        print(
            "ELDER CHECK HTTP XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }

    except Exception as e:

        print(
            "ELDER CHECK XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }


# =========================================================
# ELDER ANIQ SUMMA TEKSHIRISH
# =========================================================

async def elder_check_exact_amount(amount: int) -> bool:

    url = (
        f"https://pay.elder.uz/"
        f"{SHOP_ID}/status.php?amount={amount}"
    )

    try:

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(url) as response:

                text = await response.text()

                try:
                    result = json.loads(text)

                except Exception:

                    print(
                        "❌ EXACT AMOUNT JSON XATO:",
                        text
                    )

                    return False

                print(
                    "ELDER EXACT AMOUNT:",
                    amount,
                    response.status,
                    result
                )

                if response.status != 200:
                    return False

                transaction = result.get("result") or {}

                if transaction.get("status") != "paid":
                    return False

                real_amount = transaction.get("amount")

                if real_amount is None:
                    return False

                try:

                    real_amount = int(
                        float(
                            str(real_amount)
                        )
                    )

                except Exception:

                    return False

                # ANIQ SUMMA TEKSHIRISH
                if real_amount != int(amount):

                    print(
                        f"❌ SUMMA MOS EMAS: "
                        f"kutilgan={amount}, "
                        f"kelgan={real_amount}"
                    )

                    return False

                print(
                    f"✅ ANIQ SUMMA TASDIQLANDI: {amount}"
                )

                return True

    except Exception as e:

        print(
            "EXACT AMOUNT XATO:",
            repr(e)
        )

        return False


# =========================================================
# ELDER TO'LOVNI BEKOR QILISH
# =========================================================

async def elder_cancel_payment(elder_order: str) -> dict:

    payload = {
        "method": "cancel",
        "shop_id": SHOP_ID,
        "shop_key": SHOP_KEY,
        "order": elder_order
    }

    try:

        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                ELDER_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json"
                }
            ) as response:

                text = await response.text()

                try:
                    result = json.loads(text)

                except Exception:

                    result = {
                        "status": "error",
                        "message": "Elder noto'g'ri JSON qaytardi"
                    }

                result["_http_status"] = response.status

                print(
                    "ELDER CANCEL:",
                    elder_order,
                    response.status,
                    result
                )

                return result

    except asyncio.TimeoutError:

        print("ELDER CANCEL TIMEOUT")

        return {
            "status": "error",
            "message": "Elder API timeout",
            "_http_status": 0
        }

    except aiohttp.ClientError as e:

        print(
            "ELDER CANCEL HTTP XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }

    except Exception as e:

        print(
            "ELDER CANCEL XATO:",
            repr(e)
        )

        return {
            "status": "error",
            "message": str(e),
            "_http_status": 0
        }


# =========================================================
# BALANCE ROUTER
# =========================================================

def register_balance(dp):

    dp.include_router(router)

    create_payment_table()


# =========================================================
# BALANSNI TO'LDIRISH
# =========================================================

@router.message(F.text == "💰 Balansni to'ldirish")
async def balance(
    message: Message,
    state: FSMContext,
    bot: Bot
):

    if not await subscription_check_message(
        message,
        bot
    ):
        return

    await state.clear()

    await state.set_state(
        FillBalance.amount
    )
    await message.answer(
        """
💳 <b>BALANSNI TO'LDIRISH</b>

💰 Minimal: <b>1 000 so'm</b>
💰 Maksimal: <b>1 000 000 so'm</b>

✍️ Summani kiriting:
""",
        parse_mode="HTML",
        reply_markup=back_menu
    )
 


@router.message(FillBalance.amount)
async def get_amount(
    message: Message,
    state: FSMContext
):

    if message.text == "🔙 Orqaga":

        await state.clear()

        await message.answer(
            "🏠 Bosh menyu",
            reply_markup=menu
        )

        return

    if message.text is None:
        return

    if not message.text.isdigit():

        await message.answer(
            "❌ Faqat son kiriting."
        )

        return

    amount = int(message.text)

    if amount < 1000 or amount > 1000000:

        await message.answer(
            "❌ Summa 1 000 - 1 000 000 oralig'ida bo'lishi kerak."
        )

        return

    await state.update_data(
        amount=amount
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚡ AVTO TO'LOV",
                    callback_data="payment_auto"
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 KARTA — ADMIN TASDIQLAYDI",
                    callback_data="payment_card"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="payment_cancel"
                )
            ]
        ]
    )

    await message.answer(
        f"""
💳 <b>TO'LOV USULINI TANLANG</b>

💰 Summa: <b>{amount:,} so'm</b>

Quyidagi usullardan birini tanlang:
""",
        parse_mode="HTML",
        reply_markup=keyboard
    )


@router.callback_query(F.data == "payment_cancel")
async def payment_cancel(
    call: CallbackQuery,
    state: FSMContext
):

    await state.clear()

    try:
        await call.answer(
            "❌ Bekor qilindi"
        )
    except Exception:
        pass

    await call.message.edit_text(
        "❌ To'lov bekor qilindi."
    )

    await call.message.answer(
        "🏠 Bosh menyu",
        reply_markup=menu
    )


@router.callback_query(F.data == "payment_auto")
async def payment_auto(
    call: CallbackQuery,
    state: FSMContext
):

    try:
        await call.answer(
            "🔄 To'lov yaratilmoqda..."
        )
    except Exception:
        pass

    data = await state.get_data()

    amount = data.get("amount")

    if not amount:

        await call.message.answer(
            "❌ Summa topilmadi. Qaytadan urinib ko'ring."
        )

        return

    result = await elder_create_payment(
        int(amount),
        call.from_user.id
    )

    http_status = result.get(
        "_http_status"
    )

    if result.get("status") != "success":

        if http_status == 409:

            await call.message.answer(
                f"""
⚠️ <b>{amount:,} so'm</b>lik to'lov hozir boshqa foydalanuvchi tomonidan amalga oshirilmoqda.

Iltimos, boshqa summa kiriting.

Masalan: <b>{amount + 1:,} so'm.</b>
""",
                parse_mode="HTML"
            )

        else:

            error_message = result.get(
                "message",
                "Elder orqali to'lov yaratilmadi."
            )

            await call.message.answer(
                f"❌ {error_message}"
            )

        return

    elder_order = result.get(
        "order"
    )

    if not elder_order:

        await call.message.answer(
            "❌ Elder order ID qaytmadi."
        )

        return

    created_at = int(
        time.time()
    )

    sql.execute(
        """
        INSERT INTO payments
        (user_id, amount, status, created_at, elder_order)
        VALUES (?, ?, 'pending', ?, ?)
        """,
        (
            call.from_user.id,
            int(amount),
            created_at,
            elder_order
        )
    )

    db.commit()

    payment_id = sql.lastrowid

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 To'lovni tekshirish",
                    callback_data=f"check_payment:{payment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data=f"cancel_payment:{payment_id}"
                )
            ]
        ]
    )

    await call.message.answer(
        f"""
⚡ <b>AVTO TO'LOV</b>

👤 <b>Karta egasi:</b>
<b>{CARD_OWNER}</b>

💳 <b>To'lov karta:</b>
<code>{CARD_NUMBER}</code>

💰 <b>Miqdori:</b>
<b>{amount:,} so'm</b>

🆔 <b>To'lov ID:</b>
<code>{payment_id}</code>

⏰ <b>Kutish vaqti:</b> 5 daqiqa

✅ To'lov avtomatik qabul qilinadi.

👉🏻 <b>Aynan {amount:,} so'm yuboring</b> —
ortiq yoki kam summa avtomatik aniqlanmasligi mumkin.

⚡ To'lov tasdiqlangach, balansingiz avtomatik to'ldiriladi.
""",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await state.clear()
@router.callback_query(
    F.data.startswith("check_payment:")
)
async def check_payment(
    call: CallbackQuery
):

    try:

        payment_id = int(
            call.data.split(":")[1]
        )

    except Exception:

        await call.answer(
            "❌ Xatolik yuz berdi.",
            show_alert=True
        )

        return


    sql.execute(
        """
        SELECT
            id,
            user_id,
            amount,
            status,
            created_at,
            elder_order
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = sql.fetchone()


    if not payment:

        await call.answer(
            "❌ To'lov topilmadi.",
            show_alert=True
        )

        return


    (
        db_payment_id,
        user_id,
        amount,
        status,
        created_at,
        elder_order
    ) = payment


    if user_id != call.from_user.id:

        await call.answer(
            "❌ Bu to'lov sizniki emas.",
            show_alert=True
        )

        return


    # =========================
    # TO'LOV MUDDATI TUGAGAN
    # =========================

    if status in (
        "cancelled",
        "expired"
    ):

        await call.answer(
            "❌ TO'LOV MUDDATI TUGADI!\n\n"
            "🔄 Yangi to'lov yarating.",
            show_alert=True
        )

        return


    # =========================
    # TO'LOV ALLAQACHON PAID
    # =========================

    if status == "paid":

        await call.answer(
            "⚠️ Bu to'lov allaqachon tasdiqlangan.",
            show_alert=True
        )

        return


    # =========================
    # FAQAT PENDING BO'LSA
    # =========================

    if status != "pending":

        await call.answer(
            "⚠️ Bu to'lov ishlamaydi.",
            show_alert=True
        )

        return


    if not elder_order:

        await call.answer(
            "❌ To'lov ma'lumoti topilmadi.",
            show_alert=True
        )

        return


    await call.answer(
        "🔎 Tekshirilmoqda..."
    )


    # =========================
    # ELDER TEKSHIRISH
    # =========================

    result = await elder_check_payment(
        elder_order
    )


    if result.get("status") != "success":

        return


    elder_data = result.get(
        "data"
    ) or {}


    elder_status = elder_data.get(
        "status"
    )


    if elder_status != "paid":

        return


   # =========================
# KARTA ORQALI TO'LOV
# =========================

@router.callback_query(F.data == "payment_card")
async def payment_card(
    call: CallbackQuery,
    state: FSMContext
):

    try:
        user_id = call.from_user.id

        # =========================
        # USERNI TEKSHIRISH
        # =========================

        sql.execute(
            """
            SELECT id
            FROM users
            WHERE id=?
            """,
            (user_id,)
        )

        user_row = sql.fetchone()

        # User bazada bo'lmasa avtomatik yaratish
        if not user_row:

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
                    call.from_user.username or "NoUsername",
                    0,
                    0,
                    0,
                    0
                )
            )

            db.commit()

        # =========================
        # SUMMANI OLISH
        # =========================

        data = await state.get_data()
        amount = data.get("amount")

        if not amount:

            await call.answer(
                "❌ Summa topilmadi. Qaytadan urinib ko'ring.",
                show_alert=True
            )

            return

        try:
            amount = int(float(str(amount)))
        except Exception:

            await call.answer(
                "❌ Summa noto'g'ri.",
                show_alert=True
            )

            return

        # =========================
        # TO'LOVNI YARATISH
        # =========================

        created_at = int(time.time())

        sql.execute(
            """
            INSERT INTO payments
            (user_id, amount, status, created_at)
            VALUES (?, ?, 'pending_card', ?)
            """,
            (
                user_id,
                amount,
                created_at
            )
        )

        payment_id = sql.lastrowid

        db.commit()

        # =========================
        # PAYMENT ID NI SAQLASH
        # =========================

        await state.update_data(
            payment_id=payment_id,
            amount=amount
        )

        # =========================
        # CHEK KUTISH HOLATI
        # =========================

        await state.set_state(
            CardReceipt.payment_id
        )

        # =========================
        # BEKOR QILISH TUGMASI
        # =========================

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❌ Bekor qilish",
                        callback_data=f"cancel_card:{payment_id}"
                    )
                ]
            ]
        )

        # =========================
        # KARTA MA'LUMOTLARI
        # =========================

        await call.answer()

        await call.message.answer(
            f"""
💳 <b>KARTA ORQALI TO'LOV</b>

💰 <b>Summa:</b>
<b>{amount:,} so'm</b>

👤 <b>Qabul qiluvchi:</b>
<b>{CARD_OWNER}</b>

💳 <b>Karta:</b>
<code>{CARD_NUMBER}</code>

📌 To'lovni amalga oshirgandan keyin
<b>chek rasmini yuboring.</b>

🆔 <b>To'lov ID:</b>
<code>{payment_id}</code>

📷 <b>Endi chek rasmini shu yerga yuboring.</b>
""",
            parse_mode="HTML",
            reply_markup=keyboard
        )

    except Exception as e:

        print(
            f"❌ payment_card xatosi: {e}"
        )

        try:
            await call.answer(
                "❌ Xatolik yuz berdi.",
                show_alert=True
            )
        except Exception:
            pass


# =========================
# KARTA TO'LOVNI BEKOR QILISH
# =========================

@router.callback_query(
    F.data.startswith("cancel_card:")
)
async def cancel_card(
    call: CallbackQuery,
    state: FSMContext
):

    try:

        payment_id = int(
            call.data.split(":")[1]
        )

    except Exception:

        await state.clear()
        return

    sql.execute(
        """
        UPDATE payments
        SET status='cancel'
        WHERE id=?
        AND user_id=?
        AND status='pending_card'
        """,
        (
            payment_id,
            call.from_user.id
        )
    )

    db.commit()

    await state.clear()

    try:

        await call.answer(
            "❌ Bekor qilindi"
        )

    except Exception:
        pass

    await call.message.edit_text(
        "❌ Karta orqali to'lov bekor qilindi."
    )

    await call.message.answer(
        "🏠 Bosh menyu",
        reply_markup=menu
    )
### 2-QISM — `card_receipt()` va `approve_card()`


# =========================
# CHEK QABUL QILISH
# =========================

@router.message(
    CardReceipt.payment_id,
    F.photo
)
async def card_receipt(
    message: Message,
    state: FSMContext,
    bot: Bot
):

    data = await state.get_data()
    payment_id = data.get("payment_id")

    if not payment_id:
        await state.clear()
        return

    sql.execute(
        """
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = sql.fetchone()

    if not payment:
        await state.clear()
        return

    user_id, amount, status = payment

    if user_id != message.from_user.id:
        return

    if status != "pending_card":
        await state.clear()
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data=f"approve_card:{payment_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Rad etish",
                    callback_data=f"reject_card:{payment_id}"
                )
            ]
        ]
    )

    photo_id = message.photo[-1].file_id

    await bot.send_photo(
        ADMIN_ID,
        photo=photo_id,
        caption=f"""
💳 <b>KARTA TO'LOVI</b>

👤 <b>User:</b>
<b>@{message.from_user.username or 'username yo‘q'}</b>

🆔 <b>User ID:</b>
<code>{user_id}</code>

💰 <b>Summa:</b>
<b>{amount:,} so'm</b>

🆔 <b>To'lov ID:</b>
<code>{payment_id}</code>

📷 Chek yuborildi.
""",
        parse_mode="HTML",
        reply_markup=keyboard
    )

    await message.answer(
        f"""
💳 <b>KARTA TO'LOVI</b>

💰 <b>Summa:</b>
<b>{amount:,} so'm</b>

🆔 <b>To'lov ID:</b>
<code>{payment_id}</code>

📷 <b>Chek yuborildi.</b>

⏳ Admin to'lovni tekshirmoqda.

✅ Tasdiqlangandan keyin
<b>{amount:,} so'm</b> balansingizga qo'shiladi.
""",
        parse_mode="HTML",
        reply_markup=menu
    )

    await state.clear()


# =========================
# KARTA TO'LOVNI TASDIQLASH
# =========================

@router.callback_query(
    F.data.startswith("approve_card:")
)
async def approve_card(
    call: CallbackQuery,
    bot: Bot
):

    if call.from_user.id != ADMIN_ID:
        return

    try:
        payment_id = int(
            call.data.split(":")[1]
        )
    except Exception:
        await call.answer(
            "❌ To'lov ID xato.",
            show_alert=True
        )
        return

    sql.execute(
        """
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = sql.fetchone()

    if not payment:
        await call.answer(
            "❌ To'lov topilmadi.",
            show_alert=True
        )
        return

    user_id, amount, status = payment

    if status != "pending_card":
        await call.answer(
            "⚠️ Bu to'lov allaqachon ko'rib chiqilgan.",
            show_alert=True
        )
        return

    # =========================
    # USERNI TEKSHIRISH
    # =========================

    sql.execute(
        """
        SELECT id, username
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    user_row = sql.fetchone()

    if not user_row:

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
                "NoUsername",
                0,
                0,
                0,
                0
            )
        )

    # =========================
    # TO'LOVNI PAID QILISH
    # =========================

    sql.execute(
        """
        UPDATE payments
        SET status='paid'
        WHERE id=?
        AND status='pending_card'
        """,
        (payment_id,)
    )

    if sql.rowcount != 1:
        db.rollback()

        await call.answer(
            "⚠️ Bu to'lov allaqachon tasdiqlangan.",
            show_alert=True
        )
        return

    # =========================
    # BALANSNI QO'SHISH
    # =========================

    sql.execute(
        """
        UPDATE users
        SET
            balance = COALESCE(balance, 0) + ?,
            total = COALESCE(total, 0) + ?,
            orders = COALESCE(orders, 0) + 1
        WHERE id=?
        """,
        (
            amount,
            amount,
            user_id
        )
    )

    if sql.rowcount != 1:
        db.rollback()

        await call.answer(
            "❌ Userni yaratishda xatolik.",
            show_alert=True
        )
        return

    # =========================
    # USERNAME
    # =========================

    sql.execute(
        """
        SELECT username
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )

    user_row = sql.fetchone()

    if user_row and user_row[0]:
        username = user_row[0]
    else:
        username = "username yo'q"

    db.commit()

    await call.answer(
        "✅ To'lov tasdiqlandi."
    )

    try:
        await call.message.edit_caption(
            caption=f"""
✅ <b>KARTA TO'LOVI TASDIQLANDI</b>

👤 <b>User:</b>
<b>@{username}</b>

🆔 <b>User ID:</b>
<code>{user_id}</code>

💰 <b>Summa:</b>
<b>{amount:,} so'm</b>

🆔 <b>To'lov ID:</b>
<code>{payment_id}</code>

✅ <b>Balansga qo'shildi.</b>
""",
            parse_mode="HTML",
            reply_markup=None
        )
    except Exception as e:
        print(
            "❌ TASDIQLANGAN XABARNI O'ZGARTIRISH XATOSI:",
            repr(e)
        )

    try:
        await bot.send_message(
            user_id,
            f"""
🎉 <b>BALANS TO'LDIRILDI</b>

💰 Qo'shilgan summa:
<b>{amount:,} so'm</b>

🆔 To'lov ID:
<code>{payment_id}</code>

✅ Admin to'lovingizni tasdiqladi.
""",
            parse_mode="HTML",
            reply_markup=menu
        )
    except Exception as e:
        print(
            "❌ USERGA XABAR YUBORISHDA XATO:",
            repr(e)
        )


### 3-QISM — `reject_card`, `cancel_payment`, `expire_payments_loop`, `check_payments_loop`


# =========================
# KARTA TO'LOVNI RAD ETISH
# =========================

@router.callback_query(
    F.data.startswith("reject_card:")
)
async def reject_card(
    call: CallbackQuery,
    bot: Bot
):

    if call.from_user.id != ADMIN_ID:
        return

    try:
        payment_id = int(
            call.data.split(":")[1]
        )
    except Exception:
        return

    sql.execute(
        """
        SELECT user_id, amount, status
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = sql.fetchone()

    if not payment:
        await call.answer(
            "❌ To'lov topilmadi."
        )
        return

    user_id, amount, status = payment

    if status != "pending_card":
        await call.answer(
            "⚠️ Bu to'lov allaqachon ko'rib chiqilgan."
        )
        return

    sql.execute(
        """
        UPDATE payments
        SET status='rejected'
        WHERE id=?
        AND status='pending_card'
        """,
        (payment_id,)
    )

    db.commit()

    await call.answer(
        "❌ To'lov rad etildi."
    )

    try:
        await call.message.edit_caption(
            caption=f"""
❌ <b>TO'LOV RAD ETILDI</b>

👤 User ID:
<code>{user_id}</code>

💰 Summa:
<b>{amount:,} so'm</b>

🆔 To'lov ID:
<code>{payment_id}</code>
""",
            parse_mode="HTML",
            reply_markup=None
        )
    except Exception:
        pass

    try:
        await bot.send_message(
            user_id,
            f"""
❌ <b>TO'LOV RAD ETILDI</b>

💰 Summa:
<b>{amount:,} so'm</b>

🆔 To'lov ID:
<code>{payment_id}</code>

📞 Muammo bo'lsa, qo'llab-quvvatlash xizmatiga murojaat qiling.
""",
            parse_mode="HTML",
            reply_markup=menu
        )
    except Exception as e:
        print(
            "USERGA RAD ETILGAN XABAR XATOSI:",
            repr(e)
        )


# =========================
# AVTO TO'LOVNI BEKOR QILISH
# =========================

@router.callback_query(
    F.data.startswith("cancel_payment:")
)
async def cancel_payment(
    call: CallbackQuery
):

    try:
        payment_id = int(
            call.data.split(":")[1]
        )
    except Exception:
        return

    sql.execute(
        """
        SELECT user_id, status, elder_order
        FROM payments
        WHERE id=?
        """,
        (payment_id,)
    )

    payment = sql.fetchone()

    if not payment:
        return

    user_id, status, elder_order = payment

    if user_id != call.from_user.id:
        return

    if status != "pending":
        return

    if elder_order:

        result = await elder_cancel_payment(
            elder_order
        )

        if result.get("status") != "success":
            return

    sql.execute(
        """
        UPDATE payments
        SET status='cancel'
        WHERE id=?
        AND user_id=?
        AND status='pending'
        """,
        (
            payment_id,
            user_id
        )
    )

    db.commit()

    try:
        await call.answer(
            "❌ To'lov bekor qilindi."
        )
    except Exception:
        pass

    await call.message.edit_text(
        "❌ <b>AVTO TO'LOV BEKOR QILINDI</b>",
        parse_mode="HTML",
        reply_markup=None
    )

    await call.message.answer(
        "🏠 Bosh menyu",
        reply_markup=menu
    )


# =========================
# AVTO TO'LOVLARNI MUDDATI TUGAGANDA BEKOR QILISH
# =========================

async def expire_payments_loop(bot: Bot):

    print(
        "⏰ ELDER TO'LOVLARINI AVTOMATIK BEKOR QILISH ISHGA TUSHDI"
    )

    while True:

        try:

            expire_before = int(time.time()) - 300

            sql.execute(
                """
                SELECT id, user_id, amount, elder_order
                FROM payments
                WHERE status='pending'
                AND created_at <= ?
                AND elder_order IS NOT NULL
                AND elder_order != ''
                """,
                (expire_before,)
            )

            rows = sql.fetchall()

            for row in rows:

                payment_id, user_id, amount, elder_order = row

                try:

                    check_result = await elder_check_payment(
                        elder_order
                    )

                    if check_result.get("status") != "success":
                        continue

                    elder_data = (
                        check_result.get("data") or {}
                    )

                    elder_status = elder_data.get(
                        "status"
                    )

                    # =========================
                    # ELDER TOMONIDAN BEKOR QILINGAN
                    # =========================

                    if elder_status == "cancel":

                        sql.execute(
                            """
                            UPDATE payments
                            SET status='cancel'
                            WHERE id=?
                            AND status='pending'
                            """,
                            (payment_id,)
                        )

                        if sql.rowcount == 1:
                            db.commit()

                        continue

                    # =========================
                    # TO'LOV QILINGAN
                    # =========================

                    if elder_status == "paid":
                        continue

                    # =========================
                    # HALI PENDING BO'LSA
                    # =========================

                    if elder_status == "pending":

                        result = await elder_cancel_payment(
                            elder_order
                        )

                        if result.get("status") == "success":

                            sql.execute(
                                """
                                UPDATE payments
                                SET status='cancel'
                                WHERE id=?
                                AND status='pending'
                                """,
                                (payment_id,)
                            )

                            if sql.rowcount == 1:
                                db.commit()

                except Exception as e:

                    print(
                        f"❌ To'lov {payment_id} tekshirish xatosi: {e}"
                    )

            await asyncio.sleep(10)

        except Exception as e:

            print(
                f"❌ expire_payments_loop xatosi: {e}"
            )

            await asyncio.sleep(10)
            # =========================================================
# AVTO TO'LOVLARNI AVTOMATIK TEKSHIRISH
# =========================================================

async def check_payments_loop(bot: Bot):

    print(
        "🔄 ELDER TO'LOVLARINI AVTOMATIK TEKSHIRISH ISHGA TUSHDI"
    )

    while True:

        try:

            sql.execute(
                """
                SELECT
                    id,
                    user_id,
                    amount,
                    elder_order
                FROM payments
                WHERE status='pending'
                AND elder_order IS NOT NULL
                AND elder_order != ''
                """
            )

            rows = sql.fetchall()

            for row in rows:

                payment_id, user_id, amount, elder_order = row

                try:

                    # =========================
                    # ELDERDAN TO'LOVNI TEKSHIRISH
                    # =========================

                    result = await elder_check_payment(
                        elder_order
                    )

                    if result.get("status") != "success":
                        continue

                    elder_data = (
                        result.get("data") or {}
                    )

                    elder_status = elder_data.get(
                        "status"
                    )

                    # =========================
                    # HALI TO'LANMAGAN
                    # =========================

                    if elder_status != "paid":
                        continue

                    # =========================
                    # ANIQ SUMMANI TEKSHIRISH
                    # =========================

                    paid_amount = elder_data.get(
                        "amount"
                    )

                    if paid_amount is None:
                        print(
                            f"❌ To'lov {payment_id}: Elder summa qaytarmadi."
                        )
                        continue

                    try:

                        paid_amount = int(
                            float(
                                str(paid_amount)
                            )
                        )

                    except Exception:

                        print(
                            f"❌ To'lov {payment_id}: summa noto'g'ri."
                        )
                        continue

                    expected_amount = int(amount)

                    if paid_amount != expected_amount:

                        print(
                            f"❌ SUMMA MOS EMAS: "
                            f"payment_id={payment_id}, "
                            f"kutilgan={expected_amount}, "
                            f"kelgan={paid_amount}"
                        )

                        continue

                    # =========================
                    # USERNI TEKSHIRISH
                    # =========================

                    sql.execute(
                        """
                        SELECT id
                        FROM users
                        WHERE id=?
                        """,
                        (user_id,)
                    )

                    user_row = sql.fetchone()

                    if not user_row:

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
                                "NoUsername",
                                0,
                                0,
                                0,
                                0
                            )
                        )

                    # =========================
                    # TO'LOVNI PAID QILISH
                    # =========================

                    sql.execute(
                        """
                        UPDATE payments
                        SET status='paid'
                        WHERE id=?
                        AND status='pending'
                        """,
                        (payment_id,)
                    )

                    # Agar 1 ta qator o'zgarmagan bo'lsa,
                    # boshqa tekshiruv allaqachon to'lagan
                    if sql.rowcount != 1:

                        db.rollback()

                        continue

                    # =========================
                    # BALANSNI QO'SHISH
                    # =========================

                    sql.execute(
                        """
                        UPDATE users
                        SET
                            balance = COALESCE(balance, 0) + ?,
                            total = COALESCE(total, 0) + ?,
                            orders = COALESCE(orders, 0) + 1
                        WHERE id=?
                        """,
                        (
                            expected_amount,
                            expected_amount,
                            user_id
                        )
                    )

                    if sql.rowcount != 1:

                        db.rollback()

                        print(
                            f"❌ To'lov {payment_id}: "
                            f"user balansini yangilab bo'lmadi."
                        )

                        continue

                    db.commit()

                    print(
                        f"✅ TO'LOV TASDIQLANDI: "
                        f"payment_id={payment_id}, "
                        f"user_id={user_id}, "
                        f"amount={expected_amount}"
                    )

                    # =========================
                    # USERGA XABAR
                    # =========================

                    try:

                        await bot.send_message(
                            user_id,
                            f"""
🎉 <b>BALANS TO'LDIRILDI</b>

💰 Qo'shilgan summa:
<b>{expected_amount:,} so'm</b>

🆔 To'lov ID:
<code>{payment_id}</code>

✅ To'lov avtomatik tasdiqlandi.
""",
                            parse_mode="HTML",
                            reply_markup=menu
                        )

                    except Exception as e:

                        print(
                            f"❌ Userga xabar yuborilmadi "
                            f"{user_id}: {e}"
                        )

                except Exception as e:

                    print(
                        f"❌ To'lov {payment_id} "
                        f"avtomatik tekshirish xatosi: {e}"
                    )

            await asyncio.sleep(10)

        except Exception as e:

            print(
                f"❌ check_payments_loop xatosi: {e}"
            )

            await asyncio.sleep(10)