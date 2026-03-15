import os
import json

# ==========================================
# ENVIRONMENT CONFIGURATION
# Set to 'PROD' to connect to AWS backend
# Set to 'DEV' to connect to local backend
# ==========================================
BIZISHIP_ENV = 'PROD'
BIZISHIP_MODULE_VERSION = '2.0.0'
BIZISHIP_APP_NAME = 'BiziShip Odoo'

# Unit Conversion Constants
KG_TO_LBS = 2.20462
CM_TO_IN = 0.393701
M_TO_IN = 39.3701
FT_TO_IN = 12.0

def convert_to_lbs(weight, unit):
    """Converts weight to lbs."""
    if not weight:
        return 0.0
    if unit == 'kg':
        return weight * KG_TO_LBS
    return weight

def convert_to_inches(dim, unit):
    """Converts dimension to inches."""
    if not dim:
        return 0.0
    if unit == 'cm':
        return dim * CM_TO_IN
    elif unit == 'm':
        return dim * M_TO_IN
    elif unit == 'ft':
        return dim * FT_TO_IN
    return dim

def get_secrets():
    secrets_path = os.path.join(os.path.dirname(__file__), 'secrets.json')
    if os.path.exists(secrets_path):
        with open(secrets_path, 'r') as f:
            return json.load(f)
    return {}

def get_biziship_api_url():
    """Returns the API URL based on the current environment."""
    if BIZISHIP_ENV == 'PROD':
        return 'https://api.biziship.ai'
        
    # Development URL
    secrets = get_secrets()
    return secrets.get("EMAIL2QUOTE_API_URL", "http://localhost:8000")

def get_email2quote_api_key():
    return get_secrets().get("EMAIL2QUOTE_API_KEY", "")

def get_groq_api_key():
    return get_secrets().get("GROQ_API_KEY", "")
