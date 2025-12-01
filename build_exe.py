"""
Build script for creating standalone executable
Run with: python build_exe.py
"""
import subprocess
import sys
import os

def build_exe():
    """Build executable using PyInstaller"""
    
    print("Building VRChat Friend Network Visualizer executable...")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name=VRChat_Network_Visualizer",
        "--onefile",
        "--windowed",
        "--icon=NONE",
        "--add-data=extract_vrcx_mutuals.py;.",
        "--add-data=fetch_vrchat_mutuals.py;.",
        "--add-data=vrchat_friend_network_visualizer.py;.",
        "--clean",
        "vrchat_network_gui.py"
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("\nBuild complete!")
        print("Executable location: dist/VRChat_Network_Visualizer.exe")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed: {e}")
        print("\nMake sure PyInstaller is installed:")
        print("  pip install pyinstaller")
        sys.exit(1)

if __name__ == "__main__":
    build_exe()
