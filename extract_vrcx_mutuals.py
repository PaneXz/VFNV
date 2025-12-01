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

def get_vrcx_users():
    """Get list of all VRCX users with their display names and user IDs"""
    db_path = get_vrcx_db_path()
    
    if not os.path.exists(db_path):
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Find friend_log tables (pattern: usr[hash]_friend_log_current)
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%friend_log_current'")
    friend_tables = cursor.fetchall()
    
    users = []
    for (table_name,) in friend_tables:
        # Extract user hash from table name
        user_hash = table_name.replace('_friend_log_current', '')
        
        try:
            friend_count = cursor.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            
            # Format user ID with hyphens for display
            user_id = user_hash.replace('usr', 'usr_')
            # Insert hyphens at proper positions: usr_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
            if len(user_id) == 36:  # usr_ + 32 hex chars
                formatted_id = f"{user_id[:12]}-{user_id[12:16]}-{user_id[16:20]}-{user_id[20:24]}-{user_id[24:]}"
            else:
                formatted_id = user_id
            
            # Try to get display name from gamelog_join_leave (most reliable)
            display_name = None
            try:
                gamelog_result = cursor.execute(
                    "SELECT display_name FROM gamelog_join_leave WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
                    (formatted_id,)
                ).fetchone()
                if gamelog_result:
                    display_name = gamelog_result[0]
            except:
                pass
            
            # Fallback: try feed_status table
            if not display_name:
                try:
                    feed_table = f"{user_hash}_feed_status"
                    feed_result = cursor.execute(
                        f"SELECT display_name FROM {feed_table} ORDER BY created_at DESC LIMIT 1"
                    ).fetchone()
                    if feed_result:
                        display_name = feed_result[0]
                except:
                    pass
            
            # Create display string with name if found
            if display_name:
                display = f"{display_name} - {formatted_id} ({friend_count} friends)"
            else:
                display = f"{formatted_id} ({friend_count} friends)"
            
            users.append({
                'user_hash': user_hash,
                'user_id': formatted_id,
                'display_name': display_name or 'Unknown',
                'table_name': table_name,
                'friend_count': friend_count,
                'display': display
            })
        except Exception as e:
            print(f"Error processing user {user_hash}: {e}")
    
    conn.close()
    return users

def extract_friends_and_mutuals(user_hash=None):
    """Extract friends list from VRCX (returns friend IDs and names only, no mutuals)
    
    Args:
        user_hash: Specific user hash to extract (e.g., 'usr49f62904b3194265aa3279a39714616b')
                   If None, uses the first user found
    """
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
    
    # Select the appropriate table
    if user_hash:
        table_name = f"{user_hash}_friend_log_current"
        if (table_name,) not in friend_tables:
            print(f"Table for user {user_hash} not found")
            conn.close()
            return {}
        print(f"Using table for selected user: {table_name}")
    else:
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
