"""Tests for antidetect configuration models."""

from __future__ import annotations

from pathlib import Path

import pytest

from antidetect.config import (
    FingerprintProfile,
    MediaDevicesConfig,
    NavigatorConfig,
    ScreenConfig,
    WebGLConfig,
    build_user_agent,
    get_chrome_version,
    get_reduced_chrome_version,
    get_timezone_offset,
)


class TestChromeVersion:
    """Tests for Chrome version detection."""

    def test_get_chrome_version_returns_string(self) -> None:
        version = get_chrome_version()
        assert isinstance(version, str)
        assert len(version.split(".")) == 4

    def test_get_reduced_chrome_version(self) -> None:
        assert get_reduced_chrome_version("144.0.7559.59") == "144.0.0.0"
        assert get_reduced_chrome_version("132.0.6834.83") == "132.0.0.0"

    def test_get_reduced_chrome_version_single_part(self) -> None:
        assert get_reduced_chrome_version("144") == "144.0.0.0"


class TestBuildUserAgent:
    """Tests for User-Agent string generation."""

    def test_linux_user_agent(self) -> None:
        ua = build_user_agent("Linux x86_64", "144.0.7559.59")
        assert "X11; Linux x86_64" in ua
        assert "Chrome/144.0.0.0" in ua  # reduced version

    def test_windows_user_agent(self) -> None:
        ua = build_user_agent("Win32", "144.0.7559.59")
        assert "Windows NT 10.0" in ua
        assert "Chrome/144.0.0.0" in ua

    def test_macos_user_agent(self) -> None:
        ua = build_user_agent("MacIntel", "144.0.7559.59")
        assert "Macintosh" in ua
        assert "Chrome/144.0.0.0" in ua

    def test_unknown_platform_defaults_to_linux(self) -> None:
        ua = build_user_agent("UnknownPlatform", "144.0.7559.59")
        assert "Linux x86_64" in ua


class TestTimezoneOffset:
    """Tests for timezone offset calculation."""

    def test_utc_offset(self) -> None:
        assert get_timezone_offset("UTC") == 0

    def test_unknown_timezone_returns_zero(self) -> None:
        assert get_timezone_offset("Invalid/Timezone") == 0

    def test_known_timezone_returns_int(self) -> None:
        offset = get_timezone_offset("America/New_York")
        assert isinstance(offset, int)
        # EST is UTC-5 (300 min) or EDT UTC-4 (240 min)
        assert offset in (240, 300)


class TestFingerprintProfile:
    """Tests for FingerprintProfile model."""

    def test_default_profile_creation(self) -> None:
        profile = FingerprintProfile()
        assert profile.name == "default"
        assert profile.screen.width == 1920
        assert profile.screen.height == 1080
        assert profile.navigator.platform == "Linux x86_64"
        assert profile.canvas_noise > 0

    def test_custom_profile(self) -> None:
        profile = FingerprintProfile(
            name="test",
            screen=ScreenConfig(width=2560, height=1440),
            navigator=NavigatorConfig(hardware_concurrency=16),
        )
        assert profile.screen.width == 2560
        assert profile.navigator.hardware_concurrency == 16

    def test_webgl_config_defaults(self) -> None:
        config = WebGLConfig()
        assert "NVIDIA" in config.renderer
        assert config.vendor == config.unmasked_vendor

    def test_media_devices_defaults(self) -> None:
        config = MediaDevicesConfig()
        assert config.audio_inputs == 1
        assert config.video_inputs == 1


class TestProfileLoading:
    """Tests for profile loading from JSON."""

    def test_load_profile_from_json(self) -> None:
        from antidetect.profiles.loader import load_profile_from_json

        profiles_dir = Path(__file__).parent.parent / "profiles"
        profile_path = profiles_dir / "mazamaka_local.json"

        if profile_path.exists():
            profile = load_profile_from_json(profile_path)
            assert profile.name == "mazamaka_local"
            assert profile.screen.width == 3440

    def test_load_nonexistent_profile_raises(self) -> None:
        from antidetect.profiles.loader import load_profile_from_json

        with pytest.raises(FileNotFoundError):
            load_profile_from_json("/nonexistent/path.json")

    def test_load_profile_from_dict(self) -> None:
        from antidetect.profiles.loader import load_profile_from_dict

        data = {
            "name": "test_dict",
            "screen": {"width": 1280, "height": 720},
            "navigator": {"platform": "Win32"},
        }
        profile = load_profile_from_dict(data, "test_dict")
        assert profile.name == "test_dict"
        assert profile.screen.width == 1280
        assert profile.navigator.platform == "Win32"

    def test_list_profiles(self) -> None:
        from antidetect.profiles.loader import list_profiles

        profiles_dir = Path(__file__).parent.parent / "profiles"
        if profiles_dir.exists():
            profiles = list_profiles(profiles_dir)
            assert isinstance(profiles, list)
            assert "mazamaka_local" in profiles

    def test_profile_roundtrip(self) -> None:
        """Test save and load profile roundtrip."""
        from antidetect.profiles.loader import (
            load_profile_from_dict,
            profile_to_dict,
        )

        original = FingerprintProfile(
            name="roundtrip_test",
            screen=ScreenConfig(width=2560, height=1440),
        )
        data = profile_to_dict(original)
        restored = load_profile_from_dict(data, "roundtrip_test")

        assert restored.name == original.name
        assert restored.screen.width == original.screen.width
        assert restored.screen.height == original.screen.height


class TestStealthScript:
    """Tests for stealth script generation."""

    def test_build_stealth_script_returns_string(self) -> None:
        from antidetect.stealth import build_stealth_script

        profile = FingerprintProfile()
        script = build_stealth_script(profile)
        assert isinstance(script, str)
        assert "'use strict'" in script

    def test_stealth_script_contains_modules(self) -> None:
        from antidetect.stealth import build_stealth_script

        profile = FingerprintProfile()
        script = build_stealth_script(profile)

        # Check key modules are included
        assert "wrapFn" in script  # utils.js
        assert "webdriver" in script  # webdriver.js
        assert "UNMASKED_VENDOR_WEBGL" in script  # webgl.js
        assert "enumerateDevices" in script  # media.js

    def test_stealth_script_contains_config(self) -> None:
        from antidetect.stealth import build_stealth_script

        profile = FingerprintProfile(
            webgl=WebGLConfig(vendor="Test Vendor", renderer="Test Renderer"),
        )
        script = build_stealth_script(profile)
        assert "Test Vendor" in script
        assert "Test Renderer" in script

    def test_stealth_script_no_debug_markers(self) -> None:
        from antidetect.stealth import build_stealth_script

        profile = FingerprintProfile()
        script = build_stealth_script(profile)
        assert "__stealth_applied" not in script
        assert "__stealth_profile" not in script


class TestJSLoader:
    """Tests for JavaScript file loader."""

    def test_load_js_returns_content(self) -> None:
        from antidetect.js import load_js

        content = load_js("utils")
        assert "wrapFn" in content
        assert "defineProperty" in content

    def test_load_js_nonexistent_raises(self) -> None:
        from antidetect.js import load_js

        with pytest.raises(FileNotFoundError):
            load_js("nonexistent_module")

    def test_load_all_js(self) -> None:
        from antidetect.js import load_all_js

        all_js = load_all_js()
        assert "utils" in all_js
        assert "webgl" in all_js
        assert "canvas" in all_js
        assert len(all_js) >= 10


class TestSessionManager:
    """Tests for session management."""

    def test_session_manager_creation(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")
        assert manager.base_dir.exists()

    def test_create_and_list_session(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")
        manager.create("test_session", profile_name="default")

        sessions = manager.list()
        assert len(sessions) == 1
        assert sessions[0].name == "test_session"

    def test_session_locking(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")
        manager.create("lockable")

        assert manager.lock("lockable") is True
        assert manager.is_locked("lockable") is False  # Same process owns lock
        manager.unlock("lockable")

    def test_invalid_session_name(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")

        with pytest.raises(ValueError, match="Invalid session name"):
            manager.create("invalid name with spaces")

    def test_clone_session(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")
        manager.create("original", notes="original session")
        manager.clone("original", "clone")

        assert manager.exists("clone")
        meta = manager.get_metadata("clone")
        assert meta is not None
        assert "Cloned from original" in (meta.notes or "")

    def test_delete_session(self, tmp_path: Path) -> None:
        from antidetect.session import SessionManager

        manager = SessionManager(base_dir=tmp_path / "sessions")
        manager.create("to_delete")
        assert manager.exists("to_delete")

        manager.delete("to_delete")
        assert not manager.exists("to_delete")


class TestChromeArgsBuilder:
    """Tests for Chrome arguments builder."""

    def test_build_args_contains_essentials(self) -> None:
        from antidetect.chrome_args import ChromeArgsBuilder

        builder = ChromeArgsBuilder(FingerprintProfile(), sandbox=True)
        args = builder.build()

        assert "--disable-blink-features=AutomationControlled" in args
        assert "--enable-webgl" in args
        assert any("--window-size=" in a for a in args)

    def test_docker_args_added_without_sandbox(self) -> None:
        from antidetect.chrome_args import ChromeArgsBuilder

        builder = ChromeArgsBuilder(FingerprintProfile(), sandbox=False)
        args = builder.build()

        assert "--no-sandbox" in args
        assert "--disable-dev-shm-usage" in args

    def test_sandbox_args_not_added_with_sandbox(self) -> None:
        from antidetect.chrome_args import ChromeArgsBuilder

        builder = ChromeArgsBuilder(FingerprintProfile(), sandbox=True)
        args = builder.build()

        assert "--no-sandbox" not in args

    def test_extra_args_appended(self) -> None:
        from antidetect.chrome_args import ChromeArgsBuilder

        builder = ChromeArgsBuilder(FingerprintProfile(), sandbox=True)
        args = builder.build(extra_args=["--custom-flag"])

        assert "--custom-flag" in args
