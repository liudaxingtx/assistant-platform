"""
HermesManager — programmatic control of Hermes multi-profile lifecycle.

In production (Docker with Hermes installed): uses hermes CLI.
In development (local venv): writes config files directly to disk.
"""

import os
import yaml
from pathlib import Path

HERMES_HOME = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))


class HermesManager:
    """Manages Hermes profile lifecycle for the AI Assistant Platform."""

    @staticmethod
    def create_profile(profile_name: str) -> dict:
        """Create a new Hermes profile directory structure."""
        profile_dir = HERMES_HOME / "profiles" / profile_name
        profile_dir.mkdir(parents=True, exist_ok=True)
        # Create default config if not exists
        config_path = profile_dir / "config.yaml"
        if not config_path.exists():
            config_path.write_text(yaml.dump({
                "platforms": {},
                "skills": ["email", "web-search", "calendar"],
            }))
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
        """Enable WhatsApp gateway for a profile."""
        config_path = HERMES_HOME / "profiles" / profile_name / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) or {} if config_path.exists() else {}
        config.setdefault("platforms", {})["whatsapp"] = {
            "enabled": True,
            "number": whatsapp_number,
        }
        config_path.write_text(yaml.dump(config, default_flow_style=False))

    @staticmethod
    def configure_email(profile_name: str, email_type: str, credentials: dict):
        """Add an email account to the profile's email skill config."""
        config_path = HERMES_HOME / "profiles" / profile_name / "config.yaml"
        config = yaml.safe_load(config_path.read_text()) or {} if config_path.exists() else {}
        config.setdefault("email_accounts", []).append({
            "type": email_type,
            **credentials,
        })
        config_path.write_text(yaml.dump(config, default_flow_style=False))

    @staticmethod
    def delete_profile(profile_name: str):
        """Remove a client's Hermes profile entirely."""
        import shutil
        profile_dir = HERMES_HOME / "profiles" / profile_name
        if profile_dir.exists():
            shutil.rmtree(profile_dir)

    @staticmethod
    def get_status(profile_name: str) -> str:
        """Check if a profile's gateway process is running."""
        profile_dir = HERMES_HOME / "profiles" / profile_name
        if not profile_dir.exists():
            return "offline"
        config_path = profile_dir / "config.yaml"
        if config_path.exists():
            return "online"  # In dev, presence of config == "online"
        return "offline"

    @staticmethod
    def list_profiles() -> list[str]:
        """List all Hermes profiles on this machine."""
        profiles_dir = HERMES_HOME / "profiles"
        if not profiles_dir.exists():
            return []
        return [d.name for d in profiles_dir.iterdir() if d.is_dir()]
