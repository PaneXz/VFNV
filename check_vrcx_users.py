import sqlite3
import os

db = os.path.join(os.getenv('APPDATA'), 'VRCX', 'VRCX.sqlite3')
conn = sqlite3.connect(db)
c = conn.cursor()

# Get friend_log tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%friend_log_current' ORDER BY name").fetchall()
print(f'Friend tables found: {len(tables)}')
for t in tables:
    print(f'  {t[0]}')

# Get all tables first
print('\nAll tables:')
all_tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
for t in all_tables:
    print(f'  {t[0]}')

# Check for current user in configs
print('\n\nLooking for current user...')
current_user_configs = c.execute("SELECT * FROM configs WHERE key LIKE '%currentuser%' OR key LIKE '%active%'").fetchall()
for cfg in current_user_configs:
    print(f'  {cfg[0]}: {cfg[1]}')

# Also check cookies table
print('\nChecking cookies table...')
cookie_schema = c.execute(f"PRAGMA table_info(cookies)").fetchall()
cols = [s[1] for s in cookie_schema]
print(f'  Columns: {", ".join(cols)}')
cookie_data = c.execute("SELECT * FROM cookies LIMIT 5").fetchall()
for cd in cookie_data:
    print(f'    {cd}')

# Check if we can find user display names
print('\n\nTrying to find user display names...')
for friend_table in tables:
    user_hash = friend_table[0].split('_')[0]
    print(f'\n{user_hash} ({friend_table[0]}):')
    
    # Check friend_log_history for "self" entries
    history_table = friend_table[0].replace('_current', '_history')
    try:
        # Get most recent entry
        recent = c.execute(f"SELECT display_name, user_id FROM {history_table} LIMIT 1").fetchone()
        if recent:
            print(f'  Sample friend: {recent[0]} ({recent[1]})')
    except:
        pass

conn.close()
