from . import db

class Student(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(200), nullable=False)
    # 生徒が削除されたら、関連するToDoもすべて削除されるように設定
    todos = db.relationship('Todo', backref='author', lazy=True, cascade="all, delete-orphan")

class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    material = db.Column(db.String(200))
    start_page = db.Column(db.Integer)
    end_page = db.Column(db.Integer)
    target_hour = db.Column(db.Integer, default=0)
    target_min = db.Column(db.Integer, default=0)
    actual_hour = db.Column(db.Integer, default=0)
    actual_min = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)