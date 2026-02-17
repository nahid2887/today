"""Read SECRET_KEY from file to avoid shell variable expansion issues"""
import os

def get_secret_key() -> str:
    """Get JWT secret key from file first, then environment, then default"""
    # Try to read from mounted secret file
    secret_file = "/app/secret_key.txt"
    if os.path.isfile(secret_file):
        with open(secret_file, 'r') as f:
            key = f.read().strip()
            if key:
                return key
    
    # Fall back to environment variable
    key = os.getenv("JWT_SECRET_KEY")
    if key:
        return key
    
    # Final fallback
    return "your-secret-key-change-in-production-2026"

# Set it in os.environ for use by FastAPI and other libraries
os.environ['JWT_SECRET_KEY'] = get_secret_key()
