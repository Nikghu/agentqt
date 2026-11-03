Publish a new GitHub release for the USSwing installer.

Usage: /project:push-updates [<version> | major | minor | patch]
Does the whole release: bumps the version (if needed), builds the app with PyInstaller,
builds the installer with Inno Setup, creates a GitHub release tag, uploads the .exe and
.sha256 assets, and patches updater_manifest.json with the live download URL so the in-app
updater can resolve it. Finally deletes all older GitHub releases so only the latest one
is available. Running this command is the user's approval for the bump PR merge, tag and release.

Pre-conditions (verify before proceeding — abort with a clear message if any fail):
  - `gh` CLI is authenticated  →  run: gh auth status
  - On `main`, working tree clean, up to date  →  git status --short; git pull
  - Inno Setup exists at `installer.inno_setup_path` in `us_swing/usswing_installer.yaml`
  - Project venv has PyInstaller  →  F:\USMarket_Backtesting\.venv\Scripts\python.exe -c "import PyInstaller"

$ARGUMENTS

Status reporting (mandatory — the user must always know where the release stands):
  - Before each step, write one short text line to the user: `[<n>/9] <step name> …`
    (steps: 1 Checks · 2 Version · 3 PyInstaller · 4 Installer · 5 Artifacts · 6 Tag ·
    7 Release · 8 Manifest · 9 Old releases). After it, write `✓ <result>` with the key fact.
  - For long steps (PyInstaller, Installer) say how long it may take before starting, run in the
    background, and report the elapsed time when done.
  - On any failure: stop and write
    `✗ Failed at step <n> (<name>): <plain reason>` + `Done so far: …` + `Not done: …` +
    `What to do: …` — and the last 20 lines of tool output. Never end silently.
  - Close with the step-10 summary, whether the release succeeded or not.

Steps:

1. Checks
   - Run the pre-conditions above. ✓ line: `gh OK · main clean · Inno Setup OK · PyInstaller <ver>`.

2. Version — bump if needed
   The single source of truth is `__version__` in `us_swing/src/us_swing/__init__.py`;
   `app.version` in `us_swing/usswing_installer.yaml` is kept equal to it.
   - CURRENT = `__version__`; LAST = newest tag: `git tag --sort=-v:refname | head -1` (strip `v`).
   - Pick VERSION:
     - Argument is an explicit version (e.g. `1.9.1`) → use it (must be > LAST).
     - Argument is `major` / `minor` / `patch` → bump LAST by that part.
     - No argument and CURRENT > LAST (already bumped) → VERSION = CURRENT, no bump.
     - No argument and CURRENT == LAST → look at `git log v<LAST>..HEAD --oneline`:
       any `feat` commit → minor bump, else patch bump.
   - If the commit list since LAST is empty, abort with "No changes since v<LAST> — nothing to release."
   - If tag v<VERSION> already exists (`git tag -l "v<VERSION>"`), abort with
     "Tag v<VERSION> already exists — did you already publish this version?"
   - Tell the user: `Last release v<LAST> · this release v<VERSION> · <reason>` and the number of
     commits since LAST (`<n> commits: <x> feat, <y> fix, <z> other`).
   - If VERSION != CURRENT:
     - Branch `chore/bump-<VERSION>`; set `__version__ = "<VERSION>"` and `app.version: <VERSION>`
       (edit only those two lines).
     - Commit `chore: bump version to <VERSION>` (with the Co-Authored-By line), push,
       `gh pr create --base main` (body lists the commits since LAST, ends with the Claude Code line),
       `gh pr merge --merge --delete-branch`, then `git checkout main; git pull`.
     - ✓ line: `Version updated <CURRENT> → <VERSION> · PR #<n> merged`.
   - Else ✓ line: `Version already <VERSION> — no bump needed`.
   - Verify both files now read VERSION; the tag in step 6 must point at `main` after this step.

3–4. PyInstaller, then Installer
   Tell the user first: `Building v<VERSION> — PyInstaller then Inno Setup, about 5–10 minutes`.
   Run from `F:\USMarket_Backtesting\us_swing` with the project venv Python (PowerShell,
   run_in_background, wait for the notification):
   ```powershell
   $env:PYTHONPATH = "F:\USMarket_Backtesting"
   F:\USMarket_Backtesting\.venv\Scripts\python.exe -c "import time; from pathlib import Path; from installer.config import load_config; from installer.builder import package, build; p = Path('usswing_installer.yaml').resolve(); c = load_config(p); assert c.app.version == '<VERSION>', c.app.version; t = time.time(); d = package(c.package, c.app.name, c.app.icon, log=lambda s: None, cwd=p.parent); print('PACKAGE_OK', d, round(time.time() - t)); t = time.time(); print('INSTALLER_OK', build(c, log=lambda s: None, config_dir=p.parent), round(time.time() - t))"
   ```
   - This is the same as the installer GUI: open the YAML → PyInstaller → Build Installer.
   - ✓ step 3 from the `PACKAGE_OK` line: `App packaged → <dist folder> (<s> s)`.
   - ✓ step 4 from the `INSTALLER_OK` line: `Installer built → USSwing_<VERSION>_Setup.exe, <size> MB (<s> s)`.
   - No `PACKAGE_OK` → failed at step 3; `PACKAGE_OK` but no `INSTALLER_OK` → failed at step 4.
     Do not tag or release.

5. Artifacts
   - Read REPO = update.github_repo from `us_swing/usswing_installer.yaml`.
   - EXE  = installer/installer_output/USSwing_<VERSION>_Setup.exe
   - SHA_FILE = installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256
   - MANIFEST = installer/installer_output/updater_manifest.json
   - Verify EXE exists and was written in this run (newer than the build start). If not: abort.
   - Read SHA256 and version from MANIFEST. If sha256 is empty or the manifest version is not VERSION: abort
     with "updater_manifest.json does not match v<VERSION> — rebuild the installer."
   - If SHA_FILE does not exist:
     Run PowerShell: `"<sha256_value>  USSwing_<VERSION>_Setup.exe" | Out-File -Encoding ascii installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256`
   - ✓ line: `Installer + SHA-256 ready (<first 12 chars of sha256>…)`.

6. Create and push the git tag
   Run:
     git tag v<VERSION>
     git push origin v<VERSION>
   - ✓ line: `Tag v<VERSION> pushed`.

7. Create GitHub release and upload assets
   Run:
     gh release create v<VERSION> \
       "installer/installer_output/USSwing_<VERSION>_Setup.exe" \
       "installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256" \
       --title "USSwing v<VERSION>" \
       --notes "USSwing v<VERSION>" \
       --repo <REPO>
   - ✓ line: `Release created: <URL>`.

8. Resolve the download URL and patch updater_manifest.json
   - Run: gh release view v<VERSION> --repo <REPO> --json assets --jq '.assets[] | select(.name | contains("_Setup.exe")) | .url'
     (Note: `gh` returns the browser_download_url for assets — use `--jq '.assets[] | select(.name | endswith("_Setup.exe")) | .browserDownloadUrl'` if the above field is empty)
   - DOWNLOAD_URL = the resolved URL (must start with https://github.com/...)
   - Read MANIFEST JSON, set:
       manifest.download_url = DOWNLOAD_URL
       manifest.release_notes = "USSwing v<VERSION>"
   - Write the updated JSON back to MANIFEST (pretty-print, 2-space indent).
   - ✓ line: `Manifest patched with download URL`.

9. Delete old GitHub releases
   Only run this after step 8 succeeds, so the new release is live first.
   - Run: gh release list --repo <REPO> --limit 100 --json tagName --jq '.[].tagName'
   - For every tag that is not v<VERSION>, run:
       gh release delete <TAG> --repo <REPO> --yes
   - Keep the git tags — delete only the releases and their assets.
   - ✓ line: `Old releases deleted: <TAG list>` (or `No old releases to delete`).

10. Summary
   Print a summary table (on failure, fill what is known and mark the rest `not done`):
   ```
   Status:        SUCCESS | FAILED at step <n> (<name>)
   Version:       v<LAST> → v<VERSION> (<bumped via PR #n | already set>)
   App package:   <dist folder> (<s> s)
   Installer:     USSwing_<VERSION>_Setup.exe, <size> MB (<s> s)
   SHA-256:       <sha256_value>
   Release:       https://github.com/<REPO>/releases/tag/v<VERSION>
   Download URL:  <DOWNLOAD_URL>
   Updater mode:  GitHub Releases (active)
   Old releases:  <deleted TAG list or "none">
   ```
   On success print: "Done — users will receive this update within 24 hours of next app launch."
