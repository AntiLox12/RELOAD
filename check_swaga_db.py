import sqlite3
db = sqlite3.connect('bot_data.db')
tables = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
swaga_related = [t[0] for t in tables if 'swaga' in t[0].lower() or 'player_swaga' in t[0].lower()]
print("All swaga-related tables:", swaga_related)

# Check if player_swaga_tracks exists
all_tables = [t[0] for t in tables]
print("\nAll tables containing 'player':", [t for t in all_tables if 'player' in t.lower()])

# Check recent searches to see if swaga cards were logged
try:
    recent = db.execute("SELECT user_id, rarity, quantity FROM swaga_card_inventory ORDER BY id DESC LIMIT 20").fetchall()
    print("\nRecent swaga card records:", recent)
except Exception as e:
    print("Error:", e)

db.close()
