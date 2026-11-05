from aiogram.fsm.state import State, StatesGroup


# =========================
# UC KOD QO'SHISH
# =========================

class AddUCCode(StatesGroup):
    name = State()
    count = State()
    codes = State()


# =========================
# UC NOMI / NARXINI O'ZGARTIRISH
# =========================

class EditUC(StatesGroup):
    product_id = State()
    name = State()
    price = State()