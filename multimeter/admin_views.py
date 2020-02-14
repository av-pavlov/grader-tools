import os
from functools import reduce
from os.path import join

from flask import Blueprint, session, url_for, redirect, request, render_template, abort

from multimeter import users, settings, tasks, set_config_param, languages, results
from .helpers import admin_required, moment, results_dir, load_json, save_json

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin/login/', methods=('GET', 'POST'))
def admin_login():
    """ Страница авторизации администратора системы """
    if 'admin' in session:
        return redirect(request.form.get('next', url_for('admin.admin_index')))
    message = None
    if request.method == 'POST':
        if request.form['password'] == settings.password:
            session['admin'] = True
            return redirect(request.form.get('next', url_for('admin.admin_index')))
        else:
            message = 'Неправильный пароль'
    return render_template('admin_login.html', message=message)


@admin_bp.route('/admin/logout/')
def admin_logout():
    """ Выход администратора из системы """
    session.pop('admin', None)
    return redirect(url_for('admin.admin_login'))


@admin_bp.route('/admin/', methods=('GET', 'POST'))
@admin_required
def admin_index():
    """ Главная страница интерфейса администратора """
    message = ''
    if request.method == 'POST':
        if 'title' in request.form:  # Изменение заголовка системы
            message += set_config_param('title', request.form['title'])

        if 'statement_file' in request.form:
            message += set_config_param('statement_file', request.form['statement_file'])

        if 'password' in request.form:
            message += set_config_param('password', request.form['password'])

        if 'start_time' in request.form:
            try:
                message += set_config_param('start_time', moment(request.form['start_time'].replace(' ', 'T')))
            except ValueError:
                message += '<br>Ошибка в формате даты и времени. Правильный формат: ГГГГ-ММ-ДД чч:мм:сс'

        if 'freeze_time' in request.form:
            try:
                message += set_config_param('freeze_time', moment(request.form['freeze_time'].replace(' ', 'T')))
            except ValueError:
                message += '<br>Ошибка в формате даты и времени. Правильный формат: ГГГГ-ММ-ДД чч:мм:сс'

        if 'end_time' in request.form:
            try:
                message += set_config_param('end_time', moment(request.form['end_time'].replace(' ', 'T')))
            except ValueError:
                message += '<br>Ошибка в формате даты и времени. Правильный формат: ГГГГ-ММ-ДД чч:мм:сс'

        if 'registration' in request.form:  # Включение / отключение регистрации
            message += set_config_param('registration_enabled', request.form['registration'] == 'enabled')

        if 'show_results' in request.form:  # Включение / отключение отображения общих результатов пользователям
            message += set_config_param('show_results', request.form['show_results'] == 'show')

        if 'testing' in request.form:  # ???
            message += set_config_param('testing', request.form['testing'])

    # hostname = socket.gethostname()
    # addresses = socket.getaddrinfo(hostname, settings.port)
    # addresses = [a[4] for a in addresses if a[0] == socket.AF_INET]
    return render_template('admin_index.html', message=message[4:])


@admin_bp.route("/admin/tasks/", methods=('GET', 'POST'))
@admin_required
def admin_tasks():
    """ Список заданий """
    if request.method == 'POST':
        code = request.form.get('code', '')
        if code in tasks:
            del (tasks[code])
            tasks.save()
    return render_template('admin_tasks.html', codes=sorted(tasks.keys()))


@admin_bp.route("/admin/task/", methods=('GET', 'POST'))
@admin_bp.route("/admin/task/<code>", methods=('GET', 'POST'))
@admin_required
def admin_task(code=None):
    """ Страница редактирования задания
    :param code: Код задачи
    """
    errors = []
    if code is None:
        new_code = ''
        new_data = {'tests': {}}
    else:
        if code not in tasks:
            abort(404)
        new_code = code
        new_data = tasks[code]
    if request.method == 'POST':
        new_code = request.form.get('code', '')
        new_data = dict(
            name=request.form.get('name', ''),
            brief_name=request.form.get('brief_name', ''),
            statement=request.form.get('statement', ''),
            test_suites={},
        )
        # for key, value in request.form.items():
        #     if key[:8] == 'filename':
        #         new_data['tests'][value] = int(request.form['score' + key[8:]])
        errors = tasks.validate_task(new_code, new_data, code != new_code)
        if not errors:
            tasks[new_code] = new_data
            if code is not None and code != new_code:
                del (tasks[code])
            save_json(tasks.tasks, join(settings.work_dir))
            return redirect(url_for('admin.admin_tasks'))
    return render_template('admin_task.html', errors=errors, code=new_code, data=new_data)


@admin_bp.route('/admin/users/', methods=('GET', 'POST'))
@admin_required
def admin_users():
    """ Список пользователей системы """
    if request.method == 'POST':
        username = request.form.get('username', '')
        if username in users:
            del (users[username])
            users.save()
    return render_template('admin_users.html', usernames=sorted(users.keys()))


@admin_bp.route('/admin/user/', methods=('GET', 'POST'), defaults={'username': None})
@admin_bp.route('/admin/user/<username>/', methods=('GET', 'POST'))
@admin_required
def admin_user(username=None):
    """ Редактирование пользователя администратором
    :param username: Имя пользователя
    """
    errors = []
    if username is None:
        new_name = ''
        new_data = {}
    else:
        if username not in users:
            abort(404)
        new_name = username
        new_data = users[username]
    if request.method == 'POST':
        new_name = request.form.get('username', '')
        new_data = dict(password=request.form.get('password', ''))
        for attr in settings.users_attributes:
            new_data[attr] = request.form.get(attr, '')
        errors = users.validate_user(new_name, new_data, new_data['password'], username != new_name)
        if not errors:
            users[new_name] = new_data
            if username is not None and username != new_name:
                del (users[username])
            users.save()
            return redirect(url_for('admin.admin_users'))
    return render_template('admin_user.html', errors=errors, username=new_name, data=new_data)


@admin_bp.route('/admin/languages/', methods=('GET', 'POST'))
@admin_required
def admin_languages():
    """ Список языков программирования """
    if request.method == 'POST':
        action = request.form.get('action', '')
        if action == 'delete':
            code = request.form.get('code', '')
            if code in languages:
                del (languages[code])
                languages.save()
        if action == 'autodiscover':
            languages.autodiscover()
            languages.save()

    return render_template('admin_languages.html', languages=languages)


@admin_bp.route('/admin/language/', methods=('GET', 'POST'))
@admin_bp.route('/admin/language/<code>/', methods=('GET', 'POST'))
@admin_required
def admin_language(code=''):
    """ Страница редактирования языка программирования
    :param code:
    """
    errors = []
    if code == '':
        cur_data = {}
    elif code not in languages:
        cur_data = {}
        abort(404)
    else:
        cur_data = languages[code]
    if request.method == 'POST':
        new_code = request.form.get('code', '')
        new_data = dict(
            name=request.form.get('name', ''),
            extension=request.form.get('extension', ''),
            execution=request.form.get('execution', ''),
            compilation=request.form.get('compilation', '').splitlines(),
        )
        errors = languages.validate(new_code, new_data, code != new_code)
        if not errors:
            languages[new_code] = new_data
            if code != '' and code != new_code:
                del (languages[code])
            languages.save()
            return redirect(url_for('admin.admin_languages'))
    return render_template('admin_language.html', code=code, data=cur_data, errors=errors)


@admin_bp.route('/admin/results/')
@admin_required
def admin_results():
    """ Страница общих результатов """
    columns = ['rank', 'name', 'tasks', 'total_maximum_points']
    # columns = ['rank', 'name', 'tasks', 'total_accepts', 'total_penalty_time']
    results.reload()
    return render_template('admin_results.html', rows=results.rows, cells=results.cells, columns=columns)


@admin_bp.route('/admin/results_xml/')
@admin_required
def admin_results_xml():
    """ Страница общих результатов """
    context_results = {}
    for user in users:
        res = {'first_name': users[user].get('first_name', ''),
               'last_name': users[user].get('last_name', ''),
               'second_name': users[user].get('second_name', ''),
               'birthday': users[user].get('birthday', ''),
               'teacher': users[user].get('teacher', ''),
               'school': users[user].get('school', ''),
               'class': users[user].get('class', '')}
        for task in tasks.keys():
            res[task] = 0
        context_results[user] = res

    directory = results_dir(settings)
    for filename in os.listdir(directory):
        if filename[-5:] != '.json':
            continue
        name = filename[:-5]
        (task_code, username, attempt) = name.split('-')
        res = load_json(filename, {}, directory)
        if 'results' not in res:
            continue
        task = tasks[task_code]
        total = 0
        for key, values in res['results'].items():
            task_settings = task['test_suites'][key]
            if task_settings['scoring'] == 'entire':
                total += reduce(lambda a, b: a if b['result'] == 'OK' else 0, values, task_settings['total_score'])
            elif task_settings['scoring'] == 'partial':
                total += reduce(lambda a, b: a + task_settings['test_score'] if b['result'] == 'OK' else a, values, 0)
        if context_results[username][task_code] < total:
            context_results[username][task_code] = total

    ratings = []
    for user, res in context_results.items():
        total = 0
        for task in tasks.keys():
            total += res[task]
        ratings.append({
            "user": user,
            "total": total
        })

    ratings = sorted(ratings, key=lambda element: element['total'], reverse=True)
    totals = sorted(set([r['total'] for r in ratings] + [0, 0, 0]), reverse=True)
    cups = dict(zip(totals[:3], ["I", "II", "III"]))

    context = dict(
        tasks_num=len(tasks),
        results=context_results,
        codes=sorted(tasks.keys()),
        ratings=ratings,
        cups=cups
    )

    from flask import make_response
    response = make_response(render_template('results.xml', **context))
    response.headers['Content-Disposition'] = "attachment; filename=results.xml"
    response.headers['Content-Type'] = "application/vnd.ms-excel"
    return response
