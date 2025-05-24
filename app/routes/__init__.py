from flask import Blueprint

from .config import bp as config_bp
from .sales import bp as sales_bp
from .refunds import bp as refunds_bp
from .reversals import bp as reversals_bp


def init_app(app):
    app.register_blueprint(config_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(refunds_bp)
    app.register_blueprint(reversals_bp)
