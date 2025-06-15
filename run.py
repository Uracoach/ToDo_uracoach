# run.py
from flask_todo_app import create_app

# アプリケーションファクトリからアプリケーションインスタンスを作成
app = create_app()

if __name__ == "__main__":
    # debug=Trueでデバッグモードを有効にする
    # host='0.0.0.0'は、外部からのアクセスも許可する場合に指定
    app.run(debug=True)