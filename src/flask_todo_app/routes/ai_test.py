from flask import Blueprint, render_template, redirect, url_for, session, current_app, flash, request, jsonify
import json
import os
from datetime import date, timedelta, datetime
# import google.generativeai as genai
from .. import db
from ..models import Student, Todo, AiTest, AiQuestion, AiAnswer

bp = Blueprint('ai_test', __name__, url_prefix='/test')

def generate_test_from_ai_dummy(prompt, num_questions=10):
    """AI API呼び出しのシミュレーション（ダミーデータを返す）"""
    print(f"--- AIへの指示（プロンプト） ---\n{prompt}\n---------------------------------")
    dummy_questions = []
    for i in range(num_questions):
        dummy_questions.append({
            "question": f"これはダミー問題 {i+1} です。正しい答えは A です。",
            "options": {"A": f"選択肢A-{i+1}", "B": f"選択肢B-{i+1}", "C": f"選択肢C-{i+1}", "D": f"選択肢D-{i+1}"},
            "correct_answer": "A"
        })
    return json.dumps(dummy_questions)

@bp.route('/daily')
def daily_test():
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    student_name = session['student']
    today = date.today()
    
    existing_test = AiTest.query.filter(
        AiTest.student_name == student_name,
        AiTest.test_type == 'daily',
        db.func.date(AiTest.created_at) == today.strftime('%Y-%m-%d')
    ).first()

    if existing_test:
        return redirect(url_for('ai_test.view_test', test_id=existing_test.id))
    
    recent_todos = Todo.query.filter(
        Todo.student_name == student_name,
        Todo.date == (today - timedelta(days=1)).strftime('%Y-%m-%d'),
        Todo.completed == True
    ).all()
    topics = "、".join(list(set(t.subject for t in recent_todos))) or "総合復習"
    
    prompt = f"生徒「{student_name}」の昨日の学習内容「{topics}」に基づいた中学レベルの確認テストを10問作成してください。"
    test_data_json = generate_test_from_ai_dummy(prompt, 10)
    questions_data = json.loads(test_data_json)
    
    new_test = AiTest(student_name=student_name, test_type='daily', title=f"{today.strftime('%Y年%m月%d日')}のデイリーテスト")
    db.session.add(new_test)
    db.session.flush()

    for q_data in questions_data:
        question = AiQuestion(
            test_id=new_test.id,
            question_text=q_data.get('question'),
            options=json.dumps(q_data.get('options', {})),
            correct_answer=q_data.get('correct_answer')
        )
        db.session.add(question)
    
    db.session.commit()
    flash("今日のテストが作成されました！", "success")
    return redirect(url_for('ai_test.view_test', test_id=new_test.id))

@bp.route('/view/<int:test_id>')
def view_test(test_id):
    if 'student' not in session: return redirect(url_for('main.login'))
    test = AiTest.query.get_or_404(test_id)
    if test.author.name != session['student'] and 'admin' not in session:
        flash("アクセス権がありません", "error")
        return redirect(url_for('main.home'))

    if test.is_completed:
        return redirect(url_for('ai_test.view_result', test_id=test.id))

    return render_template('test_view.html', test=test)

@bp.route('/submit_test/<int:test_id>', methods=['POST'])
def submit_test(test_id):
    if 'student' not in session: return redirect(url_for('main.login'))
    
    student_name = session['student']
    test = AiTest.query.get_or_404(test_id)
    if test.author.name != student_name or test.is_completed:
        flash("無効なテストか、すでに解答済みです。", "error")
        return redirect(url_for('main.home'))

    score = 0
    for q in test.questions:
        user_answer = request.form.get(f'q-{q.id}')
        is_correct = (user_answer == q.correct_answer)
        if is_correct: score += 1
        
        ans = AiAnswer(question_id=q.id, student_name=student_name, selected_option=user_answer, is_correct=is_correct)
        db.session.add(ans)

    test.score = score
    test.is_completed = True
    db.session.commit()

    flash(f"{len(test.questions)}問中{score}問正解です！お疲れ様でした。", "success")
    return redirect(url_for('ai_test.view_result', test_id=test.id))

@bp.route('/result/<int:test_id>')
def view_result(test_id):
    if 'student' not in session and 'admin' not in session: return redirect(url_for('main.login'))
    test = AiTest.query.get_or_404(test_id)
    
    if 'admin' not in session and test.author.name != session.get('student'):
        flash("アクセス権がありません", "error")
        return redirect(url_for('main.home'))
        
    student_answers = AiAnswer.query.filter(
        AiAnswer.question_id.in_([q.id for q in test.questions]),
        AiAnswer.student_name == test.student_name
    ).all()
    user_answers = {ans.question_id: ans.selected_option for ans in student_answers}

    return render_template('test_result.html', test=test, user_answers=user_answers)

@bp.route('/history')
def test_history():
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    student_name = session['student']
    tests = AiTest.query.filter_by(student_name=student_name).order_by(AiTest.created_at.desc()).all()
    
    return render_template('test_history.html', tests=tests)

# --- ★★★ ここが今回の修正箇所です ★★★ ---
# 関数名を create_weekly_test_form から create_weekly_test に変更
@bp.route('/admin/create_weekly', methods=['GET', 'POST'])
def create_weekly_test():
    if 'admin' not in session:
        return redirect(url_for('admin.admin_login'))
    
    all_students = Student.query.all()

    if request.method == 'POST':
        student_names = request.form.getlist('student_names')
        title = request.form.get('title')
        content = request.form.get('content')
        weak_points = request.form.get('weak_points')
        num_questions = request.form.get('num_questions')
        difficulty = request.form.get('difficulty')

        if not student_names:
            flash("対象の生徒を一人以上選択してください。", "error")
            return render_template('create_weekly_test.html', students=all_students)

        prompt = f"""
        以下の条件で、週テストを作成してください。
        タイトル: {title}
        主な内容: {content}
        特に強化したい苦手分野: {weak_points}
        問題数は{num_questions}問、難易度は{difficulty}でお願いします。
        """
        
        flash(f"{len(student_names)}人の生徒に「{title}」を配布しました（シミュレーション）", "success")
        return redirect(url_for('admin.dashboard'))

    return render_template('create_weekly_test.html', students=all_students)