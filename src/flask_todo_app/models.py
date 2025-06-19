from . import db
from datetime import datetime

# 生徒とミッションの中間テーブル
mission_completions = db.Table('mission_completions',
    db.Column('student_name', db.String(80), db.ForeignKey('student.name'), primary_key=True),
    db.Column('mission_id', db.Integer, db.ForeignKey('mission.id'), primary_key=True)
)

class Student(db.Model):
    name = db.Column(db.String(80), primary_key=True)
    password = db.Column(db.String(200), nullable=False)
    todos = db.relationship('Todo', backref='author', lazy=True, cascade="all, delete-orphan")
    missions = db.relationship('Mission', backref='author', lazy=True, cascade="all, delete-orphan")
    completed_missions = db.relationship('Mission', secondary=mission_completions, lazy='subquery',
        backref=db.backref('completed_by', lazy=True))
    ai_tests = db.relationship('AiTest', backref='author', lazy=True, cascade="all, delete-orphan")
    ai_answers = db.relationship('AiAnswer', backref='author', lazy=True, cascade="all, delete-orphan")

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

class AiTest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    test_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.relationship('AiQuestion', backref='test', lazy=True, cascade="all, delete-orphan")
    is_completed = db.Column(db.Boolean, default=False)
    score = db.Column(db.Integer, nullable=True)

class AiQuestion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    test_id = db.Column(db.Integer, db.ForeignKey('ai_test.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    options = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.String(10), nullable=False)
    answers = db.relationship('AiAnswer', backref='question', lazy=True, cascade="all, delete-orphan")

class AiAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('ai_question.id'), nullable=False)
    student_name = db.Column(db.String(80), db.ForeignKey('student.name'), nullable=False)
    selected_option = db.Column(db.String(10))
    is_correct = db.Column(db.Boolean)