#!/bin/bash
# Side Effect Capture Script for Legacy Binary Execution
# Monitors file system and network operations during execution

set -e

# Configuration
OUTPUT_DIR="/app/side-effects"
FS_LOG="$OUTPUT_DIR/filesystem.log"
NETWORK_PCAP="$OUTPUT_DIR/network.pcap"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Start file system monitoring
echo "Starting file system monitoring..."
inotifywait -m -r -e create,modify,delete \
    --format '%T|%e|%w%f' \
    --timefmt '%s' \
    /app/output > "$FS_LOG" 2>&1 &
FS_MONITOR_PID=$!

# Start network monitoring
echo "Starting network monitoring..."
tcpdump -i any -w "$NETWORK_PCAP" -U > /dev/null 2>&1 &
NETWORK_MONITOR_PID=$!

# Function to stop monitoring
stop_monitoring() {
    echo "Stopping monitoring..."
    
    # Stop file system monitor
    if [ ! -z "$FS_MONITOR_PID" ]; then
        kill $FS_MONITOR_PID 2>/dev/null || true
    fi
    
    # Stop network monitor
    if [ ! -z "$NETWORK_MONITOR_PID" ]; then
        kill $NETWORK_MONITOR_PID 2>/dev/null || true
    fi
    
    echo "Monitoring stopped"
}

# Register cleanup handler
trap stop_monitoring EXIT INT TERM

# Wait for monitoring to be ready
sleep 1

echo "Side effect capture ready"

# Keep script running
wait
