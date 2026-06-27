import os
from flask import Flask
from flask_login import LoginManager
from flask_bcrypt import Bcrypt
from flask_wtf import CSRFProtect
from mongoengine import connect

# Inicializar extensiones
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'
login_manager.login_message_category = 'warning'

bcrypt = Bcrypt()
csrf = CSRFProtect()

def create_app(config_name='dev'):
    app = Flask(__name__)
    
    # Cargar configuración
    from config import config_by_name
    app.config.from_object(config_by_name[config_name])
    
    # Inicializar base de datos MongoDB
    db_settings = app.config['MONGODB_SETTINGS']
    connect(
        db=db_settings['db'],
        host=db_settings['host']
    )
    
    # Inicializar extensiones con la app
    login_manager.init_app(app)
    bcrypt.init_app(app)
    csrf.init_app(app)

    # Detrás del reverse proxy (Caddy) en producción: confiar en los headers
    # X-Forwarded-* para que Flask conozca el esquema/host reales (HTTPS).
    if config_name == 'prod':
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    
    # Asegurar que existe la carpeta de subida de archivos
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Registro de Blueprints
    from app.blueprints.public import public_bp
    from app.blueprints.auth import auth_bp
    from app.blueprints.superadmin import superadmin_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.planning import planning_bp
    from app.blueprints.formulation import formulation_bp
    from app.blueprints.api import api_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(planning_bp, url_prefix='/planning')
    app.register_blueprint(formulation_bp, url_prefix='/formulation')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Context processor para hacer accesible el año actual en templates
    @app.context_processor
    def inject_now():
        from datetime import datetime
        return {'current_year': datetime.utcnow().year}
        
    return app

# User loader para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    from app.models.user import User
    try:
        return User.objects(id=user_id, is_active=True).first()
    except Exception:
        return None
