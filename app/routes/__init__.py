from .config import bp as config_bp
from .sales import bp as sales_bp
from .refunds import bp as refunds_bp
from .reversals import bp as reversals_bp
from .postbacks import bp as postbacks_bp
from app.routes.user import create_user_blueprint


def init_app(app):
    app.register_blueprint(config_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(refunds_bp)
    app.register_blueprint(reversals_bp)
    app.register_blueprint(postbacks_bp)
    if "user" not in app.blueprints:
        app.register_blueprint(create_user_blueprint(), url_prefix="/api/user")
