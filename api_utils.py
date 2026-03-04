import os
import json

# ==========================================
# ENVIRONMENT CONFIGURATION
# Set to 'PROD' to connect to AWS backend
# Set to 'DEV' to connect to local backend
# ==========================================
BIZISHIP_ENV = 'PROD'

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
