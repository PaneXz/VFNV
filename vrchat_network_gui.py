"""
VRChat Friend Network Visualizer - GUI Application
Uses VRCX SQLite database for friend data
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog
import os
import sys
import json
import webbrowser
import threading
import time
import traceback

# Add PyInstaller temp directory to path if running as exe
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    bundle_dir = sys._MEIPASS
else:
    # Running as script
    bundle_dir = os.path.dirname(os.path.abspath(__file__))

# Ensure the bundle directory is in the path for imports
if bundle_dir not in sys.path:
    sys.path.insert(0, bundle_dir)

# Import the visualizer and VRCX extractor
from vrchat_friend_network_visualizer import FriendNetworkVisualizer
from extract_vrcx_mutuals import extract_friends_and_mutuals


class VRChatNetworkGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("VRChat Friend Network Visualizer")
        self.root.geometry("1050x850")
        self.root.minsize(1000, 800)

        self.processing = False
        self.stop_requested = False
        self.output_path = None
        self.login_required = False
        self.fetcher = None
        self.dark_mode_gui = True
        self.exe_dir = self.get_exe_dir()
        self.vrcx_users = []  # List of available VRCX users
        self.selected_user_hash = None  # Currently selected user hash
        
        # Statistics tracking
        self.total_friends = 0
        self.total_mutuals = 0
        self.total_connections = 0
        
        # Configure style
        self.style = ttk.Style()
        self.style.theme_use('clam')
        
        self.create_widgets()
        self.apply_theme()
    
    def get_exe_dir(self):
        """Get the data directory for storing generated files"""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            base_dir = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Create VFNV Data subfolder
        data_dir = os.path.join(base_dir, 'VFNV Data')
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        return data_dir

    def create_widgets(self):
        """Create GUI widgets"""
        # Main container with padding
        main_container = ttk.Frame(self.root, padding="15")
        main_container.pack(fill='both', expand=True)
        
        # Header Section
        header_frame = ttk.Frame(main_container)
        header_frame.pack(fill='x', pady=(0, 12))
        
        ttk.Label(header_frame, text="VRChat Friend Network Visualizer",
                 font=('Segoe UI', 14, 'bold')).pack(anchor='w')
        ttk.Label(header_frame, text="Extract and visualize your VRChat friend network using VRCX database and VRChat API",
                 font=('Segoe UI', 9), foreground='#666').pack(anchor='w', pady=(3, 0))
        
        # Content area with two columns
        content_frame = ttk.Frame(main_container)
        content_frame.pack(fill='both', expand=True)
        
        # Left column - Configuration
        left_frame = ttk.Frame(content_frame)
        left_frame.pack(side='left', fill='both', expand=True, padx=(0, 10))
        
        # Database Section
        db_section = ttk.LabelFrame(left_frame, text="Database Configuration", padding=10)
        db_section.pack(fill='x', pady=(0, 10))
        
        ttk.Label(db_section, text="VRCX Database Location:").pack(anchor='w', pady=(0, 5))
        
        # Explanation text
        ttk.Label(db_section, text="VRCX database is used to get your friend list.\nMutual connections are then fetched from VRChat API.",
                 font=('Segoe UI', 8), foreground='#666', wraplength=350, justify='left').pack(anchor='w', pady=(0, 10))
        
        db_path_frame = ttk.Frame(db_section)
        db_path_frame.pack(fill='x', pady=(0, 10))
        
        self.db_path_var = tk.StringVar(value="Not selected")
        db_entry = ttk.Entry(db_path_frame, textvariable=self.db_path_var, state='readonly')
        db_entry.pack(side='left', fill='x', expand=True, padx=(0, 5))
        
        ttk.Button(db_path_frame, text="Browse", command=self.browse_vrcx, width=10).pack(side='left')
        
        ttk.Button(db_section, text="Auto-Detect", command=self.detect_vrcx, width=15).pack(anchor='w')
        
        # VRCX User Selection
        ttk.Label(db_section, text="VRCX Account:").pack(anchor='w', pady=(10, 5))
        self.user_select_var = tk.StringVar(value="Detect database first")
        self.user_select_dropdown = ttk.Combobox(db_section, textvariable=self.user_select_var, state='readonly')
        self.user_select_dropdown.pack(fill='x', pady=(0, 5))
        self.user_select_dropdown.bind('<<ComboboxSelected>>', self.on_user_selected)
        
        ttk.Label(db_section, text="Select which VRCX account to use if multiple logins exist",
                 font=('Segoe UI', 7), foreground='#888').pack(anchor='w')
        
        # VRChat API Login Section
        self.login_section = ttk.LabelFrame(left_frame, text="VRChat API Login (Required for Mutual Connections)", padding=10)
        self.login_section.pack(fill='x', pady=(0, 10))
        
        ttk.Label(self.login_section, text="Login to fetch mutual friend connections",
                 foreground='#666', font=('Segoe UI', 8)).pack(anchor='w', pady=(0, 10))
        
        # Username
        ttk.Label(self.login_section, text="Username:").pack(anchor='w')
        self.username_entry = ttk.Entry(self.login_section)
        self.username_entry.pack(fill='x', pady=(2, 10))
        
        # Password
        ttk.Label(self.login_section, text="Password:").pack(anchor='w')
        self.password_entry = ttk.Entry(self.login_section, show='*')
        self.password_entry.pack(fill='x', pady=(2, 10))
        
        # 2FA
        ttk.Label(self.login_section, text="2FA Code (if enabled):").pack(anchor='w')
        self.twofa_entry = ttk.Entry(self.login_section)
        self.twofa_entry.pack(fill='x', pady=(2, 10))
        
        # Login status
        self.login_status_var = tk.StringVar(value="Not logged in - Enter credentials and click Generate")
        self.login_status_label = ttk.Label(self.login_section, textvariable=self.login_status_var,
                                            foreground='#666', font=('Segoe UI', 8))
        self.login_status_label.pack(anchor='w', pady=(5, 0))
        
        # Privacy note
        privacy_frame = ttk.Frame(self.login_section)
        privacy_frame.pack(fill='x', pady=(10, 0))
        ttk.Label(privacy_frame, text="Privacy: Session saved locally, password never stored.",
                 font=('Segoe UI', 7), foreground='#888', wraplength=350).pack(anchor='w')
        
        # Options Section
        options_section = ttk.LabelFrame(left_frame, text="Options", padding=10)
        options_section.pack(fill='x')
        
        self.dark_mode_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_section, text="Dark Mode (Visualization)", variable=self.dark_mode_var).pack(anchor='w', pady=2)
        
        self.heatmap_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_section, text="Show Background Heatmap", variable=self.heatmap_var).pack(anchor='w', pady=2)
        
        self.show_edges_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_section, text="Show Unselected Connections", variable=self.show_edges_var).pack(anchor='w', pady=2)
        
        self.auto_open_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(options_section, text="Auto-open in browser", variable=self.auto_open_var).pack(anchor='w', pady=2)
        
        # Right column - Log and Progress
        right_frame = ttk.Frame(content_frame)
        right_frame.pack(side='right', fill='both', expand=True)
        
        # Progress Section
        progress_section = ttk.LabelFrame(right_frame, text="Progress", padding=10)
        progress_section.pack(fill='x', pady=(0, 10))
        
        self.status_var = tk.StringVar(value="Ready to start")
        status_label = ttk.Label(progress_section, textvariable=self.status_var, font=('Segoe UI', 9, 'bold'))
        status_label.pack(anchor='w', pady=(0, 10))
        
        # Progress bar with percentage
        progress_frame = ttk.Frame(progress_section)
        progress_frame.pack(fill='x', pady=(0, 5))
        
        self.progress = ttk.Progressbar(progress_frame, mode='determinate', length=300)
        self.progress.pack(side='left', fill='x', expand=True, padx=(0, 10))
        
        self.progress_pct_var = tk.StringVar(value="0%")
        ttk.Label(progress_frame, textvariable=self.progress_pct_var, width=5, font=('Segoe UI', 9, 'bold')).pack(side='left')
        
        # Step indicator
        self.step_var = tk.StringVar(value="")
        step_label = ttk.Label(progress_section, textvariable=self.step_var, 
                              font=('Segoe UI', 8), foreground='#666')
        step_label.pack(anchor='w')
        
        # Statistics Section
        stats_section = ttk.LabelFrame(right_frame, text="Network Statistics", padding=10)
        stats_section.pack(fill='x', pady=(0, 10))
        
        stats_grid = ttk.Frame(stats_section)
        stats_grid.pack(fill='x')
        
        ttk.Label(stats_grid, text="Total Friends:", font=('Segoe UI', 9)).grid(row=0, column=0, sticky='w', pady=2)
        self.friends_count_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.friends_count_var, font=('Segoe UI', 9, 'bold')).grid(row=0, column=1, sticky='e', pady=2)
        
        ttk.Label(stats_grid, text="Graph Edges:", font=('Segoe UI', 9)).grid(row=1, column=0, sticky='w', pady=2)
        self.edges_count_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.edges_count_var, font=('Segoe UI', 9, 'bold')).grid(row=1, column=1, sticky='e', pady=2)
        
        ttk.Label(stats_grid, text="Communities:", font=('Segoe UI', 9)).grid(row=2, column=0, sticky='w', pady=2)
        self.communities_count_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.communities_count_var, font=('Segoe UI', 9, 'bold')).grid(row=2, column=1, sticky='e', pady=2)
        
        ttk.Label(stats_grid, text="Isolated Nodes:", font=('Segoe UI', 9)).grid(row=3, column=0, sticky='w', pady=2)
        self.isolated_count_var = tk.StringVar(value="0")
        ttk.Label(stats_grid, textvariable=self.isolated_count_var, font=('Segoe UI', 9, 'bold')).grid(row=3, column=1, sticky='e', pady=2)
        
        ttk.Label(stats_grid, text="Network Density:", font=('Segoe UI', 9)).grid(row=4, column=0, sticky='w', pady=2)
        self.density_var = tk.StringVar(value="0%")
        ttk.Label(stats_grid, textvariable=self.density_var, font=('Segoe UI', 9, 'bold')).grid(row=4, column=1, sticky='e', pady=2)
        
        ttk.Separator(stats_grid, orient='horizontal').grid(row=5, column=0, columnspan=2, sticky='ew', pady=5)
        
        ttk.Label(stats_grid, text="Most Connected:", font=('Segoe UI', 9)).grid(row=6, column=0, sticky='nw', pady=2)
        
        # Top friends list (right side of stats grid)
        top_friends_frame = ttk.Frame(stats_grid)
        top_friends_frame.grid(row=6, column=1, sticky='e', pady=2)
        
        self.top_friends_text = tk.Text(top_friends_frame, height=4, width=25, 
                                        font=('Segoe UI', 8), wrap=tk.NONE,
                                        relief='flat', borderwidth=0)
        self.top_friends_text.pack()
        self.top_friends_text.insert('1.0', '-')
        self.top_friends_text.config(state='disabled')
        
        stats_grid.columnconfigure(1, weight=1)
        
        # Log Section
        log_section = ttk.LabelFrame(right_frame, text="Activity Log", padding=10)
        log_section.pack(fill='both', expand=True, pady=(0, 5))
        
        self.log_text = scrolledtext.ScrolledText(log_section, height=8, width=50,
                                                  font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill='both', expand=True)
        
        # Bottom buttons
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill='x', pady=(10, 0))
        
        # Left side buttons
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side='left')
        
        self.generate_btn = ttk.Button(left_buttons, text="Generate",
                                       command=self.start_processing)
        self.generate_btn.pack(side='left', padx=(0, 5))
        
        self.stop_btn = ttk.Button(left_buttons, text="Stop",
                                   command=self.stop_processing,
                                   state='disabled')
        self.stop_btn.pack(side='left', padx=(0, 5))
        
        self.open_btn = ttk.Button(left_buttons, text="Open",
                                   command=self.open_visualization,
                                   state='disabled')
        self.open_btn.pack(side='left')
        
        # Right side buttons
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side='right')
        
        self.clear_data_btn = ttk.Button(right_buttons, text="Clear Data",
                                        command=self.clear_user_data)
        self.clear_data_btn.pack(side='left', padx=(0, 5))
        
        self.clear_btn = ttk.Button(right_buttons, text="Clear Log",
                                    command=self.clear_log)
        self.clear_btn.pack(side='left', padx=(0, 5))
        
        self.theme_btn = ttk.Button(right_buttons, text="Theme",
                                    command=self.toggle_gui_theme)
        self.theme_btn.pack(side='left')
        
        # Privacy footer
        footer_frame = ttk.Frame(main_container)
        footer_frame.pack(fill='x', pady=(10, 0))
        ttk.Label(footer_frame, 
                 text="All data stays local - No tracking - Session cookie only - Open source",
                 font=('Segoe UI', 7), foreground='#888').pack()

    def detect_vrcx(self):
        """Auto-detect VRCX database location"""
        appdata = os.getenv('APPDATA')
        db_path = os.path.join(appdata, 'VRCX', 'VRCX.sqlite3')
        
        if os.path.exists(db_path):
            self.db_path_var.set(db_path)
            size_mb = os.path.getsize(db_path) / 1024 / 1024
            self.log(f"[Database] Found VRCX database ({size_mb:.2f} MB)")
            self.log(f"[Database] Location: {db_path}")
            self.load_vrcx_users()
        else:
            self.log(f"[Database] Not found at default location")
            self.log(f"[Database] Please use Browse to select manually")

    def browse_vrcx(self):
        """Browse for VRCX database file"""
        filename = filedialog.askopenfilename(
            title="Select VRCX Database",
            filetypes=[("SQLite Database", "*.sqlite3"), ("All Files", "*.*")]
        )
        if filename:
            self.db_path_var.set(filename)
            size_mb = os.path.getsize(filename) / 1024 / 1024
            self.log(f"[Database] Selected: {filename} ({size_mb:.2f} MB)")
            self.load_vrcx_users()

    def load_vrcx_users(self):
        """Load available VRCX users from database"""
        from extract_vrcx_mutuals import get_vrcx_users
        
        try:
            self.vrcx_users = get_vrcx_users()
            
            if not self.vrcx_users:
                self.user_select_var.set("No VRCX users found")
                self.user_select_dropdown['values'] = []
                self.log("[Database] No VRCX user accounts found in database")
            elif len(self.vrcx_users) == 1:
                user = self.vrcx_users[0]
                self.selected_user_hash = user['user_hash']
                self.user_select_var.set(user['display'])
                self.user_select_dropdown['values'] = [user['display']]
                self.log(f"[Database] Found 1 VRCX account: {user['display']}")
            else:
                displays = [user['display'] for user in self.vrcx_users]
                self.user_select_dropdown['values'] = displays
                self.user_select_var.set(displays[0])
                self.selected_user_hash = self.vrcx_users[0]['user_hash']
                self.log(f"[Database] Found {len(self.vrcx_users)} VRCX accounts - select one from dropdown")
                for user in self.vrcx_users:
                    self.log(f"[Database]   - {user['display']}")
        except Exception as e:
            self.log(f"[Database] Error loading VRCX users: {e}")
            import traceback
            traceback.print_exc()
    
    def on_user_selected(self, event=None):
        """Handle user selection from dropdown"""
        selected_display = self.user_select_var.get()
        for user in self.vrcx_users:
            if user['display'] == selected_display:
                self.selected_user_hash = user['user_hash']
                self.log(f"[Database] Selected account: {user['display']}")
                break
    
    def log(self, message):
        """Add message to log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def clear_log(self):
        """Clear the log"""
        self.log_text.delete('1.0', tk.END)
    
    def clear_user_data(self):
        """Clear all user data including sessions, cached friends, and outputs"""
        from tkinter import messagebox
        
        # Confirm action
        response = messagebox.askyesno(
            "Clear User Data",
            "This will delete:\n\n"
            "- Saved VRChat login session\n"
            "- Cached friend list (vrcx_mutual_friends.json)\n"
            "- Generated network visualization\n\n"
            "Do this before sharing the application to remove personal data.\n\n"
            "Continue?",
            icon='warning'
        )
        
        if not response:
            return
        
        files_removed = []
        files_not_found = []
        
        # List of files to remove
        files_to_remove = [
            'vrchat_session.pkl',
            'vrcx_mutual_friends.json',
            'vrchat_friend_network.html'
        ]
        
        # Remove each file if it exists
        for filename in files_to_remove:
            filepath = os.path.join(self.exe_dir, filename)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    files_removed.append(filename)
                    self.log(f"[Clear] Removed: {filename}")
                except Exception as e:
                    self.log(f"[Clear] Failed to remove {filename}: {e}")
            else:
                files_not_found.append(filename)
        
        # Reset GUI state
        self.output_path = None
        self.open_btn.config(state='disabled')
        self.login_status_var.set("Not logged in - Enter credentials and click Generate")
        self.username_entry.delete(0, tk.END)
        self.password_entry.delete(0, tk.END)
        self.twofa_entry.delete(0, tk.END)
        self.update_statistics(friends=0, mutuals=0, edges=0)
        
        # Remove the VFNV Data folder if it's empty or only has removed files
        try:
            if os.path.exists(self.exe_dir) and os.path.isdir(self.exe_dir):
                # Check if folder is empty
                if not os.listdir(self.exe_dir):
                    os.rmdir(self.exe_dir)
                    self.log("[Clear] Removed VFNV Data folder")
        except Exception as e:
            self.log(f"[Clear] Could not remove VFNV Data folder: {e}")
        
        # Show summary
        summary = f"Removed {len(files_removed)} file(s)"
        if files_removed:
            summary += f":\n" + "\n".join(f"  - {f}" for f in files_removed)
        if files_not_found:
            summary += f"\n\nNot found ({len(files_not_found)}): " + ", ".join(files_not_found)
        
        self.log("[Clear] User data cleared - application reset to clean state")
        messagebox.showinfo("User Data Cleared", summary)
    
    def toggle_gui_theme(self):
        """Toggle between light and dark mode for the GUI"""
        self.dark_mode_gui = not self.dark_mode_gui
        self.apply_theme()
        self.log(f"[GUI] Theme changed to {'dark' if self.dark_mode_gui else 'light'} mode")
    
    def apply_theme(self):
        """Apply the current theme to GUI elements"""
        if self.dark_mode_gui:
            # Dark theme colors - improved contrast
            bg_color = '#2d2d30'  # Softer dark gray
            fg_color = '#e8e8e8'  # Softer white
            frame_bg = '#3e3e42'  # Lighter frame background
            entry_bg = '#3c3c3c'  # Entry field background
            log_bg = '#1e1e1e'  # Dark log background
            log_fg = '#d4d4d4'  # Log text color
            select_bg = '#007acc'  # Blue selection
            select_fg = '#ffffff'  # White text on selection
            
            self.root.configure(bg=bg_color)
            self.style.configure('TFrame', background=bg_color)
            self.style.configure('TLabel', background=bg_color, foreground=fg_color)
            self.style.configure('TLabelframe', background=bg_color, foreground=fg_color, bordercolor='#555')
            self.style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color)
            self.style.configure('TButton', background='#505050', foreground=fg_color, bordercolor='#555')
            self.style.configure('TCheckbutton', background=bg_color, foreground=fg_color, borderwidth=0, relief='flat')
            self.style.configure('TEntry', fieldbackground=entry_bg, foreground=fg_color, bordercolor='#555')
            self.style.configure('TProgressbar', background='#4CAF50', troughcolor='#3e3e42', bordercolor='#555', lightcolor='#4CAF50', darkcolor='#4CAF50')
            self.style.map('TButton', background=[('active', '#606060')])
            self.style.map('TCheckbutton', 
                          background=[('active', '#3e3e42'), ('selected', bg_color)],
                          foreground=[('active', fg_color), ('selected', fg_color)],
                          indicatorcolor=[('selected', '#4CAF50'), ('!selected', '#555')])
            
            self.log_text.configure(
                bg=log_bg, 
                fg=log_fg, 
                insertbackground=fg_color,
                selectbackground=select_bg,
                selectforeground=select_fg
            )
            self.top_friends_text.configure(
                bg=bg_color,
                fg=fg_color
            )
        else:
            # Light theme colors
            bg_color = '#f0f0f0'
            fg_color = '#000000'
            log_bg = '#ffffff'
            log_fg = '#000000'
            select_bg = '#0078d7'  # Blue selection
            select_fg = '#ffffff'  # White text on selection
            
            self.root.configure(bg=bg_color)
            self.style.configure('TFrame', background=bg_color)
            self.style.configure('TLabel', background=bg_color, foreground=fg_color)
            self.style.configure('TLabelframe', background=bg_color, foreground=fg_color)
            self.style.configure('TLabelframe.Label', background=bg_color, foreground=fg_color)
            self.style.configure('TButton', background='#e0e0e0', foreground=fg_color)
            self.style.configure('TCheckbutton', background=bg_color, foreground=fg_color, borderwidth=0, relief='flat')
            self.style.configure('TEntry', fieldbackground='#ffffff', foreground=fg_color)
            self.style.configure('TProgressbar', background='#4CAF50', troughcolor='#e0e0e0', bordercolor='#ccc', lightcolor='#4CAF50', darkcolor='#4CAF50')
            self.style.map('TButton', background=[('active', '#d0d0d0')])
            self.style.map('TCheckbutton', 
                          background=[('active', '#e0e0e0'), ('selected', bg_color)],
                          foreground=[('active', fg_color), ('selected', fg_color)],
                          indicatorcolor=[('selected', '#4CAF50'), ('!selected', '#aaa')])
            
            self.log_text.configure(
                bg=log_bg, 
                fg=log_fg, 
                insertbackground=fg_color,
                selectbackground=select_bg,
                selectforeground=select_fg
            )
            self.top_friends_text.configure(
                bg=bg_color,
                fg=fg_color
            )

    def update_status(self, message, step="", progress=0):
        """Update status and step indicators"""
        self.status_var.set(message)
        self.step_var.set(step)
        self.progress['value'] = progress
        self.progress_pct_var.set(f"{progress}%")
        self.root.update_idletasks()
    
    def update_statistics(self, friends=None, edges=None, communities=None, isolated=None, density=None, top_friends=None):
        """Update statistics display"""
        if friends is not None:
            self.total_friends = friends
            self.friends_count_var.set(str(friends))
        if edges is not None:
            self.total_connections = edges
            self.edges_count_var.set(str(edges))
        if communities is not None:
            self.communities_count_var.set(str(communities))
        if isolated is not None:
            self.isolated_count_var.set(str(isolated))
        if density is not None:
            self.density_var.set(f"{density:.2%}")
        if top_friends is not None:
            self.top_friends_text.config(state='normal')
            self.top_friends_text.delete('1.0', tk.END)
            self.top_friends_text.insert('1.0', top_friends)
            self.top_friends_text.config(state='disabled')
        self.root.update_idletasks()
    
    def fetch_progress_callback(self, current, total):
        """Callback for fetch progress updates"""
        # Progress from 30% to 55% during fetch (25% range for step 2)
        progress = 30 + int((current / total) * 25)
        self.root.after(0, lambda: self.update_status(
            f"Fetching mutual connections...",
            f"Step 2 of 4: Processing friend {current}/{total}",
            progress
        ))

    def show_login_section(self):
        """Show the login section (already visible, just update status)"""
        self.login_status_var.set("Waiting for credentials...")
        self.login_required = True

    def attempt_login(self):
        """Attempt VRChat login with provided credentials"""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()
        twofa_code = self.twofa_entry.get().strip()
        
        if not username or not password:
            self.login_status_var.set("Error: Username and password required")
            self.log("[Login] Please enter username and password")
            return False
        
        try:
            self.log("[Login] Attempting to authenticate...")
            self.login_status_var.set("Logging in...")
            
            # Pass 2FA code to login method if provided
            if twofa_code:
                self.log(f"[Login] Using 2FA code: {twofa_code}")
                self.fetcher.login(username, password, twofa_code)
            else:
                self.fetcher.login(username, password)
            
            self.login_status_var.set("Login successful")
            self.log("[Login] Authentication successful")
            return True
            
        except Exception as e:
            error_msg = str(e)
            
            if "2FA" in error_msg or "twoFactor" in error_msg:
                if not twofa_code:
                    self.login_status_var.set("Error: 2FA code required")
                    self.log("[Login] Two-factor authentication required - please enter 2FA code above")
                else:
                    self.login_status_var.set("Error: Invalid 2FA code")
                    self.log(f"[Login] Invalid 2FA code - please check and try again")
            else:
                self.login_status_var.set(f"Error: {error_msg}")
                self.log(f"[Login] Failed: {error_msg}")
            
            return False

    def start_processing(self):
        """Start the network generation process"""
        if self.processing:
            return

        db_path = self.db_path_var.get()
        if db_path == "Not selected" or not os.path.exists(db_path):
            self.log("[Error] Please select a valid VRCX database file")
            self.update_status("Error: No database selected")
            return
        
        # Check if a user has been selected
        if not self.selected_user_hash:
            self.log("[Error] Please select a VRCX account from the dropdown")
            self.update_status("Error: No VRCX account selected")
            return

        # Disable buttons and reset progress
        self.processing = True
        self.stop_requested = False
        self.generate_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.open_btn.config(state='disabled')
        self.progress['value'] = 0
        self.progress_pct_var.set("0%")
        
        # Run in separate thread
        thread = threading.Thread(target=self.process_network, args=(db_path,))
        thread.daemon = True
        thread.start()

    def stop_processing(self):
        """Request to stop the current processing"""
        if self.processing:
            self.stop_requested = True
            self.log("[Process] Stop requested, waiting for current operation to finish...")
            self.update_status("Stopping...", "Cancelling", self.progress['value'])
            self.stop_btn.config(state='disabled')

    def process_network(self, db_path):
        """Process the network in background thread"""
        try:
            self.update_status("Starting...", "Initializing", 0)
            self.log("[Process] Starting network generation")
            
            # Step 1: Extract friends from VRCX
            self.update_status("Extracting friend data...", "Step 1 of 4", 5)
            self.log("[Step 1/4] Extracting friends from VRCX database")
            
            if self.stop_requested:
                self.log("[Process] Stopped by user")
                self.update_status("Stopped by user", "Cancelled", 0)
                # Reset state without calling processing_complete since we didn't complete
                self.processing = False
                self.stop_requested = False
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
                return
            
            friends_data = extract_friends_and_mutuals(self.selected_user_hash)
            
            if not friends_data:
                raise Exception("No friends found in VRCX database")

            friend_count = len(friends_data)
            self.log(f"[Step 1/4] Found {friend_count} friends")
            self.update_statistics(friends=friend_count)
            self.update_status("Friend data extracted", "Step 1 of 4 Complete", 20)

            if self.stop_requested:
                self.log("[Process] Stopped by user")
                self.update_status("Stopped by user", "Cancelled", 0)
                # Reset state without calling processing_complete since we didn't complete
                self.processing = False
                self.stop_requested = False
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
                return

            # Step 2: Fetch mutual connections from API
            self.update_status("Checking VRChat API access...", "Step 2 of 4", 25)
            self.log("[Step 2/4] Preparing to fetch mutual connections")
            
            from fetch_vrchat_mutuals import VRChatMutualFetcher
            # Use exe directory to store session and cache files
            self.fetcher = VRChatMutualFetcher(base_dir=self.exe_dir, stop_callback=lambda: self.stop_requested)
            
            api_mutuals = {}
            
            # Check for saved session
            if not self.fetcher.load_session():
                self.log("[Step 2/4] No saved session found")
                
                # Check if credentials are provided
                username = self.username_entry.get().strip()
                password = self.password_entry.get().strip()
                
                if not username or not password:
                    # No credentials, show login section and stop
                    self.log("[Step 2/4] Please enter login credentials above and click Generate again")
                    self.root.after(0, self.show_login_section)
                    self.update_status("Login required", "Enter credentials and retry")
                    raise Exception("Login required")
                
                # Attempt login with provided credentials
                self.log("[Step 2/4] Attempting login with provided credentials")
                if self.attempt_login():
                    self.log("[Step 2/4] Login successful")
                    # Fetch mutuals after successful login
                    self.update_status("Fetching mutual connections...", "Step 2 of 4", 30)
                    friend_ids = list(friends_data.keys())
                    self.log(f"[Step 2/4] Fetching mutuals for {len(friend_ids)} friends")
                    self.log("[Step 2/4] This may take several minutes...")
                    
                    api_mutuals = self.fetcher.fetch_all_mutuals(friend_ids, progress_callback=self.fetch_progress_callback)
                else:
                    self.log("[Step 2/4] Login failed")
                    self.update_status("Login failed", "Check credentials")
                    raise Exception("Login failed")
            else:
                # Session restored, fetch mutuals
                self.update_status("Fetching mutual connections...", "Step 2 of 4", 30)
                self.login_status_var.set("Using saved session")
                friend_ids = list(friends_data.keys())
                self.log(f"[Step 2/4] Using saved session")
                self.log(f"[Step 2/4] Fetching mutuals for {len(friend_ids)} friends")
                self.log("[Step 2/4] This may take several minutes...")
                
                api_mutuals = self.fetcher.fetch_all_mutuals(friend_ids, progress_callback=self.fetch_progress_callback)
            
            # Check if we have any mutual data
            if not api_mutuals:
                self.log("[Step 2/4] No mutual data retrieved")
                self.update_status("No mutual data", "Check login")
                raise Exception("No mutual data retrieved")
            
            # Merge mutual data
            mutual_count = 0
            for friend_id, mutuals_list in api_mutuals.items():
                if friend_id in friends_data:
                    friends_data[friend_id]['mutuals'] = mutuals_list
                    mutual_count += len(mutuals_list)
            
            # Save JSON cache of friend data
            import json
            json_output = {
                'friends': {uid: {'id': uid, 'name': data.get('name', uid)} for uid, data in friends_data.items()},
                'edges': {},
                'mutual_counts': {}
            }
            # Build edges from mutuals
            for friend_id, friend_info in friends_data.items():
                mutuals = friend_info.get('mutuals', [])
                json_output['mutual_counts'][friend_id] = len(mutuals)
                for mutual_id in mutuals:
                    if mutual_id in friends_data:
                        edge_key = f"{min(friend_id, mutual_id)}|{max(friend_id, mutual_id)}"
                        json_output['edges'][edge_key] = 1
            
            json_file = os.path.join(self.exe_dir, 'vrcx_mutual_friends.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(json_output, f, indent=2, ensure_ascii=False)
            self.log(f"[Step 2/4] Saved friend cache to: {json_file}")
            
            self.log(f"[Step 2/4] Collected {mutual_count} mutual connection entries")
            # Note: actual edges will be ~half this since each connection is counted twice
            self.update_status("Mutual connections fetched", "Step 2 of 4 Complete", 55)

            if self.stop_requested:
                self.log("[Process] Stopped by user")
                self.update_status("Stopped by user", "Cancelled", 0)
                # Reset state without calling processing_complete since we didn't complete
                self.processing = False
                self.stop_requested = False
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
                return

            # Step 3: Build network graph
            self.update_status("Building network graph...", "Step 3 of 4", 60)
            self.log("[Step 3/4] Constructing network graph")
            
            friends_dict = {}
            for friend_id, friend_info in friends_data.items():
                friends_dict[friend_id] = {
                    'name': friend_info.get('name', friend_id),
                    'id': friend_id
                }
            
            visualizer = FriendNetworkVisualizer(friends_dict)
            
            edge_count = 0
            for friend_id, friend_info in friends_data.items():
                mutuals = friend_info.get('mutuals', [])
                for mutual_id in mutuals:
                    if mutual_id in friends_data:
                        visualizer.graph.add_edge(friend_id, mutual_id)
                        edge_count += 1
            
            self.log(f"[Step 3/4] Built graph with {len(friends_dict)} nodes and {edge_count} edges")
            
            # Calculate statistics
            isolated_count = sum(1 for node in visualizer.graph.nodes() if visualizer.graph.degree(node) == 0)
            connected_nodes = len(friends_dict) - isolated_count
            
            # Calculate density (only for connected component)
            if connected_nodes > 1:
                max_possible_edges = (connected_nodes * (connected_nodes - 1)) / 2
                density = edge_count / max_possible_edges if max_possible_edges > 0 else 0
            else:
                density = 0
            
            # Find top 5 connected friends
            if visualizer.graph.number_of_nodes() > 0:
                degrees = dict(visualizer.graph.degree())
                # Get top 5, sorted by degree
                top_nodes = sorted(degrees.items(), key=lambda x: x[1], reverse=True)[:5]
                top_friends_lines = []
                for i, (node, degree_count) in enumerate(top_nodes, 1):
                    name = friends_dict.get(node, {}).get('name', 'Unknown')
                    # Truncate long names
                    if len(name) > 18:
                        name = name[:15] + '...'
                    top_friends_lines.append(f"{i}. {name} ({degree_count})")
                top_friends_text = "\n".join(top_friends_lines)
            else:
                top_friends_text = "-"
            
            self.update_statistics(edges=edge_count, isolated=isolated_count, density=density, top_friends=top_friends_text)
            self.update_status("Network graph built", "Step 3 of 4 Complete", 75)

            if self.stop_requested:
                self.log("[Process] Stopped by user")
                self.update_status("Stopped by user", "Cancelled", 0)
                # Reset state without calling processing_complete since we didn't complete
                self.processing = False
                self.stop_requested = False
                self.root.after(0, lambda: self.generate_btn.config(state='normal'))
                self.root.after(0, lambda: self.stop_btn.config(state='disabled'))
                return

            # Step 4: Generate visualization
            self.update_status("Generating visualization...", "Step 4 of 4", 80)
            self.log("[Step 4/4] Creating interactive HTML visualization")
            
            # Save visualization in the exe directory
            output_file = os.path.join(self.exe_dir, 'vrchat_friend_network.html')
            dark_mode = self.dark_mode_var.get()
            show_heatmap = self.heatmap_var.get()
            show_edges = self.show_edges_var.get()
            
            visualizer.create_visualization(output_file, dark_mode, show_heatmap, show_edges)
            
            # Get community count from visualizer after generation
            try:
                import community as community_louvain
                partition = community_louvain.best_partition(visualizer.graph.subgraph(
                    [n for n in visualizer.graph.nodes() if visualizer.graph.degree(n) > 0]
                ), resolution=1.5)
                num_communities = len(set(partition.values()))
                self.update_statistics(communities=num_communities)
                self.log(f"[Step 4/4] Detected {num_communities} communities")
            except:
                pass
            
            self.output_path = output_file
            self.log(f"[Step 4/4] Saved to: {output_file}")
            self.update_status("Visualization complete", "Step 4 of 4 Complete", 95)

            # Open in browser if requested
            if self.auto_open_var.get():
                self.log("[Complete] Opening in browser")
                webbrowser.open('file://' + os.path.abspath(output_file))

            self.log("[Complete] Network visualization generated successfully")
            self.update_status("Complete", "All steps finished", 100)
            self.root.after(0, self.processing_complete)

        except Exception as e:
            error_msg = str(e)
            self.log(f"[Error] {error_msg}")
            self.root.after(0, lambda: self.processing_failed(error_msg))

    def processing_complete(self):
        """Called when processing completes successfully"""
        self.processing = False
        self.stop_requested = False
        self.generate_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.open_btn.config(state='normal')
        self.update_status("Complete - Ready to generate again", "", 100)

    def processing_failed(self, error_msg):
        """Called when processing fails"""
        self.processing = False
        self.stop_requested = False
        self.generate_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.progress['value'] = 0
        self.progress_pct_var.set("0%")
        self.update_status(f"Failed: {error_msg}", "", 0)

    def open_visualization(self):
        """Open the generated visualization"""
        # Check if we have a recent output path
        if self.output_path and os.path.exists(self.output_path):
            file_path = self.output_path
        else:
            # Look for the file in VFNV Data folder
            file_path = os.path.join(self.exe_dir, 'vrchat_friend_network.html')
        
        if os.path.exists(file_path):
            webbrowser.open('file:///' + os.path.abspath(file_path).replace(chr(92), '/'))
            self.log("[Action] Opened visualization in browser")
        else:
            self.log("[Error] No visualization file found")
            self.update_status("Error: No visualization to open")


def main():
    try:
        root = tk.Tk()
        app = VRChatNetworkGUI(root)
        
        # Auto-detect VRCX database on startup
        root.after(100, app.detect_vrcx)
        
        root.mainloop()
    except Exception as e:
        # Show error in a message box if GUI fails to start
        import tkinter.messagebox as mb
        error_msg = f"Failed to start application:\n\n{str(e)}\n\n{traceback.format_exc()}"
        try:
            root = tk.Tk()
            root.withdraw()
            mb.showerror("Startup Error", error_msg)
        except:
            # If even that fails, write to a log file
            with open("error_log.txt", "w") as f:
                f.write(error_msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
