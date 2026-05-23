"""
Logging utility untuk mencatat setiap action/penggunaan feature.
Menyimpan log dalam format JSON lines (satu objek JSON per baris).
Rotasi otomatis per hari berdasarkan nama file: usage-YYYY-MM-DD.log
"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

LOG_DIR = Path(os.path.dirname(os.path.abspath(__file__))) / "logs"
LOG_FILE_PATTERN = "usage-{date}.log"


def _get_log_path():
    LOG_DIR.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y-%m-%d")
    return LOG_DIR / LOG_FILE_PATTERN.format(date=date_str)


def _get_log_path_for_date(date_str):
    """Mendapatkan path file log untuk tanggal tertentu."""
    LOG_DIR.mkdir(exist_ok=True)
    return LOG_DIR / LOG_FILE_PATTERN.format(date=date_str)


def list_available_dates():
    """Mengembalikan daftar tanggal yang memiliki file log."""
    LOG_DIR.mkdir(exist_ok=True)
    dates = []
    for f in sorted(LOG_DIR.glob("usage-*.log"), reverse=True):
        # Extract date from filename: usage-YYYY-MM-DD.log
        date_str = f.stem.replace("usage-", "")
        try:
            datetime.strptime(date_str, "%Y-%m-%d")  # validate
            dates.append(date_str)
        except ValueError:
            continue
    return dates


def _get_client_ip():
    """Mendapatkan IP asli client dari Flask request.
    Handle X-Forwarded-For untuk reverse proxy / load balancer."""
    try:
        from flask import request
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip()
        return request.remote_addr or "unknown"
    except Exception:
        return "unknown"


def log_action(feature, action, params=None, status="success", duration_ms=None, detail=None, ip=None):
    """
    Mencatat action ke file log.

    Args:
        feature: Nama fitur (e.g., "analyze", "screener", "extract", "refresh")
        action: Aksi spesifik (e.g., "analyze_stock", "most_active", "start_extraction")
        params: Parameter yang dikirim user (dict, optional)
        status: "success" atau "error"
        duration_ms: Durasi eksekusi dalam milidetik (optional)
        detail: Pesan detail tambahan (optional)
        ip: IP asal request (optional, auto-detect dari Flask jika tidak diisi)
    """
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "feature": feature,
            "action": action,
            "status": status,
            "ip": ip or _get_client_ip(),
        }

        if params:
            sanitized = {}
            for k, v in params.items():
                if isinstance(v, str) and len(v) > 100:
                    sanitized[k] = v[:100] + "..."
                else:
                    sanitized[k] = v
            log_entry["params"] = sanitized

        if duration_ms is not None:
            log_entry["duration_ms"] = round(duration_ms, 2)

        if detail:
            log_entry["detail"] = detail

        log_path = _get_log_path()
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.error("Failed to write log entry: %s", e)


def read_recent_logs(limit=50, date=None):
    """
    Membaca log terbaru dari file log.

    Args:
        limit: Jumlah baris terakhir (default 50)
        date: Tanggal dalam format YYYY-MM-DD (None = hari ini)
    """
    if date:
        log_path = _get_log_path_for_date(date)
    else:
        log_path = _get_log_path()
    if not log_path.exists():
        return []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        entries = []
        for line in lines[-limit:]:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return list(reversed(entries))
    except Exception as e:
        logger.error("Failed to read logs: %s", e)
        return []
