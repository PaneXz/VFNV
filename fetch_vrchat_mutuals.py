"""
Fetch actual mutual friends from VRChat API using the endpoint VRCX uses
"""

import requests
import json
import base64
import time
import pickle
import os
from typing import Dict, Set, Tuple

class VRChatMutualFetcher:
    def __init__(self, base_dir=None, stop_callback=None):
        self.base_url = "https://api.vrchat.cloud/api/1"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VRChatFriendNetworkVisualizer/1.0 (Contact: github.com/vrchat-network-viz)'
        })
        # Use base_dir if provided, otherwise current directory
        self.base_dir = base_dir
        self.stop_callback = stop_callback
        if base_dir:
            self.session_file = os.path.join(base_dir, 'vrchat_session.pkl')
        else:
            self.session_file = 'vrchat_session.pkl'
    
    def save_session(self):
        """Save session cookies to file"""
        with open(self.session_file, 'wb') as f:
            pickle.dump(self.session.cookies, f)
        print("✓ Session saved for future use\n")
    
    def load_session(self):
        """Load session cookies from file"""
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'rb') as f:
                    self.session.cookies.update(pickle.load(f))
                
                # Test if session is still valid
                response = self.session.get(f"{self.base_url}/auth/user")
                if response.status_code == 200:
                    data = response.json()
                    print(f"✓ Restored session for {data.get('displayName', 'User')}\n")
                    return True
                else:
                    os.remove(self.session_file)
                    return False
            except:
                if os.path.exists(self.session_file):
                    os.remove(self.session_file)
                return False
        return False
    
    def login(self, username: str, password: str, twofa_code: str = None):
        """Login to VRChat API"""
        print("Connecting to VRChat API...")
        
        # Get config first
        try:
            self.session.get(f"{self.base_url}/config")
        except:
            pass
        
        # Create basic auth
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}'
        })
        
        # Login
        response = self.session.get(f"{self.base_url}/auth/user")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check if 2FA is required
            if 'requiresTwoFactorAuth' in data and any(data.get('requiresTwoFactorAuth', [])):
                print("\nTwo-factor authentication required")
                
                # Use provided 2FA code or prompt for it
                if not twofa_code:
                    twofa_code = input("Enter your 2FA code: ")
                
                response = self.session.post(
                    f"{self.base_url}/auth/twofactorauth/totp/verify",
                    json={'code': twofa_code}
                )
                
                if response.status_code != 200:
                    raise Exception(f"2FA failed: {response.status_code} - {response.text}")
                
                # Re-fetch user info
                response = self.session.get(f"{self.base_url}/auth/user")
                data = response.json()
            
            # Remove basic auth header after successful login (use cookies instead)
            if 'Authorization' in self.session.headers:
                del self.session.headers['Authorization']
            
            print(f"Login successful as {data.get('displayName', 'User')}")
            self.save_session()
            return data.get('id')
        else:
            raise Exception(f"Login failed: {response.status_code} - {response.text}")
    
    def get_friends(self):
        """Fetch all friends - try API first, then fallback to VRCX database"""
        print("Fetching friends list...")
        friends = {}
        
        # Try API first
        offset = 0
        n = 100
        
        while True:
            response = self.session.get(
                f"{self.base_url}/auth/user/friends",
                params={'offset': offset, 'n': n, 'offline': 'true'}
            )
            
            if response.status_code != 200:
                break
            
            data = response.json()
            if not data or len(data) == 0:
                break
            
            for friend in data:
                user_id = friend.get('id')
                if user_id:
                    friends[user_id] = {
                        'id': user_id,
                        'name': friend.get('displayName', ''),
                        'status': friend.get('status', '')
                    }
            
            print(f"  Loaded {len(friends)} friends from API...")
            
            if len(data) < n:
                break
            
            offset += n
            time.sleep(0.3)
        
        # If API only gave us partial list, supplement from VRCX database
        if len(friends) < 200:  # Likely incomplete
            print("  API returned limited friends, checking VRCX database...")
            try:
                import sqlite3
                appdata = os.getenv('APPDATA')
                db_path = os.path.join(appdata, 'VRCX', 'VRCX.sqlite3')
                
                if os.path.exists(db_path):
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    
                    # Find friend table (first account only)
                    cursor.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name LIKE '%friend_log_current'
                    """)
                    
                    friend_tables = cursor.fetchall()
                    if friend_tables:
                        table_name = friend_tables[0][0]
                        cursor.execute(f"SELECT user_id, display_name FROM {table_name}")
                        
                        for user_id, display_name in cursor.fetchall():
                            if user_id not in friends:
                                friends[user_id] = {
                                    'id': user_id,
                                    'name': display_name or user_id,
                                    'status': 'unknown'
                                }
                        
                        print(f"  Added {len(friends)} total friends from VRCX database")
                    
                    conn.close()
            except Exception as e:
                print(f"  Warning: Could not read VRCX database: {e}")
        
        print(f"✓ Total friends: {len(friends)}\n")
        return friends
    
    def fetch_all_mutuals(self, friend_ids: list, progress_callback=None) -> Dict[str, list]:
        """
        Fetch mutual friends for a list of friend IDs.
        
        Args:
            friend_ids: List of VRChat user IDs
            progress_callback: Optional callback function(current, total, friend_name)
            
        Returns:
            Dictionary mapping friend_id to list of mutual friend IDs
        """
        print(f"🔍 Fetching mutual connections for {len(friend_ids)} friends...")
        print("   (This may take several minutes due to API rate limiting)")
        
        mutuals_data = {}
        total = len(friend_ids)
        
        for i, friend_id in enumerate(friend_ids, 1):
            # Check if stop was requested
            if self.stop_callback and self.stop_callback():
                print(f"\nStopped by user at {i}/{total} friends")
                break
            
            # Call progress callback if provided
            if progress_callback:
                progress_callback(i, total)
            
            if i % 10 == 0 or i == 1:
                print(f"  Progress: {i}/{total} friends processed...")
            
            try:
                # Fetch mutuals for this friend using paginated endpoint
                all_mutuals = []
                offset = 0
                n = 100
                
                while True:
                    response = self.session.get(
                        f"{self.base_url}/users/{friend_id}/mutuals/friends",
                        params={'n': n, 'offset': offset}
                    )
                    
                    if response.status_code == 200:
                        batch = response.json()
                        if not batch or len(batch) == 0:
                            break
                        
                        # Extract just the user IDs
                        mutual_ids = [m.get('id') for m in batch if m.get('id')]
                        all_mutuals.extend(mutual_ids)
                        
                        # If we got fewer than n, we're done
                        if len(batch) < n:
                            break
                        
                        offset += n
                        time.sleep(0.2)  # Brief delay between pages
                        
                    elif response.status_code == 429:
                        print(f"    Rate limited at friend {i}/{total}, waiting 30s...")
                        time.sleep(30)
                        continue
                    else:
                        # Other error, skip this friend
                        break
                
                mutuals_data[friend_id] = all_mutuals
                
                # Rate limiting between friends
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    Error fetching mutuals for friend {i}: {e}")
                mutuals_data[friend_id] = []
                continue
        
        print(f"✓ Completed fetching mutuals for {len(mutuals_data)} friends\n")
        return mutuals_data
    
    def get_mutual_friends(self, friends: Dict):
        """
        Fetch mutual friends using VRChat's /users/{userId}/mutuals/friends endpoint
        This is the same endpoint VRCX uses
        """
        print("🔍 Fetching mutual friends (this will take a while)...")
        print(f"Processing {len(friends)} friends...\n")
        
        edges = {}
        mutual_counts = {}  # Track mutual count per friend
        my_friend_ids = set(friends.keys())
        
        for i, (friend_id, friend_data) in enumerate(friends.items()):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  Progress: {i+1}/{len(friends)} - {friend_data['name']}")
            
            try:
                # Fetch ALL mutual friends with pagination
                all_mutuals = []
                offset = 0
                n = 100
                
                while True:
                    response = self.session.get(
                        f"{self.base_url}/users/{friend_id}/mutuals/friends",
                        params={'n': n, 'offset': offset}
                    )
                    
                    if response.status_code == 200:
                        batch = response.json()
                        if not batch or len(batch) == 0:
                            break
                        
                        all_mutuals.extend(batch)
                        
                        # If we got fewer than n, we're done
                        if len(batch) < n:
                            break
                        
                        offset += n
                        time.sleep(0.3)
                    else:
                        break
                
                if all_mutuals:
                    mutual_count = len(all_mutuals)
                    mutual_counts[friend_id] = mutual_count
                    
                    # Create edges for each mutual friend
                    for mutual_friend in all_mutuals:
                        mutual_id = mutual_friend.get('id')
                        if mutual_id and mutual_id in my_friend_ids and mutual_id != friend_id:
                            edge = tuple(sorted([friend_id, mutual_id]))
                            edges[edge] = edges.get(edge, 0) + 1
                    
                    if mutual_count > 0:
                        print(f"    → {mutual_count} mutuals")
                
                elif response.status_code == 429:
                    print(f"    Rate limited, waiting 30s...")
                    time.sleep(30)
                    continue
                
                # Rate limiting
                time.sleep(0.5)
                
            except Exception as e:
                print(f"    Error: {e}")
                continue
        
        print(f"\n✓ Found {len(edges)} mutual friend connections")
        return edges, mutual_counts

def main():
    print("=" * 60)
    print("VRChat Mutual Friends Fetcher")
    print("Using VRChat API (same endpoint as VRCX)")
    print("=" * 60)
    print()
    
    fetcher = VRChatMutualFetcher()
    
    try:
        # Try to restore existing session first
        if fetcher.load_session():
            print("Using saved session (no login needed)")
        else:
            # Need to login
            username = input("VRChat Username: ")
            password = input("VRChat Password: ")
            my_id = fetcher.login(username, password)
        
        # Get friends
        friends = fetcher.get_friends()
        
        if len(friends) == 0:
            print("No friends found!")
            return
        
        # Get mutual friends
        edges, mutual_counts = fetcher.get_mutual_friends(friends)
        
        # Save results
        output = {
            'friends': {uid: {'id': uid, 'name': data['name']} for uid, data in friends.items()},
            'edges': {f"{u1}|{u2}": 1 for (u1, u2) in edges.keys()},
            'mutual_counts': mutual_counts
        }
        
        # Save to base_dir if specified, otherwise current directory
        output_file = os.path.join(self.base_dir, 'vrcx_mutual_friends.json') if self.base_dir else 'vrcx_mutual_friends.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        print(f"\n✓ Saved to: {output_file}")
        
        # Show top mutual friends
        if mutual_counts:
            print("\nFriends with most mutuals:")
            top_mutuals = sorted(mutual_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for friend_id, count in top_mutuals:
                print(f"  • {friends[friend_id]['name']}: {count} mutual friends")
        
        print("\nDone! Now run:")
        print("   python vrchat_friend_network_visualizer.py --source vrcx_json --open")
        
    except Exception as e:
        print(f"\nError: {e}")

if __name__ == '__main__':
    main()

