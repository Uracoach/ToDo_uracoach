import os
import json
from flask import Blueprint, flash, render_template, request, redirect, url_for, session, jsonify
from datetime import date, timedelta, datetime
import google.generativeai as genai
from dotenv import load_dotenv
from .. import db
from ..models import Student, Todo, Test, Question, Answer

# .flaskenvファイルから環境変数を明示的に読み込む
load_dotenv()

# APIキーを設定
try:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("エラー: GEMINI_API_KEYが.flaskenvファイルに設定されていません。")
    else:
        genai.configure(api_key=api_key)
except Exception as e:
    print(f"APIキーの設定でエラーが発生しました: {e}")


bp = Blueprint('ai_test', __name__, url_prefix='/test')


def generate_test_from_ai(student_name):
    """AI(Gemini)を使って、生徒の学習状況に基づいたテストを生成する関数"""
    
    # 前日の学習内容を取得
    yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
    recent_todos = Todo.query.filter_by(student_name=student_name, date=yesterday, completed=True).all()
    
    if not recent_todos:
        # 学習記録がない場合は一般的な問題
        topics = "中学レベルの主要5教科からランダムに"
    else:
        # 学習した内容を「教科：教材名」の形式でリストアップ
        learned_items = [f"{todo.subject}（{todo.material}）" for todo in recent_todos if todo.material]
        if not learned_items:
            # 教材名の入力がない場合は教科名だけ
            learned_subjects = list(set(todo.subject for todo in recent_todos))
            topics = "、".join(learned_subjects)
        else:
            topics = "、".join(learned_items)

    prompt = f"""
    あなたは優秀な中学生向けの教育AIです。
    生徒は昨日、特に「{topics}」という内容を重点的に学習しました。
    この内容に沿った、埼玉県の公立中学校の学習指導要領に準拠する中学2年生レベルの確認テストを、以下のJSON形式で厳密に10問作成してください。
    各問題には必ずA,B,C,Dの4つの選択肢と、正解のキー（'A','B','C','D'のいずれか）を含めてください。
    JSON以外の説明文は一切含めないでください。

    [
        {{
            "question": "問題文をここに記述",
            "options": {{
                "A": "選択肢A",
                "B": "選択肢B",
                "C": "選択肢C",
                "D": "選択肢D"
            }},
            "correct_answer": "B"
        }}
    ]
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-pro')
        response = model.generate_content(prompt)
        # AIの応答からJSON部分だけを抽出する
        json_response_text = response.text.strip().replace("```json", "").replace("```", "")
        questions_data = json.loads(json_response_text)

        # 新しいテストをデータベースに保存
        new_test = Test(student_name=student_name)
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
        return new_test
    except Exception as e:
        print(f"AIからのテスト生成またはDB保存でエラー: {e}")
        return None


@bp.route('/')
def daily_test():
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    student_name = session['student']
    today_str = date.today().strftime('%Y-%m-%d')

    # 今日のテストが既に存在するか確認
    test = Test.query.filter_by(student_name=student_name, test_date=today_str).first()

    if test:
        if test.score is not None:
            # 受験済みの場合、結果表示ページにリダイレクト
            return redirect(url_for('ai_test.view_result', test_id=test.id, message="本日のテストは受験済みです"))
        else:
            # 未受験だがテストは存在する場合
            return render_template('test.html', test=test, questions=test.questions)
    
    # 今日のテストがまだない場合、新しく生成
    new_test = generate_test_from_ai(student_name)
    if not new_test:
        flash("テストの生成に失敗しました。APIキーが正しく設定されているか、.flaskenvファイルをご確認ください。", "error")
        return redirect(url_for('main.student_view', student_name=student_name))

    return render_template('test.html', test=new_test, questions=new_test.questions)

@bp.route('/history')
def test_history():
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    student_name = session['student']
    tests = Test.query.filter_by(student_name=student_name).order_by(Test.test_date.desc()).all()
    return render_template('test_history.html', tests=tests)

@bp.route('/result/<int:test_id>')
def view_result(test_id):
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    message = request.args.get('message', None)
    student_name = session['student']
    test = Test.query.get_or_404(test_id)

    if test.student_name != student_name:
        flash("アクセス権がありません。", "error")
        return redirect(url_for('main.home'))

    # 解答を取得
    answers = Answer.query.filter(
        Answer.student_name == student_name,
        Answer.question_id.in_([q.id for q in test.questions])
    ).all()
    user_answers = {ans.question_id: ans.selected_option for ans in answers}
    
    return render_template('test_result.html', test=test, questions=test.questions, user_answers=user_answers, message=message)


@bp.route('/submit', methods=['POST'])
def submit_test():
    if 'student' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401
    
    student_name = session['student']
    data = request.get_json()
    answers = data.get('answers', {})
    test_id = data.get('test_id')

    test = Test.query.get(test_id)
    if not test or test.student_name != student_name:
        return jsonify({'success': False, 'error': 'Invalid test'}), 400

    score = 0
    total = len(test.questions)
    for q in test.questions:
        user_answer = answers.get(str(q.id))
        is_correct = (user_answer == q.correct_answer)
        if is_correct:
            score += 1
        
        # 解答履歴を保存
        ans = Answer(question_id=q.id, student_name=student_name, selected_option=user_answer, is_correct=is_correct)
        db.session.add(ans)

    test.score = score
    db.session.commit()

    return jsonify({
        'success': True,
        'score': score,
        'total': total,
        'message': f'{total}問中{score}問正解です！'
    })

@bp.route('/weekly')
def weekly_test_list():
    if 'student' not in session:
        return redirect(url_for('main.login'))
    
    # 週テスト（全生徒共通）の一覧を取得
    weekly_tests = Test.query.filter_by(test_type='weekly').order_by(Test.test_date.desc()).all()
    
    return render_template('weekly_test_list.html', tests=weekly_tests)