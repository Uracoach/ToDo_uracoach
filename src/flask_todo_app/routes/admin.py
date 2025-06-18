import os
import json
import google.generativeai as genai
from flask import Blueprint, flash, render_template, request, redirect, url_for, session
from datetime import datetime, date, timedelta
from sqlalchemy import func, case
from sqlalchemy.exc import IntegrityError
from .. import db, hash_password
from ..models import Student, Todo, Mission, Test, Question

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
    completed_mission_ids = {m.id for m in student.completed_missions}
    today_str = datetime.now().strftime('%Y-%m-%d')
    date_str = request.args.get('date', today_str)
    todos = Todo.query.filter_by(student_name=student_name, date=date_str).order_by(Todo.id.desc()).all()
    return render_template('admin_view.html', student=student, todos=todos, date=date_str, 
                           missions=missions, completed_mission_ids=completed_mission_ids)

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

@bp.route('/missions', methods=['GET', 'POST'])
def missions():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    if request.method == 'POST':
        description = request.form.get('description')
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        week_str = start_of_week.strftime('%Y-%m-%d')
        if description:
            new_mission = Mission(
                week_start_date=week_str,
                description=description
            )
            db.session.add(new_mission)
            db.session.commit()
            flash("新しいウィークリーミッションを追加しました。")
        return redirect(url_for('admin.missions'))
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_str = start_of_week.strftime('%Y-%m-%d')
    current_missions = Mission.query.filter_by(week_start_date=week_str).all()
    return render_template('missions.html', missions=current_missions)

@bp.route('/missions/delete/<int:mission_id>', methods=['POST'])
def delete_mission(mission_id):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    mission = Mission.query.get_or_404(mission_id)
    db.session.delete(mission)
    db.session.commit()
    flash("ミッションを削除しました。")
    return redirect(url_for('admin.missions'))

@bp.route('/mark_mission_complete/<student_name>/<int:mission_id>', methods=['POST'])
def mark_mission_complete(student_name, mission_id):
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    student = Student.query.get_or_404(student_name)
    mission = Mission.query.get_or_404(mission_id)
    student.completed_missions.append(mission)
    db.session.commit()
    flash(f"「{student.name}」さんのミッションを完了にしました。", "success")
    return redirect(url_for('admin.admin_view', student_name=student_name))

# --- ★★★ ここからが今回の修正箇所です ★★★
@bp.route('/create_weekly_test', methods=['GET', 'POST'])
def create_weekly_test():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))

    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        q_type = request.form.get('q_type')
        ans_type = request.form.get('ans_type')

        prompt = f"""
        あなたは優秀な塾講師です。
        以下の内容に基づいた、中学2年生レベルの小テストを、指定された形式で厳密に10問作成してください。

        # テストのテーマ・単元
        {content}

        # 問題形式
        {q_type}

        # 解答形式
        {ans_type}

        # 出力形式 (JSON)
        [
            {{
                "question": "問題文",
                "options": {{ "A": "選択肢A", "B": "選択肢B", "C": "選択肢C", "D": "選択肢D" }},
                "correct_answer": "B"
            }}
        ]
        """
        try:
            model = genai.GenerativeModel('gemini-1.5-pro')
            response = model.generate_content(prompt)
            json_response_text = response.text.strip().replace("```json", "").replace("```", "")
            questions_data = json.loads(json_response_text)

            # 週テストは特定の生徒に紐付けない (student_name=None)
            new_test = Test(title=title, test_type='weekly')
            db.session.add(new_test)
            
            for q_data in questions_data:
                question = Question(
                    test=new_test,
                    question_text=q_data.get('question', '問題の取得に失敗'),
                    option_a=q_data.get('options', {}).get('A', ''),
                    option_b=q_data.get('options', {}).get('B', ''),
                    option_c=q_data.get('options', {}).get('C', ''),
                    option_d=q_data.get('options', {}).get('D', ''),
                    correct_answer=q_data.get('correct_answer', '')
                )
                db.session.add(question)
            
            db.session.commit()
            flash(f"週テスト「{title}」を作成しました。", "success")
            return redirect(url_for('admin.dashboard'))

        except Exception as e:
            flash(f"テストの生成に失敗しました: {e}", "error")

    return render_template('create_weekly_test.html')