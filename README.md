# Raspberry Pi System Monitor

A terminal-based system monitor for Raspberry Pi, similar to NMON, that displays real-time system information.

## Features

- **Temperature Monitoring**: CPU and GPU temperatures
- **Network Activity**: Real-time network I/O with horizontal bar charts
- **Uptime**: System uptime display
- **Logged Users**: List of currently logged-in users
- **Disk Activity**: Disk I/O statistics with horizontal bar charts
- **CPU Utilization**: Per-core and average CPU usage
- **Memory Utilization**: RAM usage statistics
- **Top Processes**: Top 5 processes by CPU usage

## Installation

1. Install required Python package:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Make the script executable (already done):
   ```bash
   chmod +x rpi_monitor.py
   ```

## Usage

Run the monitor:
```bash
./rpi_monitor.py
```

Or:
```bash
python3 rpi_monitor.py
```

### Controls

- Press `q` or `Q` to quit
- The display updates every second automatically

## Requirements

- Python 3.x
- psutil library
- curses (included with Python)
- Raspberry Pi OS (tested on Pi 5)

## Notes

- The program uses `/sys/class/thermal/thermal_zone0/temp` for CPU temperature
- GPU temperature is obtained via `vcgencmd measure_temp` command
- Network and disk statistics are read from `/proc/net/dev` and `/proc/diskstats`
- The interface adapts to terminal size automatically