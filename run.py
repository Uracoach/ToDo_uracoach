from flask_todo_app import create_app
from dotenv import load_dotenv

# .flaskenvファイルを読み込む
load_dotenv()

app = create_app()

if __name__ == "__main__":
    # debug=Trueでデバッグモードを有効にする
    app.run(debug=True)