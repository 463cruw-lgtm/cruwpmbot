import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# HECH QANDAY /data tekshiruvisiz! Faqat loyiha papkasidagi users.db ishlatiladi
DB_PATH = os.path.join(BASE_DIR, "users.db")

db = sqlite3.connect(DB_PATH, check_same_thread=False)
sql = db.cursor()

# Jadvallarni tekshirish va yaratish
sql.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        user_id INTEGER UNIQUE,
        username TEXT,
        balance INTEGER DEFAULT 0,
        total_topup INTEGER DEFAULT 0,
        total INTEGER DEFAULT 0
    )
''')
db.commit()