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
    # --- ★★★ ここからが今回の修正箇所です ★★★ ---
    # instance_folder引数をなくし、instance_relative_config=True を使用します
    app = Flask(__name__, instance_relative_config=True)
    
    # instanceフォルダのパスを明示的に設定
    app.instance_path = os.path.join(os.path.dirname(app.root_path), 'instance')
    # --- ★★★ 修正箇所ここまで ★★★ ---
    
    # デフォルトの設定
    app.config.from_mapping(
        SECRET_KEY='dev',
        SQLALCHEMY_DATABASE_URI=f"sqlite:///{os.path.join(app.instance_path, 'todo.db')}",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    if test_config is not None:
        # WSGIファイルなどから渡された本番用の設定で上書き
        app.config.from_mapping(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models
    from . import routes
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