"""
Gateway Supervisor — manages Hermes gateway processes per client profile.

Each client profile can have one active gateway process.
The supervisor handles start, stop, restart, and status checks.
"""

import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Optional

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
LOG_DIR = HERMES_HOME / "logs"


class GatewaySupervisor:
    """Manages Hermes gateway processes for client profiles."""

    _processes: dict = {}  # profile_name -> subprocess.Popen

    @classmethod
    def _get_log_path(cls, profile_name: str) -> Path:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        return LOG_DIR / f"gateway-{profile_name}.log"

    @classmethod
    def start(cls, profile_name: str) -> dict:
        """Start a Hermes gateway for the given profile."""
        profile_dir = HERMES_HOME / "profiles" / profile_name
        if not profile_dir.exists():
            return {"status": "error", "detail": f"Profile '{profile_name}' not found"}
        
        # Stop any existing process for this profile
        cls.stop(profile_name)

        log_path = cls._get_log_path(profile_name)
        log_file = open(str(log_path), "a")

        try:
            # In production: hermes gateway run --profile <name>
            # In dev: simulate with a lightweight echo server that reads config
            proc = subprocess.Popen(
                [
                    "python3", "-c",
                    f"""
import time, json, sys
from pathlib import Path

profile_dir = Path.home() / ".hermes" / "profiles" / "{profile_name}"
config_path = profile_dir / "config.yaml"

print(f"[Gateway] Starting for profile: {profile_name}", flush=True)
print(f"[Gateway] Config path: {{config_path}}", flush=True)

if config_path.exists():
    import yaml
    config = yaml.safe_load(config_path.read_text())
    print(f"[Gateway] Loaded config — platforms: {{list(config.get('platforms',{{}}).keys())}}", flush=True)
    print(f"[Gateway] READY", flush=True)
else:
    print(f"[Gateway] WARNING: No config.yaml found", flush=True)
    print(f"[Gateway] READY (empty config)", flush=True)

# Keep alive — check config every 30s for changes
last_mtime = config_path.stat().st_mtime if config_path.exists() else 0
while True:
    time.sleep(30)
    if config_path.exists():
        mtime = config_path.stat().st_mtime
        if mtime > last_mtime:
            print(f"[Gateway] Config changed, reloading...", flush=True)
            last_mtime = mtime
            import yaml
            config = yaml.safe_load(config_path.read_text())
            print(f"[Gateway] Reloaded — platforms: {{list(config.get('platforms',{{}}).keys())}}", flush=True)
""",
                ],
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            cls._processes[profile_name] = proc
            
            # Wait a moment, then verify it started
            time.sleep(1.5)
            if proc.poll() is not None:
                # It already exited — read the last few log lines
                log_content = log_path.read_text() if log_path.exists() else ""
                return {
                    "status": "error",
                    "detail": f"Gateway exited immediately (code {proc.returncode})",
                    "log_tail": log_content[-500:] if log_content else "(no output)",
                }
            
            return {
                "status": "online",
                "profile_name": profile_name,
                "pid": proc.pid,
                "log": str(log_path),
            }
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @classmethod
    def stop(cls, profile_name: str) -> dict:
        """Stop the gateway process for a given profile."""
        proc = cls._processes.pop(profile_name, None)
        if proc is None:
            return {"status": "ok", "detail": f"No running gateway for '{profile_name}'"}
        
        try:
            # Try graceful shutdown first
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            return {"status": "offline", "detail": f"Gateway stopped (was PID {proc.pid})"}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    @classmethod
    def restart(cls, profile_name: str) -> dict:
        """Restart the gateway process."""
        stop_result = cls.stop(profile_name)
        start_result = cls.start(profile_name)
        return {
            "action": "restart",
            "stop": stop_result,
            "start": start_result,
        }

    @classmethod
    def status(cls, profile_name: str) -> str:
        """Check if a profile's gateway is running."""
        proc = cls._processes.get(profile_name)
        if proc is None:
            return "offline"
        if proc.poll() is not None:
            # Process exited on its own
            del cls._processes[profile_name]
            return "offline"
        return "online"

    @classmethod
    def list_all(cls) -> list[dict]:
        """List all running gateways."""
        result = []
        for name, proc in list(cls._processes.items()):
            running = proc.poll() is None
            if not running:
                del cls._processes[name]
            result.append({
                "profile_name": name,
                "status": "online" if running else "offline",
                "pid": proc.pid,
            })
        return result

    @classmethod
    def get_log(cls, profile_name: str, tail: int = 50) -> str:
        """Get the last N lines of gateway log."""
        log_path = cls._get_log_path(profile_name)
        if not log_path.exists():
            return "(no log yet)"
        lines = log_path.read_text().strip().split("\n")
        return "\n".join(lines[-tail:])

    @classmethod
    def shutdown_all(cls):
        """Stop all running gateways. Call on server shutdown."""
        for name in list(cls._processes.keys()):
            cls.stop(name)
