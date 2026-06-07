# atvnotif-hass

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/github/license/atvnotif/atvnotif-hass)](https://github.com/atvnotif/atvnotif-hass/blob/main/LICENSE)

A Home Assistant custom component integration for sending encrypted notifications to **Android TV Notifier** (`com.smrtprjcts.atvnotif`) using the standalone `atvnotif.py` library.

## Features
*   **Automatic Discovery**: Automatically detects compatible Android TV devices on your local network using mDNS (Zeroconf) and pre-fills pairing details.
*   **QR Code Pairing**: Configure easily by providing a URL to a photo of the TV's pairing QR code.
*   **Plaintext Fallback**: Supports plaintext responses from the TV's `/info` and `/open` endpoints.

## Installation

### Method 1: HACS (Recommended)
1. Make sure you have [HACS](https://hacs.xyz/) installed.
2. Go to **HACS** -> **Integrations**.
3. Click the top-right menu (three dots) and select **Custom repositories**.
4. Add the following repository URL:
   ```
   https://github.com/atvnotif/atvnotif-hass
   ```
5. Select **Integration** as the Category and click **Add**.
6. Find **Android TV Notifier** in the catalog, click **Download**, and restart Home Assistant.

### Method 2: Manual
1. Download the latest release code.
2. Copy the `custom_components/atvnotif` directory to your Home Assistant `<config_dir>/custom_components/` folder.
3. Restart Home Assistant.

## Configuration
Once installed and restarted, add the integration via the Home Assistant UI:
1. Go to **Settings** -> **Devices & Services** -> **Add Integration**.
2. Search for **Android TV Notifier**.
3. Choose one of the setup methods:
   *   **Discovered**: Select the discovered device, confirm, and HASS will automatically resolve the pairing code from network records.
   *   **QR URL**: Provide a URL of the TV pairing QR code image (e.g. hosted on Imgur) to auto-fill the configuration.
   *   **Manual**: Input the IP Address, Port (`7878`), and the TV pairing key (UUID) manually.
