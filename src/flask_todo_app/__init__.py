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
    app = Flask(__name__, instance_folder=os.path.join(os.getcwd(), 'instance'))
    
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
        # instanceフォルダのパスが絶対パスか確認し、なければ作成
        if not os.path.isabs(app.instance_path):
             app.instance_path = os.path.join(app.root_path, app.instance_path)
        os.makedirs(app.instance_path)
    except OSError:
        pass
    
    db.init_app(app)
    migrate.init_app(app, db)

    from . import models
    from . import routes
    app.register_blueprint(routes.main.bp)
    app.register_blueprint(routes.admin.bp)
    # --- ★★★ 不足していたこの行を追加しました ★★★ ---
    app.register_blueprint(routes.timer.bp)

    @app.after_request
    def add_header(response):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
        return response

    return app