from flask import Blueprint

planning_bp = Blueprint('planning', __name__)

from app.blueprints.planning import routes
