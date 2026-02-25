"""
PostHog Analytics Manager for Molt-Speak

Tracks key metrics:
- Downloads (first-run detection)
- Updates (app version changes)
- Session lengths and engagement
- User behavior patterns
- Bot detection indicators
"""

import os
import json
import uuid
import time
import atexit
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Public write-only project API key (safe to embed, like Google Analytics tracking ID)
_DEFAULT_API_KEY = "phc_pVyyYuhVRHc2CEON7HApwzVZ9Mqt5zczNtzyiIUO7mI"
_DEFAULT_HOST = "https://us.i.posthog.com"

# Load .env so POSTHOG_API_KEY is available even if caller didn't load it
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try to import PostHog, gracefully handle if not installed
try:
    import posthog
    POSTHOG_AVAILABLE = True
except ImportError:
    POSTHOG_AVAILABLE = False
    logger.warning("PostHog not installed. Analytics disabled. Run: pip install posthog>=3.0.0")


def get_persistent_analytics_dir() -> Path:
    """
    Get persistent directory for analytics data that survives uninstalls.

    Returns:
        Path to persistent analytics directory
    """
    if os.name == 'posix':
        if os.uname().sysname == 'Darwin':  # macOS
            base_dir = Path.home() / "Library" / "Application Support" / "molt-speak"
        else:  # Linux/Unix
            base_dir = Path.home() / ".config" / "molt-speak"
    else:  # Windows
        base_dir = Path.home() / "AppData" / "Local" / "molt-speak"

    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir


class AnalyticsManager:
    """
    Manages PostHog analytics for Molt-Speak application.

    Features:
    - Unique user identification (persisted)
    - First-run detection (downloads)
    - Session tracking (start/end/duration)
    - Event tracking with bot detection metadata
    - Update detection (version changes)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        host: Optional[str] = None,
        runtime_dir: Optional[str] = None,
        disabled: bool = False
    ):
        """
        Initialize analytics manager.

        Args:
            api_key: PostHog project API key (from env POSTHOG_API_KEY)
            host: PostHog host URL (default: https://us.i.posthog.com)
            runtime_dir: Directory for persistent data (default: persistent system dir)
            disabled: Disable all analytics
        """
        self.disabled = disabled or not POSTHOG_AVAILABLE

        # Use persistent directory by default (survives uninstalls)
        if runtime_dir is None:
            self.runtime_dir = get_persistent_analytics_dir()
        else:
            self.runtime_dir = Path(runtime_dir)
            self.runtime_dir.mkdir(parents=True, exist_ok=True)

        self.analytics_file = self.runtime_dir / "analytics_state.json"
        self.user_id: Optional[str] = None
        self.session_start: Optional[float] = None
        self.app_version = self._read_version()
        self.interaction_count = 0
        self.voice_interaction_count = 0

        # Initialize PostHog if enabled
        if not self.disabled:
            api_key = api_key or os.getenv("POSTHOG_API_KEY") or _DEFAULT_API_KEY
            host = host or os.getenv("POSTHOG_HOST") or _DEFAULT_HOST

            try:
                posthog.api_key = api_key
                posthog.host = host
            except Exception as e:
                logger.error(f"Failed to initialize PostHog: {e}")
                self.disabled = True

        # Load or create persistent state
        self._load_state()

        # Set person properties in PostHog so they appear in Persons
        if POSTHOG_AVAILABLE and not self.disabled and self.user_id:
            try:
                posthog.capture(
                    distinct_id=self.user_id,
                    event="app_opened",
                    properties={
                        "$set": {
                            "app_version": self.app_version,
                            "platform": os.uname().sysname,
                        }
                    }
                )
            except Exception as e:
                logger.error(f"Failed to set person properties: {e}")

        # Log analytics status clearly
        if self.disabled:
            logger.warning(f"PostHog analytics DISABLED — posthog_installed={POSTHOG_AVAILABLE}")
        else:
            logger.info(f"PostHog analytics ENABLED — host={host}")

        # Register shutdown handler
        atexit.register(self.shutdown)

    def _read_version(self) -> str:
        """Read app version from VERSION file."""
        try:
            version_file = Path(__file__).parent.parent.parent / "VERSION"
            if version_file.exists():
                return version_file.read_text().strip()
            return "1.0.0"
        except Exception as e:
            logger.error(f"Failed to read VERSION file: {e}")
            return "1.0.0"

    def _load_state(self):
        """Load persistent analytics state."""
        if self.analytics_file.exists():
            try:
                with open(self.analytics_file, 'r') as f:
                    state = json.load(f)
                    self.user_id = state.get("user_id")
                    last_version = state.get("app_version")
                    install_date = state.get("install_date")
                    total_sessions = state.get("total_sessions", 0)
                    total_runtime = state.get("total_runtime_seconds", 0)

                    # Track update if version changed
                    if last_version and last_version != self.app_version:
                        self.track_event("app_updated", {
                            "previous_version": last_version,
                            "new_version": self.app_version,
                            "total_sessions": total_sessions,
                            "total_runtime_hours": round(total_runtime / 3600, 2)
                        })

                    logger.info(f"Loaded user ID: {self.user_id}")
                    logger.info(f"Install date: {install_date}, Total sessions: {total_sessions}")

                    # Check for daily active event
                    self._check_daily_active(state)
            except Exception as e:
                logger.error(f"Failed to load analytics state: {e}")
                self.user_id = None

        # Generate new user ID if needed (first install)
        if not self.user_id:
            self.user_id = str(uuid.uuid4())
            install_date = datetime.now(timezone.utc).isoformat()
            self._save_state(install_date=install_date)

            # Track installation
            self.track_event("app_installed", {
                "install_date": install_date,
                "app_version": self.app_version,
                "platform": os.uname().sysname,
                "platform_version": os.uname().release
            })
            logger.info(f"First run detected. User ID: {self.user_id}")

    def _check_daily_active(self, state: Dict[str, Any]):
        """
        Check if user should be marked as daily active.
        Sends event once per day when app is first used.
        """
        try:
            last_checkin = state.get("last_daily_checkin")
            today = datetime.now(timezone.utc).date().isoformat()

            # Send daily active event if not checked in today
            if last_checkin != today:
                days_since_install = None
                if "install_date" in state:
                    try:
                        install_dt = datetime.fromisoformat(state["install_date"])
                        # Normalize naive timestamps (pre-fix) to UTC
                        if install_dt.tzinfo is None:
                            install_dt = install_dt.replace(tzinfo=timezone.utc)
                        days_since_install = (datetime.now(timezone.utc) - install_dt).days
                    except (ValueError, TypeError):
                        pass

                self.track_event("daily_active", {
                    "days_since_install": days_since_install,
                    "total_sessions": state.get("total_sessions", 0),
                    "total_runtime_hours": round(state.get("total_runtime_seconds", 0) / 3600, 2)
                })

                # Update last checkin date
                self._save_state(last_daily_checkin=today)
                logger.info(f"Daily active event sent (user active on {today})")
        except (ValueError, TypeError, OSError) as e:
            logger.exception(f"Failed to check daily active: {e}")

    def _save_state(self, **updates):
        """Save persistent analytics state."""
        try:
            state = {}
            if self.analytics_file.exists():
                with open(self.analytics_file, 'r') as f:
                    state = json.load(f)

            state.update({
                "user_id": self.user_id,
                "app_version": self.app_version,
                **updates
            })

            with open(self.analytics_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save analytics state: {e}")

    def start_session(self):
        """Track session start."""
        if self.disabled:
            return

        self.session_start = time.time()
        self.interaction_count = 0
        self.voice_interaction_count = 0

        # Load total sessions
        total_sessions = 0
        if self.analytics_file.exists():
            with open(self.analytics_file, 'r') as f:
                state = json.load(f)
                total_sessions = state.get("total_sessions", 0)

        # Track session start — $set updates person properties in PostHog
        self.track_event("session_started", {
            "session_number": total_sessions + 1,
            "app_version": self.app_version,
            "$set": {
                "app_version": self.app_version,
                "total_sessions": total_sessions + 1,
                "platform": os.uname().sysname,
            }
        })

        logger.info(f"Session started for user {self.user_id}")

    def end_session(self):
        """Track session end with duration."""
        if self.disabled or not self.session_start:
            return

        session_duration = time.time() - self.session_start

        # Load state
        state = {}
        if self.analytics_file.exists():
            with open(self.analytics_file, 'r') as f:
                state = json.load(f)

        total_sessions = state.get("total_sessions", 0) + 1
        total_runtime = state.get("total_runtime_seconds", 0) + session_duration

        # Bot detection heuristics
        is_suspicious = self._detect_suspicious_behavior(session_duration)

        # Track session end
        self.track_event("session_ended", {
            "duration_seconds": round(session_duration, 2),
            "duration_minutes": round(session_duration / 60, 2),
            "interactions": self.interaction_count,
            "voice_interactions": self.voice_interaction_count,
            "interactions_per_minute": round((self.interaction_count / session_duration) * 60, 2) if session_duration > 0 else 0,
            "is_suspicious": is_suspicious,
            "total_sessions": total_sessions,
            "total_runtime_hours": round(total_runtime / 3600, 2)
        })

        # Save updated state
        self._save_state(
            total_sessions=total_sessions,
            total_runtime_seconds=total_runtime,
            last_session_date=datetime.now(timezone.utc).isoformat()
        )

        logger.info(f"Session ended. Duration: {session_duration:.2f}s, Total sessions: {total_sessions}")
        self.session_start = None

    def _detect_suspicious_behavior(self, session_duration: float) -> bool:
        """
        Detect potentially bot-like behavior.

        Heuristics:
        - Session too short (< 5 seconds)
        - No voice interactions
        - Extremely high interaction rate
        - Very long session with no interactions
        """
        if session_duration < 5:
            logger.warning("Suspicious: Very short session")
            return True

        if session_duration > 60 and self.voice_interaction_count == 0:
            logger.warning("Suspicious: Long session with no voice interactions")
            return True

        if session_duration > 0:
            interaction_rate = self.interaction_count / session_duration
            if interaction_rate > 10:  # More than 10 actions per second
                logger.warning("Suspicious: Extremely high interaction rate")
                return True

        return False

    def track_event(self, event_name: str, properties: Optional[Dict[str, Any]] = None):
        """
        Track a custom event.

        Args:
            event_name: Name of the event
            properties: Additional event properties
        """
        if self.disabled:
            return

        properties = properties or {}
        properties.update({
            "user_id": self.user_id,
            "app_version": self.app_version,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "platform": os.uname().sysname
        })

        if POSTHOG_AVAILABLE:
            try:
                posthog.capture(
                    distinct_id=self.user_id,
                    event=event_name,
                    properties=properties
                )
                logger.debug(f"Event tracked: {event_name}")
            except Exception as e:
                logger.error(f"Failed to track event {event_name}: {e}")

        # Increment interaction counter
        self.interaction_count += 1

    def track_voice_interaction(self, interaction_type: str, **properties):
        """
        Track voice-specific interactions.

        Args:
            interaction_type: Type of interaction (transcription, synthesis, etc.)
            **properties: Additional properties
        """
        self.voice_interaction_count += 1
        self.track_event(f"voice_{interaction_type}", properties)

    def track_download(self):
        """Track app download (alias for first install)."""
        # This is automatically tracked in _load_state as "app_installed"
        pass

    def track_update(self):
        """Track app update (alias, handled automatically in _load_state)."""
        pass

    def shutdown(self):
        """Shutdown analytics and flush events."""
        logger.info("Shutting down analytics...")

        # End session if active
        if self.session_start:
            self.end_session()

        # Flush PostHog events
        if POSTHOG_AVAILABLE and not self.disabled:
            try:
                posthog.shutdown()
                logger.info("PostHog shutdown complete")
            except Exception as e:
                logger.error(f"Error during PostHog shutdown: {e}")


# Singleton instance
_analytics_instance: Optional[AnalyticsManager] = None


def get_analytics() -> AnalyticsManager:
    """Get or create singleton analytics manager."""
    global _analytics_instance
    if _analytics_instance is None:
        _analytics_instance = AnalyticsManager()
    return _analytics_instance


def initialize_analytics(**kwargs) -> AnalyticsManager:
    """
    Initialize analytics with custom configuration.

    Args:
        **kwargs: Arguments passed to AnalyticsManager constructor

    Returns:
        AnalyticsManager instance
    """
    global _analytics_instance
    _analytics_instance = AnalyticsManager(**kwargs)
    return _analytics_instance
