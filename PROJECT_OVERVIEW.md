# Raspberry Pi Monitor - Project Overview

## Project Structure
```
rpi-monitor/
├── rpi_monitor.py      # Main monitoring application (695 lines)
├── requirements.txt    # Dependencies (psutil>=5.8.0)
├── README.md          # User documentation
└── PROJECT_OVERVIEW.md # This file
```

## Application Architecture

### Core Class: `RPiMonitor`
- Main application class handling all monitoring functionality
- Uses curses for terminal-based UI with color support
- Updates display every 1 second with graceful error handling
- Implements 2-column layout that adapts to terminal width (minimum 80 columns)

### Key Data Structures
- `network_history`: Historical network stats (60 samples per interface)
- `disk_history`: Historical disk I/O stats (60 samples per device)
- `max_temps`: Tracks maximum temperatures seen per sensor
- `max_network_rates`: Tracks peak network rates per interface
- `max_disk_rates`: Tracks peak disk I/O rates

## Monitoring Features

### Temperature Monitoring (`get_temperature()`)
- **CPU**: `/sys/class/thermal/thermal_zone0/temp`
- **GPU**: `vcgencmd measure_temp` command
- **NVMe**: `/sys/class/hwmon/hwmon1/temp1_input` and `temp2_input`
- **ADC**: `/sys/class/hwmon/hwmon2/temp1_input`
- Color coding: Red >70°C, Yellow >60°C, Normal otherwise
- Tracks and displays maximum temperatures reached

### Fan Speed Monitoring (`get_fan_speeds()`)
- **PWM Fan**: `/sys/class/hwmon/hwmon3/fan1_input`
- **Cooling State**: `/sys/class/thermal/cooling_device0/cur_state`
- Color coding based on RPM: Red >6000, Yellow >3000

### Network Activity (`get_network_stats()`)
- Reads from `/proc/net/dev`
- Calculates RX/TX rates in KB/s
- Uses logarithmic scaling for better visualization
- Assumes 1Gbit (125,000 KB/s) for ethernet, 400Mbps (50,000 KB/s) for WiFi
- Tracks historical maximums for context

### Disk I/O (`get_disk_stats()`)
- Reads from `/proc/diskstats`
- Summarizes activity across all storage devices (sd*, mmcblk*, nvme*)
- Converts sector counts to KB/s rates
- Uses logarithmic scaling with 100MB/s (100,000 KB/s) assumed maximum

### Storage Utilization (`get_storage_capacity()`)
- Uses psutil to get filesystem usage statistics
- Monitors root filesystem (/) and additional mount points
- Shows used/total capacity in GB and percentage
- Displays capacity bars using the same visualization as other metrics
- Handles multiple filesystems and gracefully skips inaccessible ones

### System Information
- **Uptime**: `/proc/uptime` formatted as days:hours:minutes:seconds
- **Users**: `who` command output
- **CPU**: psutil per-core and average utilization
- **Memory**: psutil virtual memory statistics
- **Processes**: Top 5 by CPU usage via psutil

## UI Implementation

### Display Layout
- **Left Column**: Uptime, temperatures, fan speeds, CPU utilization, disk activity, storage utilization
- **Right Column**: Network activity, memory usage, logged users, top processes
- **Header**: Title and current timestamp
- **Footer**: Quit instruction

### Visual Elements
- Horizontal bar charts using Unicode characters (█ and ░)
- Color coding: Green text, Yellow/Red bars, Cyan headers
- Logarithmic scaling for network and disk activity visualization
- Historical maximum tracking with [M:xxx] notation

### Color Scheme (curses pairs)
1. Green text (normal data)
2. Yellow bars (<100%)
3. Red bars (≥100% or high values)
4. White text
5. Cyan headers

## Technical Details

### Data Collection Methods
- Direct file system reads for temperatures and system stats
- subprocess calls for GPU temperature and user info
- psutil library for CPU, memory, and process information
- Error handling with graceful degradation

### Performance Optimizations
- Non-blocking input with 100ms timeout
- Logarithmic scaling prevents visualization issues with low activity
- Historical data limited to 60 samples (1 minute at 1Hz)
- Efficient terminal updates using curses

### Error Handling
- Try/except blocks around all system calls
- Graceful degradation when sensors unavailable
- Display continues even if individual components fail

## Usage Patterns
- Designed for continuous monitoring sessions
- Single-key quit ('q' or 'Q')
- Automatic terminal size adaptation
- No configuration files - uses sensible defaults

## Hardware Compatibility
- Tested on Raspberry Pi 5
- Supports various thermal zones and hardware monitors
- Adapts to available sensors (missing sensors show as 0 or are omitted)
- Works with different storage types (SD cards, NVMe, USB drives)

## Dependencies
- Python 3.x (uses standard library extensively)
- psutil ≥5.8.0 (only external dependency)
- curses (included with Python)
- Standard Unix tools (vcgencmd, who)