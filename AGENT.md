# Agent Guidelines: `atvnotif_hass` (Home Assistant Integration)

This repository contains the Home Assistant custom integration for Android TV Notifier.

## Project Structure
*   `custom_components/atvnotif/atvnotif/`: Local nested copy of the standalone python library (`atvnotif.py`).
*   `custom_components/atvnotif/__init__.py`: Component setup, platform loading, and custom service registrations (`notify`, `open_app`, `info`, `apps`, `discover`, `qr`).
*   `custom_components/atvnotif/services.yaml`: UI service description schemas.
*   `custom_components/atvnotif/config_flow.py` & `select.py` & `notify.py`: HASS config flows, select app launcher entity, and modern notification entity.

## How to Release and Push New Changes

### 1. Update Nested Library Files (if applicable)
If the core `atvnotif` library received updates, ensure they are copied here first:
```bash
cp -rf ../atvnotif/atvnotif/*.py custom_components/atvnotif/atvnotif/
```

### 2. Bump Version in manifest.json
Update the integration version in [manifest.json](file:///run/media/liveuser/CachyOS/@home/blu/Projects/atvnotif_hass/custom_components/atvnotif/manifest.json):
```json
"version": "1.0.x"  # Bump this
```

### 3. Maintain Brand Icons
If brand assets are updated, maintain the HASS icon conventions under `custom_components/atvnotif/`:
*   `icon.png` (256x256) & `icon@2x.png` (512x512) - colored/light UI logos.
*   `dark_icon.png` (256x256) & `dark_icon@2x.png` (512x512) - white silhouette/dark UI logos.

### 4. Commit and Push to GitHub
```bash
git add .
git commit -m "Bump to version 1.0.x"
git push
```

### 5. Tag and Create GitHub Release (Required for HACS)
HACS requires a tagged GitHub Release to recognize and download the custom repository.
```bash
git tag v1.0.x
git push origin v1.0.x
gh release create v1.0.x --title "v1.0.x" --notes "Release notes summary here"
```
Do **not** skip this step, otherwise users will get errors in HACS stating the integration cannot be used.
