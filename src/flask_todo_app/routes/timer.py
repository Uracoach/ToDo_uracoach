from flask import Blueprint, flash, render_template, request, redirect, url_for, session, jsonify
from datetime import datetime, date
from .. import db
from ..models import Student, Todo

bp = Blueprint('timer', __name__, url_prefix='/timer')

@bp.route('/')
def timer_page():
    """タイマーページを表示する"""
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    student_name = session['student']
    today_str = date.today().strftime('%Y-%m-%d')

    # 今日の未完了ToDoのみを取得
    todays_todos = Todo.query.filter(
        Todo.student_name == student_name,
        Todo.date == today_str,
        Todo.completed == False
    ).all()
    
    return render_template('timer.html', todays_todos=todays_todos, student_name=student_name)

@bp.route('/log_time', methods=['POST'])
def log_time_api():
    """タイマーで計測した時間を記録するAPI"""
    if 'student' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    data = request.get_json()
    todo_id = data.get('todo_id')
    elapsed_seconds = data.get('seconds')
    # ▼▼▼ 休憩時間も受け取る ▼▼▼
    break_seconds = data.get('break_seconds', 0)

    if not todo_id or elapsed_seconds is None:
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    todo = Todo.query.get(int(todo_id))

    if not todo or todo.author.name != session['student']:
        return jsonify({'success': False, 'error': 'Permission denied'}), 403
    
    # 秒を時間と分に変換
    hours, remainder = divmod(elapsed_seconds, 3600)
    minutes, _ = divmod(remainder, 60)

    # 既存の実績時間に加算する
    todo.actual_hour += hours
    todo.actual_min += minutes

    # 分が60を超えていたら時間に繰り上げる
    if todo.actual_min >= 60:
        h_plus, m_new = divmod(todo.actual_min, 60)
        todo.actual_hour += h_plus
        todo.actual_min = m_new

    # ▼▼▼ 休憩時間を記録 ▼▼▼
    todo.break_seconds += break_seconds
    todo.completed = True
    db.session.commit()

    return jsonify({
        'success': True, 
        'message': f"「{todo.subject}」の学習時間を記録しました！"
    })