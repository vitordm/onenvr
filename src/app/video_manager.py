import os
import subprocess
import logging
from datetime import datetime, timedelta
import glob
import shutil

logger = logging.getLogger(__name__)

class VideoManager:
    def __init__(self, retention_days):
        self.retention_days = retention_days
        self.recorders = {}

    def set_recorders(self, recorders):
        """Update recorders reference."""
        self.recorders = recorders

    def update_retention(self, retention_days):
        """Update retention policy (hot-reload support)."""
        if self.retention_days != retention_days:
            logger.info(f"Updating retention policy: {self.retention_days} -> {retention_days} days")
            self.retention_days = retention_days

    def concatenate_daily_videos(self, camera_name):
        """Concatenate all segments from yesterday into a single file."""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        date_dir = f"/storage/{camera_name}/{yesterday}"

        if not os.path.exists(date_dir):
            logger.info(f"No directory found for {camera_name} on {yesterday}")
            return

        input_pattern = f"{date_dir}/*.mkv"
        output_file = f"{date_dir}/{camera_name}_{yesterday}.mkv"

        # Get all individual segment files (exclude already concatenated files)
        all_files = sorted(glob.glob(input_pattern))
        video_files = [f for f in all_files
                      if not f.endswith(f"{camera_name}_{yesterday}.mkv")]

        logger.debug(f"Found {len(all_files)} total files, {len(video_files)} segment files to process")

        if not video_files:
            logger.info(f"No videos to concatenate for {camera_name} on {yesterday}")
            return

        # Check disk space before concatenation (need roughly same size as segments)
        total_size = sum(os.path.getsize(f) for f in video_files)
        free_space = shutil.disk_usage(date_dir).free

        if total_size * 1.1 > free_space:  # 10% buffer
            logger.error(f"Insufficient disk space to concatenate {camera_name}: need {total_size/1024/1024:.0f}MB, have {free_space/1024/1024:.0f}MB")
            return

        filelist_path = None
        try:
            # Create file list for ffmpeg
            filelist_path = f"/tmp/filelist_{camera_name}_{yesterday}.txt"
            with open(filelist_path, 'w') as f:
                for video in video_files:
                    f.write(f"file '{os.path.abspath(video)}'\n")

            # Concatenate videos with low I/O priority
            cmd = [
                'ionice',
                '-c', '2',
                '-n', '7',
                'ffmpeg',
                '-hide_banner', '-y',
                '-loglevel', 'error',
                '-f', 'concat',
                '-safe', '0',
                '-i', filelist_path,
                '-c', 'copy',
                output_file
            ]

            logger.debug(f"FFmpeg concatenation command: {' '.join(cmd)}")

            subprocess.run(cmd, check=True)
            logger.info(f"Successfully concatenated videos for {camera_name} on {yesterday}")

            # Clean up individual segments after successful concatenation
            logger.debug(f"Cleaning up {len(video_files)} individual segment files")
            for video in video_files:
                try:
                    os.remove(video)
                except OSError as e:
                    logger.warning(f"Failed to remove segment file {video}: {str(e)}")

        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg concatenation failed for {camera_name}: {str(e)}")
            # Don't delete segments if concatenation failed
        except Exception as e:
            logger.error(f"Failed to concatenate videos for {camera_name}: {str(e)}")
        finally:
            # Clean up filelist
            if filelist_path and os.path.exists(filelist_path):
                try:
                    os.remove(filelist_path)
                except OSError:
                    pass

    def cleanup_old_recordings(self, emergency=False):
        """
        Remove recordings older than retention period.

        Args:
            emergency: If True, be more aggressive in freeing space
        """
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)

        if emergency:
            # In emergency mode, keep only last 24 hours
            cutoff_date = datetime.now() - timedelta(days=1)
            logger.warning(f"EMERGENCY CLEANUP: Removing recordings older than 24 hours")
        else:
            logger.info(f"Cleaning up recordings older than {cutoff_date.strftime('%Y-%m-%d')} ({self.retention_days} days retention)")

        removed_count = 0
        freed_bytes = 0

        try:
            storage_dirs = glob.glob('/storage/*/')
            logger.debug(f"Found {len(storage_dirs)} camera directories in /storage/")

            for camera_dir in storage_dirs:
                camera_name = os.path.basename(camera_dir.rstrip('/'))
                logger.debug(f"Processing camera directory: {camera_dir} (camera: {camera_name})")

                date_dirs = glob.glob(f"{camera_dir}*/")
                logger.debug(f"Found {len(date_dirs)} date directories for camera {camera_name}")

                for date_dir in date_dirs:
                    dir_name = os.path.basename(date_dir.rstrip('/'))
                    logger.debug(f"Processing date directory: {date_dir} (date: {dir_name})")

                    try:
                        dir_date = datetime.strptime(dir_name, '%Y-%m-%d')
                        if dir_date < cutoff_date:
                            # Calculate size before removal for logging
                            dir_size = 0
                            files_to_remove = glob.glob(f"{date_dir}*")

                            for file_path in files_to_remove:
                                try:
                                    dir_size += os.path.getsize(file_path)
                                    os.remove(file_path)
                                except OSError as e:
                                    logger.warning(f"Failed to remove file {file_path}: {str(e)}")

                            # Remove the directory
                            try:
                                os.rmdir(date_dir)
                                removed_count += 1
                                freed_bytes += dir_size
                                logger.info(f"Removed old recordings: {date_dir} ({dir_size/1024/1024:.1f}MB)")
                            except OSError as e:
                                logger.warning(f"Failed to remove directory {date_dir}: {str(e)}")
                        else:
                            logger.debug(f"Directory {date_dir} is within retention period, keeping")

                    except (ValueError, OSError) as e:
                        logger.warning(f"Could not process directory {date_dir}: {str(e)}")
                        continue

            if removed_count == 0:
                logger.info("No old recordings found to delete")
            else:
                logger.info(f"Cleanup complete: removed {removed_count} directories, freed {freed_bytes/1024/1024:.1f}MB")

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")

    def get_storage_stats(self):
        """Get storage statistics for all cameras."""
        stats = {
            'total_cameras': 0,
            'total_size_bytes': 0,
            'oldest_recording': None,
            'newest_recording': None
        }

        try:
            storage_dirs = glob.glob('/storage/*/')
            stats['total_cameras'] = len(storage_dirs)

            for camera_dir in storage_dirs:
                date_dirs = glob.glob(f"{camera_dir}*/")
                for date_dir in date_dirs:
                    try:
                        dir_date = datetime.strptime(os.path.basename(date_dir.rstrip('/')), '%Y-%m-%d')

                        if stats['oldest_recording'] is None or dir_date < stats['oldest_recording']:
                            stats['oldest_recording'] = dir_date
                        if stats['newest_recording'] is None or dir_date > stats['newest_recording']:
                            stats['newest_recording'] = dir_date

                        for file_path in glob.glob(f"{date_dir}*"):
                            try:
                                stats['total_size_bytes'] += os.path.getsize(file_path)
                            except OSError:
                                continue
                    except ValueError:
                        continue

        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")

        return stats
