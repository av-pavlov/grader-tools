from datetime import datetime

from flask import Blueprint, session, redirect, request, url_for, render_template, abort
from os.path import join, isfile
import logging
from multimeter import login_required, users, tasks, settings, results, languages, save_json


user_bp = Blueprint('multimeter', __name__)


@user_bp.route('/login/', methods=('GET', 'POST'))
def login():
    """ Страница авторизации пользователей """
    if 'username' in session:
        return redirect(request.form.get('next', url_for('multimeter.index')))
    errors = []
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == '':
            errors.append('Логин не задан')
        if password == '':
            errors.append('Пароль не задан')
        if not errors:
            if username in users and users[username]['password'] == password:
                session['username'] = username
                logging.info("{} - - User {} logged in".format(request.remote_addr, username))
                return redirect(request.form.get('next', url_for('multimeter.index')))
            errors.append('Неправильный логин или пароль')
            logging.info("{} - - Login ERROR for user {}".format(request.remote_addr, username))
    return render_template('login.html', errors=errors)


@user_bp.route('/logout/')
def logout():
    """ Выход из системы """
    username = session.get('username','')
    if username:
        logging.info("{} - - User {} logged out".format(request.remote_addr, username))
    session.pop('username', None)
    return redirect(url_for('multimeter.login'))


@user_bp.route('/register/', methods=('GET', 'POST'))
def register():
    """ Регистрация нового пользователя """
    if not settings.registration_enabled:
        abort(404)
    errors = []
    new_name = ''
    new_data = {}
    if request.method == 'POST':
        new_name = request.form.get('username', '')
        new_data = dict(password=request.form.get('password', ''))
        for attr in settings.users_attributes:
            new_data[attr] = request.form.get(attr, '')
        errors = users.validate_user(new_name, new_data, request.form.get('confirm', ''), True)
        if not errors:
            users[new_name] = new_data
            users.save()
            session['username'] = new_name
            return redirect(url_for('multimeter.index'))
    return render_template('register.html', errors=errors, username=new_name, data=new_data)


@user_bp.route('/')
@login_required
def index():
    """ Главная страница """
    results.reload()
    return render_template('index.html')


@user_bp.route('/task/<code>/')
@login_required
def task_view(code):
    """ Страница задачи """
    if code not in tasks:
        abort(404)
    results.reload()
    task = tasks[code]
    user_result = tasks.get_results(code, session['username'])

    # Количество отправок
    count = 0
    for ur in user_result:
        if ur.get('compilation') != 'OK':
            continue
        preliminary = ur.get('preliminary')
        if not isinstance(preliminary, dict):
            continue
        passed = True
        for sample, verdict in preliminary.items():
            if verdict != 'OK':
                passed = False
                break
        if not passed:
            continue
        count += 1

    # import pdb; pdb.set_trace()
    return render_template('task.html', code=code, task=task, languages=languages, results=user_result, count=count)


@user_bp.route('/task_results/<code>/<attempt>')
@login_required
def task_results(code, attempt):
    """ Результаты попытки
    :param code: Код задачи
    :param attempt: Номер попытки
    :return: Веб-страница
    """
    username = session['username']
    user_result = tasks.get_results(code, username, attempt)[0]
    if 'results' not in user_result:
        print('INVALID RESULTS:',code, username, attempt)
    task = tasks[code]

    # Подсчет итогов (общих и по подзадачам)
    total = 0
    totals = {}
    for key, values in user_result['results'].items():
        # Просмотрим очередную подзадачу
        test_suite = task.test_suites[key]

        if test_suite.scoring == 'entire':
            # Если подзадача оценивается по принципу "все или ничего"
            correct = all([v == 'OK' for v in values.values()])
            totals[key] = test_suite.total_score if correct else 0

        elif test_suite.scoring == 'partial':
            # Если подзадача оценивается пропорционально
            correct = [test_suite.test_score for v in values.values() if v == 'OK']
            totals[key] = sum(correct)

        # required = test_suite.get('required', [])
        # skip = False
        # for r in required:
        #     correct = all([test['result'] == 'OK' for test in user_result['results'][r]])
        #     if not correct:
        #         skip = True
        # if skip:
        #     totals[key] = 0

        # Общий итог
        total += totals.get(key, 0)

    return render_template('task_results.html', code=code, attempt=attempt, results=user_result, totals=totals,
                           total=total)


@user_bp.route("/task_submission/<code>", methods=('POST',))
@login_required
def task_submission(code):
    """ Страница обработки полученного решения
    :param code: Код задачи
    """
    if code not in tasks:
        abort(404)

    # Если решение отправлено после окончения тура
    if datetime.now() > settings.end_time:
        return render_template('game_over.html', code=code)

    lang_code = request.form.get('language')
    if lang_code not in languages:
        abort(404)

    # Номер новой попытки
    username = session['username']
    session['last_language'] = lang_code
    user_result = tasks.get_results(code, username)
    attempt = str(len(user_result) + 1).strip()

    # Сохраним файл с попыткой в очереди
    textarea_source = request.form.get('source', '')

    attempt_filename = "{}-{}-{}-{}".format(code, username, lang_code, attempt)
    attempt_file = request.files['file']
    if (textarea_source.strip()):
        open(join(settings.work_dir, '.queue', attempt_filename), "w", encoding="windows-1251").write(textarea_source)
    else:
        attempt_file.save(join(settings.work_dir, '.queue', attempt_filename))

    # Создаем новый пустой файл с результатом, чтобы поддерживать правильную нумерацию попыток
    results_filename = '{}-{}-{}.json'.format(code, username, attempt)
    save_json({}, results_filename, join(settings.work_dir, '.results'))

    return render_template('waiting.html', code=code)


@user_bp.route('/statement/')
@login_required
def statement():
    if 'statement_file' not in settings:
        abort(404)
    from flask import send_from_directory
    return send_from_directory(directory=settings.work_dir,
                               filename=settings['statement_file'],
                               as_attachment=True)


@user_bp.route('/results/')
@login_required
def get_total_results():
    if not settings.show_results:
        abort(404)

    columns = ['rank', 'name', 'tasks', 'total_maximum_points']
    # columns = ['rank', 'short_name', 'tasks', 'total_accepts', 'total_penalty_time']
    results.reload()
    return render_template('results.html', rows=results.frozen_rows, cells=results.frozen_cells,
                           columns=columns)


@user_bp.route('/show_results/')
def show_results():
    """ Страница общих результатов """
    columns = ['rank', 'user', 'region', 'name', 'tasks', 'total_maximum_points']
    results.reload()
    return render_template('show_results.html', rows=results.rows, cells=results.cells, columns=columns)


@user_bp.route('/show_test/<code>/<key>/<test>')
def show_test(code, key, test):
    """ Страница показа теста """
    print(code, test)
    if code not in tasks:
        abort(404)
    if len(test)>4 or '.a' in test or '..' in code or '..' in key or '..' in test or '/' in code+key+test:
        abort(404)
    test_path = join(settings.work_dir, code, 'tests', key, test)
    print(test_path)
    if not isfile(test_path):
        abort(404)
    text = open(test_path, "r", encoding='windows-1251').read(200)
    cut_msg = "(первые 200 символов)" if len(text) == 200 else  ""

    return render_template('show_test.html', code=code, test=test, text=text, cut_msg=cut_msg)
