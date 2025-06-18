from . import db
from datetime import date

mission_completions = db.Table('mission_completions',
    db.Column('student_name', db.String(80), db.ForeignKey('student.name'), primary_key=True),
    db.Column('mission_id', db.Integer, db.ForeignKey('mission.id'), primary_key=True)
)

class Student(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(200), nullable=False)
    todos = db.relationship('Todo', backref='author', lazy=True, cascade="all, delete-orphan")
    missions = db.relationship(
        'Mission', 
        foreign_keys='Mission.student_name', 
        backref='author', 
        lazy=True, 
        cascade="all, delete-orphan"
    )
    completed_missions = db.relationship('Mission', secondary=mission_completions, lazy='subquery',
        backref=db.backref('completed_by', lazy=True))
    
    # --- ★★★ ここからが今回の修正箇所です ★★★ ---
    # 'foreign_keys'を指定して、どの列でTestと紐づくかを明記します
    tests = db.relationship(
        'Test', 
        foreign_keys='Test.student_name', 
        backref='student_tester', 
        lazy=True, 
        cascade="all, delete-orphan"
    )
    answers = db.relationship(
        'Answer', 
        foreign_keys='Answer.student_name',
        backref='student_answerer', 
        lazy=True, 
        cascade="all, delete-orphan"
    )
    # --- ★★★ 修正箇所ここまで ★★★ ---


class Todo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    date = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(50), nullable=False)
    material = db.Column(db.String(200), default='')
    start_page = db.Column(db.Integer, default=0)
    end_page = db.Column(db.Integer, default=0)
    target_hour = db.Column(db.Integer, default=0)
    target_min = db.Column(db.Integer, default=0)
    actual_hour = db.Column(db.Integer, default=0)
    actual_min = db.Column(db.Integer, default=0)
    completed = db.Column(db.Boolean, default=False)
    break_seconds = db.Column(db.Integer, default=0)

class Mission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    week_start_date = db.Column(db.String(10), nullable=False)
    description = db.Column(db.Text, nullable=False)
    completed = db.Column(db.Boolean, default=False)

class Test(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=True)
    test_date = db.Column(db.String(10), default=lambda: date.today().strftime('%Y-%m-%d'))
    score = db.Column(db.Integer)
    test_type = db.Column(db.String(20), default='daily', nullable=False)
    title = db.Column(db.String(100))
    questions = db.relationship('Question', backref='test', lazy=True, cascade="all, delete-orphan")

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    option_c = db.Column(db.String(200), nullable=False)
    option_d = db.Column(db.String(200), nullable=False)
    correct_answer = db.Column(db.String(1), nullable=False)
    answers = db.relationship('Answer', backref='question', lazy=True, cascade="all, delete-orphan")

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=False)