from flask import Blueprint, flash, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, timedelta, date
from sqlalchemy import func, case
from .. import db, hash_password
from ..models import Student, Todo, Mission

bp = Blueprint('main', __name__)

@bp.route('/')
def home():
    if 'student' in session:
        return redirect(url_for('main.student_view', student_name=session['student']))
    return redirect(url_for('main.login'))

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        student_name = request.form['student']
        password = request.form['password']
        user = Student.query.filter_by(name=student_name).first()
        if user and user.password == hash_password(password):
            session['student'] = user.name
            session.permanent = False
            return redirect(url_for('main.student_view', student_name=user.name))
        else:
            flash('名前またはパスワードが正しくありません。', 'error')
    return render_template('login.html')

@bp.route('/logout')
def logout():
    session.pop('student', None)
    session.pop('admin', None)
    return redirect(url_for('main.login'))

@bp.route('/student/<student_name>')
def student_view(student_name):
    if ('student' not in session or session['student'] != student_name):
        return redirect(url_for('main.login'))
    
    student = Student.query.get_or_404(student_name)
    
    # 今週のミッションを取得
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    week_str = start_of_week.strftime('%Y-%m-%d')
    missions = Mission.query.filter_by(student_name=student_name, week_start_date=week_str).all()
    
    # ページ表示ロジック
    today_dt = date.today()
    date_str = request.args.get('date', today_dt.strftime('%Y-%m-%d'))
    current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    prev_date = (current_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_date = (current_date + timedelta(days=1)).strftime('%Y-%m-%d')
    
    todos = Todo.query.filter_by(student_name=student_name, date=date_str).order_by(Todo.id).all()
    
    return render_template('student.html', todos=todos, student_name=student_name, 
                           date=date_str, prev_date=prev_date, next_date=next_date,
                           missions=missions)

@bp.route('/api/add_todo', methods=['POST'])
def add_todo_api():
    if 'student' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    student_name = session['student']
    subject = request.form.get('subject')
    if not subject:
        return jsonify({'success': False, 'error': '教科が選択されていません。'}), 400

    new_todo = Todo(
        student_name=student_name,
        date=request.form.get('date'),
        subject=subject,
        material=request.form.get('material', ''),
        start_page=int(request.form.get('start_page') or 0),
        end_page=int(request.form.get('end_page') or 0),
        target_hour=int(request.form.get('target_hour', 0)),
        target_min=int(request.form.get('target_min', 0))
    )
    db.session.add(new_todo)
    db.session.commit()

    return jsonify({
        'success': True,
        'todo': {
            'id': new_todo.id,
            'subject': new_todo.subject,
            'material': new_todo.material,
            'start_page': new_todo.start_page,
            'end_page': new_todo.end_page,
            'target_hour': new_todo.target_hour,
            'target_min': new_todo.target_min,
            'completed': new_todo.completed
        }
    })

@bp.route('/api/update_todo/<int:todo_id>', methods=['POST'])
def update_todo_api(todo_id):
    if 'student' not in session:
        return jsonify({'success': False, 'error': 'Authentication required'}), 401
    
    todo = Todo.query.get_or_404(todo_id)
    if todo.author.name == session['student']:
        todo.actual_hour = int(request.form.get('actual_hour', 0))
        todo.actual_min = int(request.form.get('actual_min', 0))
        todo.completed = True
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'ToDoを完了しました！',
            'actual_hour': todo.actual_hour,
            'actual_min': todo.actual_min
        })
    return jsonify({'success': False, 'error': 'Permission denied'}), 403

@bp.route('/api/delete_todo/<int:todo_id>', methods=['DELETE'])
def delete_todo_api(todo_id):
    if 'student' not in session: return jsonify({'success': False, 'error': 'Authentication required'}), 401
    todo = Todo.query.get_or_404(todo_id)
    if todo.author.name == session['student']:
        db.session.delete(todo)
        db.session.commit()
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Permission denied'}), 403

@bp.route('/student/<student_name>/chart')
def student_chart(student_name):
    if ('student' not in session or session['student'] != student_name) and 'admin' not in session:
        return redirect(url_for('main.login'))
    return render_template('chart.html', student_name=student_name)

@bp.route('/student/<student_name>/chart_only')
def show_chart_only(student_name):
    if ('student' not in session or session['student'] != student_name) and 'admin' not in session:
        return redirect(url_for('main.login'))
    return render_template('chart_only.html', student_name=student_name)

@bp.route('/student/<student_name>/summary')
def show_summary(student_name):
    if ('student' not in session or session['student'] != student_name) and 'admin' not in session:
        return redirect(url_for('main.login'))
        
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        selected_month_dt = datetime.strptime(month_str, '%Y-%m')
    except ValueError:
        selected_month_dt = date.today().replace(day=1)

    today = date.today()
    start_of_month = selected_month_dt.date()
    end_of_month = (start_of_month.replace(month=start_of_month.month % 12 + 1, year=start_of_month.year + (start_of_month.month // 12)) - timedelta(days=1))
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    first_todo = db.session.query(func.min(Todo.date)).filter_by(student_name=student_name, completed=True).scalar()
    total_days = (today - datetime.strptime(first_todo, '%Y-%m-%d').date()).days + 1 if first_todo else 0
    total_minutes_expression = Todo.actual_hour * 60 + Todo.actual_min
    
    rows = db.session.query(
        Todo.subject,
        func.sum(case((Todo.date == today.strftime('%Y-%m-%d'), total_minutes_expression), else_=0)).label('today_total'),
        func.sum(case((Todo.date.between(start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d')), total_minutes_expression), else_=0)).label('week_total'),
        func.sum(case((Todo.date.between(start_of_month.strftime('%Y-%m-%d'), end_of_month.strftime('%Y-%m-%d')), total_minutes_expression), else_=0)).label('month_total'),
        func.sum(total_minutes_expression).label('all_time_total')
    ).filter(Todo.student_name == student_name, Todo.completed == True).group_by(Todo.subject).all()

    subjects = ["国語", "数学", "理科", "社会", "英語"]
    summary_data = {s: {'today_total': 0, 'week_total': 0, 'month_total': 0, 'all_time_total': 0} for s in subjects}
    for row in rows:
        if row.subject in summary_data:
            summary_data[row.subject].update(dict(row._asdict()))

    total_row = {
        'today': sum(d['today_total'] for d in summary_data.values()),
        'week': sum(d['week_total'] for d in summary_data.values()),
        'month': sum(d['month_total'] for d in summary_data.values()),
        'all_time': sum(d['all_time_total'] for d in summary_data.values())
    }
    start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
    end_of_last_month = start_of_month - timedelta(days=1)
    
    last_month_total = db.session.query(func.sum(total_minutes_expression)).filter(
        Todo.student_name == student_name, Todo.completed == True,
        Todo.date.between(start_of_last_month.strftime('%Y-%m-%d'), end_of_last_month.strftime('%Y-%m-%d'))
    ).scalar() or 0
    comparison_minutes = total_row['month'] - last_month_total
    total_month_hours = total_row['month'] / 60
    
    levels = {
        10: ("勉強見習い", "#888", "images/level_novice.png"), 20: ("勉強修行中", "#3498db", "images/level_novice.png"),
        30: ("勉強玄人", "#2ecc71", "images/level_novice.png"), 40: ("勉強名人", "#e67e22", "images/level_master.png"),
        50: ("勉強達人", "#9b59b6", "images/level_master.png"), 60: ("勉強超人", "#1abc9c", "images/level_master.png"),
        70: ("勉強大達人", "#f39c12", "images/level_god.png"), 80: ("勉強仙人", "#e74c3c", "images/level_god.png")
    }
    level_text, level_style, level_image = "勉強神", "color: #c0392b; font-weight: bold; font-size: 1.5em; text-shadow: 0 0 10px gold;", "images/level_god.png"
    for threshold, (text, style_color, image_path) in sorted(levels.items()):
        if total_month_hours < threshold:
            level_text, level_style, level_image = text, f"color: {style_color};", image_path
            break
            
    date_info = {
        'today': f"{today.month}月{today.day}日", 'week_start': f"{start_of_week.month}月{start_of_week.day}日",
        'week_end': f"{end_of_week.month}月{end_of_week.day}日", 'month': start_of_month.strftime('%Y年%m月'),
        'total_days': total_days
    }
    return render_template('summary.html', student_name=student_name, summary_data=summary_data, date_info=date_info, 
                           level_text=level_text, level_style=level_style, level_image=level_image,
                           month_str=month_str, total_row=total_row, comparison_minutes=comparison_minutes)

@bp.route('/api/student/<student_name>/chart_data')
def chart_data(student_name):
    if ('student' not in session or session['student'] != student_name) and 'admin' not in session:
        return jsonify({'error': 'Unauthorized'}), 403
    week_offset = int(request.args.get('week_offset', 0))
    subject_filter = request.args.get('subject', 'all')
    today = datetime.now() + timedelta(weeks=week_offset)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    labels = [(start_of_week + timedelta(days=i)).strftime('%m/%d') for i in range(7)]
    base_query = db.session.query(
        Todo.date, Todo.subject, func.sum(Todo.actual_hour * 60 + Todo.actual_min).label('total_minutes')
    ).filter(
        Todo.student_name == student_name, Todo.completed == True,
        Todo.date.between(start_of_week.strftime('%Y-%m-%d'), end_of_week.strftime('%Y-%m-%d'))
    )
    if subject_filter != 'all':
        base_query = base_query.filter(Todo.subject == subject_filter)
    rows = base_query.group_by(Todo.date, Todo.subject).all()
    datasets = {}
    subjects = ["国語", "数学", "理科", "社会", "英語"] if subject_filter == 'all' else [subject_filter]
    for sub in subjects:
        datasets[sub] = {'label': sub, 'data': [0] * 7}
    for row in rows:
        day_index = (datetime.strptime(row.date, '%Y-%m-%d').date() - start_of_week.date()).days
        if 0 <= day_index < 7 and row.subject in datasets:
            datasets[row.subject]['data'][day_index] = row.total_minutes
    return jsonify({
        'title': f'{start_of_week.strftime("%Y/%m/%d")} - {end_of_week.strftime("%Y/%m/%d")}の学習記録',
        'labels': labels,
        'datasets': list(datasets.values())
    })