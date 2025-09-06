#!/usr/bin/env python3

import curses
import time
import os
import psutil
import subprocess
import threading
import math
from collections import defaultdict, deque
from datetime import datetime, timedelta

class UbuntuMonitor:
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
        
    def get_temperature(self):
        """Get all available system temperatures"""
        temps = {}
        
        # CPU thermal zones
        try:
            # Try thermal_zone0 first (usually CPU)
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                cpu_temp = float(f.read().strip()) / 1000
                temps['CPU'] = cpu_temp
        except:
            temps['CPU'] = 0
        
        # Try additional thermal zones
        for i in range(1, 5):  # Check thermal_zone1 through thermal_zone4
            try:
                with open(f'/sys/class/thermal/thermal_zone{i}/temp', 'r') as f:
                    temp = float(f.read().strip()) / 1000
                    # Read the type to give it a meaningful name
                    try:
                        with open(f'/sys/class/thermal/thermal_zone{i}/type', 'r') as type_f:
                            zone_type = type_f.read().strip()
                            if 'x86_pkg_temp' in zone_type:
                                temps['CPU_PKG'] = temp
                            elif 'acpi' in zone_type:
                                temps['ACPI'] = temp
                            else:
                                temps[f'Zone{i}'] = temp
                    except:
                        temps[f'Zone{i}'] = temp
            except:
                pass
        
        # Try hwmon sensors for more detailed temperature info
        try:
            # Intel coretemp usually shows up in hwmon1
            hwmon_paths = ['/sys/class/hwmon/hwmon1', '/sys/class/hwmon/hwmon0']
            for hwmon_path in hwmon_paths:
                if os.path.exists(hwmon_path):
                    # Try to find temp sensors
                    for temp_file in ['temp1_input', 'temp2_input', 'temp3_input']:
                        temp_path = os.path.join(hwmon_path, temp_file)
                        if os.path.exists(temp_path):
                            try:
                                with open(temp_path, 'r') as f:
                                    temp = float(f.read().strip()) / 1000
                                    # Try to get a label for this sensor
                                    label_path = temp_path.replace('_input', '_label')
                                    try:
                                        with open(label_path, 'r') as lf:
                                            label = lf.read().strip()
                                            temps[label] = temp
                                    except:
                                        # Use generic core name
                                        core_num = temp_file.replace('temp', '').replace('_input', '')
                                        temps[f'Core{core_num}'] = temp
                            except:
                                pass
        except:
            pass
            
        return temps
    
    def get_network_stats(self):
        """Get network interface statistics"""
        stats = {}
        try:
            with open('/proc/net/dev', 'r') as f:
                lines = f.readlines()[2:]  # Skip header lines
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 17:
                        iface = parts[0].rstrip(':')
                        rx_bytes = int(parts[1])
                        tx_bytes = int(parts[9])
                        stats[iface] = {'rx': rx_bytes, 'tx': tx_bytes}
        except:
            pass
        return stats
    
    def get_disk_stats(self):
        """Get disk I/O statistics"""
        stats = {}
        try:
            with open('/proc/diskstats', 'r') as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 14 and not parts[2].startswith('ram'):
                        device = parts[2]
                        read_sectors = int(parts[5])
                        write_sectors = int(parts[9])
                        stats[device] = {'read': read_sectors, 'write': write_sectors}
        except:
            pass
        return stats
    
    def get_uptime(self):
        """Get system uptime"""
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = float(f.read().split()[0])
                uptime_delta = timedelta(seconds=uptime_seconds)
                days = uptime_delta.days
                hours, remainder = divmod(uptime_delta.seconds, 3600)
                minutes, seconds = divmod(remainder, 60)
                return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"
        except:
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
        """Get disk utilization for all mounted filesystems"""
        disk_usage = []
        total_used = 0
        total_size = 0
        
        try:
            # Get all disk partitions
            partitions = psutil.disk_partitions()
            for partition in partitions:
                try:
                    # Skip virtual/special filesystems
                    if partition.fstype in ['tmpfs', 'devtmpfs', 'proc', 'sysfs', 'cgroup', 'cgroup2', 'pstore', 'bpf', 'debugfs']:
                        continue
                    if partition.mountpoint in ['/dev', '/proc', '/sys', '/run']:
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
                        # Add to totals (for root filesystem and main data partitions)
                        if partition.mountpoint in ['/', '/home', '/var', '/usr'] or partition.mountpoint.startswith('/mnt') or partition.mountpoint.startswith('/media'):
                            total_used += usage.used
                            total_size += usage.total
                            
                except (PermissionError, OSError):
                    continue
                    
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
        
        bar_width = min(10, max_width - 30)  # Narrower network bars for 80-column display
        
        for iface, stats in net_stats.items():
            if iface != 'lo':  # Skip loopback
                history = self.network_history[iface]
                if len(history) >= 2:
                    prev_rx, prev_tx = history[-2]['rx'], history[-2]['tx']
                    curr_rx, curr_tx = stats['rx'], stats['tx']
                    
                    rx_rate = max(0, (curr_rx - prev_rx) / 1024)  # KB/s
                    tx_rate = max(0, (curr_tx - prev_tx) / 1024)  # KB/s
                    
                    max_capacity = 125000  # KB/s for 1Gbit interface
                    if iface.startswith('wlan') or iface.startswith('wlp'):
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
                        pass  # Handle any display errors gracefully
                
                history.append(stats)
        
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
            if device.startswith(('sd', 'nvme', 'vd', 'hd')):  # Include common Ubuntu disk prefixes
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
            max_disk_rate = 500000  # KB/s - Higher for modern SSDs
            
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
            # Display total disk utilization
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
            self.screen.addstr(0, 0, "Ubuntu System Monitor", header_color)
            time_str = f"Update: {datetime.now().strftime('%H:%M:%S')}"
            self.screen.addstr(0, max_x - len(time_str), time_str, text_color)
            
            # LEFT COLUMN - Start at row 2
            left_row = 2
            
            # Uptime
            uptime = self.get_uptime()
            self.screen.addstr(left_row, 0, "Uptime:", section_color)
            self.screen.addstr(left_row, 8, uptime, text_color)
            left_row += 2
            
            # Temperatures (with both C and F)
            temps = self.get_temperature()
            if temps:
                self.screen.addstr(left_row, 0, "Temperatures:", section_color)
                left_row += 1
                for name, temp in temps.items():
                    if temp > 0:  # Only show valid temperatures
                        color = text_color
                        if temp > 80:  # Higher thresholds for x86 CPUs
                            color = curses.color_pair(3) if curses.has_colors() else curses.A_BOLD
                        elif temp > 70:
                            color = curses.color_pair(2) if curses.has_colors() else curses.A_DIM
                        temp_f = temp * 9/5 + 32
                        
                        # Format with fixed-width name field and bold temperatures
                        name_field = f"{name}:"[:8].ljust(8)  # Slightly wider for x86 sensor names
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
            bar_width = min(12, col_split - 18)  # Narrower bars for 80-column display
            for i, usage in enumerate(cpu_usage):
                self.draw_bar(left_row, 2, bar_width, usage, f"Core {i}")
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
            mem_bar_width = min(12, max_x - right_col - 25)  # Narrower memory bar
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
        
        curses.wrapper(main)

if __name__ == "__main__":
    monitor = UbuntuMonitor()
    try:
        monitor.run()
    except KeyboardInterrupt:
        print("\nMonitor stopped.")