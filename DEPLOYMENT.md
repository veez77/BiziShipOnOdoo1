# BiziShip Odoo App Deployment Guide

This guide outlines the steps required to install and configure the BiziShip Odoo module on a customer server (Odoo v17).

## 1. Prerequisites

*   **Odoo Version**: v17.0 (Community or Enterprise).
*   **Access**: Terminal/SSH access to the Odoo server.
*   **Dependencies**: The following Python libraries must be installed on the Odoo server's Python environment:
    *   `requests`
    *   `PyPDF2`

## 2. Installation Steps

### Step 1: Download the Module
Navigate to your Odoo custom addons directory and clone the repository:
```bash
git clone https://github.com/veez77/BiziShipOnOdoo1.git BiziShip
```

### Step 2: Install Python Requirements
While in the `BiziShip` directory, run:
```bash
pip3 install -r requirements.txt
```

### Step 3: Configure API Keys
The module requires a `secrets.json` file in its root directory to communicate with the BiziShip backend. This file is **not** included in the repository for security.

Create a file named `secrets.json` in the `BiziShip` folder with the following content:
```json
{
  "EMAIL2QUOTE_API_KEY": "YOUR_BIZISHIP_API_KEY_HERE"
}
```
*Note: Replace `YOUR_BIZISHIP_API_KEY_HERE` with the actual key provided by BiziShip.*

### Step 4: Update Odoo Configuration
Ensure the directory containing the `BiziShip` module is included in your Odoo configuration file (`odoo.conf`):
```ini
addons_path = /path/to/standard/addons, /path/to/custom_addons
```

### Step 5: Restart Odoo
Restart the Odoo service to recognize the new module:
```bash
sudo service odoo restart
```
*(Command may vary based on your OS/Setup).*

## 3. Activation in Odoo UI

1.  Log into Odoo as an **Administrator**.
2.  Enable **Developer Mode** (Settings -> Scroll to bottom -> Activate Developer Mode).
3.  Navigate to the **Apps** menu.
4.  Click **"Update Apps List"** in the top menu.
5.  Search for **"BiziShip"**.
6.  Click **"Activate"**.

## 4. Post-Install Setup

*   **User Email**: Ensure that all users who will fetch quotes have an email address set in their Odoo User Profile.
*   **Company Profile**: Ensure your company address and Zip code are correctly configured in Odoo Settings.

---
*Generated: 2026-03-15*
