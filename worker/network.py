import subprocess

def ping_pi(ip: str, timeout_sec: int = 1) -> bool:
    try:
        result = subprocess.run(
            ["ping", "-c", "1", "-W", str(timeout_sec), ip],
            # cmd = ["ping", "-n", "1", "-w", str(timeout_sec * 1000), ip] for Windows
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0
    except Exception:
        return False