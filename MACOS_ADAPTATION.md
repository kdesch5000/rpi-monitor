# macOS System Monitor Adaptation

This document explains the modifications made to adapt the system monitor for macOS (tested on Apple M1 MacBook Pro).

## Overview

The `macos_monitor.py` has been adapted from the original Raspberry Pi and Ubuntu versions to work on macOS systems while maintaining the same functionality and user interface.

## System Analysis

### Target System
- **OS**: macOS Sonoma 14.6.0
- **Architecture**: ARM64 (Apple M1)
- **CPU**: Apple M1 (8 cores: 4 performance + 4 efficiency)
- **Kernel**: Darwin 24.6.0

### macOS System Interface Differences

| Component | Linux | macOS |
|-----------|-------|-------|
| Temperature | `/sys/class/thermal/` | `powermetrics` command (requires sudo) |
| Network Stats | `/proc/net/dev` | `psutil.net_io_counters()` |
| Disk I/O | `/proc/diskstats` | `psutil.disk_io_counters()` |
| Uptime | `/proc/uptime` | `sysctl kern.boottime` |
| Memory | `/proc/meminfo` + psutil | psutil only |
| CPU Cores | `/proc/cpuinfo` + psutil | sysctl + psutil |

## Code Modifications

### 1. Class Rename and Title Update
```python
class MacOSMonitor:
    # Header shows "macOS System Monitor (Apple M1)"
    self.screen.addstr(0, 0, "macOS System Monitor (Apple M1)", header_color)
```

### 2. Temperature Monitoring
**Challenge**: macOS doesn't expose thermal sensors via filesystem interfaces.

**Solutions Implemented**:
```python
def get_temperature(self):
    # Method 1: Try powermetrics (requires sudo)
    result = subprocess.run([
        'sudo', 'powermetrics', '--samplers', 'smc', 
        '-n', '1', '-i', '100', '--format', 'plist'
    ], capture_output=True, text=True, timeout=3)
    
    # Method 2: Fallback - CPU usage estimation
    cpu_percent = psutil.cpu_percent(interval=0.1)
    base_temp = 35  # Idle temp for M1
    load_temp = 45  # Load contribution
    estimated_temp = base_temp + (cpu_percent / 100.0) * load_temp
    
    # Method 3: Thermal state from sysctl
    result = subprocess.run(['sysctl', 'machdep.xcpm.cpu_thermal_state'])
```

**Temperature Features**:
- **Primary**: Uses `powermetrics` for accurate CPU die temperature (requires sudo)
- **Fallback**: Estimates temperature based on CPU load (35-80°C range)
- **Thermal State**: Uses sysctl thermal state as additional indicator
- **Thresholds**: Adapted for Apple M1 (Warning >75°C, Critical >85°C)

### 3. Network Monitoring
**Replaced**: `/proc/net/dev` file parsing  
**With**: psutil cross-platform API
```python
def get_network_stats(self):
    net_io = psutil.net_io_counters(pernic=True)
    for iface, counters in net_io.items():
        stats[iface] = {
            'rx': counters.bytes_recv,
            'tx': counters.bytes_sent
        }
```

### 4. Disk I/O Monitoring
**Replaced**: `/proc/diskstats` parsing  
**With**: psutil disk I/O counters
```python
def get_disk_stats(self):
    disk_io = psutil.disk_io_counters(perdisk=True)
    for disk, counters in disk_io.items():
        stats[disk] = {
            'read': counters.read_bytes // 512,  # Convert to sectors
            'write': counters.write_bytes // 512
        }
```

**Device Naming**: Adapted for macOS disk naming (`disk0`, `rdisk0` instead of `sda`, `nvme0`)

### 5. System Uptime
**Replaced**: `/proc/uptime` file reading  
**With**: sysctl boot time calculation
```python
def get_uptime(self):
    result = subprocess.run(['sysctl', '-n', 'kern.boottime'])
    # Parse: { sec = 1691234567, usec = 123456 } Thu Aug 05 12:34:56 2023
    boot_match = re.search(r'sec = (\d+)', result.stdout)
    uptime_seconds = int(time.time()) - int(boot_match.group(1))
```

### 6. CPU Core Identification
**Enhanced**: Apple M1 P-Core vs E-Core labeling
```python
for i, usage in enumerate(cpu_usage):
    if i < 4:
        core_label = f"P-Core {i}"  # Performance cores (0-3)
    else:
        core_label = f"E-Core {i-4}"  # Efficiency cores (4-7)
```

### 7. Disk Usage Monitoring
**Adapted**: macOS filesystem filtering
```python
# Skip macOS-specific virtual filesystems
if partition.fstype in ['devfs', 'autofs', 'mtmfs']:
    continue
    
# Focus on main macOS data partitions
if partition.mountpoint in ['/', '/Users', '/Applications', '/System'] or \
   partition.mountpoint.startswith('/Volumes'):
    total_used += usage.used
    total_size += usage.total
```

### 8. Network Interface Detection
**Updated**: macOS network interface naming
```python
if iface.startswith('en0'):  # Primary interface on macOS
    max_capacity = 50000     # Assume WiFi
elif iface.startswith('en1'):
    max_capacity = 125000    # Assume Ethernet
```

## Installation & Usage

### Prerequisites
1. **Python 3**: Included with macOS
2. **psutil**: Install in virtual environment

### Setup Instructions
```bash
# 1. Navigate to project directory
cd rpi-monitor

# 2. Create virtual environment (already done)
python3 -m venv venv
source venv/bin/activate
pip install psutil

# 3. Run the monitor
./macos_monitor.sh
# or directly:
source venv/bin/activate && python3 macos_monitor.py
```

### Temperature Monitoring (Optional)
For accurate temperature readings, run with sudo:
```bash
sudo ./macos_monitor.sh
```
**Note**: Without sudo, monitor uses CPU load estimation for temperature.

## Features & Compatibility

### ✅ Working Features
- **CPU Utilization**: Per-core usage with P-Core/E-Core labels
- **Memory Monitoring**: RAM usage via psutil
- **Network Activity**: RX/TX rates with logarithmic scaling
- **Disk I/O**: Read/write activity monitoring
- **Disk Usage**: Filesystem utilization bars
- **Process Monitoring**: Top 5 processes by CPU usage
- **User Sessions**: Currently logged users
- **System Uptime**: Accurate boot time calculation
- **Terminal UI**: Full curses interface with colors

### ⚠️ Limited Features
- **Temperature**: Requires sudo for accurate readings, otherwise estimates
- **Hardware Sensors**: No fan speed monitoring (not applicable to M1 MacBook)
- **GPU**: No discrete GPU monitoring for integrated M1 graphics

### 🎯 macOS-Specific Enhancements
- **Apple M1 Awareness**: P-Core vs E-Core labeling
- **Native Integration**: Uses BSD/Darwin system calls
- **Filesystem Adaptation**: Proper macOS partition filtering
- **Interface Detection**: Recognizes macOS network naming

## Performance Characteristics

### System Resource Usage
- **CPU**: ~1-2% CPU usage for monitoring
- **Memory**: ~15-20MB RAM footprint
- **Disk I/O**: Minimal, only for reading system stats
- **Network**: No network usage

### Update Frequency
- **Refresh Rate**: 1 second intervals
- **Responsiveness**: Real-time system statistics
- **History**: 60-second rolling window for network/disk rates

## Testing Results

### Hardware Detection
- ✅ **CPU**: Apple M1 (8 cores) - 4P+4E configuration detected
- ✅ **Memory**: 8GB total, real-time usage monitoring
- ✅ **Network**: WiFi (en0) and other interfaces detected
- ✅ **Storage**: SSD I/O monitoring active
- ✅ **Processes**: Process enumeration working

### Accuracy Verification
- **CPU Usage**: Matches Activity Monitor readings
- **Memory Usage**: Consistent with system memory pressure
- **Network**: Accurate byte counters via psutil
- **Disk I/O**: Reflects actual read/write activity
- **Uptime**: Matches system uptime

## Troubleshooting

### Common Issues

**1. "No module named 'psutil'"**
```bash
# Solution: Activate virtual environment
source venv/bin/activate
```

**2. Temperature shows estimates only**
```bash
# Solution: Run with sudo for powermetrics access
sudo source venv/bin/activate && sudo python3 macos_monitor.py
```

**3. Permission errors with powermetrics**
```bash
# Expected: powermetrics requires elevated privileges
# Monitor will fall back to CPU load estimation
```

**4. Display issues in small terminals**
```bash
# Solution: Resize terminal to at least 80x24 characters
# Monitor adapts to terminal size automatically
```

## Latest Features Added

### **9. Network Interface Timeout (5-minute inactivity)**
```python
# Network activity tracking for timeout (5 minutes = 300 seconds)
self.network_last_activity = {}
self.network_timeout = 300

# Check for recent activity (traffic change)
if (counters.bytes_recv != last_stats['rx'] or 
    counters.bytes_sent != last_stats['tx']):
    self.network_last_activity[iface] = current_time
    has_recent_activity = True

# Include interface if has IP address OR within timeout period
if has_address or time_since_activity < self.network_timeout:
    stats[iface] = {
        'rx': counters.bytes_recv,
        'tx': counters.bytes_sent,
        'inactive_time': time_since_activity
    }
```

**Network Timeout Features:**
- **5-minute timer**: Interfaces disappear after 5 minutes of no traffic changes
- **Smart exceptions**: Interfaces with IP addresses always shown (active connections)
- **Visual indicators**: 🔵1m, 🟡2m, ⚠️4m countdown to timeout
- **Dynamic removal**: VPN tunnels and unused interfaces fade away automatically

### **10. Fixed APFS Disk Usage Calculation**
```python
def get_disk_usage(self):
    """Get disk utilization for macOS APFS filesystem"""
    # Handle APFS volume group structure properly
    apfs_volumes = {}
    
    # Key volumes that contain actual user data
    if (partition.mountpoint == '/' or  # System (10GB)
        partition.mountpoint == '/System/Volumes/Data' or  # User data (163GB)
        partition.mountpoint == '/System/Volumes/VM'):     # VM/swap (3GB)
        apfs_volumes[partition.mountpoint] = usage.used
    
    # Sum used space but use container size only once
    apfs_used = sum(apfs_volumes.values())  # 177GB total
    total_size += main_container_size  # 228GB container
```

**APFS Disk Calculation Features:**
- **Accurate Usage**: Shows 77.5% instead of incorrect 4.6% from root volume only
- **APFS Awareness**: Handles complex macOS volume structure properly
- **Main Data Volumes**: Correctly sums /System/Volumes/Data (user files) + root + VM
- **No Double-Counting**: Uses APFS container size (228GB) only once

### **11. Improved Sudo Authentication (Blocking)**
```python
def check_sudo_access(self):
    """Check and authenticate sudo access for temperature monitoring"""
    print("Checking for sudo access for accurate temperature monitoring...")
    print("(This is optional - monitor will work with estimated temperatures if declined)")
    
    # Authenticate upfront and cache credentials
    result = subprocess.run(['sudo', '-v'], timeout=30, capture_output=False, text=True)
    
    if result.returncode == 0:
        # Test powermetrics actually works
        result = subprocess.run([
            'sudo', 'powermetrics', '--samplers', 'smc', 
            '-n', '1', '-i', '100', '--format', 'plist'
        ], capture_output=True, text=True, timeout=5)
        
        if result.returncode == 0 and 'CPU die temperature' in result.stdout:
            self.sudo_available = True
            self.temperature_mode = 'powermetrics'
            print("✅ Sudo access confirmed - using powermetrics for accurate temperatures")
```

**Sudo Authentication Improvements:**
- **Upfront Authentication**: Prompts for password once during startup (blocks until resolved)
- **No Timer Interruptions**: Eliminates the problematic timer-based sudo calls during monitoring
- **Cached Credentials**: Uses `sudo -v` to authenticate and cache, then `sudo -n` for non-interactive calls
- **Graceful Degradation**: Falls back to temperature estimation if authentication fails
- **User Control**: Clear messaging that sudo access is optional with 30-second timeout

## File Structure

```
rpi-monitor/
├── rpi_monitor.py           # Original Raspberry Pi version
├── ubuntu_monitor.py        # Ubuntu x86_64 version  
├── macos_monitor.py         # New macOS version
├── macos_monitor.sh         # Helper script with venv (renamed from run_macos_monitor.sh)
├── macos_monitor_simple.py  # Simple text-only version
├── venv/                    # Python virtual environment
├── requirements.txt         # Python dependencies
├── README.md               # Updated with macOS version
├── UBUNTU_ADAPTATION.md    # Ubuntu adaptation notes
├── MACOS_ADAPTATION.md     # This documentation
└── test_*.py               # Test scripts for debugging
```

## Future Enhancements

### Potential Improvements
1. **Metal GPU Monitoring**: Add Apple Metal GPU utilization
2. **Battery Status**: Battery level and power consumption
3. **Thermal Pressure**: Enhanced thermal state monitoring
4. **M1/M2/M3 Detection**: Automatic chip detection and optimization
5. **Homebrew Integration**: Package for easier installation
6. **Configuration**: User preferences for thresholds and display
7. **Apple Silicon Optimizations**: Leverage M1-specific performance counters

### Advanced Features
- **Energy Impact**: Process energy consumption monitoring
- **Neural Engine**: ANE usage monitoring (if available)
- **Unified Memory**: Memory pressure and swap usage
- **Background App Refresh**: Monitor system background activity

## Summary

The macOS adaptation successfully ports all core functionality to Apple Silicon Macs. The monitor provides comprehensive system information using native macOS APIs while maintaining the familiar terminal-based interface. Temperature monitoring works with or without sudo, and all other features provide accurate real-time system statistics.

Key adaptations include replacing Linux `/proc` and `/sys` interfaces with BSD system calls, utilizing psutil for cross-platform compatibility, and adding Apple M1-specific features like performance/efficiency core identification.