# VRChat Friend Network Visualizer

A standalone application that visualizes your VRChat friend network using VRCX database and VRChat API.

## What's Included

- `vrchat_network_gui.py` - Main GUI application with integrated login
- `fetch_vrchat_mutuals.py` - VRChat API integration for mutual friends
- `extract_vrcx_mutuals.py` - VRCX database extraction for friend list
- `vrchat_friend_network_visualizer.py` - Core visualization engine
- `build_exe.py` - PyInstaller build script
- `build_exe.bat` - Windows batch file to build executable
- `run_gui.bat` - Quick launch script for the GUI
- `VRChat_Network_Visualizer.spec` - PyInstaller build configuration
- `requirements.txt` - Python dependencies

## Quick Start

### Option 1: Run from Source

**Requirements:**
- Python 3.8 or higher
- Install dependencies: `pip install -r requirements.txt`

**To Run:**
```bash
python vrchat_network_gui.py
```
Or double-click `run_gui.bat` for quick launch

### Option 2: Build Executable (Recommended for Distribution)

1. Install dependencies: `pip install -r requirements.txt`
2. Run build script:
   ```bash
   .\build_exe.bat
   ```
   Or directly: `python build_exe.py`
3. Find your executable in `dist\VRChat_Network_Visualizer.exe`

**No additional files needed** - The EXE is completely standalone!

## Using the Application

1. **Launch the app** - Double-click the .exe or run `python vrchat_network_gui.py`
2. **Browse for VRCX database** - Click "Browse" or it will auto-detect at default location
3. **Enter VRChat credentials** (if no saved session exists)
   - Username and password
   - 2FA code if prompted
4. **Configure options:**
   - Dark Mode (Visualization) - Toggle between light/dark theme for the HTML output
   - Auto-open in browser - Opens visualization automatically when complete (enabled by default)
5. **Click "Generate"** - The app will:
   - Extract your friends list from VRCX database
   - Log into VRChat API (only if no saved session)
   - Fetch mutual connections for all friends
   - Build network graph and detect communities
   - Generate interactive HTML visualization
6. **View your network** - Opens automatically in your default browser

**Note:** 
- First run requires VRChat login and may take 5-10 minutes for large friend lists (500+)
- Login session is saved for future use (no need to log in every time)
- Click "Stop" button to cancel generation mid-process
- Use "Clear Data" to remove saved session and start fresh

## Features

**GUI:**
- Auto-detect VRCX database location
- Integrated VRChat login with 2FA support
- Real-time progress tracking with percentage
- Stop button to cancel mid-generation
- Clear data button to remove all cached files
- Light/Dark theme toggle for GUI
- Network statistics display (friends, edges, communities, density)
- Top connected friends list

**Visualization:**
- Interactive network graph with Louvain community detection
- Search by friend name or user ID (e.g., "usr_xxxxx")
- Theme toggle (light/dark modes)
- Click nodes to highlight connections
- Ctrl+Click for multi-select
- Hover tooltips with friend details and mutual connections
- Color-coded communities with spatial centrality layout
- Auto-layout with force-directed positioning

## How It Works

The application combines two data sources:

1. **VRCX Database** - Extracts your complete friends list locally
2. **VRChat API** - Fetches mutual friend connections for each friend

**Process:**
1. Reads friend list from VRCX SQLite database
2. Logs into VRChat API with your credentials
3. For each friend, fetches their mutual connections
4. Builds network graph showing who knows who
5. Detects friend communities using Louvain algorithm
6. Generates interactive HTML visualization

**Generated Files (stored in "VFNV Data" folder next to exe):**
- `vrchat_session.pkl` - Saved login session (reused automatically)
- `vrcx_mutual_friends.json` - Cached friend and mutual data
- `vrchat_friend_network.html` - Interactive visualization

Files are organized in a "VFNV Data" subfolder. The HTML visualization can be shared with others.

## Distribution

### Sharing the Executable

1. Build using `build_exe.bat`
2. Share the file: `dist\VRChat_Network_Visualizer.exe`
3. That's it! The EXE is completely standalone

**To share without your personal data:**
- Just share the .exe file
- Don't include the "VFNV Data" folder (it contains your session and friend data)
- Or use "Clear Data" button before sharing to remove all personal data

**Recipients need:**
- Windows 7 or higher
- VRCX installed (for database access)
- VRChat account credentials
- Internet connection (to fetch mutual connections from API)

## System Requirements

### For Running Source:
- Windows 7 or higher (or macOS/Linux with appropriate Python)
- Python 3.8+
- ~50MB disk space for dependencies

### For Running Executable:
- Windows 7 or higher
- No Python required
- ~100MB disk space (executable includes Python runtime)

## Troubleshooting

**"No database selected"**
- Click "Browse" to manually select your VRCX database
- Default location: `%APPDATA%\VRCX\VRCX.sqlite3`
- Make sure VRCX is installed and has been run at least once

**"Login required"**
- Enter your VRChat username and password
- Click "Generate" again after entering credentials
- Check that credentials work by logging into VRChat website

**2FA prompt**
- Enter your 2FA code when prompted
- The dialog may appear behind other windows
- Session will be saved after successful login

**"No mutual data retrieved"**
- This means the VRChat API login failed
- Check your credentials and try again
- Wait a few minutes if you've tried multiple times (rate limiting)

**Build fails**
- Install all dependencies: `pip install -r requirements.txt`
- Python 3.8+ required
- Try: `pip install --upgrade pyinstaller`

**Antivirus blocks executable**
- PyInstaller executables are sometimes flagged
- Add an exception or build from source yourself to verify safety

**Generation is slow**
- Normal for 500+ friends (5-10 minutes)
- VRChat API has rate limits that must be respected
- Click "Stop" button if you want to cancel

## File Sizes

- **Source files**: ~200KB total
- **Dependencies**: ~50MB when installed
- **Built executable**: ~80-100MB (includes Python runtime and all libraries)

## Privacy & Security

- **Hybrid data sources** - Uses local VRCX database + VRChat API
- **No data collection** - Your credentials and friend data stay on your machine
- **Session storage** - Only saves the session cookie locally (not your password)
- **Open source** - All code is visible and auditable
- **Local processing** - Network graph is generated entirely on your computer
- **Generated files** - All outputs saved next to the executable for easy management

## Advanced

### Build Options

Edit `VRChat_Network_Visualizer.spec` or `build_exe.py` to customize:
- Console mode (show/hide terminal window)
- Icon file (replace with your own .ico)
- Excluded modules for smaller file size
- UPX compression settings

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Verify you have the latest version of the files
3. Ensure VRCX is installed and has been run at least once
4. Test VRChat login credentials on vrchat.com

## License

This is open source software. Feel free to modify and distribute.
