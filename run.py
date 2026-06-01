import os
from app import create_app

config_name = os.environ.get('FLASK_ENV', 'dev')
app = create_app(config_name)

if __name__ == '__main__':
    # Ejecutar en puerto 5000 por defecto
    app.run(host='0.0.0.0', port=5000)
