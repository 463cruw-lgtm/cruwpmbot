from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery

from database import sql
from config import ADMIN_ID


class BanMiddleware(BaseMiddleware):

    async def __call__(self, handler, event, data):

        user = event.from_user

        # =========================
        # USER YO'Q BO'LSA
        # =========================

        if not user:
            return await handler(event, data)

        # =========================
        # ADMIN HAR DOIM ISHLAYDI
        # =========================

        if user.id == ADMIN_ID:
            return await handler(event, data)

        # =========================
        # USER BAN TEKSHIRUVI
        # =========================

        sql.execute(
            "SELECT ban FROM users WHERE id=?",
            (user.id,)
        )

        ban_row = sql.fetchone()

        if ban_row and ban_row[0] == 1:

            if isinstance(event, Message):

                await event.answer(
                    "🚫 <b>Siz botdan ban qilingansiz.</b>\n\n"
                    "❌ Hozircha botdan foydalanishingiz mumkin emas.",
                    parse_mode="HTML"
                )

            elif isinstance(event, CallbackQuery):

                await event.answer(
                    "🚫 Siz botdan ban qilingansiz.",
                    show_alert=True
                )

            return

        # =========================
        # HANDLERGA O'TKAZISH
        # =========================

        return await handler(event, data)