# Multi-Platform System Monitor

A cross-platform terminal-based system monitor similar to NMON that displays real-time system information. Originally designed for Raspberry Pi, now featuring a comprehensive macOS implementation with advanced Apple Silicon support:

- **`rpi_monitor.py`**: Optimized for Raspberry Pi hardware
- **`ubuntu_monitor.py`**: Adapted for Ubuntu x86_64 systems  
- **`macos_monitor.py`**: **Featured version** adapted for macOS (Apple Silicon & Intel)

## Features

### Common Features (All Versions)
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

### macOS Version (`macos_monitor.py`) - **Featured Implementation**
- **Apple Silicon Support**: P-Core/E-Core labeling for M1/M2/M3 chips
- **Advanced Temperature Monitoring**: CPU temperature via powermetrics (sudo) or intelligent load estimation
- **APFS Filesystem**: Accurate disk usage calculation for macOS volume structure
- **Smart Network Filtering**: Dynamic interface detection with 5-minute inactivity timeout
- **Native Integration**: Uses BSD system calls and Darwin kernel interfaces
- **Robust Authentication**: Single sudo prompt at startup with graceful fallback

## Quick Start (macOS - Recommended)

The macOS version represents the most advanced implementation with the latest features:

```bash
git clone https://github.com/kdesch5000/rpi-monitor.git
cd rpi-monitor
chmod +x macos_monitor.sh
./macos_monitor.sh
```

The setup script automatically creates a Python virtual environment, installs dependencies, and launches the monitor.

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

### For macOS (`macos_monitor.py`)
1. Run the setup script (handles virtual environment and dependencies):
   ```bash
   chmod +x macos_monitor.sh
   ./macos_monitor.sh
   ```

   **Note:** The monitor will prompt once for sudo access during startup for accurate temperature readings. This is optional - you can decline and use temperature estimation instead. No sudo prompts occur during monitoring.

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

### macOS Version
```bash
./macos_monitor.sh
# or
source venv/bin/activate && python3 macos_monitor.py
# Simple text version (no curses):
source venv/bin/activate && python3 macos_monitor_simple.py
```

**Startup Process:**
- Checks/creates Python virtual environment
- Prompts once for optional sudo access (for accurate temperature readings)
- Starts monitoring interface with no further interruptions

### Controls

- Press `q` or `Q` to quit
- The display updates every second automatically

## Requirements

### All Versions
- Python 3.x
- psutil library
- curses (included with Python)

### Raspberry Pi Version
- Raspberry Pi OS (tested on Pi 5)
- vcgencmd utility (for GPU temperature)

### Ubuntu Version
- Ubuntu 18.04+ or similar Linux distribution
- x86_64 architecture

### macOS Version  
- macOS 10.14+ (tested on macOS Sonoma 14.6)
- Apple Silicon (M1/M2/M3) or Intel architecture
- Optional: sudo access for accurate temperature readings

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

### macOS Version
- CPU temperature: powermetrics command or load-based estimation
- APFS filesystem: Handles complex volume structure (/System/Volumes/Data, etc.)
- Network filtering: Dynamic interface detection with 5-minute inactivity timeout
- Apple Silicon: P-Core (0-3) and E-Core (4-7) identification for M1 chips
- System calls: Uses BSD sysctl and Darwin kernel interfaces

### Common Features
- Network and disk I/O: Platform-specific interfaces (Linux: /proc, macOS: psutil)
- Interface adapts to terminal size automatically
- Real-time updates every second
- Two-column layout for efficient space usage

## Documentation

- **`UBUNTU_ADAPTATION.md`**: Detailed documentation of all modifications made for Ubuntu compatibility, including code changes, system analysis, and technical details.
- **`MACOS_ADAPTATION.md`**: Comprehensive documentation of macOS adaptation, including Apple Silicon support, APFS filesystem handling, and network timeout features.