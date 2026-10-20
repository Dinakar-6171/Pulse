# Pulse — PC Health Monitor

Pulse is a Windows desktop application built with Python and PySide6 to monitor PC health and performance through a modern dashboard.

## Features

- **CPU Monitoring** — View processor usage and available temperature readings.
- **RAM Monitoring** — Track memory usage.
- **GPU Monitoring** — View NVIDIA GPU information, utilization, and supported sensor readings.
- **Storage Health** — Check available drive health information through SMART monitoring where supported.
- **Bottleneck Detective** — Analyze system metrics to identify potential performance bottlenecks.
- **Performance Dashboard** — View system metrics through a desktop interface.

## Built With

- Python
- PySide6
- NVIDIA Management Library (`nvidia-ml-py`)
- smartmontools for supported storage-health readings

## Platform

Windows 10/11

Some metrics depend on the hardware, drivers, permissions, and installed monitoring tools. Unsupported readings are not guaranteed to be available.

## Project Status

Pulse is under active development. Features and compatibility may change as the project evolves.

## Running from Source

1. Clone this repository.
2. Create and activate a Python virtual environment.
3. Install the dependencies listed in `requirements.txt`.
4. Run `main.py` using the environment's Python interpreter.

See [BUILDING_WINDOWS.md](BUILDING_WINDOWS.md) for Windows packaging instructions.

## License

No license has been added yet. All rights are reserved by default until a license is chosen.
