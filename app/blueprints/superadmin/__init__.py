from flask import Blueprint

superadmin_bp = Blueprint('superadmin', __name__)

from app.blueprints.superadmin import routes
