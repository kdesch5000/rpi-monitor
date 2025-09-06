# Ubuntu System Monitor Adaptation

This document explains the modifications made to adapt the Raspberry Pi system monitor for Ubuntu x86_64 systems.

## Overview

The original `rpi_monitor.py` was designed specifically for Raspberry Pi hardware and used RPi-specific system interfaces. The new `ubuntu_monitor.py` has been adapted to work on standard Ubuntu x86_64 systems while maintaining the same functionality and user interface.

## System Analysis

### Target System
- **OS**: Ubuntu 24.04.3 LTS (Noble)
- **Architecture**: x86_64
- **CPU**: Intel N97 (4 cores)
- **Kernel**: Linux 6.8.0-79-generic

### Hardware Differences
| Component | Raspberry Pi | Ubuntu x86_64 |
|-----------|-------------|---------------|
| CPU Temperature | `/sys/class/thermal/thermal_zone0/temp` | Multiple thermal zones + hwmon sensors |
| GPU Temperature | `vcgencmd measure_temp` | Not applicable / integrated |
| Fan Control | PWM fan via hwmon3 | System-managed or not present |
| Cooling | `/sys/class/thermal/cooling_device0` | Standard x86 thermal management |
| Disk Interfaces | `mmcblk`, `sd` | `nvme`, `sd`, `vd`, `hd` |
| Network Interfaces | `wlan0`, `eth0` | `wlp*`, `enp*`, `eth*` |

## Code Modifications

### 1. Class Rename and Title Update
```python
# Before
class RPiMonitor:
    # ...
    self.screen.addstr(0, 0, "Raspberry Pi System Monitor", header_color)

# After  
class UbuntuMonitor:
    # ...
    self.screen.addstr(0, 0, "Ubuntu System Monitor", header_color)
```

### 2. Temperature Monitoring Overhaul

#### Removed RPi-Specific Code
- **GPU Temperature**: Removed `vcgencmd measure_temp` command execution
- **NVMe Sensors**: Removed hardcoded `/sys/class/hwmon/hwmon1/temp1_input` paths
- **ADC Temperature**: Removed `/sys/class/hwmon/hwmon2/temp1_input` monitoring

#### Added x86 CPU Temperature Detection
```python
def get_temperature(self):
    """Get all available system temperatures"""
    temps = {}
    
    # CPU thermal zones (enhanced for x86)
    for i in range(0, 5):  # Check thermal_zone0 through thermal_zone4
        try:
            with open(f'/sys/class/thermal/thermal_zone{i}/temp', 'r') as f:
                temp = float(f.read().strip()) / 1000
                # Read zone type for meaningful names
                with open(f'/sys/class/thermal/thermal_zone{i}/type', 'r') as type_f:
                    zone_type = type_f.read().strip()
                    if 'x86_pkg_temp' in zone_type:
                        temps['CPU_PKG'] = temp
                    elif 'acpi' in zone_type:
                        temps['ACPI'] = temp
                    else:
                        temps[f'Zone{i}'] = temp
        except:
            pass
    
    # Intel coretemp hwmon sensors
    hwmon_paths = ['/sys/class/hwmon/hwmon1', '/sys/class/hwmon/hwmon0']
    for hwmon_path in hwmon_paths:
        if os.path.exists(hwmon_path):
            for temp_file in ['temp1_input', 'temp2_input', 'temp3_input']:
                # Read per-core temperatures with labels
```

### 3. Removed Fan Speed Monitoring
Completely removed the `get_fan_speeds()` function and its display logic since:
- Ubuntu systems typically use automatic fan control
- No standard interface for fan speed monitoring on x86 systems
- PWM fan control is hardware-specific and not universally available

### 4. Updated Temperature Thresholds
```python
# Before (RPi-optimized)
if temp > 70:    # Red warning
    color = curses.color_pair(3)
elif temp > 60:  # Yellow caution
    color = curses.color_pair(2)

# After (x86-optimized)  
if temp > 80:    # Red warning (higher for x86 CPUs)
    color = curses.color_pair(3)
elif temp > 70:  # Yellow caution
    color = curses.color_pair(2)
```

### 5. Enhanced Disk Device Detection
```python
# Before
if device.startswith(('sd', 'mmcblk', 'nvme')):

# After
if device.startswith(('sd', 'nvme', 'vd', 'hd')):  # Added vd, hd for Ubuntu
```

### 6. Network Interface Compatibility
```python
# Before
if iface.startswith('wlan'):
    max_capacity = 50000  # WiFi capacity

# After
if iface.startswith('wlan') or iface.startswith('wlp'):  # Added wlp* for modern naming
    max_capacity = 50000  # WiFi capacity
```

### 7. Performance Optimizations for x86

#### Increased Disk Performance Expectations
```python
# Before (RPi SD card/eMMC optimized)
max_disk_rate = 100000  # KB/s (100MB/s)

# After (SSD optimized)
max_disk_rate = 500000  # KB/s (500MB/s)
```

#### Temperature Field Width Adjustment
```python
# Before
name_field = f"{name}:"[:6].ljust(6)  # RPi sensor names are short

# After
name_field = f"{name}:"[:8].ljust(8)  # x86 sensor names can be longer (Core1, CPU_PKG)
```

## Dependency Management

### Installation Method Change
```bash
# Ubuntu 24.04 uses externally-managed Python environment
# Before: pip3 install -r requirements.txt
# After: sudo apt install python3-psutil -y
```

The system uses Ubuntu's package manager instead of pip to avoid conflicts with the system-managed Python environment.

## Testing Results

### System Detection
- ✅ CPU: Intel N97 (4 cores) detected correctly
- ✅ Temperature sensors: Multiple thermal zones found
- ✅ Network interfaces: Detected successfully
- ✅ Memory monitoring: Working via psutil
- ✅ Disk I/O: Monitoring active devices

### Functionality Verification
- ✅ Real-time CPU usage per core
- ✅ Temperature monitoring with color coding
- ✅ Network activity with logarithmic scaling
- ✅ Disk I/O monitoring
- ✅ **Disk utilization monitoring with horizontal bar**
- ✅ Memory utilization display
- ✅ Process monitoring (top 5 by CPU)
- ✅ User session tracking
- ✅ Two-column terminal layout

## Usage Instructions

### Running the Monitor
```bash
# Make executable (already done)
chmod +x ubuntu_monitor.py

# Run the monitor
./ubuntu_monitor.py

# Or with Python directly
python3 ubuntu_monitor.py
```

### Controls
- Press `q` or `Q` to quit
- Display updates automatically every second
- Terminal resizing is supported

## Compatibility Notes

### What Works Unchanged
- Core system monitoring via `/proc` and `/sys` interfaces
- psutil library functions
- Curses-based terminal UI
- Network and disk statistics parsing
- Process monitoring
- Memory utilization

### What Required Adaptation
- Hardware-specific temperature sensors
- Device naming conventions
- Performance expectations and scaling
- Temperature warning thresholds

## File Structure

```
rpi-monitor/
├── rpi_monitor.py           # Original Raspberry Pi version
├── ubuntu_monitor.py        # New Ubuntu x86_64 version
├── requirements.txt         # Python dependencies
├── README.md               # Original documentation
└── UBUNTU_ADAPTATION.md    # This documentation
```

### 8. Added Disk Utilization Monitoring

#### New Function: `get_disk_usage()`
```python
def get_disk_usage(self):
    """Get disk utilization for all mounted filesystems"""
    disk_usage = []
    total_used = 0
    total_size = 0
    
    # Get all disk partitions and filter out virtual filesystems
    partitions = psutil.disk_partitions()
    for partition in partitions:
        # Skip virtual/special filesystems
        if partition.fstype in ['tmpfs', 'devtmpfs', 'proc', 'sysfs', ...]:
            continue
        if partition.mountpoint in ['/dev', '/proc', '/sys', '/run']:
            continue
        
        # Calculate usage for real filesystems
        usage = psutil.disk_usage(partition.mountpoint)
        # Focus on main data partitions (/, /home, /var, /usr, /mnt, /media)
```

#### Enhanced Disk Activity Display
```python
# Added to draw_disk_summary_column() function
disk_usage = self.get_disk_usage()
if disk_usage['total_size'] > 0:
    used_gb = disk_usage['total_used'] / (1024**3)
    total_gb = disk_usage['total_size'] / (1024**3)
    usage_str = f"{used_gb:.1f}GB/{total_gb:.1f}GB"
    
    self.draw_bar(row, 2, bar_width, disk_usage['overall_percent'], "Disk Usage", usage_str)
```

**Features of Disk Utilization Monitoring:**
- **Smart Filtering**: Excludes virtual filesystems (tmpfs, proc, sys, etc.)
- **Aggregate View**: Combines usage across all real storage partitions
- **Visual Display**: Horizontal bar showing percentage with GB usage
- **Partition Focus**: Prioritizes main data partitions (/, /home, /var, /usr, mounted drives)

## Future Enhancements

Potential improvements for the Ubuntu version:
1. **GPU Monitoring**: Add NVIDIA/AMD GPU temperature monitoring
2. **Advanced Sensors**: Integrate with lm-sensors for more hardware data
3. **Systemd Integration**: Add systemd service file for background monitoring
4. **Configuration File**: Allow customization of thresholds and display options
5. **Per-Disk Monitoring**: Individual disk utilization instead of aggregate
6. **Network Interface Configuration**: Auto-detect interface types and speeds
7. **Disk Health Monitoring**: Add SMART data monitoring for SSDs/HDDs

## Summary

The adaptation successfully ports all core functionality from the Raspberry Pi-specific monitor to a generic Ubuntu x86_64 system. The new version maintains the same user experience while properly adapting to the different hardware architecture and system interfaces available on standard PC hardware.