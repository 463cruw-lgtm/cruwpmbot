# =========================
# OTZIF KANAL
# =========================

from aiogram import Bot


OTZIF_CHANNEL_ID = "@cruw_otzif"


async def send_otzif(
    bot: Bot,
    user_id: int,
    username: str,
    product_name: str,
    count: int,
    total: int,
    product_type: str
):

    if product_type == "UC":
        product_text = "🎁 Redem"
    else:
        product_text = "🎁 Promokod"

    if username:
        user_text = f"@{username}"
    else:
        user_text = "Username yo'q"

    text = f"""🛒 <b>Yangi xarid</b> (OTZIF)

👤 Foydalanuvchi: ID: {user_id}
👤 User: {user_text}
💰 Narx: <b>{total:,} so'm</b>
🤖 Bot: @cruwpromokod_bot
{product_text}: {product_name} SONI {count} TA
"""

    try:
        await bot.send_message(
            chat_id=OTZIF_CHANNEL_ID,
            text=text,
            parse_mode="HTML"
        )

        print("✅ OTZIF kanalga xarid yuborildi")

    except Exception as e:
        print("❌ OTZIF kanalga yuborishda xato:", e)