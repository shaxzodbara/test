from flask import Flask, render_template, request, redirect, url_for, session, flash
import json
import random
import csv
from datetime import timedelta, datetime
import os
from collections import defaultdict

app = Flask(__name__)
app.secret_key = 'secret123'
app.permanent_session_lifetime = timedelta(hours=1)

USERS_FILE = 'users.json'
RESULTS_FILE = 'results.json'
QUESTION_FOLDER = 'subjects'
SUBJECT_CONFIG_FILE = 'subject_config.json'

# Load and save subject configuration
def load_subject_config():
    if os.path.exists(SUBJECT_CONFIG_FILE):
        with open(SUBJECT_CONFIG_FILE) as f:
            return json.load(f)
    return {'matematika': 10, 'ingilis': 10, 'tarix': 10, 'huquq': 30}

def save_subject_config(config):
    with open(SUBJECT_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# Load and save users
def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE) as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f, indent=4)

# Load and save questions
def load_questions():
    all_questions = []
    config = load_subject_config()
    for subject, count in config.items():
        path = os.path.join(QUESTION_FOLDER, f'{subject}.csv')
        if os.path.exists(path):
            with open(path, newline='') as csvfile:
                reader = list(csv.DictReader(csvfile))
                selected = random.sample(reader, min(count, len(reader)))
                for idx, row in enumerate(selected):
                    all_questions.append({
                        'id': f"{subject}_{idx}",
                        'subject': subject,
                        'savol': row['savol'],
                        'variantlar': [row['a'], row['b'], row['c'], row['d']],
                        'javob': row['javob'].strip().lower()
                    })
    return all_questions

# Load and save results
def save_result(username, score, total, details):
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            data = json.load(f)
    else:
        data = []
    data.append({
        'username': username,
        'score': score,
        'total': total,
        'details': details
    })
    with open(RESULTS_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE) as f:
            return json.load(f)
    return []

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()
        if username in users and users[username] == password:
            session['username'] = username
            session.permanent = True
            user_results = [r for r in load_results() if r['username'] == username]
            if user_results:
                session['already_taken'] = True
            return redirect(url_for('admin_panel' if username == 'admin' else 'test'))
        else:
            flash("Login yoki parol noto‘g‘ri!")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/test', methods=['GET', 'POST'])
def test():
    if 'username' not in session:
        return redirect(url_for('login'))

    if session.get('already_taken'):
        return redirect(url_for('my_results'))

    if request.method == 'POST':
        score = 0
        results = []
        for q in session['questions']:
            user_answer = request.form.get(f'q{q["id"]}')
            user_answer_key = None
            for idx, opt in enumerate(q['variantlar']):
                if user_answer == opt:
                    user_answer_key = ['a', 'b', 'c', 'd'][idx]
                    break
            correct = (user_answer_key == q['javob'])
            correct_answer_text = q['variantlar'][['a', 'b', 'c', 'd'].index(q['javob'])] if q['javob'] in ['a', 'b', 'c', 'd'] else ''
            results.append({
                'savol': q['savol'],
                'user_answer': user_answer,
                'correct_answer': correct_answer_text,
                'correct': correct,
                'subject': q['subject']
            })
            if correct:
                score += 1

        save_result(session['username'], score, len(results), results)
        session['already_taken'] = True
        session.pop('questions', None)
        return render_template('test.html', result={'score': score, 'total': len(results), 'details': results})

    if 'questions' not in session:
        session['questions'] = load_questions()
        session['started_at'] = datetime.now().timestamp()

    return render_template('test.html', questions=session['questions'], started_at=session['started_at'])

@app.route('/my-results')
def my_results():
    if 'username' not in session:
        return redirect(url_for('login'))
    username = session['username']
    all_results = load_results()
    user_results = [r for r in all_results if r['username'] == username]
    return render_template('my_results.html', results=user_results, username=username)

@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    users = load_users()
    results = load_results()
    stats = defaultdict(lambda: {'correct': 0, 'incorrect': 0, 'attempts': 0})

    for res in results:
        stats[res['username']]['correct'] += res['score']
        stats[res['username']]['incorrect'] += res['total'] - res['score']
        stats[res['username']]['attempts'] += 1

    if request.method == 'POST':
        new_user = request.form.get('username')
        new_pass = request.form.get('password')
        if not new_user or not new_pass:
            flash("Foydalanuvchi nomi yoki parol bo‘sh bo‘lmasligi kerak.")
        elif new_user in users:
            flash("Bu foydalanuvchi allaqachon mavjud.")
        else:
            users[new_user] = new_pass
            save_users(users)
            flash(f"Foydalanuvchi '{new_user}' muvaffaqiyatli qo‘shildi!")

    all_questions = {}
    for subject in load_subject_config().keys():
        path = os.path.join(QUESTION_FOLDER, f"{subject}.csv")
        if os.path.exists(path):
            with open(path, newline='') as csvfile:
                reader = list(csv.DictReader(csvfile))
                all_questions[subject] = reader

    return render_template('admin.html', users=users, stats=stats, passwords=users, all_questions=all_questions)

@app.route('/add-question', methods=['GET', 'POST'])
def add_question():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        subject = request.form['subject']
        savol = request.form['savol']
        a = request.form['a']
        b = request.form['b']
        c = request.form['c']
        d = request.form['d']
        javob = request.form['javob'].strip().lower()

        filename = os.path.join(QUESTION_FOLDER, f"{subject}.csv")
        file_exists = os.path.isfile(filename)

        with open(filename, 'a', newline='') as csvfile:
            fieldnames = ['savol', 'a', 'b', 'c', 'd', 'javob']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow({
                'savol': savol,
                'a': a,
                'b': b,
                'c': c,
                'd': d,
                'javob': javob
            })

        flash("Savol muvaffaqiyatli qo‘shildi!")
        return redirect(url_for('add_question'))

    return render_template('savol.html')

@app.route('/configure', methods=['GET', 'POST'])
def configure_subjects():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    config = load_subject_config()

    if request.method == 'POST':
        for subject in config:
            value = request.form.get(subject)
            if value.isdigit():
                config[subject] = int(value)
        save_subject_config(config)
        flash("Fanlar konfiguratsiyasi yangilandi!")

    return render_template('configure.html', config=config)

@app.route('/delete-question', methods=['POST'])
def delete_question():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    subject = request.form['subject']
    question_text = request.form['savol']
    filepath = os.path.join(QUESTION_FOLDER, f"{subject}.csv")

    if not os.path.exists(filepath):
        flash("Fayl topilmadi!")
        return redirect(url_for('admin_panel'))

    updated_rows = []
    with open(filepath, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row['savol'] != question_text:
                updated_rows.append(row)

    with open(filepath, 'w', newline='') as csvfile:
        fieldnames = ['savol', 'a', 'b', 'c', 'd', 'javob']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    flash("Savol o‘chirildi!")
    return redirect(url_for('admin_panel'))

@app.route('/edit-question', methods=['GET', 'POST'])
def edit_question():
    if 'username' not in session or session['username'] != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        subject = request.form['subject']
        old_savol = request.form['old_savol']
        new_savol = request.form['savol']
        a = request.form['a']
        b = request.form['b']
        c = request.form['c']
        d = request.form['d']
        javob = request.form['javob'].strip().lower()

        filepath = os.path.join(QUESTION_FOLDER, f"{subject}.csv")
        if not os.path.exists(filepath):
            flash("Savol fayli topilmadi!")
            return redirect(url_for('admin_panel'))

        updated_rows = []
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['savol'] == old_savol:
                    updated_rows.append({
                        'savol': new_savol,
                        'a': a,
                        'b': b,
                        'c': c,
                        'd': d,
                        'javob': javob
                    })
                else:
                    updated_rows.append(row)

        with open(filepath, 'w', newline='') as csvfile:
            fieldnames = ['savol', 'a', 'b', 'c', 'd', 'javob']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(updated_rows)

        flash("Savol tahrirlandi!")
        return redirect(url_for('admin_panel'))

    subject = request.args.get('subject')
    savol_text = request.args.get('savol')
    filepath = os.path.join(QUESTION_FOLDER, f"{subject}.csv")
    question = None
    if os.path.exists(filepath):
        with open(filepath, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['savol'] == savol_text:
                    question = row
                    break

    return render_template('edit_question.html', subject=subject, question=question)

if __name__ == '__main__':
    os.makedirs(QUESTION_FOLDER, exist_ok=True)
    app.run(debug=True)
