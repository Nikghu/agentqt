Publish a new GitHub release for the USSwing installer.

Usage: /project:push-updates
Run AFTER building the installer via the installer GUI. Creates a GitHub release tag,
uploads the .exe and .sha256 assets, and patches updater_manifest.json with the live
download URL so the in-app updater can resolve it.

Pre-conditions (verify before proceeding — abort with a clear message if any fail):
  - `gh` CLI is authenticated  →  run: gh auth status
  - Installer EXE exists       →  installer/installer_output/USSwing_<version>_Setup.exe
  - updater_manifest.json has a non-empty sha256 field
  - No existing git tag v<version>  →  run: git tag -l "v<version>"

$ARGUMENTS

Steps:

1. Read version and repo from config
   - Read `us_swing/usswing_installer.yaml`
   - Extract: VERSION = app.version, REPO = update.github_repo
   - Print: `Publishing USSwing v<VERSION> → github.com/<REPO>`

2. Locate installer artifacts
   - EXE  = installer/installer_output/USSwing_<VERSION>_Setup.exe
   - SHA_FILE = installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256
   - MANIFEST = installer/installer_output/updater_manifest.json
   - Verify EXE exists. If not: abort with "Installer EXE not found — build it in the installer GUI first."
   - Read SHA256 value from MANIFEST (field: sha256). If empty: abort with "SHA-256 missing in updater_manifest.json — rebuild the installer to regenerate it."

3. Write .sha256 asset file (if missing)
   The GitHub updater stub fetches a paired `<installer>.sha256` file from the release assets.
   - If SHA_FILE does not exist:
     Run PowerShell: `"<sha256_value>  USSwing_<VERSION>_Setup.exe" | Out-File -Encoding ascii installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256`
   - Print: `SHA-256 file ready: USSwing_<VERSION>_Setup.exe.sha256`

4. Create and push the git tag
   Run:
     git tag v<VERSION>
     git push origin v<VERSION>
   - If tag already exists locally: abort with "Tag v<VERSION> already exists — did you already publish this version?"
   - Print: `Tag v<VERSION> pushed`

5. Create GitHub release and upload assets
   Run:
     gh release create v<VERSION> \
       "installer/installer_output/USSwing_<VERSION>_Setup.exe" \
       "installer/installer_output/USSwing_<VERSION>_Setup.exe.sha256" \
       --title "USSwing v<VERSION>" \
       --notes "USSwing v<VERSION>" \
       --repo <REPO>
   - Capture the release URL printed by gh.
   - Print: `Release created: <URL>`

6. Resolve the download URL and patch updater_manifest.json
   - Run: gh release view v<VERSION> --repo <REPO> --json assets --jq '.assets[] | select(.name | contains("_Setup.exe")) | .url'
     (Note: `gh` returns the browser_download_url for assets — use `--jq '.assets[] | select(.name | endswith("_Setup.exe")) | .browserDownloadUrl'` if the above field is empty)
   - DOWNLOAD_URL = the resolved URL (must start with https://github.com/...)
   - Read MANIFEST JSON, set:
       manifest.download_url = DOWNLOAD_URL
       manifest.release_notes = "USSwing v<VERSION>"
   - Write the updated JSON back to MANIFEST (pretty-print, 2-space indent).
   - Print: `Manifest patched with download URL`

7. Confirm
   Print a summary table:
   ```
   Release:       v<VERSION>
   GitHub:        https://github.com/<REPO>/releases/tag/v<VERSION>
   Installer:     USSwing_<VERSION>_Setup.exe
   SHA-256:       <sha256_value>
   Download URL:  <DOWNLOAD_URL>
   Updater mode:  GitHub Releases (active)
   ```
   Print: "Done — users will receive this update within 24 hours of next app launch."
