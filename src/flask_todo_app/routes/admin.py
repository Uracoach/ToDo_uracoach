import os
from flask import Blueprint, flash, render_template, request, redirect, url_for, session
from datetime import datetime, date, timedelta
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from .. import db, hash_password
from ..models import Student, Todo, Mission

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
    student = Student.query.get_or_404(student_name)
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_str = start_of_week.strftime('%Y-%m-%d')
    missions = Mission.query.filter_by(student_name=student_name, week_start_date=week_str).all()
    today_str = datetime.now().strftime('%Y-%m-%d')
    date_str = request.args.get('date', today_str)
    todos = Todo.query.filter_by(student_name=student_name, date=date_str).order_by(Todo.id.desc()).all()
    return render_template('admin_view.html', student=student, todos=todos, date=date_str, missions=missions)

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

@bp.route('/report/<student_name>')
def report(student_name):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    student = Student.query.get_or_404(student_name)
    today = date.today()
    month_str = request.args.get('month', today.strftime('%Y-%m'))
    try:
        selected_month_dt = datetime.strptime(month_str, '%Y-%m')
    except ValueError:
        selected_month_dt = today.replace(day=1)
    start_of_month = selected_month_dt.date()
    end_of_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, year=start_of_month.year + (start_of_month.month // 12)) - timedelta(days=1))
    month_todos = Todo.query.filter(
        Todo.student_name == student_name, Todo.completed == True,
        Todo.date.between(start_of_month.strftime('%Y-%m-%d'), end_of_month.strftime('%Y-%m-%d'))
    ).order_by(Todo.date).all()
    total_minutes_expression = Todo.actual_hour * 60 + Todo.actual_min
    subject_totals = db.session.query(
        Todo.subject, func.sum(total_minutes_expression).label('total_minutes')
    ).filter(
        Todo.student_name == student_name, Todo.completed == True,
        Todo.date.between(start_of_month.strftime('%Y-%m-%d'), end_of_month.strftime('%Y-%m-%d'))
    ).group_by(Todo.subject).all()
    total_minutes = sum(item.total_minutes for item in subject_totals if item.total_minutes)
    return render_template('report.html', student=student, month_todos=month_todos,
                           subject_totals=subject_totals, total_minutes=total_minutes,
                           report_date=today, month_str=start_of_month.strftime('%Y年%m月'))

# 古いmissions, delete_missionを削除し、新しい関数を追加
@bp.route('/add_mission/<student_name>', methods=['POST'])
def add_student_mission(student_name):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    student = Student.query.get_or_404(student_name)
    description = request.form.get('description')
    if description:
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        week_str = start_of_week.strftime('%Y-%m-%d')
        new_mission = Mission(
            student_name=student_name,
            week_start_date=week_str,
            description=description
        )
        db.session.add(new_mission)
        db.session.commit()
        flash(f"「{student.name}」さんに新しいミッションを追加しました。")
    return redirect(url_for('admin.admin_view', student_name=student_name))

@bp.route('/mark_mission_complete/<int:mission_id>', methods=['POST'])
def mark_mission_complete(mission_id):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    mission = Mission.query.get_or_404(mission_id)
    mission.completed = True
    db.session.commit()
    flash("ミッションを完了にしました。", "success")
    return redirect(url_for('admin.admin_view', student_name=mission.student_name))