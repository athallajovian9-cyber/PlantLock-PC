"""Hosts-file social media lock (marked entries, fully reversible)."""
import subprocess

BLOCK = [
    "instagram.com", "www.instagram.com",
    "facebook.com", "www.facebook.com", "m.facebook.com",
    "x.com", "www.x.com", "twitter.com", "www.twitter.com",
    "tiktok.com", "www.tiktok.com", "m.tiktok.com",
    "reddit.com", "www.reddit.com", "old.reddit.com",
    "threads.net", "www.threads.net",
]
MARK_BEGIN = "# <PlantLock BEGIN>"
MARK_END = "# <PlantLock END>"
HOSTS = r"C:\Windows\System32\drivers\etc\hosts"


def is_elevated() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _read() -> str:
    with open(HOSTS, "r", encoding="utf-8") as f:
        return f.read()


def locked() -> bool:
    try:
        return MARK_BEGIN in _read()
    except OSError:
        return False


def apply_lock() -> bool:
    """Insert blocked entries inside markers. Requires admin."""
    try:
        text = _read()
        if MARK_BEGIN in text:
            return True
        lines = [MARK_BEGIN]
        for host in BLOCK:
            lines.append(f"0.0.0.0 {host}")
        lines.append(MARK_END)
        block = "\n" + "\n".join(lines) + "\n"
        with open(HOSTS, "a", encoding="utf-8") as f:
            f.write(block)
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=15)
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def release_lock() -> bool:
    """Remove our marked block. Requires admin."""
    try:
        text = _read()
        if MARK_BEGIN not in text:
            return True
        start = text.index(MARK_BEGIN)
        end = text.index(MARK_END) + len(MARK_END) + 1
        new = text[:start] + text[end:]
        with open(HOSTS, "w", encoding="utf-8") as f:
            f.write(new)
        subprocess.run(["ipconfig", "/flushdns"], capture_output=True, timeout=15)
        return True
    except (PermissionError, OSError, ValueError):
        return False
