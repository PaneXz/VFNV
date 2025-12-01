import sqlite3
import os
import json

db = os.path.join(os.getenv('APPDATA'), 'VRCX', 'VRCX.sqlite3')
conn = sqlite3.connect(db)
c = conn.cursor()

# Get friend tables
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%friend_log_current' ORDER BY name").fetchall()

for t in tables:
    table_name = t[0]
    user_hash = table_name.replace('_friend_log_current', '')
    
    print(f'\n{user_hash}:')
    print(f'  Table: {table_name}')
    
    # Try to find the user's own display name from group data in configs
    user_id_with_hyphens = user_hash.replace('usr', 'usr_')
    if len(user_id_with_hyphens) > 12:
        formatted_id = f"{user_id_with_hyphens[:12]}-{user_id_with_hyphens[12:16]}-{user_id_with_hyphens[16:20]}-{user_id_with_hyphens[20:24]}-{user_id_with_hyphens[24:]}"
    else:
        formatted_id = user_id_with_hyphens
    
    print(f'  User ID: {formatted_id}')
    
    # Check avatar_history schema
    avatar_history_table = f'{user_hash}_avatar_history'
    try:
        schema = c.execute(f"PRAGMA table_info({avatar_history_table})").fetchall()
        print(f'  Avatar history columns: {[s[1] for s in schema]}')
        
        # Get a sample row
        sample = c.execute(f"SELECT * FROM {avatar_history_table} LIMIT 1").fetchone()
        if sample:
            print(f'  Sample row length: {len(sample)}')
    except Exception as e:
        print(f'  No avatar history table')
    
    # Check feed tables for user's own name
    feed_status_table = f'{user_hash}_feed_status'
    try:
        status = c.execute(f"SELECT display_name FROM {feed_status_table} ORDER BY created_at DESC LIMIT 1").fetchone()
        if status:
            print(f'  Display Name (from feed): {status[0]}')
    except Exception as e:
        pass
    
    # Try gamelog_join_leave for this user
    try:
        gamelog = c.execute(f"SELECT display_name FROM gamelog_join_leave WHERE user_id = '{formatted_id}' LIMIT 1").fetchone()
        if gamelog:
            print(f'  Display Name (from gamelog): {gamelog[0]}')
    except Exception as e:
        pass

conn.close()
