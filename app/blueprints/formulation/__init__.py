from flask import Blueprint

formulation_bp = Blueprint('formulation', __name__)

from app.blueprints.formulation import routes
