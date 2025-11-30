"""
Extract mutual friend data from VRCX SQLite database
"""

import sqlite3
import os
import json

def get_vrcx_db_path():
    """Get path to VRCX database"""
    appdata = os.getenv('APPDATA')
    return os.path.join(appdata, 'VRCX', 'VRCX.sqlite3')

def explore_vrcx_database():
    """Explore VRCX database structure"""
    db_path = get_vrcx_db_path()
    
    if not os.path.exists(db_path):
        print(f"VRCX database not found at: {db_path}")
        return None
    
    print(f"Opening VRCX database: {db_path}")
    print(f"Size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB\n")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = cursor.fetchall()
    
    print("=" * 60)
    print("VRCX DATABASE TABLES:")
    print("=" * 60)
    
    for (table_name,) in tables:
        print(f"\nTable: {table_name}")
        
        # Get table schema
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        print(f"  Columns: {', '.join([col[1] for col in columns])}")
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  Rows: {count}")
        
        # Show sample data if table has rows
        if count > 0 and count < 1000:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
            samples = cursor.fetchall()
            if samples:
                print(f"  Sample data:")
                for row in samples[:2]:
                    print(f"    {row[:5]}...")  # First 5 fields
    
    conn.close()
    print("\n" + "=" * 60)

def extract_friends_and_mutuals():
    """Extract friends list from VRCX (returns friend IDs and names only, no mutuals)"""
    db_path = get_vrcx_db_path()
    
    if not os.path.exists(db_path):
        print(f"VRCX database not found")
        return {}
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find friend_log tables (pattern: usr[hash]_friend_log_current)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%friend_log_current'")
    friend_tables = cursor.fetchall()
    
    if not friend_tables:
        print("No friend_log tables found")
        conn.close()
        return {}
    
    print(f"Found {len(friend_tables)} friend_log tables")
    
    # Use the first user's friend table
    table_name = friend_tables[0][0]
    print(f"Using table: {table_name}")
    
    # Extract friends (names only, mutuals will come from API)
    friends_dict = {}
    
    try:
        # Get all friends from the table
        cursor.execute(f"SELECT user_id, display_name FROM {table_name}")
        rows = cursor.fetchall()
        
        print(f"Found {len(rows)} friends in VRCX database")
        
        for user_id, display_name in rows:
            if user_id and display_name:
                friends_dict[user_id] = {
                    'name': display_name,
                    'mutuals': []  # Will be populated by API fetch
                }
    except Exception as e:
        print(f"Error extracting friends: {e}")
        import traceback
        traceback.print_exc()
    
    conn.close()
    return friends_dict

if __name__ == '__main__':
    print("VRCX Database Explorer\n")
    explore_vrcx_database()
    print("\n\nAttempting to extract friend data...")
    extract_friends_and_mutuals()

