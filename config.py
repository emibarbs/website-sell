import os
from dotenv import load_dotenv

load_dotenv()  # Carga las variables de .env al entorno ANTES de leerlas

def str_to_bool(value, default=False):
    """Auxiliar para convertir strings de variables de entorno a booleanos."""
    if value is None:
        return default
    return str(value).strip().lower() in ('true', '1', 't', 'yes', 'on')

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'digital-agency-secret-key'
    
    # Manejo de URL de base de datos para PostgreSQL en Railway
    raw_db_url = os.environ.get('DATABASE_URL') or 'sqlite:///site.db'
    if raw_db_url and raw_db_url.startswith("postgres://"):
        raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)
        
    SQLALCHEMY_DATABASE_URI = raw_db_url
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Seguridad de Cookies y Sesión (Necesario para HTTPS en Railway)
    SESSION_COOKIE_SECURE = str_to_bool(os.environ.get('SESSION_COOKIE_SECURE'), default=True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = str_to_bool(os.environ.get('REMEMBER_COOKIE_SECURE'), default=True)
    REMEMBER_COOKIE_HTTPONLY = True

    # Stripe
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Correos que se promueven automáticamente a rol Admin
    ADMIN_EMAILS = {
        e.strip().lower()
        for e in os.environ.get('ADMIN_EMAILS', '').split(',')
        if e.strip()
    }

    # Google OAuth
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID') or 'mock_google_id'
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET') or 'mock_google_secret'

    # Correo (Flask-Mail)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = str_to_bool(os.environ.get('MAIL_USE_TLS'), default=True)
    MAIL_USE_SSL = str_to_bool(os.environ.get('MAIL_USE_SSL'), default=False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
