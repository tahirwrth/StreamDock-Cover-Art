# Cover Art Plugin for Steam Dock

Windows Media Cover Art displayed in a button on a AJAZZ Stream Dock device

## Features

- Live display of cover art based on current media
- Fallback to default image if no media playing


## Installation and Usage

1. Download latest release or compile yourself

2. Close Stream Dock AJAZZ software if open

3. Copy `com.wrth.mediacover` to AJAZZ StreamDock plugin directory. i.e.,
```
%APPDATA%\HotSpot\StreamDock\plugins
```

3. Open Stream Dock AJAZZ software. If installation is successful, `Media` category will be present on the right-side menu under `Key`

4. Drag `Cover Art` action from `Media` onto desired key

## Development Environment Setup and Build

1. Create virtual environment:
```bash
python -m venv venv
```

2. Activate virtual environment:
- Windows:
```bash
venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Use PyInstaller to package into an executable file:
```bash
pyinstaller main.spec
```
