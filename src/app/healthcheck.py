import os
import sys
import glob
import subprocess
from datetime import datetime, timedelta

def check_storage_access():
    """Check if storage directory is accessible"""
    return os.path.exists('/storage') and os.access('/storage', os.W_OK)

def check_config_access():
    """Check if config directory is accessible"""
    return os.path.exists('/config') and os.access('/config', os.R_OK)

def check_web_server():
    """Check if web server is responding"""
    try:
        import urllib.request
        with urllib.request.urlopen('http://localhost:5000/', timeout=5) as response:
            return response.getcode() == 200
    except Exception:
        return False

def check_ffmpeg_processes():
    """Check if ffmpeg recording processes are running"""
    try:
        result = subprocess.run(['pgrep', '-f', 'ffmpeg.*segment'],
                              capture_output=True, text=True)
        return len(result.stdout.strip()) > 0
    except Exception:
        return False

def check_camera_recordings():
    """Check if cameras are actively recording (recent files exist)"""
    # Get camera directories (immediate subdirs of /storage)
    camera_dirs = glob.glob('/storage/*/')
    if not camera_dirs:
        print("No camera directories found in /storage/")
        return False

    current_time = datetime.now()
    current_date = current_time.strftime('%Y-%m-%d')
    healthy_cameras = 0

    for camera_dir in camera_dirs:
        camera_name = os.path.basename(camera_dir.rstrip('/'))

        # Check today's directory for this camera
        date_dir = os.path.join(camera_dir, current_date)
        if not os.path.exists(date_dir):
            continue

        # Check for recent files (modified in last 10 minutes)
        files = glob.glob(f"{date_dir}/*.mkv")
        for file_path in files:
            try:
                mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                if current_time - mod_time < timedelta(minutes=10):
                    healthy_cameras += 1
                    break
            except Exception:
                continue

    if healthy_cameras == 0:
        print(f"No recent recordings found. Checked {len(camera_dirs)} cameras for date {current_date}")

    return healthy_cameras > 0

def check_health():
    """Comprehensive health check"""
    checks = [
        ("Storage directory", check_storage_access),
        ("Config directory", check_config_access),
        ("Web server", check_web_server),
        ("FFmpeg processes", check_ffmpeg_processes),
        ("Camera recordings", check_camera_recordings)
    ]

    failed_checks = []
    for check_name, check_func in checks:
        if not check_func():
            failed_checks.append(check_name)
            print(f"Health check failed: {check_name}")

    if failed_checks:
        return False

    return True

if __name__ == "__main__":
    sys.exit(0 if check_health() else 1)
