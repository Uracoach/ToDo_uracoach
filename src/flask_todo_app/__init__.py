import os
import hashlib
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    instance_path = os.environ.get('RENDER_INSTANCE_DIR', app.instance_path)
    if not os.path.isabs(instance_path):
        instance_path = os.path.join(app.root_path, instance_path)
    
    db_path = os.path.join(instance_path, 'todo.db')

    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models, routes
    app.register_blueprint(routes.main.bp)
    app.register_blueprint(routes.admin.bp)
    app.register_blueprint(routes.timer.bp)

    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return app