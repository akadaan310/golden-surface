"""Subprocess execution with time, RSS and output limits; no shell interpolation."""
from collections import deque
import os
from pathlib import Path
import signal
import subprocess
import threading
import time


def _rss_mb(pid):
    try:
        import psutil
        process = psutil.Process(pid)
        return sum(p.memory_info().rss for p in [process, *process.children(recursive=True)]
                   if p.is_running()) / 1048576
    except Exception:
        try:
            text = Path(f'/proc/{pid}/status').read_text()
            return float(text.split('VmRSS:')[1].split()[0]) / 1024
        except Exception:
            return 0.0


def _stop(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        pass
    # A successful wait only reaps the group leader. Resistant descendants may
    # still own stdout/CPU; terminate the entire owned session even after exit.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=2)


def execute(command, cwd, timeout_s, max_rss_mb, max_log_bytes):
    started = time.monotonic()
    tail = bytearray()
    error, peak_rss = None, 0.0
    try:
        process = subprocess.Popen(command, cwd=cwd, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as exc:
        return {'returncode': 127, 'duration_s': time.monotonic()-started,
                'peak_rss_mb': 0, 'output': str(exc), 'error': 'missing_resource'}

    def drain():
        while chunk := process.stdout.read(8192):
            tail.extend(chunk)
            if len(tail) > max_log_bytes:
                del tail[:-max_log_bytes]
        process.stdout.close()

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    try:
        while process.poll() is None:
            elapsed = time.monotonic()-started
            peak_rss = max(peak_rss, _rss_mb(process.pid))
            if elapsed > timeout_s or peak_rss > max_rss_mb:
                error = 'resource_budget'
                _stop(process)
                break
            time.sleep(min(0.025, timeout_s/4))
    except BaseException:
        _stop(process)
        reader.join(timeout=2)
        raise
    _stop(process)  # no background descendants survive a completed task
    reader.join(timeout=2)
    return {'returncode': process.returncode, 'duration_s': time.monotonic()-started,
            'peak_rss_mb': round(peak_rss, 2),
            'output': bytes(tail).decode('utf-8', errors='replace'), 'error': error}
