import os
from flask import Blueprint, flash, render_template, request, redirect, url_for, session, current_app
from datetime import datetime, date, timedelta
from sqlalchemy import func, case
from werkzeug.utils import secure_filename
from sqlalchemy.exc import IntegrityError
from .. import db, hash_password
from ..models import Student, Todo, Mission, AiTest

bp = Blueprint('admin', __name__, url_prefix='/admin')

@bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin' in session:
        return redirect(url_for('admin.dashboard'))
        
    if request.method == 'POST':
        if request.form['password'] == current_app.config.get('ADMIN_PASSWORD'):
            session['admin'] = True
            session.permanent = False
            return redirect(url_for('admin.dashboard'))
        else:
            flash('管理者パスワードが違います', 'error')
            
    return render_template('admin_login.html')

@bp.route('/')
def dashboard():
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    # 生徒のリストをデータベースから取得
    students = Student.query.order_by(Student.name).all()
    return render_template('admin.html', students=students)

@bp.route('/add_student', methods=['POST'])
def add_student():
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    
    new_student_name = request.form['new_student']
    new_password = request.form['new_password']
    
    if not new_student_name or not new_password:
        flash("名前とパスワードの両方を入力してください。", "error")
        return redirect(url_for('admin.dashboard'))
        
    existing_user = Student.query.get(new_student_name)
    if existing_user:
        flash(f"生徒「{new_student_name}」はすでに存在します。", "error")
    else:
        new_student = Student(name=new_student_name, password=hash_password(new_password))
        db.session.add(new_student)
        db.session.commit()
        flash(f"生徒「{new_student_name}」を登録しました。", "success")
        
    return redirect(url_for('admin.dashboard'))

# ... (以降のadmin.py内の他の関数は、以前提示した最終版から変更ありません) ...

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
    else:
        flash(f"生徒「{student_name}」が見つかりません。", "error")
    
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

@bp.route('/add_mission/<student_name>', methods=['POST'])
def add_mission(student_name):
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
    mission.completed = not mission.completed
    db.session.commit()
    flash("ミッションの状態を更新しました。", "success")
    return redirect(url_for('admin.admin_view', student_name=mission.student_name))

@bp.route('/weekly_test_history/<student_name>')
def weekly_test_history(student_name):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    student = Student.query.get_or_404(student_name)
    tests = AiTest.query.filter_by(author=student, test_type='weekly').order_by(AiTest.created_at.desc()).all()
    return render_template('admin_weekly_test_history.html', student=student, tests=tests)

@bp.route('/upload_and_send/<int:test_id>', methods=['POST'])
def upload_and_send(test_id):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    
    test = AiTest.query.get_or_404(test_id)
    
    if 'graded_pdf' not in request.files:
        flash('ファイルが選択されていません', 'error')
        return redirect(request.url)
        
    file = request.files['graded_pdf']
    
    if file.filename == '':
        flash('ファイルが選択されていません', 'error')
        return redirect(request.url)
        
    if file:
        filename = secure_filename(f"test_{test.id}_{file.filename}")
        upload_path = current_app.config['UPLOAD_FOLDER']
        file.save(os.path.join(upload_path, filename))
        
        # DBに情報を保存
        test.graded_pdf_path = filename
        test.is_sent_to_student = True
        db.session.commit()
        
        flash(f"テスト「{test.title}」をアップロードし、{test.student_name}さんに送信しました。", "success")
        return redirect(url_for('admin.weekly_test_history', student_name=test.student_name))

    return redirect(url_for('admin.weekly_test_history', student_name=test.student_name))

@bp.route('/view_printable_test/<int:test_id>')
def view_printable_test(test_id):
    if 'admin' not in session: return redirect(url_for('admin.admin_login'))
    test = AiTest.query.get_or_404(test_id)
    return render_template('printable_test.html', test=test)

@bp.route('/daily_test_history/<student_name>')
def daily_test_history(student_name):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    
    student = Student.query.get_or_404(student_name)
    
    daily_tests = AiTest.query.filter_by(
        student_name=student_name,
        test_type='daily'
    ).order_by(AiTest.created_at.desc()).all()
    
    return render_template('admin_daily_test_history.html', student=student, tests=daily_tests)