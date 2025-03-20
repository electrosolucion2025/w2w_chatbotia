import os
import sys
from dotenv import load_dotenv

def check_env_vars():
    load_dotenv()
    
    required_vars = [
        'SECRET_KEY',
        'DB_NAME', 
        'DB_USER', 
        'DB_PASSWORD',
        'OPENAI_API_KEY',
    ]
    
    optional_vars = [
        'WHATSAPP_API_TOKEN',
        'WHATSAPP_PHONE_NUMBER_ID',
        'WHATSAPP_VERIFY_TOKEN',
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        print("Error: The following required environment variables are missing:")
        for var in missing:
            print(f"  - {var}")
        sys.exit(1)
    
    warnings = []
    for var in optional_vars:
        if not os.getenv(var):
            warnings.append(var)
    
    if warnings:
        print("Warning: The following optional environment variables are not set:")
        for var in warnings:
            print(f"  - {var}")
    
    print("Environment check completed successfully!")

if __name__ == "__main__":
    check_env_vars()