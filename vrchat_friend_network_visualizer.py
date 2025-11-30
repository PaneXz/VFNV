"""
VRChat Friend Network Visualizer

This script creates an interactive visualization of your VRChat mutual friend network
from VRCX data or VRChat API data.

Usage:
    python vrchat_friend_network_visualizer.py --source vrcx
    python vrchat_friend_network_visualizer.py --source api --username YOUR_USERNAME --password YOUR_PASSWORD
"""

import sqlite3
import json
import argparse
import os
import math
import random
import colorsys
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple
import webbrowser

try:
    import networkx as nx
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import requests
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'networkx', 'plotly', 'requests'])
    import networkx as nx
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import requests


class VRCXDataParser:
    """Parse friend and mutual friend data from VRCX SQLite database"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            # Default VRCX database location
            appdata = os.getenv('APPDATA')
            db_path = os.path.join(appdata, 'VRCX', 'VRCX.sqlite3')
        
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"VRCX database not found at: {db_path}")
    
    def get_friends(self) -> Dict[str, dict]:
        """Extract friends data from VRCX database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        friends = {}
        
        try:
            # Query friends from the database
            # VRCX stores friends in various tables - we'll try common ones
            cursor.execute("""
                SELECT DISTINCT userId, displayName, currentAvatarImageUrl, statusDescription
                FROM friends
                WHERE userId IS NOT NULL
            """)
            
            for row in cursor.fetchall():
                user_id, display_name, avatar_url, status = row
                friends[user_id] = {
                    'id': user_id,
                    'name': display_name or user_id,
                    'avatar': avatar_url,
                    'status': status
                }
        except sqlite3.OperationalError as e:
            print(f"Note: Could not query friends table: {e}")
            print("Trying alternative method...")
            
            # Try reading from cached API responses if direct table doesn't work
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            print(f"Available tables: {[t[0] for t in tables]}")
        
        conn.close()
        return friends
    
    def get_mutual_friends(self, friends: Dict[str, dict]) -> Dict[str, Set[str]]:
        """
        Get mutual friend relationships.
        Returns a dictionary mapping user_id to set of mutual friend user_ids
        """
        # This is a simplified version - VRCX may store this data differently
        # You may need to make API calls to get actual mutual friends
        mutuals = {}
        
        # For now, we'll create a placeholder structure
        # In reality, you'd query the VRChat API for each friend to get their friends
        print("Note: Mutual friend data requires VRChat API access")
        print("      This script can be extended to fetch that data with authentication")
        
        return mutuals


class VRChatAPIParser:
    """Parse friend and mutual friend data from VRChat API"""
    
    def __init__(self, username: str = None, password: str = None):
        self.base_url = "https://api.vrchat.cloud/api/1"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'VRChatFriendNetworkVisualizer/1.0 (Contact: github.com/vrchat-network-viz)'
        })
        self.session_file = 'vrchat_session.pkl'
        
        # Try to load existing session first
        if self.load_session():
            print("Using saved session\n")
        elif username and password:
            self.login(username, password)
    
    def save_session(self):
        """Save session cookies to file"""
        import pickle
        with open(self.session_file, 'wb') as f:
            pickle.dump(self.session.cookies, f)
        print("Session saved for future use")
    
    def load_session(self):
        """Load session cookies from file"""
        import pickle
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'rb') as f:
                    self.session.cookies.update(pickle.load(f))
                
                # Test if session is still valid
                response = self.session.get(f"{self.base_url}/auth/user")
                if response.status_code == 200:
                    data = response.json()
                    print(f"Restored session for {data.get('displayName', 'User')}")
                    return True
                else:
                    os.remove(self.session_file)
                    return False
            except:
                if os.path.exists(self.session_file):
                    os.remove(self.session_file)
                return False
        return False
    
    def login(self, username: str, password: str):
        """Login to VRChat API"""
        # VRChat API requires getting user info with basic auth first
        import base64
        
        # Step 1: Get config to initialize session properly
        try:
            config_response = self.session.get(f"{self.base_url}/config")
            if config_response.status_code != 200:
                print(f"Warning: Config fetch returned {config_response.status_code}")
        except Exception as e:
            print(f"Warning: Config fetch failed: {e}")
        
        # Step 2: Create basic auth header
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.session.headers.update({
            'Authorization': f'Basic {credentials}'
        })
        
        try:
            response = self.session.get(f"{self.base_url}/auth/user")
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if 2FA is required
                if 'requiresTwoFactorAuth' in data and any(data.get('requiresTwoFactorAuth', [])):
                    print("\nTwo-factor authentication required")
                    code = input("Enter your 2FA code: ")
                    self.verify_2fa(code)
                    
                    # Re-fetch user info after 2FA
                    response = self.session.get(f"{self.base_url}/auth/user")
                    data = response.json()
                
                print(f"Logged in successfully as {data.get('displayName', 'User')}")
                self.save_session()
                
            else:
                raise Exception(f"{response.status_code} - {response.text}")
                
        except Exception as e:
            raise Exception(f"Login failed: {e}")
    
    def verify_2fa(self, code: str):
        """Verify two-factor authentication"""
        response = self.session.post(
            f"{self.base_url}/auth/twofactorauth/totp/verify",
            json={'code': code}
        )
        
        if response.status_code != 200:
            print(f"2FA response: {response.status_code} - {response.text}")
            raise Exception("2FA verification failed")
    
    def get_my_user_id(self) -> str:
        """Get the current authenticated user's ID"""
        try:
            response = self.session.get(f"{self.base_url}/auth/user")
            if response.status_code == 200:
                return response.json().get('id', '')
        except:
            pass
        return ''
    
    def get_friends(self) -> Dict[str, dict]:
        """Get list of friends from VRChat API"""
        friends = {}
        offset = 0
        n = 60  # VRChat API has a limit, try smaller batches
        
        print("Fetching friends...")
        
        while True:
            response = self.session.get(
                f"{self.base_url}/auth/user/friends",
                params={'offset': offset, 'n': n, 'offline': 'true'}
            )
            
            if response.status_code != 200:
                print(f"  API returned status {response.status_code}, stopping...")
                break
            
            data = response.json()
            if not data or not isinstance(data, list) or len(data) == 0:
                break
            
            batch_count = len(data)
            for friend in data:
                user_id = friend.get('id')
                if user_id:
                    friends[user_id] = {
                        'id': user_id,
                        'name': friend.get('displayName', ''),
                        'status': friend.get('status', ''),
                        'statusDescription': friend.get('statusDescription', ''),
                        'tags': friend.get('tags', [])
                    }
            
            print(f"  Loaded {len(friends)} friends so far (this batch: {batch_count})...")
            
            # If we got less than a full page, we're done
            if len(data) < n:
                break
                
            offset += n
            
            # Add a small delay between requests
            import time
            time.sleep(0.5)
            
            # Safety limit to prevent infinite loops
            if offset > 10000:
                print("  Reached safety limit, stopping...")
                break
        
        print(f"Total friends: {len(friends)}")
        return friends
    
    def get_my_user_id(self) -> str:
        """Get the current user's ID"""
        try:
            response = self.session.get(f"{self.base_url}/auth/user")
            if response.status_code == 200:
                return response.json().get('id')
        except:
            pass
        return None
    
    def get_mutual_friends(self, friends: Dict[str, dict]) -> Dict[Tuple[str, str], int]:
        """
        Get mutual friend relationships using VRChat's /users/{userId}/mutuals/friends endpoint.
        This is the same endpoint VRCX uses.
        """
        print("\nFetching mutual friends data using VRChat API...")
        print(f"Processing {len(friends)} friends...\n")
        
        edges = {}
        my_friend_ids = set(friends.keys())
        
        for i, (friend_id, friend_data) in enumerate(friends.items()):
            if (i + 1) % 10 == 0 or i == 0:
                print(f"  Progress: {i+1}/{len(friends)} - {friend_data['name']}")
            
            try:
                # Use VRChat's mutual friends endpoint (same as VRCX)
                response = self.session.get(
                    f"{self.base_url}/users/{friend_id}/mutuals/friends",
                    params={'n': 100, 'offset': 0}  # Can paginate if needed
                )
                
                if response.status_code == 200:
                    mutual_friends = response.json()
                    
                    if isinstance(mutual_friends, list):
                        # Create edges for each mutual friend
                        for mutual_friend in mutual_friends:
                            mutual_id = mutual_friend.get('id')
                            if mutual_id and mutual_id in my_friend_ids and mutual_id != friend_id:
                                edge = tuple(sorted([friend_id, mutual_id]))
                                edges[edge] = edges.get(edge, 0) + 1
                        
                        if len(mutual_friends) > 0:
                            print(f"    Found {len(mutual_friends)} mutuals")
                
                # Rate limiting
                import time
                time.sleep(0.5)
                
            except Exception as e:
                continue
        
        print(f"\nFound {len(edges)} mutual friend connections")
        return edges


class FriendNetworkVisualizer:
    """Create interactive network visualization of friends"""
    
    def __init__(self, friends: Dict[str, dict], edges: Dict[Tuple[str, str], int] = None):
        self.friends = friends
        self.edges = edges or {}
        self.graph = nx.Graph()
        self._build_graph()
    
    def _build_graph(self):
        """Build NetworkX graph from friends and edges"""
        # Add nodes
        for user_id, data in self.friends.items():
            self.graph.add_node(user_id, **data)
        
        # Add edges
        for (user1, user2), weight in self.edges.items():
            if user1 in self.graph and user2 in self.graph:
                self.graph.add_edge(user1, user2, weight=weight)
        
        print(f"\nNetwork stats:")
        print(f"  Nodes (friends): {self.graph.number_of_nodes()}")
        print(f"  Edges (mutual connections): {self.graph.number_of_edges()}")
        
        if self.graph.number_of_nodes() > 0:
            print(f"  Network density: {nx.density(self.graph):.3f}")
            
            if self.graph.number_of_edges() > 0:
                # Find connected components
                components = list(nx.connected_components(self.graph))
                print(f"  Connected components: {len(components)}")
                print(f"  Largest component size: {len(max(components, key=len))}")
    
    def calculate_metrics(self):
        """Calculate network analysis metrics"""
        if self.graph.number_of_edges() == 0:
            return {}
        
        metrics = {}
        
        # Degree centrality - who has the most connections
        degree_cent = nx.degree_centrality(self.graph)
        
        # Betweenness centrality - who connects different groups
        betweenness_cent = nx.betweenness_centrality(self.graph)
        
        # Community detection
        communities = nx.community.greedy_modularity_communities(self.graph)
        
        # Map nodes to communities
        node_to_community = {}
        for idx, community in enumerate(communities):
            for node in community:
                node_to_community[node] = idx
        
        return {
            'degree_centrality': degree_cent,
            'betweenness_centrality': betweenness_cent,
            'communities': node_to_community,
            'num_communities': len(communities)
        }
    
    def create_visualization(self, output_file: str = 'vrchat_friend_network.html', dark_mode: bool = False):
        """Create interactive Plotly visualization"""
        
        if self.graph.number_of_nodes() == 0:
            print("No friends data to visualize!")
            return
        
        print("\nGenerating visualization...")
        
        # Use ALL nodes - no exclusions
        all_nodes = list(self.graph.nodes())
        
        isolated_nodes = [node for node in all_nodes if self.graph.degree(node) == 0]
        connected_nodes = [node for node in all_nodes if self.graph.degree(node) > 0]
        
        print(f"Visualizing {len(all_nodes)} total nodes ({len(connected_nodes)} connected, {len(isolated_nodes)} isolated)")
        
        # Include ALL nodes in layout - isolated nodes will naturally drift to edges
        layout_nodes = all_nodes
        
        # Use Louvain method for better community detection with higher resolution
        print("Detecting communities with Louvain method...")
        try:
            import community as community_louvain
            partition = community_louvain.best_partition(self.graph.subgraph(connected_nodes), resolution=1.5)
            
            communities_dict = {}
            for node, comm_id in partition.items():
                if comm_id not in communities_dict:
                    communities_dict[comm_id] = set()
                communities_dict[comm_id].add(node)
            communities = [communities_dict[i] for i in sorted(communities_dict.keys())]
            print(f"  Louvain detected {len(communities)} communities")
        except ImportError:
            print("  Louvain not available, using label propagation...")
            communities = list(nx.community.label_propagation_communities(self.graph.subgraph(connected_nodes)))
            print(f"  Label propagation detected {len(communities)} communities")
        
        community_map = {}
        for comm_idx, community in enumerate(communities):
            for node in community:
                community_map[node] = comm_idx
        
        node_primary_community = {}
        node_cross_connectivity = {}
        node_intra_connectivity = {}
        
        print("\nAnalyzing node connectivity patterns...")
        
        for node in connected_nodes:
            neighbors = list(self.graph.neighbors(node))
            total_connections = len(neighbors)
            
            if total_connections == 0:
                continue
            
            algo_community_connections = {}
            for neighbor in neighbors:
                neighbor_comm = community_map.get(neighbor, -1)
                algo_community_connections[neighbor_comm] = algo_community_connections.get(neighbor_comm, 0) + 1
            
            primary_community = max(algo_community_connections.items(), key=lambda x: x[1])[0]
            node_primary_community[node] = primary_community
            
            connections_in_primary = algo_community_connections.get(primary_community, 0)
            connections_outside = total_connections - connections_in_primary
            cross_ratio = connections_outside / total_connections
            node_cross_connectivity[node] = cross_ratio
            
            community_size = sum(1 for n in connected_nodes if community_map.get(n) == primary_community)
            intra_ratio = connections_in_primary / max(community_size - 1, 1)
            node_intra_connectivity[node] = intra_ratio
        
        # Calculate layout
        pos = {}
        
        if len(connected_nodes) > 0:
            import math
        
        # Pre-calculate node sizes for layout algorithm - ALL NODES
        node_visual_sizes = {}
        for node in layout_nodes:
            degree = self.graph.degree(node)
            base_size = 6
            size = base_size + min(degree * 0.2, 20) if degree > 0 else base_size
            node_visual_sizes[node] = size
        
        # Radial layout: more connections = closer to center, 0 connections = outer edge
        print("\nGenerating radial layout based on connection count...")
        
        # Calculate max degree for normalization
        max_degree = max(self.graph.degree(n) for n in layout_nodes) if layout_nodes else 1
        max_radius = 500  # Larger radius for better spread
        
        # First pass: assign radius based on degree
        node_radius = {}
        for node in layout_nodes:
            degree = self.graph.degree(node)
            # More connections = SMALLER radius (closer to center)
            # Max degree (165) -> radius near 0 (center)
            # Min degree (0) -> radius 300 (outer edge)
            if max_degree > 0:
                radius = max_radius * (1.0 - (degree / max_degree))
            else:
                radius = max_radius
            node_radius[node] = radius
        
        print(f"  Max connections ({max_degree}) at center (radius ~0), 0 connections at outer edge (radius {max_radius})")
        
        # Debug: show some example radius assignments
        sample_nodes = sorted([(self.graph.degree(n), n, node_radius[n]) for n in list(layout_nodes)[:10]], reverse=True)[:5]
        print("  Sample radius assignments:")
        for deg, node, rad in sample_nodes:
            node_name = self.graph.nodes[node].get('name', str(node)[:20])
            print(f"    {node_name}: {deg} connections -> radius {rad:.1f}")
        
        # Second pass: position nodes along their radius circle
        # Nodes connected to each other should be close angularly
        print("  Positioning connected nodes near each other along radius circles...")
        
        # Start with random angles distributed around full circle
        import random
        
        # Use detected communities to assign angular regions
        community_list = sorted(set(node_primary_community.values()))
        num_communities = len(community_list)
        
        # Calculate community sizes
        comm_sizes = {}
        for node in layout_nodes:
            if node in node_primary_community:
                comm = node_primary_community[node]
                comm_sizes[comm] = comm_sizes.get(comm, 0) + 1
        
        print(f"  Assigning {num_communities} communities proportionally with gaps")
        print(f"  Community sizes (top 5): {sorted(comm_sizes.items(), key=lambda x: x[1], reverse=True)[:5]}")
        
        # Allocate angles proportionally to community size (with 15% gaps for maximum separation)
        total_nodes = sum(comm_sizes.values())
        usable_angle = 2 * math.pi * 0.85  # 85% for communities, 15% for gaps
        gap_per_community = (2 * math.pi * 0.15) / num_communities
        
        community_base_angles = {}
        community_angle_span = {}
        current_angle = 0
        
        for comm_id in community_list:
            size = comm_sizes.get(comm_id, 1)
            # Angle proportional to community size
            angle_span = (size / total_nodes) * usable_angle
            community_angle_span[comm_id] = angle_span
            # Center of this community's sector
            community_base_angles[comm_id] = current_angle + angle_span / 2
            current_angle += angle_span + gap_per_community
        
        # Calculate radius and size for each node
        node_radius = {}
        node_visual_size = {}
        for node in layout_nodes:
            degree = self.graph.degree(node)
            # More connections = SMALLER radius (closer to center)
            if max_degree > 0:
                radius = max_radius * (1.0 - (degree / max_degree))
            else:
                radius = max_radius
            node_radius[node] = radius
            # Calculate visual size (matching visualization formula)
            base_size = 10
            if degree == 0:
                node_visual_size[node] = base_size
            else:
                node_visual_size[node] = base_size + min(degree * 0.5, 40)
        
        # Calculate cohesion for angle assignment (needed before node_angles)
        temp_node_cohesion = {}
        for node in layout_nodes:
            if node in node_primary_community:
                node_comm = node_primary_community[node]
                neighbors = list(self.graph.neighbors(node))
                if neighbors:
                    same_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) == node_comm]
                    temp_node_cohesion[node] = len(same_comm_neighbors) / len(neighbors)
                else:
                    temp_node_cohesion[node] = 0
            else:
                temp_node_cohesion[node] = 0
        
        node_angles = {}
        for node in layout_nodes:
            if node in node_primary_community:
                comm = node_primary_community[node]
                base_angle = community_base_angles[comm]
                angle_span = community_angle_span[comm]
                
                # Get cohesion for angular positioning within sector
                cohesion = temp_node_cohesion.get(node, 0)
                
                # High cohesion = center of sector angle
                # Low cohesion = edge of sector angle
                # Map cohesion [0,1] to angular offset [-0.5, 0.5] within sector
                # Invert: 1.0 cohesion -> 0.0 offset (center), 0.0 cohesion -> ±0.5 offset (edges)
                center_angle = base_angle + angle_span / 2
                
                # Use 85% of sector to leave gaps at boundaries
                use_span = angle_span * 0.85
                
                # Bridge members (low cohesion) pushed to random edge
                if cohesion < 0.5:
                    # Push to edge: cohesion 0 -> ±0.5, cohesion 0.5 -> ±0.1
                    edge_factor = (0.5 - cohesion) * 2.0  # 0 to 1
                    edge_direction = random.choice([-1, 1])  # Random edge
                    angular_offset = edge_direction * edge_factor * 0.5 * use_span
                else:
                    # High cohesion stays near center
                    # cohesion 0.5 -> ±0.1, cohesion 1.0 -> ±0.02
                    center_factor = (cohesion - 0.5) * 2.0  # 0 to 1
                    angular_offset = random.uniform(-0.1, 0.1) * (1.0 - center_factor) * use_span
                
                node_angles[node] = center_angle + angular_offset
            else:
                # Isolated nodes distributed around full circle
                isolated_list = [n for n in layout_nodes if n not in node_primary_community]
                if node in isolated_list:
                    idx = isolated_list.index(node)
                    node_angles[node] = (idx / max(len(isolated_list), 1)) * 2 * math.pi
                else:
                    node_angles[node] = random.uniform(0, 2 * math.pi)
        
        # Store community angle boundaries for later constraint enforcement
        community_base_angles = {}
        community_angle_span = {}
        current_angle = 0
        for comm in sorted(comm_sizes.keys(), key=lambda c: comm_sizes[c], reverse=True):
            size = comm_sizes[comm]
            angle_span = (size / total_nodes) * usable_angle
            community_base_angles[comm] = current_angle
            community_angle_span[comm] = angle_span
            current_angle += angle_span + gap_per_community
        
        # Separate isolated nodes (0 connections) from connected nodes
        isolated_nodes = [n for n in layout_nodes if self.graph.degree(n) == 0]
        connected_nodes = [n for n in layout_nodes if self.graph.degree(n) > 0]
        
        # Place isolated nodes in corner grid
        print(f"  Placing {len(isolated_nodes)} isolated nodes in corner grid...")
        grid_size = int(math.ceil(math.sqrt(len(isolated_nodes)))) if isolated_nodes else 0
        grid_spacing = 25
        grid_offset_x = max_radius + 50
        grid_offset_y = max_radius + 50
        
        for idx, node in enumerate(isolated_nodes):
            grid_x = (idx % grid_size) * grid_spacing + grid_offset_x
            grid_y = (idx // grid_size) * grid_spacing + grid_offset_y
            pos[node] = (grid_x, grid_y)
        
        # Reuse cohesion calculated earlier for angle assignment
        print("  Using cohesion scores for anchor selection...")
        node_cohesion = temp_node_cohesion
        
        # Sort by cohesion FIRST (high cohesion = community core), then by degree
        # This ensures bridge members don't become anchors
        print("  Sorting nodes by cohesion (community core members first)...")
        nodes_by_cohesion = sorted(connected_nodes, 
                                   key=lambda n: (node_cohesion.get(n, 0), self.graph.degree(n)), 
                                   reverse=True)
        
        # Phase 1: Position high-cohesion anchor nodes first (top 10%)
        num_anchors = max(1, len(nodes_by_cohesion) // 10)
        anchor_nodes = nodes_by_cohesion[:num_anchors]
        remaining_nodes = nodes_by_cohesion[num_anchors:]
        
        if anchor_nodes:
            print(f"  Selected {num_anchors} high-cohesion anchors (cohesion {node_cohesion[anchor_nodes[0]]:.0%} to {node_cohesion[anchor_nodes[-1]]:.0%})...")
        
        print(f"  Placing {num_anchors} anchor nodes (high connectivity) evenly in space...")
        # Anchors get their initial polar positions with jitter for organic look
        for node in anchor_nodes:
            radius = node_radius[node]
            angle = node_angles[node]
            
            # Add radial jitter (±45%) to break up perfect circles
            radial_jitter = random.uniform(-0.45, 0.45) * radius
            adjusted_radius = max(0, radius + radial_jitter)
            
            x = adjusted_radius * math.cos(angle)
            y = adjusted_radius * math.sin(angle)
            pos[node] = (x, y)
        
        # Calculate community centers from anchor nodes
        community_centers = {}
        for comm in set(node_primary_community.values()):
            comm_anchors = [n for n in anchor_nodes if node_primary_community.get(n) == comm]
            if comm_anchors:
                center_x = sum(pos[n][0] for n in comm_anchors) / len(comm_anchors)
                center_y = sum(pos[n][1] for n in comm_anchors) / len(comm_anchors)
                community_centers[comm] = (center_x, center_y)
        
        # Phase 2: Position remaining nodes by cohesion (high cohesion near center, low at edges)
        print(f"  Placing {len(remaining_nodes)} remaining nodes weighted by cohesion...")
        for node in remaining_nodes:
            cohesion = node_cohesion.get(node, 0)  # Use pre-calculated cohesion
            node_comm = node_primary_community.get(node)
            neighbors = [n for n in self.graph.neighbors(node) if n in pos]
            
            if neighbors and node_comm is not None:
                # Use pre-calculated cohesion to determine positioning strategy
                same_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) == node_comm]
                cross_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) != node_comm]
                
                if same_comm_neighbors:
                    # Position based on same-community connections
                    same_comm_x = sum(pos[n][0] for n in same_comm_neighbors) / len(same_comm_neighbors)
                    same_comm_y = sum(pos[n][1] for n in same_comm_neighbors) / len(same_comm_neighbors)
                    
                    comm_center_x, comm_center_y = community_centers.get(node_comm, (0, 0))
                    
                    # High cohesion = strong pull to community center
                    # Low cohesion = position more toward cross-community connections
                    if cross_comm_neighbors and cohesion < 0.7:
                        # Bridge member - blend with cross-community neighbors
                        cross_comm_x = sum(pos[n][0] for n in cross_comm_neighbors) / len(cross_comm_neighbors)
                        cross_comm_y = sum(pos[n][1] for n in cross_comm_neighbors) / len(cross_comm_neighbors)
                        
                        # Weight: very low cohesion gets pushed heavily toward cross-community
                        center_weight = cohesion * cohesion * 0.1  # Squared for stronger dropoff
                        same_weight = cohesion * 0.4
                        cross_weight = (1 - cohesion) * 1.2  # Amplified cross-community pull
                        
                        total_weight = center_weight + same_weight + cross_weight
                        centroid_x = (comm_center_x * center_weight + same_comm_x * same_weight + cross_comm_x * cross_weight) / total_weight
                        centroid_y = (comm_center_y * center_weight + same_comm_y * same_weight + cross_comm_y * cross_weight) / total_weight
                    else:
                        # Strong community member - pull heavily toward center
                        # Higher cohesion = stronger center clustering
                        # Calculate intra-community strength for extra center pull
                        intra_connections_temp = len(same_comm_neighbors)
                        center_weight = cohesion * 0.9  # Very strong center pull for high cohesion
                        same_weight = 0.1
                        
                        centroid_x = comm_center_x * center_weight + same_comm_x * same_weight
                        centroid_y = comm_center_y * center_weight + same_comm_y * same_weight
                else:
                    # No same-community neighbors, use community center only
                    centroid_x, centroid_y = community_centers.get(node_comm, (0, 0))
                    
                    # If community center is at origin, use polar with heavy jitter
                    if centroid_x == 0 and centroid_y == 0:
                        angle = node_angles[node]
                        # Add very strong angular jitter to avoid straight lines
                        angle_jitter = random.uniform(-0.25, 0.25)  # ±14 degrees
                        angle = angle + angle_jitter
                        centroid_x = 100 * math.cos(angle)  # Arbitrary radius for centroid calculation
                        centroid_y = 100 * math.sin(angle)
                
                # Adjust to maintain target radial distance, modified by cohesion
                # High cohesion = pull toward center (reduce radius)
                # Low cohesion = push toward periphery (increase radius)
                base_radius = node_radius[node]
                
                # Calculate intra-community connection strength for tighter clustering
                intra_connections = len(same_comm_neighbors)
                max_intra = max([len([n for n in self.graph.neighbors(cn) if node_primary_community.get(n) == node_comm]) 
                                for cn in connected_nodes if node_primary_community.get(cn) == node_comm], default=1)
                intra_strength = intra_connections / max_intra if max_intra > 0 else 0
                
                # Cohesion modifier: High connectivity members pulled MUCH tighter to center
                # 100% cohesion + high intra = 0.3x radius, 0% cohesion = 1.5x radius
                combined_centrality = cohesion * 0.7 + intra_strength * 0.3
                cohesion_modifier = 0.3 + (1.0 - combined_centrality) * 1.2
                target_radius = base_radius * cohesion_modifier
                
                current_radius = math.sqrt(centroid_x**2 + centroid_y**2)
                
                if current_radius > 0:
                    # Reduce jitter for high-connectivity members to maintain clustering
                    # High intra_strength = less jitter (±10%), low = more jitter (±30%)
                    jitter_amount = 0.10 + (1.0 - intra_strength) * 0.20
                    radial_jitter = random.uniform(-jitter_amount, jitter_amount) * target_radius
                    adjusted_radius = max(0, target_radius + radial_jitter)
                    
                    scale = adjusted_radius / current_radius
                    x = centroid_x * scale
                    y = centroid_y * scale
                    
                    # Add stronger angular jitter for better spread
                    current_angle = math.atan2(y, x)
                    angle_jitter = random.uniform(-0.35, 0.35)  # ±0.35 radians (~±20 degrees)
                    jittered_angle = current_angle + angle_jitter
                    jittered_radius = math.sqrt(x*x + y*y)
                    x = jittered_radius * math.cos(jittered_angle)
                    y = jittered_radius * math.sin(jittered_angle)
                    
                    # Enforce angular constraint: clamp to community sector
                    angle = math.atan2(y, x)
                    base_angle = community_base_angles[node_comm]
                    angle_span = community_angle_span[node_comm]
                    min_angle = base_angle
                    max_angle = base_angle + angle_span
                    
                    # Normalize angles to [0, 2*pi]
                    angle = angle % (2 * math.pi)
                    min_angle = min_angle % (2 * math.pi)
                    max_angle = max_angle % (2 * math.pi)
                    
                    # Clamp angle to sector
                    if min_angle < max_angle:
                        if angle < min_angle:
                            angle = min_angle + 0.01
                        elif angle > max_angle:
                            angle = max_angle - 0.01
                    else:  # Sector wraps around 0
                        if angle > max_angle and angle < min_angle:
                            # Choose closer boundary
                            if abs(angle - max_angle) < abs(angle - min_angle):
                                angle = max_angle - 0.01
                            else:
                                angle = min_angle + 0.01
                    
                    # Recalculate position with constrained angle and jittered radius
                    # Add radial jitter even after angle constraint
                    final_radius = target_radius + random.uniform(-target_radius * 0.20, target_radius * 0.20)
                    final_radius = max(0, final_radius)
                    x = final_radius * math.cos(angle)
                    y = final_radius * math.sin(angle)
                else:
                    # Current radius is 0, use polar with heavy jitter
                    angle = node_angles[node] + random.uniform(-0.3, 0.3)
                    jittered_radius = target_radius + random.uniform(-target_radius * 0.30, target_radius * 0.30)
                    jittered_radius = max(0, jittered_radius)
                    x = jittered_radius * math.cos(angle)
                    y = jittered_radius * math.sin(angle)
                
                pos[node] = (x, y)
            else:
                # No positioned neighbors yet, use polar position with heavy jitter
                radius = node_radius[node]
                angle = node_angles[node]
                # Add very strong jitter to avoid radial lines
                angle_jitter = random.uniform(-0.3, 0.3)  # ±17 degrees
                radial_jitter = random.uniform(-0.35, 0.35) * radius
                jittered_angle = angle + angle_jitter
                jittered_radius = max(0, radius + radial_jitter)
                x = jittered_radius * math.cos(jittered_angle)
                y = jittered_radius * math.sin(jittered_angle)
                pos[node] = (x, y)
        
        # Phase 3: Refinement pass with strict community clustering
        print("  Refining positions with 60 iterations focusing on connection proximity...")
        for iteration in range(60):
            new_pos = {}
            for node in connected_nodes:
                node_comm = node_primary_community.get(node)
                neighbors = [n for n in self.graph.neighbors(node) if n in pos]
                if not neighbors:
                    new_pos[node] = pos[node]
                    continue
                
                # ONLY use same-community neighbors
                same_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) == node_comm]
                
                # Calculate cohesion for this node
                if same_comm_neighbors:
                    cohesion = len(same_comm_neighbors) / len(neighbors)
                else:
                    cohesion = 0
                
                if same_comm_neighbors and node_comm in community_centers:
                    # Calculate same-community neighbor centroid
                    centroid_x = sum(pos[n][0] for n in same_comm_neighbors) / len(same_comm_neighbors)
                    centroid_y = sum(pos[n][1] for n in same_comm_neighbors) / len(same_comm_neighbors)
                    
                    comm_center_x, comm_center_y = community_centers[node_comm]
                    curr_x, curr_y = pos[node]
                    
                    # Cohesion-based attraction: high cohesion = strong center pull, low = weak
                    if node in anchor_nodes:
                        # Anchors stay stable
                        comm_strength = 0.05 * (cohesion ** 2)  # Squared for stronger dropoff
                        neighbor_strength = 0.12
                    else:
                        # Regular nodes: squared cohesion for aggressive periphery push
                        # Higher cohesion = much stronger center pull for tight clustering
                        comm_strength = 0.6 * (cohesion ** 2)  # 0-60% based on squared cohesion
                        neighbor_strength = 0.4  # Reduced neighbor pull to allow center clustering
                    
                    target_x = curr_x + (comm_center_x - curr_x) * comm_strength + (centroid_x - curr_x) * neighbor_strength
                    target_y = curr_y + (comm_center_y - curr_y) * comm_strength + (centroid_y - curr_y) * neighbor_strength
                    
                    # For very low cohesion (<40%), add repulsion from community center
                    if cohesion < 0.4:
                        repulsion_strength = (0.4 - cohesion) * 0.5  # 0-20% repulsion
                        target_x += (curr_x - comm_center_x) * repulsion_strength
                        target_y += (curr_y - comm_center_y) * repulsion_strength
                else:
                    # No same-community neighbors, just maintain position
                    target_x, target_y = pos[node]
                
                # Allow radial flexibility (40%-160%) for organic look, modified by cohesion
                base_radius = node_radius[node]
                cohesion = node_cohesion.get(node, 0)
                # Cohesion modifier: high cohesion = closer to center, low = further out
                cohesion_modifier = 0.7 + (1.0 - cohesion) * 0.6
                target_radius = base_radius * cohesion_modifier
                
                current_radius = math.sqrt(target_x**2 + target_y**2)
                if current_radius > 0:
                    # Allow wide variation around target radius
                    min_radius = target_radius * 0.40
                    max_radius = target_radius * 1.60
                    if current_radius < min_radius:
                        scale = min_radius / current_radius
                    elif current_radius > max_radius:
                        scale = max_radius / current_radius
                    else:
                        scale = 1.0  # Let it stay at natural position
                    
                    new_x = target_x * scale
                    new_y = target_y * scale
                    
                    # Enforce angular constraint: keep within community sector with variance
                    if node_comm in community_base_angles:
                        angle = math.atan2(new_y, new_x)
                        base_angle = community_base_angles[node_comm]
                        angle_span = community_angle_span[node_comm]
                        min_angle = base_angle
                        max_angle = base_angle + angle_span
                        
                        # Normalize angles
                        angle = angle % (2 * math.pi)
                        min_angle = min_angle % (2 * math.pi)
                        max_angle = max_angle % (2 * math.pi)
                        
                        # Soft boundary - add random offset instead of hard clamp
                        if min_angle < max_angle:
                            if angle < min_angle:
                                angle = min_angle + random.uniform(0.02, 0.15)
                            elif angle > max_angle:
                                angle = max_angle - random.uniform(0.02, 0.15)
                        else:
                            if angle > max_angle and angle < min_angle:
                                if abs(angle - max_angle) < abs(angle - min_angle):
                                    angle = max_angle - random.uniform(0.02, 0.15)
                                else:
                                    angle = min_angle + random.uniform(0.02, 0.15)
                        
                        # Recalculate with constrained angle but flexible radius
                        angle_radius = math.sqrt(new_x**2 + new_y**2)
                        new_x = angle_radius * math.cos(angle)
                        new_y = angle_radius * math.sin(angle)
                else:
                    new_x, new_y = pos[node]
                
                new_pos[node] = (new_x, new_y)
            
            pos.update(new_pos)
        
        # Phase 4: Add repulsion forces to prevent overlap (only for connected nodes)
        print("  Applying collision prevention with cross-community intermingling (80 iterations)...")
        for iteration in range(80):
            new_pos = {}
            for node in connected_nodes:
                curr_x, curr_y = pos[node]
                node_size = node_visual_size[node]
                node_comm = node_primary_community.get(node)
                
                # Calculate node's cross-community ratio
                neighbors = list(self.graph.neighbors(node))
                same_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) == node_comm]
                node_cross_ratio = 1.0 - (len(same_comm_neighbors) / len(neighbors)) if neighbors else 0
                
                # Calculate repulsion from nearby nodes
                repulsion_x = 0
                repulsion_y = 0
                
                for other_node in connected_nodes:
                    if node == other_node:
                        continue
                    
                    other_x, other_y = pos[other_node]
                    other_size = node_visual_size[other_node]
                    other_comm = node_primary_community.get(other_node)
                    
                    # Distance between nodes
                    dx = curr_x - other_x
                    dy = curr_y - other_y
                    dist = math.sqrt(dx*dx + dy*dy)
                    
                    # Keep strict separation - no special treatment based on cross-ratio
                    if node_comm != other_comm:
                        min_dist = (node_size + other_size) * 2.0  # 2x separation for different communities
                    else:
                        min_dist = (node_size + other_size) * 1.3  # 1.3x for same community
                    
                    if dist < min_dist and dist > 0:
                        # Push apart proportional to overlap
                        overlap = min_dist - dist
                        force = overlap / dist
                        repulsion_x += dx * force
                        repulsion_y += dy * force
                
                # Apply repulsion (reduced for natural spread)
                new_x = curr_x + repulsion_x * 0.08
                new_y = curr_y + repulsion_y * 0.08
                
                # Allow radial flexibility (40%-160%) for organic distribution
                target_radius = node_radius[node]
                current_radius = math.sqrt(new_x**2 + new_y**2)
                if current_radius > 0:
                    min_radius = target_radius * 0.40
                    max_radius = target_radius * 1.60
                    if current_radius < min_radius:
                        scale = min_radius / current_radius
                    elif current_radius > max_radius:
                        scale = max_radius / current_radius
                    else:
                        scale = 1.0
                    
                    new_x *= scale
                    new_y *= scale
                    
                    # Allow boundary crossing for heavily split members based on friend balance
                    # Only affect angular position, not separation distance
                    if node_comm in community_base_angles and node_cross_ratio > 0.5:
                        # Node is heavily split (>50% cross-community)
                        angle = math.atan2(new_y, new_x)
                        base_angle = community_base_angles[node_comm]
                        angle_span = community_angle_span[node_comm]
                        
                        # Calculate which communities this node connects to most
                        cross_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) != node_comm]
                        cross_comm_counts = {}
                        for n in cross_comm_neighbors:
                            other_comm = node_primary_community.get(n)
                            if other_comm is not None:
                                cross_comm_counts[other_comm] = cross_comm_counts.get(other_comm, 0) + 1
                        
                        # Find the most connected cross-community
                        if cross_comm_counts:
                            top_cross_comm = max(cross_comm_counts.items(), key=lambda x: x[1])[0]
                            cross_connections = cross_comm_counts[top_cross_comm]
                            
                            # Calculate balance ratio between primary and top cross-community
                            same_count = len(same_comm_neighbors)
                            total_connections = len(neighbors)
                            
                            # Only shift if:
                            # 1. Cross-community has MORE connections than primary (balance > 50%)
                            # 2. AND it represents a significant portion of total connections (>40%)
                            balance_ratio = cross_connections / (same_count + cross_connections) if (same_count + cross_connections) > 0 else 0
                            cross_percentage = cross_connections / total_connections if total_connections > 0 else 0
                            
                            if balance_ratio > 0.5 and cross_percentage > 0.4 and top_cross_comm in community_base_angles:
                                target_angle = community_base_angles[top_cross_comm]
                                target_span = community_angle_span[top_cross_comm]
                                target_center = target_angle + target_span / 2
                                
                                # Shift angle proportionally toward cross-community center
                                # balance_ratio 0.5 = minimal shift, 1.0 = maximum shift
                                shift_amount = (balance_ratio - 0.5) / 0.5  # 0 to 1
                                
                                current_center = base_angle + angle_span / 2
                                # Interpolate between current and target community centers
                                # Stronger shift only when significantly more connected to other group
                                new_center = current_center + (target_center - current_center) * shift_amount * 0.5
                                
                                # Calculate new position at this shifted angle
                                angle_radius = math.sqrt(new_x**2 + new_y**2)
                                new_x = angle_radius * math.cos(new_center)
                                new_y = angle_radius * math.sin(new_center)
                    elif node_comm in community_base_angles:
                        # Normal boundary enforcement for non-split members
                        angle = math.atan2(new_y, new_x)
                        base_angle = community_base_angles[node_comm]
                        angle_span = community_angle_span[node_comm]
                        min_angle = base_angle
                        max_angle = base_angle + angle_span
                        
                        angle = angle % (2 * math.pi)
                        min_angle = min_angle % (2 * math.pi)
                        max_angle = max_angle % (2 * math.pi)
                        
                        # Soft boundary with random variance
                        if min_angle < max_angle:
                            if angle < min_angle:
                                angle = min_angle + random.uniform(0.02, 0.15)
                            elif angle > max_angle:
                                angle = max_angle - random.uniform(0.02, 0.15)
                        else:
                            if angle > max_angle and angle < min_angle:
                                if abs(angle - max_angle) < abs(angle - min_angle):
                                    angle = max_angle - random.uniform(0.02, 0.15)
                                else:
                                    angle = min_angle + random.uniform(0.02, 0.15)
                        
                        # Recalculate with constrained angle but flexible radius
                        angle_radius = math.sqrt(new_x**2 + new_y**2)
                        new_x = angle_radius * math.cos(angle)
                        new_y = angle_radius * math.sin(angle)
                
                new_pos[node] = (new_x, new_y)
            
            pos.update(new_pos)
        
        print("Layout complete!")
        
        # Skip collision resolution to maintain perfect radial structure
        print("\nSkipping collision resolution to preserve radial layout")
        
        # Create edges trace with edge mapping for JavaScript interaction
        edge_x = []
        edge_y = []
        edge_list = []  # Store edge endpoints for JavaScript
        
        for edge in self.graph.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            edge_list.append([edge[0], edge[1]])
        
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            mode='lines',
            name='Mutual Friends',
            opacity=0.15
        )
        
        # Create nodes trace
        node_x = []
        node_y = []
        node_text = []
        node_size = []
        node_color = []
        
        # Generate highly distinct colors for communities
        import colorsys
        num_communities = len(set(node_primary_community.values())) if node_primary_community else 1
        community_colors_rgb = []
        
        # Use golden ratio for better color distribution
        golden_ratio = 0.618033988749895
        for i in range(num_communities):
            hue = (i * golden_ratio) % 1.0  # Golden angle for maximum distinction
            # Very high saturation and brightness for vibrant, highly distinct colors
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)  # Max saturation and value
            # Boost RGB values for ultra-pronounced colors
            rgb = tuple(min(1.0, c * 1.2) for c in rgb)  # 20% boost for maximum vibrancy
            community_colors_rgb.append(f'rgb({int(rgb[0]*255)},{int(rgb[1]*255)},{int(rgb[2]*255)})')
        
        # Assign colors based on communities - bright contrasting colors
        print("\nAssigning colors based on communities...")
        
        num_communities = len(set(node_primary_community.values()))
        print(f"  Using {num_communities} distinct community colors")
        
        golden_ratio = 0.618033988749895
        community_colors_rgb = []
        for i in range(num_communities):
            hue = (i * golden_ratio) % 1.0
            rgb = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            rgb = tuple(min(1.0, c * 1.2) for c in rgb)
            community_colors_rgb.append(f'rgb({int(rgb[0]*255)},{int(rgb[1]*255)},{int(rgb[2]*255)})')
        
        # Build visualization data
        for node in all_nodes:
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            
            data = self.graph.nodes[node]
            name = data.get('name', node)
            degree = self.graph.degree(node)
            
            # Node size based on total degree (number of connections)
            # More connected overall = larger
            base_size = 6  # Reduced from 10 to 6
            if degree == 0:
                node_size.append(base_size)
            else:
                # Scale by degree: more connections = bigger, but controlled
                size = base_size + min(degree * 0.3, 24)  # Reduced multiplier from 0.5 to 0.3, max from 40 to 24
                node_size.append(size)
            
            # Node color - use community color directly
            if degree == 0:
                # Dark gray for isolated nodes
                node_color.append('rgb(60,60,60)')
            else:
                # Use primary community color
                if node in node_primary_community:
                    comm = node_primary_community[node]
                    node_color.append(community_colors_rgb[comm % len(community_colors_rgb)])
                else:
                    node_color.append('rgb(200,200,200)')
            
            # Hover text with detailed metrics
            hover_text = f"<b>{name}</b><br>"
            hover_text += f"Total connections: {degree}<br>"
            
            # Calculate meaningful positioning metrics
            if degree > 0 and node in node_primary_community:
                comm = node_primary_community[node]
                
                # Calculate community cohesion (% of connections within same community)
                same_comm_neighbors = [n for n in self.graph.neighbors(node) if node_primary_community.get(n) == comm]
                cross_comm_neighbors = [n for n in self.graph.neighbors(node) if node_primary_community.get(n) != comm]
                cohesion_pct = (len(same_comm_neighbors) / degree * 100) if degree > 0 else 0
                
                # Explain community assignment
                hover_text += f"<br><b>Community Assignment:</b><br>"
                hover_text += f"In-group connections: {len(same_comm_neighbors)} of {degree}<br>"
                
                if len(same_comm_neighbors) > len(cross_comm_neighbors):
                    hover_text += f"Majority of friends ({cohesion_pct:.0f}%) are in this group<br>"
                elif len(same_comm_neighbors) == len(cross_comm_neighbors):
                    hover_text += f"Evenly split between groups ({cohesion_pct:.0f}% in-group)<br>"
                else:
                    hover_text += f"⚠ Bridge member: Only {cohesion_pct:.0f}% in-group<br>"
                    # Find which other communities they connect to most
                    other_comms = {}
                    for neighbor in cross_comm_neighbors:
                        other_comm = node_primary_community.get(neighbor)
                        if other_comm is not None:
                            other_comms[other_comm] = other_comms.get(other_comm, 0) + 1
                    if other_comms:
                        top_other = sorted(other_comms.items(), key=lambda x: x[1], reverse=True)[0]
                        other_color = community_colors_rgb[top_other[0] % len(community_colors_rgb)]
                        hover_text += f"  {top_other[1]} connections to <span style='color:{other_color};font-weight:bold;text-shadow: -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000, 1px 1px 0 #000;'>group {top_other[0]}</span><br>"
                
                # Calculate community centrality (how centered node is among its group)
                # Use spatial distance from community center in the visualization
                comm_members = [n for n in all_nodes if node_primary_community.get(n) == comm and n in pos]
                if len(comm_members) > 1:
                    # Calculate community center (average position)
                    comm_center_x = sum(pos[n][0] for n in comm_members) / len(comm_members)
                    comm_center_y = sum(pos[n][1] for n in comm_members) / len(comm_members)
                    
                    # Calculate distance from node to community center
                    dist_to_center = math.sqrt((x - comm_center_x)**2 + (y - comm_center_y)**2)
                    
                    # Calculate average distance of all community members to center
                    avg_dist = sum(math.sqrt((pos[n][0] - comm_center_x)**2 + (pos[n][1] - comm_center_y)**2) for n in comm_members) / len(comm_members)
                    
                    # Calculate max distance in community for normalization
                    max_dist = max(math.sqrt((pos[n][0] - comm_center_x)**2 + (pos[n][1] - comm_center_y)**2) for n in comm_members)
                    
                    # Centrality: closer to center = higher percentage
                    # Use inverse distance normalized by max distance
                    if max_dist > 0:
                        centrality_pct = max(0, 100 - (dist_to_center / max_dist * 100))
                    else:
                        centrality_pct = 100
                else:
                    centrality_pct = 100
                
                hover_text += f"<br><b>Community Metrics:</b><br>"
                hover_text += f"Group cohesion: {cohesion_pct:.0f}% (same-group connections)<br>"
                hover_text += f"Group centrality: {centrality_pct:.0f}% (spatial distance to group center)<br>"
                hover_text += f"Network hub score: {(degree/max_degree*100):.0f}% (connection density)<br>"
            elif degree == 0:
                hover_text += f"<br>Isolated (no mutual connections)<br>"
            
            node_text.append(hover_text)
        
        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers',
            hoverinfo='text',
            text=node_text,
            marker=dict(
                size=node_size,
                color=node_color,  # RGB colors by community
                line=dict(width=2, color='white'),  # Thicker white border
                opacity=0.95
            ),
            name='Friends',
            customdata=[[node] for node in self.graph.nodes()],  # Store node ID for click events
            selected=dict(marker=dict(opacity=0.95)),  # Prevent selection styling
            unselected=dict(marker=dict(opacity=0.95))  # Prevent dim on unselected
        )
        
        # Generate community background blobs AFTER all positioning is finalized
        print("  Creating cohesion-based background highlights...")
        community_blob_traces = []
        for comm in set(node_primary_community.values()):
            comm_nodes = [n for n in all_nodes if node_primary_community.get(n) == comm]
            if not comm_nodes:
                continue
            
            # Create density map points based on cohesion using FINAL positions
            blob_x = []
            blob_y = []
            blob_intensity = []
            
            # Create a proper density field by sampling the entire group area
            # For each community member, add density contribution across a wide area
            for node in comm_nodes:
                if node not in pos:
                    continue
                x, y = pos[node]
                
                # Calculate node importance (more internal connections = more important)
                neighbors = list(self.graph.neighbors(node))
                same_comm_neighbors = [n for n in neighbors if node_primary_community.get(n) == comm]
                intra_connections = len(same_comm_neighbors)
                
                # Calculate cohesion percentage
                total_neighbors = len(neighbors)
                if total_neighbors == 0:
                    continue
                    
                cohesion_percent = intra_connections / total_neighbors
                
                # Skip nodes with very low cohesion
                if cohesion_percent < 0.1:
                    continue
                
                # Higher cohesion = more samples and tighter spread = stronger concentrated glow
                # Scale samples: 50% cohesion = 100 samples, 100% cohesion = 500 samples
                num_samples = int(100 + cohesion_percent * 400)
                
                # Higher cohesion = tighter spread = more concentrated bright spot
                # 50% cohesion = 100px spread, 100% cohesion = 40px spread
                spread = 100 - (cohesion_percent * 60)
                
                for _ in range(num_samples):
                    # Gaussian distribution creates natural falloff
                    offset_x = random.gauss(0, spread)
                    offset_y = random.gauss(0, spread)
                    blob_x.append(x + offset_x)
                    blob_y.append(y + offset_y)
                    # Weight by both connectivity and cohesion - creates intense hotspots
                    blob_intensity.append(intra_connections * cohesion_percent)
            
            # Create contour/heatmap trace for this community
            if blob_x and blob_y:
                # Extract RGB values from community color
                rgb_match = community_colors_rgb[comm % len(community_colors_rgb)]
                import re
                rgb_values = re.findall(r'\d+', rgb_match)
                if len(rgb_values) >= 3:
                    r, g, b = int(rgb_values[0]), int(rgb_values[1]), int(rgb_values[2])
                    
                    # Create custom colorscale with more gradual transitions
                    colorscale = [
                        [0, f'rgba({r},{g},{b},0)'],        # Transparent at low intensity
                        [0.3, f'rgba({r},{g},{b},0.15)'],   # Very light
                        [0.6, f'rgba({r},{g},{b},0.35)'],   # Light-medium
                        [0.85, f'rgba({r},{g},{b},0.55)'],  # Medium
                        [1, f'rgba({r},{g},{b},0.75)']      # Most intense
                    ]
                    
                    blob_trace = go.Histogram2d(
                        x=blob_x,
                        y=blob_y,
                        z=blob_intensity,
                        colorscale=colorscale,
                        showscale=False,
                        hoverinfo='skip',
                        nbinsx=50,  # Fewer bins for smoother gradients
                        nbinsy=50,
                        histfunc='sum',  # Sum creates accumulated density
                        name=f'Community {comm} background',
                        opacity=0.6,
                        showlegend=False,
                        visible=True,
                        xaxis='x',
                        yaxis='y',
                        zauto=True,
                        xgap=0,
                        ygap=0,
                        zsmooth='best'  # Critical for smooth appearance
                    )
                    community_blob_traces.append(blob_trace)
        
        # Create figure with backgrounds first (below), then edges, then nodes (top for interaction)
        fig = go.Figure(
            data=community_blob_traces + [edge_trace, node_trace],
            layout=go.Layout(
                title=dict(
                    text=f'<b>VRChat Friend Network</b><br>{len(self.friends)} friends, {self.graph.number_of_edges()} mutual connections<br><i>Click to highlight | Ctrl+Click for multi-select</i>',
                    x=0.5,
                    xanchor='center',
                    font=dict(size=20)
                ),
                showlegend=False,
                autosize=True,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=100),
                annotations=[
                    dict(
                        text="Node size = # of mutual connections | Color = friend community group<br>Click a node to highlight its connections",
                        showarrow=False,
                        xref="paper", yref="paper",
                        x=0.005, y=-0.002,
                        xanchor='left', yanchor='bottom',
                        font=dict(size=12)
                    )
                ],
                xaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    scaleanchor='y',
                    scaleratio=1,
                    range=[-1200, 1200],  # Extra large range to fit everything on screen
                    fixedrange=False
                ),
                yaxis=dict(
                    showgrid=False,
                    zeroline=False,
                    showticklabels=False,
                    range=[-1200, 1200],  # Extra large range to fit everything on screen
                    fixedrange=False
                ),
                plot_bgcolor='#1a1a2e' if dark_mode else 'white',
                clickmode='event',  # Only fire click events, don't select traces
                dragmode='pan'  # Default to pan mode, not select
            )
        )
        
        # Save to HTML with custom JavaScript for click interactions
        html_content = fig.to_html(include_plotlyjs='cdn')
        
        # Add custom JavaScript for node click highlighting with theme toggle
        initial_dark = 'true' if dark_mode else 'false'
        
        custom_js = f"""
<style>
body {{
    margin: 0;
    padding: 0;
    transition: background-color 0.3s, color 0.3s;
}}
html {{
    transition: background-color 0.3s;
}}
body.light-mode {{
    background-color: #ffffff !important;
    color: #333333 !important;
}}
body.dark-mode {{
    background-color: #1a1a2e !important;
    color: #e0e0e0 !important;
}}
html.light-mode {{
    background-color: #ffffff !important;
}}
html.dark-mode {{
    background-color: #1a1a2e !important;
}}
.plotly {{
    transition: background-color 0.3s;
}}
#theme-toggle {{
    position: fixed;
    top: 20px;
    left: 20px;
    z-index: 1001;
    padding: 10px 20px;
    border: none;
    border-radius: 20px;
    font-size: 18px;
    cursor: pointer;
    transition: all 0.3s;
    box-shadow: 0 2px 5px rgba(0,0,0,0.2);
}}
body.light-mode #theme-toggle {{
    background: #333;
    color: white;
}}
body.dark-mode #theme-toggle {{
    background: #FFD700;
    color: #333;
}}
#theme-toggle:hover {{
    transform: scale(1.1);
}}
#search-container {{
    position: fixed;
    top: 70px;
    right: 20px;
    z-index: 1000;
    padding: 15px;
    border-radius: 8px;
    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    transition: all 0.3s;
}}
body.light-mode #search-container {{
    background: rgba(255, 255, 255, 0.95);
    border: 2px solid #ccc;
}}
body.dark-mode #search-container {{
    background: rgba(26, 26, 46, 0.95);
    border: 2px solid #444;
}}
#friend-search {{
    width: 250px;
    padding: 8px 12px;
    font-size: 14px;
    border: 2px solid;
    border-radius: 4px;
    outline: none;
    transition: all 0.3s;
}}
body.light-mode #friend-search {{
    background: #ffffff;
    color: #333;
    border-color: #999;
}}
body.dark-mode #friend-search {{
    background: #2a2a3e;
    color: white;
    border-color: #555;
}}
#friend-search:focus {{
    border-color: #FFD700;
}}
#search-results {{
    max-height: 300px;
    overflow-y: auto;
    margin-top: 8px;
    display: none;
}}
.search-result-item {{
    padding: 8px 12px;
    cursor: pointer;
    transition: background 0.2s;
}}
body.light-mode .search-result-item {{
    border-bottom: 1px solid #ddd;
    color: #333;
}}
body.dark-mode .search-result-item {{
    border-bottom: 1px solid #444;
    color: #ddd;
}}
body.light-mode .search-result-item:hover {{
    background: #f0f0f0;
}}
body.dark-mode .search-result-item:hover {{
    background: #3a3a4e;
}}
.search-result-item:last-child {{
    border-bottom: none;
}}
#search-status {{
    font-size: 12px;
    margin-top: 8px;
    transition: color 0.3s;
}}
body.light-mode #search-status {{
    color: #666;
}}
body.dark-mode #search-status {{
    color: #888;
}}
</style>
<button id="theme-toggle">Dark</button>
<div id="search-container">
    <input type="text" id="friend-search" placeholder="🔍 Search for a friend...">
    <div id="search-results"></div>
    <div id="search-status"></div>
</div>
<script>
// Theme toggle functionality
var isDarkMode = {initial_dark};

function toggleTheme() {{
    isDarkMode = !isDarkMode;
    applyTheme();
    localStorage.setItem('darkMode', isDarkMode);
}}

function applyTheme() {{
    var body = document.body;
    var html = document.documentElement;
    var toggleBtn = document.getElementById('theme-toggle');
    var myPlot = document.getElementsByClassName('plotly-graph-div')[0];
    
    if (isDarkMode) {{
        body.classList.remove('light-mode');
        body.classList.add('dark-mode');
        html.classList.remove('light-mode');
        html.classList.add('dark-mode');
        if (toggleBtn) toggleBtn.textContent = 'Light';
        
        // Update plotly background
        if (myPlot && myPlot.layout) {{
            Plotly.relayout(myPlot, {{
                'plot_bgcolor': '#1a1a2e',
                'paper_bgcolor': '#1a1a2e'
            }});
        }}
    }} else {{
        body.classList.remove('dark-mode');
        body.classList.add('light-mode');
        html.classList.remove('dark-mode');
        html.classList.add('light-mode');
        if (toggleBtn) toggleBtn.textContent = 'Dark';
        
        // Update plotly background
        if (myPlot && myPlot.layout) {{
            Plotly.relayout(myPlot, {{
                'plot_bgcolor': 'white',
                'paper_bgcolor': 'white'
            }});
        }}
    }}
}}

// Initialize theme from localStorage or default and set up button
document.addEventListener('DOMContentLoaded', function() {{
    var savedMode = localStorage.getItem('darkMode');
    if (savedMode !== null) {{
        isDarkMode = savedMode === 'true';
    }}
    
    // Set up button click handler
    var toggleBtn = document.getElementById('theme-toggle');
    if (toggleBtn) {{
        toggleBtn.addEventListener('click', toggleTheme);
    }}
    
    // Apply initial theme immediately
    applyTheme();
    
    // Now set up the friend network visualization
    var myPlot = document.getElementsByClassName('plotly-graph-div')[0];
    
    // Function to initialize visualization once Plotly is ready
    function initVisualization() {{
        if (!myPlot || !myPlot.data) {{
            setTimeout(initVisualization, 100);
            return;
        }}
        
        // Apply theme to plotly
        applyTheme();
        
        // Find the edge and node traces by their names (since blob traces are added dynamically)
        var edgeTraceIdx = -1;
        var nodeTraceIdx = -1;
        var backgroundTraceIndices = [];  // Track all background traces
"""
        # Continue with rest of JavaScript (no variables, so use regular string)
        custom_js = custom_js + """
        
        for (var i = 0; i < myPlot.data.length; i++) {
        if (myPlot.data[i].name === 'Mutual Friends') {
            edgeTraceIdx = i;
        } else if (myPlot.data[i].name === 'Friends') {
            nodeTraceIdx = i;
        } else if (myPlot.data[i].name && myPlot.data[i].name.includes('background')) {
            backgroundTraceIndices.push(i);
        }
    }
    
    // Store original background trace properties to restore them
    var originalBackgroundProps = {};
    for (var i = 0; i < backgroundTraceIndices.length; i++) {
        var idx = backgroundTraceIndices[i];
        originalBackgroundProps[idx] = {
            opacity: myPlot.data[idx].opacity,
            visible: myPlot.data[idx].visible
        };
    }
    
    if (edgeTraceIdx === -1 || nodeTraceIdx === -1) {
        console.error('Could not find edge or node traces');
        return;
    }
    
    var edges = myPlot.data[edgeTraceIdx];
    var nodes = myPlot.data[nodeTraceIdx];
    
    // Build coordinate to node index map for O(1) lookup
    var coordToIdx = {};
    for (var i = 0; i < nodes.x.length; i++) {
        var key = nodes.x[i].toFixed(2) + ',' + nodes.y[i].toFixed(2);
        coordToIdx[key] = i;
    }
    
    // Build edge data structure for quick lookup
    var edgeData = [];
    var adjacency = {};  // Map node index to list of connected node indices
    
    // Parse edge data (every 3 points: x1, x2, null)
    for (var i = 0; i < edges.x.length; i += 3) {
        if (edges.x[i] !== null && edges.x[i+1] !== null) {
            var x1 = edges.x[i];
            var y1 = edges.y[i];
            var x2 = edges.x[i+1];
            var y2 = edges.y[i+1];
            
            // Fast O(1) lookup using coordinate map
            var key1 = x1.toFixed(2) + ',' + y1.toFixed(2);
            var key2 = x2.toFixed(2) + ',' + y2.toFixed(2);
            var node1Idx = coordToIdx[key1];
            var node2Idx = coordToIdx[key2];
            
            if (node1Idx !== undefined && node2Idx !== undefined) {
                // Build adjacency list
                if (!adjacency[node1Idx]) adjacency[node1Idx] = [];
                if (!adjacency[node2Idx]) adjacency[node2Idx] = [];
                adjacency[node1Idx].push(node2Idx);
                adjacency[node2Idx].push(node1Idx);
                
                edgeData.push({
                    x1: x1, y1: y1,
                    x2: x2, y2: y2,
                    nodes: [node1Idx, node2Idx]
                });
            }
        }
    }
    
    var selectedNode = null;
    var selectedNodes = [];  // Array for multi-select
    var originalNodeOpacity = null;
    
    // Store original node opacity
    if (originalNodeOpacity === null) {
        originalNodeOpacity = Array(nodes.x.length).fill(0.95);
    }
    
    // Handle clicks
    myPlot.on('plotly_click', function(data) {
        var point = data.points[0];
        var clickedTrace = myPlot.data[point.curveNumber];
        
        // Check if it's a node click by trace name
        if (!clickedTrace || clickedTrace.name !== 'Friends') {
            if (selectedNode !== null || selectedNodes.length > 0) {
                resetSelection();
            }
            return;
        }
        
        var nodeIdx = point.pointNumber;
        var ctrlPressed = data.event.ctrlKey || data.event.metaKey;
        
        if (ctrlPressed) {
            // Multi-select mode
            var idx = selectedNodes.indexOf(nodeIdx);
            if (idx > -1) {
                // Deselect this node
                selectedNodes.splice(idx, 1);
            } else {
                // Add to selection
                selectedNodes.push(nodeIdx);
            }
            
            if (selectedNodes.length === 0) {
                resetSelection();
            } else {
                highlightMultipleNodes();
            }
        } else {
            // Single select mode
            if (selectedNode === nodeIdx && selectedNodes.length === 0) {
                resetSelection();
            } else {
                selectedNodes = [];
                selectedNode = nodeIdx;
                highlightSingleNode(nodeIdx);
            }
        }
    });
    
    // Double-click to deselect
    myPlot.on('plotly_doubleclick', function() {
        if (selectedNode !== null || selectedNodes.length > 0) {
            resetSelection();
        }
    });
    
    // Function to ensure background traces stay unchanged (batch operation)
    function preserveBackgrounds() {
        if (backgroundTraceIndices.length === 0) return;
        var opacities = backgroundTraceIndices.map(function(idx) { return originalBackgroundProps[idx].opacity; });
        var visibles = backgroundTraceIndices.map(function(idx) { return originalBackgroundProps[idx].visible; });
        Plotly.restyle(myPlot, {
            opacity: opacities,
            visible: visibles
        }, backgroundTraceIndices);
    }
    
    function highlightSingleNode(nodeIdx) {
        // Build highlighted edges for selected node
        var highlightX = [];
        var highlightY = [];
        
        var connected = adjacency[nodeIdx] || [];
        for (var i = 0; i < edgeData.length; i++) {
            var edge = edgeData[i];
            if (edge.nodes[0] === nodeIdx || edge.nodes[1] === nodeIdx) {
                highlightX.push(edge.x1, edge.x2, null);
                highlightY.push(edge.y1, edge.y2, null);
            }
        }
        
        // Build node styling updates efficiently
        var newNodeOpacity = Array(nodes.x.length).fill(0.2);
        var newBorderWidths = Array(nodes.x.length).fill(1);
        var newBorderColors = Array(nodes.x.length).fill('white');
        
        // Highlight selected node with gold
        newNodeOpacity[nodeIdx] = 1.0;
        newBorderWidths[nodeIdx] = 6;
        newBorderColors[nodeIdx] = '#FFD700';
        
        // Highlight connected nodes with orange
        for (var i = 0; i < connected.length; i++) {
            newNodeOpacity[connected[i]] = 1.0;
            newBorderWidths[connected[i]] = 4;
            newBorderColors[connected[i]] = '#FFD700';
        }
        
        // Single batch update for all visual changes
        var highlightTraceIdx = -1;
        var currentNodeTraceIdx = -1;
        
        // Find both highlight and node traces dynamically
        for (var i = 0; i < myPlot.data.length; i++) {
            if (myPlot.data[i].name === 'Highlighted Edges') {
                highlightTraceIdx = i;
            }
            if (myPlot.data[i].name === 'Friends') {
                currentNodeTraceIdx = i;
            }
        }
        
        // Check if highlight trace exists
        if (highlightTraceIdx === -1) {
            // Insert highlight trace AFTER edges but BEFORE nodes (so it's behind dots)
            var insertPosition = edgeTraceIdx + 1;
            Plotly.addTraces(myPlot, {
                x: highlightX,
                y: highlightY,
                mode: 'lines',
                line: {color: 'rgba(220,80,80,0.8)', width: 2},
                hoverinfo: 'none',
                showlegend: false,
                name: 'Highlighted Edges'
            }, insertPosition);
            // Re-find node trace after insertion
            for (var i = 0; i < myPlot.data.length; i++) {
                if (myPlot.data[i].name === 'Friends') {
                    currentNodeTraceIdx = i;
                    break;
                }
            }
            // Then update edge and node traces
            Plotly.restyle(myPlot, {'opacity': 0.03}, [edgeTraceIdx]);
            Plotly.restyle(myPlot, {
                'marker.opacity': [newNodeOpacity],
                'marker.line.width': [newBorderWidths],
                'marker.line.color': [newBorderColors]
            }, [currentNodeTraceIdx]);
        } else {
            // Highlight trace exists - update all three separately
            Plotly.restyle(myPlot, {
                'opacity': 0.03
            }, [edgeTraceIdx]);
            Plotly.restyle(myPlot, {
                'x': [highlightX],
                'y': [highlightY]
            }, [highlightTraceIdx]);
            Plotly.restyle(myPlot, {
                'marker.opacity': [newNodeOpacity],
                'marker.line.width': [newBorderWidths],
                'marker.line.color': [newBorderColors]
            }, [currentNodeTraceIdx]);
        }
    }
    
    function highlightMultipleNodes() {
        // Calculate common connections efficiently using Set intersection
        var commonConnections = [];
        if (selectedNodes.length > 1) {
            var firstNodeConnections = new Set(adjacency[selectedNodes[0]] || []);
            for (var i = 1; i < selectedNodes.length; i++) {
                var currentConnections = adjacency[selectedNodes[i]] || [];
                // Fast Set-based intersection
                var newIntersection = new Set();
                for (var j = 0; j < currentConnections.length; j++) {
                    if (firstNodeConnections.has(currentConnections[j])) {
                        newIntersection.add(currentConnections[j]);
                    }
                }
                firstNodeConnections = newIntersection;
            }
            commonConnections = Array.from(firstNodeConnections);
        }
        
        // Build highlighted edges using Set for fast lookup
        var selectedSet = new Set(selectedNodes);
        var highlightX = [];
        var highlightY = [];
        
        for (var i = 0; i < edgeData.length; i++) {
            var edge = edgeData[i];
            if (selectedSet.has(edge.nodes[0]) || selectedSet.has(edge.nodes[1])) {
                highlightX.push(edge.x1, edge.x2, null);
                highlightY.push(edge.y1, edge.y2, null);
            }
        }
        
        // Build node styling - dim all first
        var newNodeOpacity = Array(nodes.x.length).fill(0.2);
        var newBorderWidths = Array(nodes.x.length).fill(1);
        var newBorderColors = Array(nodes.x.length).fill('white');
        
        // Highlight selected nodes with thick gold borders
        for (var i = 0; i < selectedNodes.length; i++) {
            newNodeOpacity[selectedNodes[i]] = 1.0;
            newBorderWidths[selectedNodes[i]] = 6;
            newBorderColors[selectedNodes[i]] = '#FF1493';  // Pink for selected
        }
        
        // Highlight common mutual friends with gold borders
        for (var i = 0; i < commonConnections.length; i++) {
            newNodeOpacity[commonConnections[i]] = 1.0;
            newBorderWidths[commonConnections[i]] = 5;
            newBorderColors[commonConnections[i]] = '#FFD700';  // Gold for common mutuals
        }
        
        // Find highlight and node trace indices
        var highlightTraceIdx = -1;
        var currentNodeTraceIdx = -1;
        for (var i = 0; i < myPlot.data.length; i++) {
            if (myPlot.data[i].name === 'Highlighted Edges') {
                highlightTraceIdx = i;
            }
            if (myPlot.data[i].name === 'Friends') {
                currentNodeTraceIdx = i;
            }
        }
        
        // Check if highlight trace exists
        if (highlightTraceIdx === -1) {
            // Insert highlight trace AFTER edges but BEFORE nodes
            var insertPosition = edgeTraceIdx + 1;
            Plotly.addTraces(myPlot, {
                x: highlightX,
                y: highlightY,
                mode: 'lines',
                line: {color: 'rgba(220,80,80,0.8)', width: 2},
                hoverinfo: 'none',
                showlegend: false,
                name: 'Highlighted Edges'
            }, insertPosition);
            // Re-find node trace after insertion
            for (var i = 0; i < myPlot.data.length; i++) {
                if (myPlot.data[i].name === 'Friends') {
                    currentNodeTraceIdx = i;
                    break;
                }
            }
            // Update traces
            Plotly.restyle(myPlot, {'opacity': 0.03}, [edgeTraceIdx]);
            Plotly.restyle(myPlot, {
                'marker.opacity': [newNodeOpacity],
                'marker.line.width': [newBorderWidths],
                'marker.line.color': [newBorderColors]
            }, [currentNodeTraceIdx]);
        } else {
            // Update existing traces
            Plotly.restyle(myPlot, {'opacity': 0.03}, [edgeTraceIdx]);
            Plotly.restyle(myPlot, {
                'x': [highlightX],
                'y': [highlightY]
            }, [highlightTraceIdx]);
            Plotly.restyle(myPlot, {
                'marker.opacity': [newNodeOpacity],
                'marker.line.width': [newBorderWidths],
                'marker.line.color': [newBorderColors]
            }, [currentNodeTraceIdx]);
        }
        
        // Show status message
        if (selectedNodes.length > 1 && commonConnections.length > 0) {
            searchStatus.innerHTML = 'Common mutual friends: ' + commonConnections.length;
            searchStatus.style.display = 'block';
        } else if (selectedNodes.length > 1) {
            searchStatus.innerHTML = 'No common mutual friends';
            searchStatus.style.display = 'block';
        }
    }
    
    // Continue with remaining functions...
    
    function resetSelection() {
        // Restore edge opacity
        Plotly.restyle(myPlot, {'opacity': [0.15]}, [edgeTraceIdx]);
        
        // Remove highlight trace if it exists
        var highlightTraceIdx = -1;
        for (var i = 0; i < myPlot.data.length; i++) {
            if (myPlot.data[i].name === 'Highlighted Edges') {
                highlightTraceIdx = i;
                break;
            }
        }
        if (highlightTraceIdx !== -1) {
            Plotly.deleteTraces(myPlot, highlightTraceIdx);
        }
        
        // Reset nodes
        Plotly.restyle(myPlot, {
            'marker.opacity': [originalNodeOpacity],
            'marker.line.width': [2],
            'marker.line.color': ['white']
        }, [nodeTraceIdx]);
        
        selectedNode = null;
        selectedNodes = [];
        searchStatus.innerHTML = '';
        searchStatus.style.display = 'none';
    }
    
    function selectNodeByIndex(nodeIdx) {
        // Simulate clicking on a node
        selectedNode = nodeIdx;
        
        // Dim the original edge trace
        Plotly.restyle(myPlot, {'opacity': [0.03]}, [edgeTraceIdx]);
        
        // Build highlighted edges
        var highlightX = [];
        var highlightY = [];
        
        for (var i = 0; i < edgeData.length; i++) {
            var edge = edgeData[i];
            if (edge.nodes[0] === nodeIdx || edge.nodes[1] === nodeIdx) {
                highlightX.push(edge.x1, edge.x2, null);
                highlightY.push(edge.y1, edge.y2, null);
            }
        }
        
        // Add or update highlight trace
        var highlightTrace = {
            x: highlightX,
            y: highlightY,
            mode: 'lines',
            line: {color: 'rgba(220,80,80,0.8)', width: 2},
            hoverinfo: 'none',
            showlegend: false,
            name: 'Highlighted Edges'
        };
        
        var highlightTraceIdx = -1;
        for (var i = 0; i < myPlot.data.length; i++) {
            if (myPlot.data[i].name === 'Highlighted Edges') {
                highlightTraceIdx = i;
                break;
            }
        }
        
        if (highlightTraceIdx !== -1) {
            Plotly.restyle(myPlot, {
                x: [highlightX],
                y: [highlightY]
            }, [highlightTraceIdx]);
        } else {
            Plotly.addTraces(myPlot, highlightTrace);
        }
        
        // Dim all nodes
        var newNodeOpacity = Array(nodes.x.length).fill(0.2);
        var newBorderWidths = Array(nodes.x.length).fill(1);
        var newBorderColors = Array(nodes.x.length).fill('white');
        
        // Highlight selected node
        newNodeOpacity[nodeIdx] = 1.0;
        newBorderWidths[nodeIdx] = 6;
        newBorderColors[nodeIdx] = '#FFD700';
        
        // Highlight connected nodes
        var connected = adjacency[nodeIdx] || [];
        for (var i = 0; i < connected.length; i++) {
            newNodeOpacity[connected[i]] = 1.0;
            newBorderWidths[connected[i]] = 3;
            newBorderColors[connected[i]] = '#FF6B00';
        }
        
        Plotly.restyle(myPlot, {
            'marker.opacity': [newNodeOpacity],
            'marker.line.width': [newBorderWidths],
            'marker.line.color': [newBorderColors]
        }, [nodeTraceIdx]);
        
        // Center on the node
        var nodeX = nodes.x[nodeIdx];
        var nodeY = nodes.y[nodeIdx];
        Plotly.relayout(myPlot, {
            'xaxis.range': [nodeX - 300, nodeX + 300],
            'yaxis.range': [nodeY - 300, nodeY + 300]
        });
    }
    
    // Search functionality
    var searchInput = document.getElementById('friend-search');
    var searchResults = document.getElementById('search-results');
    var searchStatus = document.getElementById('search-status');
    
    // Build searchable friend list
    var friendList = [];
    for (var i = 0; i < nodes.text.length; i++) {
        var nameMatch = nodes.text[i].match(/<b>([^<]+)<\\/b>/);
        if (nameMatch) {
            friendList.push({
                name: nameMatch[1],
                index: i
            });
        }
    }
    
    searchInput.addEventListener('input', function(e) {
        var query = e.target.value.toLowerCase().trim();
        
        if (query === '') {
            searchResults.style.display = 'none';
            searchStatus.textContent = '';
            return;
        }
        
        // Filter friends
        var matches = friendList.filter(function(friend) {
            return friend.name.toLowerCase().includes(query);
        });
        
        // Sort by relevance (starts with query first, then contains)
        matches.sort(function(a, b) {
            var aStarts = a.name.toLowerCase().startsWith(query);
            var bStarts = b.name.toLowerCase().startsWith(query);
            if (aStarts && !bStarts) return -1;
            if (!aStarts && bStarts) return 1;
            return a.name.localeCompare(b.name);
        });
        
        // Limit results
        var maxResults = 20;
        var limited = matches.slice(0, maxResults);
        
        // Display results
        searchResults.innerHTML = '';
        searchResults.style.display = 'block';
        
        if (limited.length === 0) {
            searchResults.innerHTML = '<div class="search-result-item">No friends found</div>';
            searchStatus.textContent = '';
        } else {
            limited.forEach(function(friend) {
                var item = document.createElement('div');
                item.className = 'search-result-item';
                item.textContent = friend.name;
                item.onclick = function() {
                    selectNodeByIndex(friend.index);
                    searchInput.value = '';
                    searchResults.style.display = 'none';
                    searchStatus.textContent = '';
                };
                searchResults.appendChild(item);
            });
            
            if (matches.length > maxResults) {
                searchStatus.textContent = 'Showing ' + limited.length + ' of ' + matches.length + ' matches';
            } else {
                searchStatus.textContent = matches.length + ' friend' + (matches.length !== 1 ? 's' : '') + ' found';
            }
        }
    });
    
    // Close search results when clicking outside
    document.addEventListener('click', function(e) {
        if (!document.getElementById('search-container').contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });
    
    } // End initVisualization
    
    // Start visualization initialization
    initVisualization();
});
</script>
"""
        
        # Insert custom JS before closing body tag
        html_content = html_content.replace('</body>', custom_js + '</body>')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"Visualization saved to: {output_file}")
        
        # Statistics summary
        num_communities_detected = len(set(node_primary_community.values())) if node_primary_community else 0
        if num_communities_detected > 0:
            print(f"\n📊 Network Analysis:")
            print(f"  • Detected {num_communities_detected} friend communities/groups")
            
            # Find most connected friends
            node_degrees = [(node, self.graph.degree(node)) for node in self.graph.nodes()]
            top_connected = sorted(node_degrees, key=lambda x: x[1], reverse=True)[:5]
            
            print(f"\n  Most connected friends (mutual friend hubs):")
            for user_id, connections in top_connected:
                name = self.graph.nodes[user_id].get('name', user_id)
                cross = node_cross_connectivity.get(user_id, 0)
                print(f"    • {name}: {connections} mutual connections ({cross:.0%} cross-community)")
        
        return output_file


def main():
    parser = argparse.ArgumentParser(
        description='Visualize your VRChat mutual friend network'
    )
    parser.add_argument(
        '--source',
        choices=['vrcx', 'api', 'vrcx_json'],
        default='vrcx',
        help='Data source: vrcx (local VRCX database) or api (VRChat API) or vrcx_json (pre-analyzed JSON)'
    )
    parser.add_argument(
        '--db-path',
        help='Path to VRCX database file (optional, auto-detects by default)'
    )
    parser.add_argument(
        '--username',
        help='VRChat username (required for --source api)'
    )
    parser.add_argument(
        '--password',
        help='VRChat password (required for --source api)'
    )
    parser.add_argument(
        '--output',
        default='vrchat_friend_network.html',
        help='Output HTML file path'
    )
    parser.add_argument(
        '--open',
        action='store_true',
        help='Open visualization in browser after creating'
    )
    parser.add_argument(
        '--dark-mode',
        action='store_true',
        help='Use dark background instead of white'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("VRChat Friend Network Visualizer")
    print("=" * 60)
    
    friends = {}
    edges = {}
    
    if args.source == 'vrcx_json':
        print("\nLoading data from vrcx_mutual_friends.json...")
        try:
            with open('vrcx_mutual_friends.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert friends
            for user_id, name in data['friends'].items():
                friends[user_id] = {
                    'id': user_id,
                    'name': name,
                    'status': '',
                    'statusDescription': ''
                }
            
            # Convert edges
            for edge_key, count in data['edges'].items():
                user1, user2 = edge_key.split('|')
                edges[(user1, user2)] = count
            
            print(f"Loaded {len(friends)} friends and {len(edges)} connections")
            
        except FileNotFoundError:
            print("vrcx_mutual_friends.json not found!")
            print("   Run: python analyze_vrcx_mutuals.py first")
            return
        except Exception as e:
            print(f"Error loading JSON: {e}")
            return
    
    elif args.source == 'vrcx':
        print("\nLoading data from VRCX database...")
        try:
            parser_obj = VRCXDataParser(args.db_path)
            friends = parser_obj.get_friends()
            print(f"Loaded {len(friends)} friends from VRCX")
            
            # Note: VRCX doesn't directly store mutual friend connections
            # We'd need to infer them or use the API
            print("\nNote: VRCX doesn't store mutual friend connections.")
            print("    For full network visualization, use --source api")
            print("    Continuing with friend list only...")
            
        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("\nTip: VRCX database is usually at:")
            print("    %APPDATA%\\VRCX\\VRCX.sqlite3")
            return
    
    elif args.source == 'api':
        if not args.username or not args.password:
            print("Error: --username and --password required for API source")
            return
        
        print("\nConnecting to VRChat API...")
        try:
            api = VRChatAPIParser(args.username, args.password)
            friends = api.get_friends()
            edges = api.get_mutual_friends(friends)
        except Exception as e:
            print(f"Error: {e}")
            return
    
    # Create visualization
    visualizer = FriendNetworkVisualizer(friends, edges)
    output_path = visualizer.create_visualization(args.output, dark_mode=args.dark_mode)
    
    if args.open and output_path:
        print(f"\nOpening visualization in browser...")
        webbrowser.open('file://' + os.path.abspath(output_path))
    
    print("\nDone!")
    print("=" * 60)


if __name__ == '__main__':
    main()



