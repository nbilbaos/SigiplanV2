import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'sigiplan-dev-secret-key-18239487')
    MONGODB_SETTINGS = {
        'db': os.environ.get('MONGODB_DB', 'sigiplan'),
        'host': os.environ.get('MONGODB_HOST', 'mongodb://localhost:27017/sigiplan')
    }
    # Upload folder
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'app', 'static', 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB limit for uploads

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    MONGODB_SETTINGS = {
        'db': 'sigiplan_test',
        'host': 'mongodb://localhost:27017/sigiplan_test'
    }

class ProductionConfig(Config):
    DEBUG = False
    # In production, secret key and host must be loaded from env
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Endurecimiento de la sesión. SESSION_COOKIE_SECURE va a True por defecto
    # (HTTPS). Para staging por IP/HTTP plano sin dominio, poner SECURE_COOKIES=false
    # en el .env para poder iniciar sesión; volver a true al quedar tras HTTPS.
    SESSION_COOKIE_SECURE = os.environ.get('SECURE_COOKIES', 'true').strip().lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True     # inaccesible desde JS
    SESSION_COOKIE_SAMESITE = 'Lax'
    PREFERRED_URL_SCHEME = 'https'

config_by_name = {
    'dev': DevelopmentConfig,
    'test': TestingConfig,
    'prod': ProductionConfig
}
