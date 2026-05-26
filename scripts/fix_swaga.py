# file: fix_swaga.py
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3
import core.database as db
from core.constants import SWAGA_RARITIES

def fix():
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DB_PATH = os.path.join(BASE_DIR, "data", "bot_data.db")
    
    # 1. Clear out bad data
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM swaga_card_inventory WHERE typeof(user_id) != 'integer'")
    conn.commit()
    conn.close()
    
    # 2. Get AntiLox ID
    session = db.SessionLocal()
    try:
        players = session.query(db.Player).all()
        for p in players:
            if p.username and 'antilox' in p.username.lower():
                print(f"User: {p.username}, ID: {p.user_id}")
                # Give 500 of each
                for r in SWAGA_RARITIES.keys():
                    inv = session.query(db.SwagaCardInventory).filter_by(user_id=p.user_id, rarity=r).first()
                    if inv:
                        inv.quantity += 500
                    else:
                        session.add(db.SwagaCardInventory(user_id=p.user_id, rarity=r, quantity=500))
        session.commit()
        print("Fixed and gave cards.")
    finally:
        session.close()

if __name__ == '__main__':
    fix()
