# System Monitor

A terminal-based system monitor similar to NMON that displays real-time system information. Available in two versions:

- **`rpi_monitor.py`**: Optimized for Raspberry Pi hardware
- **`ubuntu_monitor.py`**: Adapted for Ubuntu x86_64 systems

## Features

### Common Features (Both Versions)
- **CPU Utilization**: Per-core and average CPU usage with horizontal bars
- **Memory Utilization**: RAM usage statistics with visual bar
- **Network Activity**: Real-time network I/O with horizontal bar charts
- **Disk Activity**: Disk I/O statistics with horizontal bar charts
- **Top Processes**: Top 5 processes by CPU usage
- **Logged Users**: List of currently logged-in users
- **Uptime**: System uptime display

### Raspberry Pi Version (`rpi_monitor.py`)
- **Temperature Monitoring**: CPU and GPU temperatures via vcgencmd
- **Fan Control**: PWM fan speeds and cooling device states
- **Hardware Sensors**: NVMe and ADC temperature monitoring

### Ubuntu Version (`ubuntu_monitor.py`)
- **Temperature Monitoring**: Intel CPU temperatures via thermal zones and hwmon
- **Disk Utilization**: Total disk space usage across all partitions with horizontal bar
- **Enhanced Hardware Support**: Support for modern x86_64 hardware sensors

## Installation

### For Raspberry Pi (`rpi_monitor.py`)
1. Install required Python package:
   ```bash
   pip3 install -r requirements.txt
   ```

2. Make the script executable:
   ```bash
   chmod +x rpi_monitor.py
   ```

### For Ubuntu (`ubuntu_monitor.py`)
1. Install psutil via system package manager:
   ```bash
   sudo apt install python3-psutil -y
   ```

2. Make the script executable:
   ```bash
   chmod +x ubuntu_monitor.py
   ```

## Usage

### Raspberry Pi Version
```bash
./rpi_monitor.py
# or
python3 rpi_monitor.py
```

### Ubuntu Version
```bash
./ubuntu_monitor.py
# or
python3 ubuntu_monitor.py
```

### Controls

- Press `q` or `Q` to quit
- The display updates every second automatically

## Requirements

### Both Versions
- Python 3.x
- psutil library
- curses (included with Python)

### Raspberry Pi Version
- Raspberry Pi OS (tested on Pi 5)
- vcgencmd utility (for GPU temperature)

### Ubuntu Version
- Ubuntu 18.04+ or similar Linux distribution
- x86_64 architecture

## Technical Notes

### Raspberry Pi Version
- CPU temperature: `/sys/class/thermal/thermal_zone0/temp`
- GPU temperature: `vcgencmd measure_temp` command
- Fan control: PWM via `/sys/class/hwmon/hwmon3/fan1_input`
- Cooling states: `/sys/class/thermal/cooling_device0/cur_state`

### Ubuntu Version
- CPU temperatures: Multiple thermal zones and hwmon sensors
- Disk utilization: psutil disk_partitions() and disk_usage()
- Enhanced filtering: Excludes virtual filesystems (tmpfs, proc, sys, etc.)
- Network interfaces: Support for modern naming (wlp*, enp*)

### Common Features
- Network and disk I/O: `/proc/net/dev` and `/proc/diskstats`
- Interface adapts to terminal size automatically
- Real-time updates every second
- Two-column layout for efficient space usage

## Documentation

- **`UBUNTU_ADAPTATION.md`**: Detailed documentation of all modifications made for Ubuntu compatibility, including code changes, system analysis, and technical details.