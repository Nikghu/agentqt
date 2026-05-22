"""
Updater Stub — copy this file into your application.

Call check_for_updates() at startup to silently check for a newer version.
The installer writes 'updater_config.json' next to the executable at install time.

Two update modes (set in updater_config.json):
  - GitHub Releases mode  (recommended, no server needed):
      "github_repo": "owner/repo"
      "github_asset_pattern": "_Setup.exe"   # substring match on asset filename
  - Custom manifest mode:
      "check_url": "https://example.com/updates/manifest.json"

No third-party dependencies — stdlib only (Python 3.8+).
Only HTTPS URLs are accepted to prevent SSRF / downgrade attacks.
"""
from __future__ import annotations

import hashlib
import json
import logging
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen

log = logging.getLogger("updater")

_CONFIG_FILE = Path(sys.executable).parent / "updater_config.json"
_LAST_CHECK_FILE = Path(sys.executable).parent / ".last_update_check"
_PUBLIC_KEY_FILE = Path(sys.executable).parent / "update_public.pem"

# GitHub API base — kept as a constant so it is easy to audit
_GITHUB_API = "https://api.github.com"


# ── Public API ────────────────────────────────────────────────────────────────

class UpdateInfo(NamedTuple):
    """Describes an available update; returned by check_update_available()."""
    cfg: dict[str, Any]
    remote_version: str
    download_url: str
    expected_sha256: str
    sig_url: str


def check_update_available() -> UpdateInfo | None:
    """Return UpdateInfo if a newer version exists on the configured source, else None.

    Stamps the check time immediately so rapid restarts do not re-poll GitHub.
    """
    cfg = _load_config()
    if not cfg.get("enabled", False):
        return None
    interval_secs = cfg.get("interval_hours", 24) * 3600
    if not _is_check_due(interval_secs):
        return None
    _stamp_check_time()
    github_repo: str = cfg.get("github_repo", "").strip()
    manifest = _fetch_github_manifest(github_repo, cfg) if github_repo else _fetch_custom_manifest(cfg)
    if manifest is None:
        return None
    remote_version: str = manifest.get("version", "")
    current_version: str = cfg.get("current_version", "0.0.0")
    if _ver(remote_version) <= _ver(current_version):
        return None
    download_url: str = manifest.get("download_url", "")
    if not _https_only(download_url):
        log.warning("Updater: download_url must use https — skipping.")
        return None
    return UpdateInfo(
        cfg=cfg,
        remote_version=remote_version,
        download_url=download_url,
        expected_sha256=manifest.get("sha256", ""),
        sig_url=manifest.get("signature_url", ""),
    )


def download_and_verify_update(
    info: UpdateInfo,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Path:
    """Download, verify, and copy the installer to a stable temp path.

    Args:
        info: Update descriptor from check_update_available().
        progress_cb: Optional callback(received_bytes, total_bytes) for progress.

    Returns:
        Path to the verified installer ready to launch.

    Raises:
        ValueError: On checksum or signature mismatch.
        Exception: On network or I/O failure.
    """
    stable = Path(tempfile.gettempdir()) / f"usswing_update_{info.remote_version}_setup.exe"
    tmp_dir = Path(tempfile.mkdtemp())
    installer = tmp_dir / f"update_{info.remote_version}_setup.exe"
    try:
        _download(info.download_url, installer, progress_cb=progress_cb)
        if info.cfg.get("verify_checksum", True) and info.expected_sha256:
            if _sha256(installer) != info.expected_sha256:
                raise ValueError("SHA-256 checksum mismatch — installer may be corrupt")
        if info.cfg.get("verify_signature", False) and info.sig_url:
            if not _https_only(info.sig_url):
                raise ValueError("Signature URL must use HTTPS")
            sig_file = tmp_dir / "update.sig"
            _download(info.sig_url, sig_file)
            if not _verify_rsa(installer, sig_file.read_bytes()):
                raise ValueError("RSA signature invalid — installer rejected")
        shutil.copy2(installer, stable)
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except OSError:
            pass
    return stable


def check_for_updates(interactive: bool = True) -> None:
    """Headless update check — no GUI. Blocks until download completes if an update exists.

    Args:
        interactive: When True, sys.exit(0) is called after launching the installer.
    """
    info = check_update_available()
    if info is None:
        return
    try:
        stable = download_and_verify_update(info)
    except Exception as exc:
        log.warning("Updater: update failed: %s", exc)
        return
    subprocess.Popen(  # noqa: S603 — path comes from verified download
        [str(stable), "/SILENT", "/NORESTART"],
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
    )
    if interactive:
        sys.exit(0)


# ── GitHub Releases mode ──────────────────────────────────────────────────────

def _fetch_github_manifest(
    repo: str, cfg: dict[str, Any]
) -> dict[str, Any] | None:
    """
    Query the GitHub Releases API for the latest release of *repo*.

    Builds a normalised manifest dict compatible with the rest of the pipeline:
      version, download_url, sha256, signature_url

    SHA-256 is looked up from a release asset named '<installer>.sha256'
    uploaded alongside the installer.  Signature look-up follows the same
    pattern with '<installer>.sig'.
    """
    api_url = f"{_GITHUB_API}/repos/{repo}/releases/latest"
    try:
        # GitHub API requires a User-Agent header
        release = _fetch_json(api_url, user_agent="updater-stub/1.0")
    except Exception as exc:
        log.debug("Updater(GitHub): releases/latest fetch failed: %s", exc)
        return None

    tag: str = release.get("tag_name", "").lstrip("v")
    asset_pattern: str = cfg.get("github_asset_pattern", "_Setup.exe")
    assets: list[dict[str, Any]] = release.get("assets", [])

    # Find installer asset
    installer_asset = next(
        (a for a in assets if asset_pattern in a.get("name", "")),
        None,
    )
    if installer_asset is None:
        log.debug(
            "Updater(GitHub): no asset matching %r in release %s.", asset_pattern, tag
        )
        return None

    installer_name: str = installer_asset["name"]
    download_url: str = installer_asset.get("browser_download_url", "")

    # Look for a paired .sha256 file (e.g. "MyApp_1.1.0_Setup.exe.sha256")
    sha256_asset = next(
        (a for a in assets if a.get("name", "") == installer_name + ".sha256"),
        None,
    )
    sha256_value = ""
    if sha256_asset:
        try:
            raw = _fetch_raw(sha256_asset["browser_download_url"])
            # File contains "<hash>  <filename>" or just "<hash>"
            sha256_value = raw.split()[0]
        except Exception as exc:
            log.debug("Updater(GitHub): could not fetch .sha256 asset: %s", exc)

    # Look for a paired .sig file
    sig_asset = next(
        (a for a in assets if a.get("name", "") == installer_name + ".sig"),
        None,
    )
    sig_url = sig_asset.get("browser_download_url", "") if sig_asset else ""

    return {
        "version": tag,
        "download_url": download_url,
        "sha256": sha256_value,
        "signature_url": sig_url,
    }


# ── Custom manifest mode ──────────────────────────────────────────────────────

def _fetch_custom_manifest(cfg: dict[str, Any]) -> dict[str, Any] | None:
    check_url: str = cfg.get("check_url", "")
    if not _https_only(check_url):
        log.warning("Updater: check_url must use https — skipping.")
        return None
    try:
        return _fetch_json(check_url)
    except (URLError, json.JSONDecodeError, Exception) as exc:
        log.debug("Updater: manifest fetch failed: %s", exc)
        return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_config() -> dict[str, Any]:
    if not _CONFIG_FILE.exists():
        return {}
    with _CONFIG_FILE.open("r", encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[no-any-return]


def _is_check_due(interval_secs: float) -> bool:
    if not _LAST_CHECK_FILE.exists():
        return True
    try:
        return time.time() - float(_LAST_CHECK_FILE.read_text()) >= interval_secs
    except ValueError:
        return True


def _stamp_check_time() -> None:
    try:
        _LAST_CHECK_FILE.write_text(str(time.time()))
    except OSError:
        pass


def _https_only(url: str) -> bool:
    return url.startswith("https://")


def _fetch_json(
    url: str, timeout: int = 10, user_agent: str = "updater-stub/1.0"
) -> dict[str, Any]:
    ctx = ssl.create_default_context()
    req = Request(url, headers={"User-Agent": user_agent, "Accept": "application/json"})
    with urlopen(req, timeout=timeout, context=ctx) as resp:  # type: ignore[call-arg]
        return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]


def _fetch_raw(url: str, timeout: int = 10) -> str:
    """Download a small text asset (e.g. .sha256 file) and return its content."""
    ctx = ssl.create_default_context()
    req = Request(url, headers={"User-Agent": "updater-stub/1.0"})
    with urlopen(req, timeout=timeout, context=ctx) as resp:  # type: ignore[call-arg]
        return resp.read().decode("utf-8").strip()


def _download(
    url: str,
    dest: Path,
    timeout: int = 120,
    progress_cb: Callable[[int, int], None] | None = None,
) -> None:
    ctx = ssl.create_default_context()
    req = Request(url, headers={"User-Agent": "updater-stub/1.0"})
    with urlopen(req, timeout=timeout, context=ctx) as resp, dest.open("wb") as out:  # type: ignore[call-arg]
        total = int(resp.headers.get("Content-Length") or 0)
        received = 0
        for chunk in iter(lambda: resp.read(65_536), b""):
            out.write(chunk)
            received += len(chunk)
            if progress_cb is not None:
                progress_cb(received, total)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65_536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_rsa(file_path: Path, signature: bytes) -> bool:
    if not _PUBLIC_KEY_FILE.exists():
        log.warning("Updater: public key file not found at %s.", _PUBLIC_KEY_FILE)
        return False
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding, utils

        public_key = serialization.load_pem_public_key(_PUBLIC_KEY_FILE.read_bytes())
        digest_bytes = bytes.fromhex(_sha256(file_path))
        public_key.verify(  # type: ignore[union-attr]
            signature,
            digest_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            utils.Prehashed(hashes.SHA256()),
        )
        return True
    except Exception as exc:
        log.error("Updater: RSA verify error: %s", exc)
        return False


def _ver(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.strip().split("."))
    except ValueError:
        return (0,)
