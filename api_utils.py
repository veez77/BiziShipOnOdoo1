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
BIZISHIP_FALLBACK_KEY = '116b2056ca09c1006119ec548cff60a66a1182b579b86f0f6168ec44e74a1409=Odoo'

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
        return 'https://6k90hxqjwe.execute-api.us-east-1.amazonaws.com/dev'
        
    # Development URL
    secrets = get_secrets()
    return secrets.get("EMAIL2QUOTE_API_URL", "https://6k90hxqjwe.execute-api.us-east-1.amazonaws.com/dev")

def get_email2quote_api_key():
    return get_secrets().get("EMAIL2QUOTE_API_KEY", "")

def get_groq_api_key():
    return get_secrets().get("GROQ_API_KEY", "")

def get_erp_api_key(env=None):
    """
    Returns the ERP API Key securely with the following priority:
    1. Odoo System Parameters (ir.config_parameter: biziship.erp_api_key)
    2. Odoo Config File (odoo.conf: biziship_erp_api_key)
    3. OS Environment Variables (BIZISHIP_ERP_API_KEY)
    4. Local secrets.json fallback (development only)
    5. Hardcoded generic fallback key
    """
    key = None
    
    # 1. System Parameters (Best for UI management)
    if env:
        key = env['ir.config_parameter'].sudo().get_param('biziship.erp_api_key')
    
    # 2. Odoo Config File (odoo.conf)
    if not key:
        try:
            from odoo.tools import config
            key = config.get('biziship_erp_api_key')
        except ImportError:
            pass
            
    # 3. Environment Variables (Best for Docker/Cloud deployments)
    if not key:
        key = os.environ.get('BIZISHIP_ERP_API_KEY')
    
    # 4. Local secrets.json Fallback
    if not key:
        secrets = get_secrets()
        key = secrets.get("BIZISHIP_ERP_GATEWAY_KEY") or secrets.get("EMAIL2QUOTE_API_KEY")
        
    return key or BIZISHIP_FALLBACK_KEY
