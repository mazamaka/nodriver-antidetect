"""Session management for antidetect browser.

Provides persistent browser sessions with cookies, localStorage, and cache preservation.
"""

from __future__ import annotations

import fcntl
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field


class SessionMetadata(BaseModel):
    """Metadata for browser session."""

    name: str
    profile_name: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_used_at: datetime = Field(default_factory=datetime.now)
    user_agent: str | None = None
    notes: str | None = None


class SessionManager:
    """
    Manager for browser sessions with persistent storage.

    Sessions are stored as Chrome user_data_dir directories with metadata.
    Each session preserves: cookies, localStorage, cache, history.

    Usage:
        manager = SessionManager()

        # List sessions
        sessions = manager.list()

        # Get session path for browser
        session_path = manager.get_or_create("my_session")

        # Clone session
        manager.clone("my_session", "my_session_copy")

        # Delete session
        manager.delete("my_session")
    """

    DEFAULT_BASE_DIR = Path("./sessions")
    METADATA_FILE = "metadata.json"
    LOCK_FILE = ".lock"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        """
        Initialize session manager.

        Args:
            base_dir: Base directory for sessions. Default: ./sessions
        """
        self.base_dir = Path(base_dir) if base_dir else self.DEFAULT_BASE_DIR
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, Any] = {}

    def list(self) -> list[SessionMetadata]:
        """List all available sessions with metadata."""
        sessions = []

        for session_dir in self.base_dir.iterdir():
            if session_dir.is_dir() and not session_dir.name.startswith("."):
                metadata = self._load_metadata(session_dir.name)
                if metadata:
                    sessions.append(metadata)

        return sorted(sessions, key=lambda s: s.last_used_at, reverse=True)

    def exists(self, name: str) -> bool:
        """Check if session exists."""
        session_dir = self.base_dir / name
        return session_dir.exists() and session_dir.is_dir()

    def get_path(self, name: str) -> Path:
        """Get path to session directory (user_data_dir for Chrome)."""
        return self.base_dir / name

    def get_or_create(
        self,
        name: str,
        profile_name: str | None = None,
        user_agent: str | None = None,
    ) -> Path:
        """
        Get existing session or create new one.

        Args:
            name: Session name
            profile_name: Associated fingerprint profile name
            user_agent: User agent string for metadata

        Returns:
            Path to session directory (use as user_data_dir)
        """
        session_dir = self.base_dir / name

        if not session_dir.exists():
            return self.create(name, profile_name, user_agent)

        self._update_last_used(name)
        return session_dir

    def create(
        self,
        name: str,
        profile_name: str | None = None,
        user_agent: str | None = None,
        notes: str | None = None,
    ) -> Path:
        """
        Create new session.

        Args:
            name: Session name (alphanumeric, underscores, hyphens)
            profile_name: Associated fingerprint profile
            user_agent: User agent for metadata
            notes: Optional notes

        Returns:
            Path to session directory

        Raises:
            ValueError: If session already exists or invalid name
        """
        if not self._is_valid_name(name):
            raise ValueError(
                f"Invalid session name: {name}. Use only alphanumeric, underscores, hyphens."
            )

        session_dir = self.base_dir / name

        if session_dir.exists():
            raise ValueError(f"Session already exists: {name}")

        session_dir.mkdir(parents=True)

        metadata = SessionMetadata(
            name=name,
            profile_name=profile_name,
            user_agent=user_agent,
            notes=notes,
        )
        self._save_metadata(name, metadata)

        logger.info(f"Created session: {name}")
        return session_dir

    def delete(self, name: str, force: bool = False) -> None:
        """
        Delete session and all its data.

        Args:
            name: Session name
            force: Delete even if locked

        Raises:
            ValueError: If session doesn't exist
            RuntimeError: If session is locked and not force
        """
        session_dir = self.base_dir / name

        if not session_dir.exists():
            raise ValueError(f"Session not found: {name}")

        if not force and self.is_locked(name):
            raise RuntimeError(
                f"Session is locked (in use): {name}. Use force=True or close the browser first."
            )

        self.unlock(name)
        shutil.rmtree(session_dir)
        logger.info(f"Deleted session: {name}")

    def clone(self, source: str, target: str) -> Path:
        """
        Clone session to new name.

        Args:
            source: Source session name
            target: Target session name

        Returns:
            Path to new session directory
        """
        source_dir = self.base_dir / source
        target_dir = self.base_dir / target

        if not source_dir.exists():
            raise ValueError(f"Source session not found: {source}")

        if target_dir.exists():
            raise ValueError(f"Target session already exists: {target}")

        if not self._is_valid_name(target):
            raise ValueError(f"Invalid target name: {target}")

        shutil.copytree(source_dir, target_dir)

        metadata = self._load_metadata(target)
        if metadata:
            metadata.name = target
            metadata.created_at = datetime.now()
            metadata.notes = f"Cloned from {source}"
            self._save_metadata(target, metadata)

        logger.info(f"Cloned session: {source} -> {target}")
        return target_dir

    def get_metadata(self, name: str) -> SessionMetadata | None:
        """Get session metadata."""
        return self._load_metadata(name)

    def update_metadata(
        self,
        name: str,
        profile_name: str | None = None,
        user_agent: str | None = None,
        notes: str | None = None,
    ) -> None:
        """Update session metadata."""
        metadata = self._load_metadata(name)
        if not metadata:
            raise ValueError(f"Session not found: {name}")

        if profile_name is not None:
            metadata.profile_name = profile_name
        if user_agent is not None:
            metadata.user_agent = user_agent
        if notes is not None:
            metadata.notes = notes

        self._save_metadata(name, metadata)

    # === Locking mechanism ===

    def lock(self, name: str) -> bool:
        """
        Acquire exclusive lock on session.

        Returns:
            True if lock acquired, False if already locked
        """
        session_dir = self.base_dir / name
        lock_file = session_dir / self.LOCK_FILE

        if name in self._locks:
            return True

        try:
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            f = open(lock_file, "w")
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._locks[name] = f
            logger.debug(f"Locked session: {name}")
            return True
        except OSError:
            return False

    def unlock(self, name: str) -> None:
        """Release lock on session."""
        if name in self._locks:
            try:
                f = self._locks[name]
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                f.close()
                lock_file = self.base_dir / name / self.LOCK_FILE
                lock_file.unlink(missing_ok=True)
            except OSError as e:
                logger.debug(f"Failed to unlock session {name}: {e}")
            finally:
                del self._locks[name]
            logger.debug(f"Unlocked session: {name}")

    def is_locked(self, name: str) -> bool:
        """Check if session is locked by another process."""
        if name in self._locks:
            return False

        session_dir = self.base_dir / name
        lock_file = session_dir / self.LOCK_FILE

        if not lock_file.exists():
            return False

        try:
            f = open(lock_file)
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            f.close()
            return False
        except OSError:
            return True

    # === Private methods ===

    def _is_valid_name(self, name: str) -> bool:
        """Validate session name."""
        return bool(re.match(r"^[a-zA-Z0-9_-]+$", name))

    def _load_metadata(self, name: str) -> SessionMetadata | None:
        """Load metadata from file."""
        metadata_file = self.base_dir / name / self.METADATA_FILE

        if not metadata_file.exists():
            if (self.base_dir / name).exists():
                return SessionMetadata(name=name)
            return None

        try:
            with open(metadata_file) as f:
                data = json.load(f)
            return SessionMetadata(**data)
        except Exception as e:
            logger.warning(f"Failed to load metadata for {name}: {e}")
            return SessionMetadata(name=name)

    def _save_metadata(self, name: str, metadata: SessionMetadata) -> None:
        """Save metadata to file."""
        metadata_file = self.base_dir / name / self.METADATA_FILE
        metadata_file.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_file, "w") as f:
            json.dump(metadata.model_dump(mode="json"), f, indent=2, default=str)

    def _update_last_used(self, name: str) -> None:
        """Update last_used_at timestamp."""
        metadata = self._load_metadata(name)
        if metadata:
            metadata.last_used_at = datetime.now()
            self._save_metadata(name, metadata)
