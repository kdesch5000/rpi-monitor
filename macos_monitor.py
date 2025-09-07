#!/usr/bin/env python3

import curses
import time
import os
import psutil
import subprocess
import threading
import math
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta

class MacOSMonitor:
    def __init__(self):
        self.running = True
        self.screen = None
        self.update_interval = 1.0
        self.network_history = defaultdict(lambda: deque(maxlen=60))
        self.disk_history = defaultdict(lambda: deque(maxlen=60))
        self.colors_initialized = False
        
        # Maximum value tracking
        self.max_temps = {}
        self.max_network_rates = defaultdict(lambda: {'rx': 0, 'tx': 0})
        self.max_disk_rates = {'read': 0, 'write': 0}
        
        # Network activity tracking for timeout (5 minutes = 300 seconds)
        self.network_last_activity = {}
        self.network_timeout = 300  # 5 minutes in seconds
        
    def get_temperature(self):
        """Get CPU temperature using powermetrics (requires sudo) or estimate from CPU usage"""
        temps = {}
        
        # Try to get temperature from powermetrics (needs sudo)
        try:
            result = subprocess.run([
                'sudo', 'powermetrics', '--samplers', 'smc', 
                '-n', '1', '-i', '100', '--format', 'plist'
            ], capture_output=True, text=True, timeout=3)
            
            if result.returncode == 0:
                # Parse plist output for temperature data
                # This is a simplified approach - real implementation would parse XML
                output = result.stdout
                if 'CPU die temperature' in output:
                    # Extract temperature value (simplified regex approach)
                    import re
                    temp_match = re.search(r'CPU die temperature.*?(\d+(?:\.\d+)?)', output)
                    if temp_match:
                        temps['CPU'] = float(temp_match.group(1))
        except:
            # Fallback: estimate temperature based on CPU usage
            try:
                cpu_percent = psutil.cpu_percent(interval=0.1)
                # Rough estimation: idle ~30°C, full load ~80°C for M1
                base_temp = 35
                load_temp = 45
                estimated_temp = base_temp + (cpu_percent / 100.0) * load_temp
                temps['CPU_Est'] = estimated_temp
            except:
                temps['CPU_Est'] = 40  # Default estimate
        
        # Try to get additional thermal info from sysctl
        try:
            result = subprocess.run(['sysctl', 'machdep.xcpm.cpu_thermal_state'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                thermal_state = result.stdout.strip().split(':')[-1].strip()
                temps['Thermal_State'] = int(thermal_state) * 10 + 30  # Convert state to rough temp
        except:
            pass
            
        return temps
    
    def get_network_stats(self):
        """Get network interface statistics using psutil (only active interfaces with timeout)"""
        stats = {}
        current_time = time.time()
        
        try:
            net_io = psutil.net_io_counters(pernic=True)
            net_if_addrs = psutil.net_if_addrs()
            net_if_stats = psutil.net_if_stats()
            
            for iface, counters in net_io.items():
                # Skip loopback
                if iface == 'lo0':
                    continue
                
                # Check if interface is up and has an address
                is_up = False
                has_address = False
                
                # Check if interface is up
                if iface in net_if_stats:
                    is_up = net_if_stats[iface].isup
                
                # Check if interface has a real IP address (not just link-local)
                if iface in net_if_addrs:
                    for addr in net_if_addrs[iface]:
                        if addr.family == 2:  # AF_INET (IPv4)
                            if not addr.address.startswith('169.254.'):  # Skip link-local
                                has_address = True
                                break
                
                # Check basic eligibility (up and has activity or address)
                if is_up and (has_address or counters.bytes_recv > 1024 or counters.bytes_sent > 1024):
                    
                    # Check for recent activity (traffic change)
                    has_recent_activity = False
                    if iface in self.network_history and len(self.network_history[iface]) > 0:
                        last_stats = self.network_history[iface][-1]
                        if (counters.bytes_recv != last_stats['rx'] or 
                            counters.bytes_sent != last_stats['tx']):
                            # Traffic has changed - update last activity time
                            self.network_last_activity[iface] = current_time
                            has_recent_activity = True
                    else:
                        # First time seeing this interface - count as activity
                        self.network_last_activity[iface] = current_time
                        has_recent_activity = True
                    
                    # Check if interface has been inactive for more than timeout period
                    last_activity_time = self.network_last_activity.get(iface, current_time)
                    time_since_activity = current_time - last_activity_time
                    
                    # Include interface if:
                    # 1. Has IP address (always show active connections), OR
                    # 2. Has recent activity (within timeout period)
                    if has_address or time_since_activity < self.network_timeout:
                        stats[iface] = {
                            'rx': counters.bytes_recv,
                            'tx': counters.bytes_sent,
                            'inactive_time': time_since_activity if not has_recent_activity else 0
                        }
            
            # Clean up tracking for interfaces that no longer exist
            existing_interfaces = set(net_io.keys())
            for iface in list(self.network_last_activity.keys()):
                if iface not in existing_interfaces:
                    del self.network_last_activity[iface]
                    
        except:
            pass
        return stats
    
    def get_disk_stats(self):
        """Get disk I/O statistics using psutil"""
        stats = {}
        try:
            disk_io = psutil.disk_io_counters(perdisk=True)
            if disk_io:
                for disk, counters in disk_io.items():
                    stats[disk] = {
                        'read': counters.read_bytes // 512,  # Convert to sectors
                        'write': counters.write_bytes // 512
                    }
        except:
            pass
        return stats
    
    def get_uptime(self):
        """Get system uptime using sysctl"""
        try:
            result = subprocess.run(['sysctl', '-n', 'kern.boottime'], 
                                  capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                # Parse boot time and calculate uptime
                import re
                boot_match = re.search(r'sec = (\d+)', result.stdout)
                if boot_match:
                    boot_time = int(boot_match.group(1))
                    current_time = int(time.time())
                    uptime_seconds = current_time - boot_time
                    uptime_delta = timedelta(seconds=uptime_seconds)
                    days = uptime_delta.days
                    hours, remainder = divmod(uptime_delta.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
            pass
        return "Unknown"
    
    def get_logged_users(self):
        """Get list of logged-in users"""
        users = []
        try:
            result = subprocess.run(['who'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        parts = line.split()
                        if len(parts) >= 2:
                            users.append(f"{parts[0]} ({parts[1]})")
        except:
            pass
        return users
    
    def get_cpu_usage(self):
        """Get CPU utilization per core"""
        try:
            return psutil.cpu_percent(interval=None, percpu=True)
        except:
            return [0]
    
    def get_memory_usage(self):
        """Get memory utilization"""
        try:
            mem = psutil.virtual_memory()
            return {
                'total': mem.total,
                'used': mem.used,
                'available': mem.available,
                'percent': mem.percent
            }
        except:
            return {'total': 0, 'used': 0, 'available': 0, 'percent': 0}
    
    def get_disk_usage(self):
        """Get disk utilization for macOS APFS filesystem"""
        disk_usage = []
        total_used = 0
        total_size = 0
        
        try:
            # Get all disk partitions
            partitions = psutil.disk_partitions()
            
            # For macOS, we need to handle the APFS volume group structure
            # Find the main APFS container and sum up the important volumes
            apfs_volumes = {}
            main_container_size = 0
            
            for partition in partitions:
                try:
                    # Skip virtual/special filesystems
                    if partition.fstype in ['devfs', 'autofs', 'mtmfs']:
                        continue
                    if partition.mountpoint in ['/dev']:
                        continue
                    
                    usage = psutil.disk_usage(partition.mountpoint)
                    if usage.total > 0:  # Valid filesystem
                        disk_usage.append({
                            'device': partition.device,
                            'mountpoint': partition.mountpoint,
                            'fstype': partition.fstype,
                            'total': usage.total,
                            'used': usage.used,
                            'free': usage.free,
                            'percent': (usage.used / usage.total) * 100
                        })
                        
                        # For macOS APFS, identify the main container and key volumes
                        if partition.fstype == 'apfs' and usage.total > 1024**3:  # > 1GB
                            # This is likely part of the main APFS container
                            if main_container_size == 0 or usage.total > main_container_size:
                                main_container_size = usage.total
                            
                            # Key volumes that contain actual user data
                            if (partition.mountpoint == '/' or  # System
                                partition.mountpoint == '/System/Volumes/Data' or  # User data
                                partition.mountpoint == '/System/Volumes/VM'):     # VM/swap
                                apfs_volumes[partition.mountpoint] = usage.used
                        
                        # Also count external volumes
                        elif partition.mountpoint.startswith('/Volumes'):
                            total_used += usage.used
                            total_size += usage.total
                            
                except (PermissionError, OSError):
                    continue
            
            # For APFS volumes, sum the used space but use the container size once
            if apfs_volumes and main_container_size > 0:
                apfs_used = sum(apfs_volumes.values())
                total_used += apfs_used
                total_size += main_container_size
                    
        except:
            pass
            
        # Calculate overall utilization percentage
        overall_percent = (total_used / total_size * 100) if total_size > 0 else 0
        
        return {
            'partitions': disk_usage,
            'total_used': total_used,
            'total_size': total_size,
            'overall_percent': overall_percent
        }

    def get_top_processes(self):
        """Get top 5 processes by CPU usage"""
        processes = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            
            processes.sort(key=lambda x: x['cpu_percent'] or 0, reverse=True)
            return processes[:5]
        except:
            return []
    
    def init_colors(self):
        """Initialize color pairs"""
        if not self.colors_initialized and curses.has_colors():
            curses.start_color()
            curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)    # Green text
            curses.init_pair(2, curses.COLOR_YELLOW, curses.COLOR_BLACK)   # Yellow bars
            curses.init_pair(3, curses.COLOR_RED, curses.COLOR_BLACK)      # Red bars (100%)
            curses.init_pair(4, curses.COLOR_WHITE, curses.COLOR_BLACK)    # White text
            curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)     # Cyan for headers
            self.colors_initialized = True
    
    def get_bar_color(self, percentage):
        """Get appropriate color for bar based on percentage"""
        if not curses.has_colors():
            return curses.A_NORMAL
        if percentage >= 100:
            return curses.color_pair(3)  # Red
        else:
            return curses.color_pair(2)  # Yellow
    
    def log_scale_percentage(self, value, max_value, min_threshold=1):
        """Convert value to logarithmic percentage for better visualization"""
        if value <= min_threshold:
            return 0
        if value >= max_value:
            return 100
        
        # Use log10 scale with minimum threshold to avoid log(0)
        log_value = math.log10(max(value, min_threshold))
        log_max = math.log10(max_value)
        log_min = math.log10(min_threshold)
        
        percentage = ((log_value - log_min) / (log_max - log_min)) * 100
        return min(100, max(0, percentage))
    
    def draw_bar(self, y, x, width, percentage, label="", rate_str=""):
        """Draw a horizontal bar chart with colors"""
        try:
            filled = int(width * percentage / 100)
            bar = "█" * filled + "░" * (width - filled)
            
            # Draw label in green
            label_color = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
            self.screen.addstr(y, x, f"{label:<12}", label_color)
            
            # Draw bar in yellow/red
            bar_color = self.get_bar_color(percentage)
            self.screen.addstr(y, x + 12, f" [{bar}] ", bar_color)
            
            # Draw percentage and rate in green
            info_text = f"{percentage:5.1f}%"
            if rate_str:
                info_text += f" {rate_str}"
            self.screen.addstr(y, x + 12 + width + 4, info_text, label_color)
        except:
            pass
    
    def draw_network_bars_column(self, start_y, start_x, net_stats, max_width):
        """Draw network activity bars for column layout"""
        row = start_y
        header_color = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD
        self.screen.addstr(row, start_x, "Network Activity:", header_color)
        row += 1
        
        bar_width = min(10, max_width - 30)
        
        for iface, stats in net_stats.items():
            # All interfaces in net_stats are already filtered to active only
            history = self.network_history[iface]
            
            # Always add current stats to history first
            history.append(stats)
            
            if len(history) >= 2:
                prev_rx, prev_tx = history[-2]['rx'], history[-2]['tx']
                curr_rx, curr_tx = stats['rx'], stats['tx']
                
                rx_rate = max(0, (curr_rx - prev_rx) / 1024)  # KB/s
                tx_rate = max(0, (curr_tx - prev_tx) / 1024)  # KB/s
                
                max_capacity = 125000  # KB/s for 1Gbit interface
                if iface.startswith('en0'):  # WiFi on macOS
                    max_capacity = 50000  # Assume 400Mbps for WiFi
                
                # Track maximum network rates
                if rx_rate > self.max_network_rates[iface]['rx']:
                    self.max_network_rates[iface]['rx'] = rx_rate
                if tx_rate > self.max_network_rates[iface]['tx']:
                    self.max_network_rates[iface]['tx'] = tx_rate
                
                rx_pct = self.log_scale_percentage(rx_rate, max_capacity, 10)
                tx_pct = self.log_scale_percentage(tx_rate, max_capacity, 10)
                
                # Adjust bar drawing for right column
                try:
                    filled_rx = int(bar_width * rx_pct / 100)
                    bar_rx = "█" * filled_rx + "░" * (bar_width - filled_rx)
                    
                    filled_tx = int(bar_width * tx_pct / 100)
                    bar_tx = "█" * filled_tx + "░" * (bar_width - filled_tx)
                    
                    # Draw labels and bars
                    text_color = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
                    bar_color_rx = self.get_bar_color(rx_pct)
                    bar_color_tx = self.get_bar_color(tx_pct)
                    
                    # Format rate strings with max values
                    max_rx = self.max_network_rates[iface]['rx']
                    max_tx = self.max_network_rates[iface]['tx']
                    
                    if max_rx == rx_rate:
                        rx_rate_str = f"{rx_pct:3.0f}% {rx_rate:4.0f}K"
                    else:
                        rx_rate_str = f"{rx_pct:2.0f}% {rx_rate:3.0f}K[M:{max_rx:3.0f}]"
                    
                    if max_tx == tx_rate:
                        tx_rate_str = f"{tx_pct:3.0f}% {tx_rate:4.0f}K"
                    else:
                        tx_rate_str = f"{tx_pct:2.0f}% {tx_rate:3.0f}K[M:{max_tx:3.0f}]"
                    
                    # Add inactive time indicator if interface has been idle
                    inactive_time = stats.get('inactive_time', 0)
                    if inactive_time > 60:  # Show after 1 minute of inactivity
                        inactive_mins = int(inactive_time // 60)
                        if inactive_mins >= 4:  # Warning at 4+ minutes (close to 5 min timeout)
                            inactive_indicator = f" ⚠️{inactive_mins}m"
                            # Use warning color
                            rx_rate_str = f"{rx_pct:2.0f}%{inactive_indicator}"
                        elif inactive_mins >= 2:  # Caution at 2+ minutes
                            inactive_indicator = f" 🟡{inactive_mins}m"
                            rx_rate_str = f"{rx_pct:2.0f}%{inactive_indicator}"
                        else:
                            inactive_indicator = f" 🔵{inactive_mins}m"
                            rx_rate_str = rx_rate_str.replace("]", f"{inactive_indicator}]")
                    
                    # RX line
                    self.screen.addstr(row, start_x, f"{iface} RX", text_color)
                    self.screen.addstr(row, start_x + 8, f" [{bar_rx}] ", bar_color_rx)
                    self.screen.addstr(row, start_x + 8 + bar_width + 4, rx_rate_str, text_color)
                    row += 1
                    
                    # TX line
                    self.screen.addstr(row, start_x, f"{iface} TX", text_color)
                    self.screen.addstr(row, start_x + 8, f" [{bar_tx}] ", bar_color_tx)
                    self.screen.addstr(row, start_x + 8 + bar_width + 4, tx_rate_str, text_color)
                    row += 1
                except:
                    pass
            else:
                # First run - no previous data, show interface but no rates
                try:
                    text_color = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
                    self.screen.addstr(row, start_x, f"{iface} RX", text_color)
                    self.screen.addstr(row, start_x + 8, " [Initializing...] ", text_color)
                    row += 1
                    self.screen.addstr(row, start_x, f"{iface} TX", text_color)
                    self.screen.addstr(row, start_x + 8, " [Initializing...] ", text_color)
                    row += 1
                except:
                    pass
        
        return row
    
    def draw_disk_summary_column(self, start_y, disk_stats, bar_width):
        """Draw summarized disk activity for column layout"""
        row = start_y
        header_color = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD
        self.screen.addstr(row, 0, "Disk Activity:", header_color)
        row += 1
        
        total_read_rate = 0
        total_write_rate = 0
        active_devices = 0
        
        for device, stats in disk_stats.items():
            if device.startswith(('disk', 'rdisk')):  # macOS disk naming
                history = self.disk_history[device]
                if len(history) >= 2:
                    prev_read, prev_write = history[-2]['read'], history[-2]['write']
                    curr_read, curr_write = stats['read'], stats['write']
                    
                    read_rate = max(0, (curr_read - prev_read) * 512 / 1024)  # KB/s
                    write_rate = max(0, (curr_write - prev_write) * 512 / 1024)  # KB/s
                    
                    total_read_rate += read_rate
                    total_write_rate += write_rate
                    active_devices += 1
                
                history.append(stats)
        
        if active_devices > 0:
            max_disk_rate = 500000  # KB/s - High for modern SSDs
            
            # Track maximum disk rates
            if total_read_rate > self.max_disk_rates['read']:
                self.max_disk_rates['read'] = total_read_rate
            if total_write_rate > self.max_disk_rates['write']:
                self.max_disk_rates['write'] = total_write_rate
            
            read_pct = self.log_scale_percentage(total_read_rate, max_disk_rate, 10)
            write_pct = self.log_scale_percentage(total_write_rate, max_disk_rate, 10)
            
            # Format rate strings with max values
            max_read = self.max_disk_rates['read']
            max_write = self.max_disk_rates['write']
            
            if max_read == total_read_rate:
                read_rate_str = f"{total_read_rate:4.0f}K"
            else:
                read_rate_str = f"{total_read_rate:3.0f}K[M:{max_read:3.0f}]"
            
            if max_write == total_write_rate:
                write_rate_str = f"{total_write_rate:4.0f}K"
            else:
                write_rate_str = f"{total_write_rate:3.0f}K[M:{max_write:3.0f}]"
            
            self.draw_bar(row, 2, bar_width, read_pct, "Total Read", read_rate_str)
            row += 1
            self.draw_bar(row, 2, bar_width, write_pct, "Total Write", write_rate_str)
            row += 1
        else:
            text_color = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
            self.screen.addstr(row, 2, "No disk activity", text_color)
            row += 1
        
        # Add disk utilization bar
        disk_usage = self.get_disk_usage()
        if disk_usage['total_size'] > 0:
            row += 1  # Add some spacing
            used_gb = disk_usage['total_used'] / (1024**3)
            total_gb = disk_usage['total_size'] / (1024**3)
            usage_str = f"{used_gb:.1f}GB/{total_gb:.1f}GB"
            
            self.draw_bar(row, 2, bar_width, disk_usage['overall_percent'], "Disk Usage", usage_str)
            row += 1
        
        return row
    
    def update_display(self):
        """Update the display with current system information in 2-column layout"""
        try:
            self.screen.clear()
            
            # Initialize colors if needed
            self.init_colors()
            
            # Color definitions
            header_color = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD | curses.A_UNDERLINE
            text_color = curses.color_pair(1) if curses.has_colors() else curses.A_NORMAL
            section_color = curses.color_pair(5) if curses.has_colors() else curses.A_BOLD
            
            # Get terminal dimensions
            max_y, max_x = self.screen.getmaxyx()
            col_split = max_x // 2  # Split screen in half
            
            # Header
            self.screen.addstr(0, 0, "macOS System Monitor (Apple M1)", header_color)
            time_str = f"Update: {datetime.now().strftime('%H:%M:%S')}"
            self.screen.addstr(0, max_x - len(time_str), time_str, text_color)
            
            # LEFT COLUMN - Start at row 2
            left_row = 2
            
            # Uptime
            uptime = self.get_uptime()
            self.screen.addstr(left_row, 0, "Uptime:", section_color)
            self.screen.addstr(left_row, 8, uptime, text_color)
            left_row += 2
            
            # Temperatures
            temps = self.get_temperature()
            if temps:
                self.screen.addstr(left_row, 0, "Temperatures:", section_color)
                left_row += 1
                for name, temp in temps.items():
                    if temp > 0:  # Only show valid temperatures
                        color = text_color
                        if temp > 85:  # Apple M1 thermal thresholds
                            color = curses.color_pair(3) if curses.has_colors() else curses.A_BOLD
                        elif temp > 75:
                            color = curses.color_pair(2) if curses.has_colors() else curses.A_DIM
                        temp_f = temp * 9/5 + 32
                        
                        # Format with fixed-width name field
                        name_field = f"{name}:"[:10].ljust(10)
                        temp_str = f"{temp:5.1f}°C ({temp_f:5.1f}°F)"
                        if len(name_field + temp_str) > col_split - 2:
                            temp_str = f"{temp:4.0f}°C ({temp_f:4.0f}°F)"
                        
                        # Track maximum temperature
                        if name not in self.max_temps or temp > self.max_temps[name]:
                            self.max_temps[name] = temp
                        
                        # Format temperature string with max value
                        max_temp = self.max_temps.get(name, temp)
                        max_temp_f = max_temp * 9/5 + 32
                        if max_temp == temp:
                            temp_str = f"{temp:5.1f}°C ({temp_f:5.1f}°F)"
                        else:
                            temp_str = f"{temp:5.1f}°C ({temp_f:5.1f}°F) [Max: {max_temp:4.1f}°C]"
                        
                        # Shorten if too long for column
                        if len(name_field + temp_str) > col_split - 4:
                            if max_temp == temp:
                                temp_str = f"{temp:4.0f}°C ({temp_f:4.0f}°F)"
                            else:
                                temp_str = f"{temp:4.0f}°C [Max:{max_temp:4.0f}]"
                        
                        # Draw name in normal color, temperatures in bold
                        self.screen.addstr(left_row, 2, name_field, color)
                        bold_color = color | curses.A_BOLD if curses.has_colors() else curses.A_BOLD
                        self.screen.addstr(left_row, 2 + len(name_field), temp_str, bold_color)
                        left_row += 1
                
                left_row += 1
            
            # CPU utilization
            cpu_usage = self.get_cpu_usage()
            self.screen.addstr(left_row, 0, "CPU Utilization:", section_color)
            left_row += 1
            bar_width = min(12, col_split - 18)
            for i, usage in enumerate(cpu_usage):
                core_label = f"Core {i}"
                # Mark performance vs efficiency cores for M1
                if i < 4:
                    core_label = f"P-Core {i}"  # Performance cores
                else:
                    core_label = f"E-Core {i-4}"  # Efficiency cores
                self.draw_bar(left_row, 2, bar_width, usage, core_label)
                left_row += 1
            
            # Overall CPU
            avg_cpu = sum(cpu_usage) / len(cpu_usage) if cpu_usage else 0
            self.draw_bar(left_row, 2, bar_width, avg_cpu, "Average")
            left_row += 2
            
            # Disk activity (summarized)
            disk_stats = self.get_disk_stats()
            left_row = self.draw_disk_summary_column(left_row, disk_stats, bar_width)
            
            # RIGHT COLUMN - Start at row 2
            right_row = 2
            right_col = col_split + 2
            
            # Network activity
            net_stats = self.get_network_stats()
            right_row = self.draw_network_bars_column(right_row, right_col, net_stats, max_x - right_col - 2)
            right_row += 1
            
            # Memory utilization
            mem_info = self.get_memory_usage()
            self.screen.addstr(right_row, right_col, "Memory Utilization:", section_color)
            right_row += 1
            mem_bar_width = min(12, max_x - right_col - 25)
            self.draw_bar(right_row, right_col, mem_bar_width, mem_info['percent'], "RAM")
            right_row += 1
            total_gb = mem_info['total'] / (1024**3)
            used_gb = mem_info['used'] / (1024**3)
            mem_str = f"Used: {used_gb:.1f}GB / {total_gb:.1f}GB"
            self.screen.addstr(right_row, right_col, mem_str, text_color)
            right_row += 2
            
            # Logged users
            users = self.get_logged_users()
            self.screen.addstr(right_row, right_col, "Logged Users:", section_color)
            right_row += 1
            if users:
                for user in users[:5]:  # Limit to 5 users
                    user_str = user if len(user) <= max_x - right_col - 2 else user[:max_x - right_col - 5] + "..."
                    self.screen.addstr(right_row, right_col + 2, user_str, text_color)
                    right_row += 1
            else:
                self.screen.addstr(right_row, right_col + 2, "None", text_color)
                right_row += 1
            right_row += 1
            
            # Top processes
            processes = self.get_top_processes()
            self.screen.addstr(right_row, right_col, "Top 5 Processes:", section_color)
            right_row += 1
            header_str = "PID    Name            CPU%   MEM%"
            if len(header_str) > max_x - right_col - 2:
                header_str = "PID   Name        CPU% MEM%"
            self.screen.addstr(right_row, right_col + 2, header_str, text_color)
            right_row += 1
            for proc in processes:
                pid = proc.get('pid', 0)
                name = proc.get('name', 'Unknown')[:12]
                cpu_pct = proc.get('cpu_percent', 0) or 0
                mem_pct = proc.get('memory_percent', 0) or 0
                proc_str = f"{pid:<6} {name:<12} {cpu_pct:4.1f}  {mem_pct:4.1f}"
                if len(proc_str) > max_x - right_col - 2:
                    proc_str = f"{pid:<5} {name:<10} {cpu_pct:3.0f} {mem_pct:3.0f}"
                self.screen.addstr(right_row, right_col + 2, proc_str, text_color)
                right_row += 1
            
            # Instructions
            self.screen.addstr(max_y - 1, 0, "Press 'q' to quit", curses.A_DIM)
            
            self.screen.refresh()
            
        except Exception as e:
            # Handle any drawing errors gracefully
            pass
    
    def run(self):
        """Main run loop"""
        def main(screen):
            try:
                self.screen = screen
                curses.curs_set(0)  # Hide cursor
                screen.nodelay(1)   # Non-blocking input
                screen.timeout(100) # 100ms timeout for getch
                
                while self.running:
                    try:
                        # Check for quit command
                        ch = screen.getch()
                        if ch == ord('q') or ch == ord('Q'):
                            break
                        
                        self.update_display()
                        time.sleep(self.update_interval)
                        
                    except KeyboardInterrupt:
                        break
                    except Exception:
                        # Handle any errors and continue
                        time.sleep(self.update_interval)
            except Exception as e:
                print(f"Terminal initialization error: {e}")
                print("Try running in a different terminal or resizing your terminal window.")
                return
        
        try:
            curses.wrapper(main)
        except Exception as e:
            print(f"Curses error: {e}")
            print("This may happen if:")
            print("1. Terminal is too small (needs at least 80x24)")
            print("2. Running in an unsupported terminal")
            print("3. Terminal capabilities are limited")
            print("\nTry running in Terminal.app or iTerm2 with a larger window size.")

if __name__ == "__main__":
    # Check terminal size before starting
    try:
        import shutil
        columns, rows = shutil.get_terminal_size()
        if columns < 80 or rows < 24:
            print(f"Warning: Terminal size is {columns}x{rows}")
            print("For best experience, resize terminal to at least 80x24")
            print("Press Enter to continue anyway, or Ctrl+C to exit...")
            input()
    except:
        pass
    
    monitor = MacOSMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")