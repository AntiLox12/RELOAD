import sqlite3
import database as db

def fix():
    # 1. Clear out bad data
    conn = sqlite3.connect('bot_data.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM swaga_card_inventory WHERE typeof(user_id) != 'integer'")
    conn.commit()
    
    # 2. Get AntiLox ID
    session = db.SessionLocal()
    try:
        players = session.query(db.Player).all()
        for p in players:
            if p.username and 'antilox' in p.username.lower():
                print(f"User: {p.username}, ID: {p.user_id}")
                # Give 500 of each
                from constants import SWAGA_RARITIES
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
