import os
import sys
import subprocess

def run_build():
    print("=========================================")
    print("🚀 Starting Claude Code Proxy Packaging...")
    print("=========================================")

    # Define path constants
    base_dir = os.path.dirname(os.path.abspath(__file__))
    app_entry = os.path.join(base_dir, "app.py")
    ui_folder = os.path.join(base_dir, "ui")

    if not os.path.exists(app_entry):
        print(f"❌ Error: app.py not found at {app_entry}")
        sys.exit(1)

    # Clean previous build artifacts
    print("🧹 Cleaning old build workspace...")
    for folder in ["build", "dist"]:
        folder_path = os.path.join(base_dir, folder)
        if os.path.exists(folder_path):
            import shutil
            try:
                shutil.rmtree(folder_path)
            except Exception as e:
                print(f"Warning: could not delete {folder_path}: {e}")

    # Build PyInstaller parameters
    # '--onefile' generates single double-clickable binary
    # '--windowed' / '--noconsole' ensures no ugly console window pops up upon start
    params = [
        app_entry,
        "--name=ClaudeCodeProxy",
        "--onefile",
        "--windowed",
        "--clean",
    ]

    # Include static UI files
    # PyInstaller maps path separator on Windows as ';' and on Mac/Linux as ':'
    path_sep = os.pathsep
    params.append(f"--add-data={ui_folder}{path_sep}ui")

    # Optional native application icons integration
    assets_dir = os.path.join(base_dir, "assets")
    if os.path.exists(assets_dir):
        if sys.platform == "darwin":
            mac_icon = os.path.join(assets_dir, "icon.icns")
            if os.path.exists(mac_icon):
                params.append(f"--icon={mac_icon}")
        elif sys.platform == "win32":
            win_icon = os.path.join(assets_dir, "icon.ico")
            if os.path.exists(win_icon):
                params.append(f"--icon={win_icon}")

    print(f"📦 Compiling workspace with options: {' '.join(params)}")

    # Execute PyInstaller compiler
    try:
        import PyInstaller.__main__
        PyInstaller.__main__.run(params)
        print("\n=========================================")
        print("🎉 Packaging completed successfully!")
        print(f"📍 Binary output path: {os.path.join(base_dir, 'dist')}")
        print("=========================================")
    except ImportError:
        print("\n⚠️ PyInstaller is not installed in current environment.")
        print("Installing pyinstaller dynamically...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
            import PyInstaller.__main__
            PyInstaller.__main__.run(params)
            print("\n🎉 Compiling succeeded after installing dependencies!")
        except Exception as err:
            print(f"❌ Dynamic build failed: {err}")
            sys.exit(1)

if __name__ == "__main__":
    run_build()
