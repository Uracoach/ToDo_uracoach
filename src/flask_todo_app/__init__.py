import os
import hashlib
import json
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def from_json(value):
    return json.loads(value)

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)

    if 'INSTANCE_PATH' in os.environ:
        app.instance_path = os.environ['INSTANCE_PATH']
    elif not os.path.isabs(app.instance_path):
        app.instance_path = os.path.join(app.root_path, '..', 'instance')

    db_path = os.path.join(app.instance_path, 'todo.db')
    
    app.config.from_mapping(
        SECRET_KEY=os.environ.get('SECRET_KEY', 'dev'),
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{db_path}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        ADMIN_PASSWORD=os.environ.get('ADMIN_PASSWORD', 'adminpass')
    )

    if test_config is not None:
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    migrate.init_app(app, db)

    # Jinja2にカスタムフィルターを登録
    app.jinja_env.filters['fromjson'] = from_json

    from . import models, routes
    app.register_blueprint(routes.main.bp)
    app.register_blueprint(routes.admin.bp)
    app.register_blueprint(routes.timer.bp)
    app.register_blueprint(routes.ai_test.bp)

    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return app