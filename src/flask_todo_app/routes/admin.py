import os
from flask import Blueprint, flash, render_template, request, redirect, url_for, session
from datetime import datetime, date, timedelta
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from .. import db, hash_password
from ..models import Student, Todo

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin' in session:
        return redirect(url_for('admin.dashboard'))
    if request.method == 'POST':
        admin_password = os.environ.get('ADMIN_PASSWORD', 'adminpass')
        if request.form['password'] == admin_password:
            session['admin'] = True
            session.permanent = False
            return redirect(url_for('admin.dashboard'))
        else:
            flash('管理者パスワードが違います', 'error')
    return render_template('admin_login.html')

@bp.route('/')
def dashboard():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    
    student_stats = db.session.query(
        Student.name,
        func.sum(case(
            ((Todo.date >= start_of_week.strftime('%Y-%m-%d')) & (Todo.completed == True), Todo.actual_hour * 60 + Todo.actual_min),
            else_=0
        )).label('week_total'),
        func.sum(case(
            (Todo.completed == True, Todo.actual_hour * 60 + Todo.actual_min),
            else_=0
        )).label('all_time_total')
    ).outerjoin(Todo, Student.name == Todo.student_name) \
     .group_by(Student.name) \
     .order_by(db.desc('week_total')).all()

    inactive_students = [s.name for s in student_stats if s.week_total == 0]
    
    return render_template('admin.html', student_stats=student_stats, inactive_students=inactive_students)

@bp.route('/add_student', methods=['POST'])
def add_student():
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    
    new_student_name = request.form['new_student']
    new_password = request.form['new_password']
    
    existing_user = Student.query.get(new_student_name)
    if existing_user:
        flash(f"生徒「{new_student_name}」はすでに存在します。", "error")
    else:
        new_student = Student(name=new_student_name, password=hash_password(new_password))
        db.session.add(new_student)
        db.session.commit()
        flash(f"生徒「{new_student_name}」を登録しました。", "success")
        
    return redirect(url_for('admin.dashboard'))

@bp.route('/view/<student_name>')
def admin_view(student_name):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
        
    today_str = datetime.now().strftime('%Y-%m-%d')
    date_str = request.args.get('date', today_str)
    todos = Todo.query.filter_by(student_name=student_name, date=date_str).order_by(Todo.id.desc()).all()
    student = Student.query.get_or_404(student_name)
    return render_template('admin_view.html', todos=todos, student=student, date=date_str)

@bp.route('/delete_student/<student_name>', methods=['POST'])
def delete_student(student_name):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    
    student = Student.query.get(student_name)
    if student:
        db.session.delete(student)
        db.session.commit()
        flash(f"生徒「{student_name}」を全ての記録と共に削除しました。", "success")
    
    return redirect(url_for('admin.dashboard'))

@bp.route('/reset_password/<student_name>', methods=['GET', 'POST'])
def reset_password(student_name):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))

    student = Student.query.get_or_404(student_name)

    if request.method == 'POST':
        new_password = request.form['new_password']
        if not new_password:
            flash("新しいパスワードを入力してください。", "error")
        else:
            student.password = hash_password(new_password)
            db.session.commit()
            flash(f"生徒「{student_name}」のパスワードをリセットしました。", "success")
            return redirect(url_for('admin.dashboard'))

    return render_template('reset_password.html', student_name=student.name)