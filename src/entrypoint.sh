#!/bin/sh
set -eo pipefail

echo "#####################################################"
echo "######## OneNVR - One Network Video Recorder ########"
echo "#####################################################"

# Basic directory checks
if [ ! -d "/config" ] || [ ! -d "/storage" ]; then
    echo "ERROR: Required directories /config and /storage must exist"
    exit 1
fi

# Create default config on first run so the web UI can be used for setup
if [ ! -f "/config/config.yaml" ]; then
    echo "No config.yaml found – creating default configuration"
    cat > /config/config.yaml << 'EOF'
cameras: []
retention_days: 7
concatenation: true
concatenation_time: "02:00"
deletion_time: "01:00"
EOF
    echo "Default config created. Add cameras via the web interface."
fi

# Quick initial network check (3 attempts only)
echo "Performing initial network check"
MAX_ATTEMPTS=3
for attempt in $(seq 1 $MAX_ATTEMPTS); do
    if ping -c 1 -W 2 "8.8.8.8" >/dev/null 2>&1; then
        echo "Network connectivity confirmed"
        exec python /app/main.py
        exit 0
    fi
    echo "Network check attempt $attempt/$MAX_ATTEMPTS failed - retrying..."
    sleep 2
done

echo "WARNING: Starting OneNVR despite network check failure - Runtime recovery will handle camera reconnection"
exec python /app/main.py
