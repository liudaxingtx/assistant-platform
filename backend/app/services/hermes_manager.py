"""
HermesManager — programmatic control of Hermes multi-profile lifecycle.

Each client gets their own Hermes profile. This service:
- Creates profiles via `hermes profile create`
- Configures WhatsApp gateway via config file edits
- Updates persona.md for personality
- Manages email skill credentials
"""

import subprocess
import json
import os
from pathlib import Path


HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


def _run_hermes(*args) -> str:
    """Run a hermes CLI command and return stdout."""
    result = subprocess.run(
        ["hermes", *args],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"hermes {' '.join(args)} failed: {result.stderr}")
    return result.stdout.strip()


class HermesManager:
    """Manages Hermes profile lifecycle for the AI Assistant Platform."""

    @staticmethod
    def create_profile(profile_name: str) -> dict:
        """
        Create a new Hermes profile for a client.
        Returns the profile path and initial config.
        """
        _run_hermes("profile", "create", profile_name)
        profile_dir = HERMES_HOME / "profiles" / profile_name
        return {
            "profile_name": profile_name,
            "path": str(profile_dir),
        }

    @staticmethod
    def configure_personality(profile_name: str, persona_text: str):
        """Write the agent's persona.md file."""
        persona_path = HERMES_HOME / "profiles" / profile_name / "persona.md"
        persona_path.parent.mkdir(parents=True, exist_ok=True)
        persona_path.write_text(persona_text)

    @staticmethod
    def configure_gateway(profile_name: str, whatsapp_number: str):
        """
        Enable WhatsApp gateway for a profile.
        Updates the profile's config.yaml to add whatsapp platform.
        """
        config_path = HERMES_HOME / "profiles" / profile_name / "config.yaml"
        # Read existing config, add whatsapp platform if not present
        import yaml
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text()) or {}
        else:
            config = {}
        if "platforms" not in config:
            config["platforms"] = {}
        config["platforms"]["whatsapp"] = {
            "enabled": True,
            "number": whatsapp_number,
        }
        config_path.write_text(yaml.dump(config, default_flow_style=False))

    @staticmethod
    def configure_email(profile_name: str, email_type: str, credentials: dict):
        """Add an email account to the profile's email skill config."""
        config_path = HERMES_HOME / "profiles" / profile_name / "config.yaml"
        import yaml
        config = yaml.safe_load(config_path.read_text()) or {} if config_path.exists() else {}
        if "email_accounts" not in config:
            config["email_accounts"] = []
        config["email_accounts"].append({
            "type": email_type,
            **credentials,
        })
        config_path.write_text(yaml.dump(config, default_flow_style=False))

    @staticmethod
    def delete_profile(profile_name: str):
        """Remove a client's Hermes profile entirely."""
        _run_hermes("profile", "delete", profile_name, "--force")

    @staticmethod
    def get_status(profile_name: str) -> str:
        """Check if a profile's gateway is running."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", f"hermes.*{profile_name}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return "online" if result.returncode == 0 else "offline"
        except Exception:
            return "unknown"

    @staticmethod
    def list_profiles() -> list[str]:
        """List all Hermes profiles on this machine."""
        profiles_dir = HERMES_HOME / "profiles"
        if not profiles_dir.exists():
            return []
        return [d.name for d in profiles_dir.iterdir() if d.is_dir()]
