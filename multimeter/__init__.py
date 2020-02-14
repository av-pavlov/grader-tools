# -*- coding: utf-8 -*=
from flask import session, request, url_for, redirect

from ._languages import Languages
from ._results import Results
from ._settings import Settings
from ._tasks import Tasks
from ._users import Users
from .helpers import load_json, results_dir, moment, queue_dir, save_json, validate_code, admin_required


settings = Settings()
languages = Languages(settings.work_dir)
tasks = Tasks(settings, languages)
users = Users(settings)
results = Results(results_dir(settings), tasks, users, settings)


def login_required(f):
    """
    Декоратор обязательной авторизации пользователей
    :param f: Функция, генерирующая страницу для авторизированных пользователей
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session or session['username'] not in users:
            next_path = request.path if request.path != url_for('multimeter.login') else ''
            return redirect(url_for('multimeter.login', next=next_path))
        return f(*args, **kwargs)

    return decorated_function


def set_config_param(param, value):
    """ Установка параметров конфигурации системы
    :param value:
    :param param:
    """
    settings[param] = value
    settings.save()
    return '<br>Данные успешно сохранены'
