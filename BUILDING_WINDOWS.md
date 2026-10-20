# Building Pulse for Windows

## Entry point and output

The application entry point is `main.py`. The GUI release build is a PyInstaller `onedir` application at `dist\Pulse\Pulse.exe`; distribute the entire `dist\Pulse` folder, not just the EXE. The separate diagnostic build is at `dist-debug\Pulse\Pulse.exe`. This PyInstaller version places bundled resources and runtime files under `_internal`, including `assets\logo.svg`, `assets\logo.png`, and `assets\logo.ico`.

## Build prerequisites

- Build on Windows x64 using the project `.venv` and its Python 3.13 interpreter. The resulting executable is for 64-bit Windows 10/11; validate on the oldest Windows 10 release you intend to support.
- Install build-only dependencies with `\.venv\Scripts\python.exe -m pip install -r requirements-build.txt`.
- `smartctl.exe` is not bundled. Users may install smartmontools separately; Pulse discovers it on PATH, in standard Program Files locations, or through `PULSE_SMARTCTL_PATH`.
- NVIDIA GPU readings are optional and require compatible NVIDIA hardware/drivers on the destination PC. Other CPU/RAM/disk readings remain available without an NVIDIA GPU.

## Build commands

From the project directory in PowerShell:

Build the debuggable console version first. Its output and work files are separate from the GUI release:

```powershell
$env:PULSE_DEBUG_BUILD = "1"
\.venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist-debug --workpath build-debug Pulse.spec
Remove-Item Env:PULSE_DEBUG_BUILD
```

Run and diagnose `dist-debug\Pulse\Pulse.exe` before making the release build. The debug build keeps a console and bootloader diagnostics. Do not redistribute it as the normal desktop release.

After the debug build works, create the windowed release build:

```powershell
\.venv\Scripts\pyinstaller.exe --clean --noconfirm --distpath dist --workpath build Pulse.spec
```

Both builds use the same spec; with `PULSE_DEBUG_BUILD` unset, the release opens without a console. Build commands do not overwrite the other build's output folder.

Full preparation and verification from the project folder:

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Runtime notes

Pulse stores no generated files in the installation directory. Its logo is painted from the existing source artwork, and the bundled assets are read-only resources. SMART scans are explicitly requested from Storage Health and run in a worker with a timeout. If `smartctl` is absent or a drive/controller does not expose SMART, Pulse explains that rather than inventing health information.

For a smoke test, run `dist-debug\Pulse\Pulse.exe` first and inspect its console, then run `dist\Pulse\Pulse.exe`, confirm CPU/RAM/disk/GPU metrics, visit Bottleneck Detective and Storage Health, and close the window. On a test machine without NVIDIA hardware, SMART support, or temperature sensors, those fields should report unavailable while the rest of the app stays open.

PyInstaller output is platform-specific. Build on Windows for Windows; test on both Windows 10 and Windows 11 before public release. Check smartmontools redistribution/licensing independently before bundling that external utility. Code signing and installer creation are not included in this first onedir release.
