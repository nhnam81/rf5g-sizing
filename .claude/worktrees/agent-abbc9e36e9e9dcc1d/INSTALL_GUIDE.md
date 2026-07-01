# rf5g-sizing — Installation Guide

## System Requirements

| Requirement | Minimum |
|------------|---------|
| OS | Windows 10 (64-bit) or later |
| Disk Space | ~500 MB |
| RAM | 4 GB |
| Browser | Chrome, Edge, or Firefox |

**No Python installation required.** The installer includes a self-contained Python 3.12 runtime with all dependencies pre-bundled.

## Installation Steps

### 1. Run the Installer

Double-click `rf5g-sizing-1.0.0-setup.exe`.

> ⚠️ **Windows SmartScreen**: If you see "Windows protected your PC", click **More info** → **Run anyway**. This appears because the app is not code-signed.

### 2. Follow the Wizard

1. **Welcome** → Click **Next**
2. **License Agreement** → Accept MIT License → **Next**
3. **Install Directory** → Default: `C:\Users\<you>\rf5g-sizing` → **Next**
4. **Install** → Wait for extraction (~1-2 minutes)
5. **Finish** → Check "Launch rf5g-sizing" → **Finish**

### 3. First Launch

The app starts a local Streamlit server and opens your browser at:

```
http://localhost:8501
```

If the browser doesn't open automatically, open it manually and go to the URL above.

## Uninstallation

- **Start Menu** → rf5g-sizing → Uninstall
- Or: Settings → Apps → rf5g-sizing → Uninstall

## Troubleshooting

### "Embedded Python not found"

Reinstall the application. The `python\` folder is required for the app to run.

### Port 8501 already in use

Close the existing Streamlit process, or edit `run_rf5g.bat` and change `PORT=8501` to another port.

### Browser doesn't open

Open your browser and go to `http://localhost:8501` manually.

### Antivirus blocks the installer

Some antivirus products may quarantine unsigned executables. Add an exclusion for the installer or the install directory.

## Silent Install (Advanced)

```cmd
rf5g-sizing-1.0.0-setup.exe /VERYSILENT /DIR=C:\rf5g-sizing
```

## What's Installed

| Path | Description |
|------|------------|
| `python\` | Embedded Python 3.12 + packages |
| `rf5g\` | Application source code |
| `run_rf5g.bat` | Launcher script |
| `README.md` | Project overview |
| `INSTALL_GUIDE.md` | This file |
| `USER_GUIDE.md` | Usage instructions |

## File Locations

- **Install dir**: `C:\Users\<you>\rf5g-sizing\` (default)
- **Desktop shortcut**: rf5g-sizing (optional)
- **Start Menu**: rf5g-sizing group