# -*- coding: utf-8 -*-
import codecs
import collections
import json
import os
import re
import logging
from datetime import datetime
from os.path import join

from flask import url_for, request, session, redirect

ISO_DATETIME = '%Y-%m-%dT%H:%M:%S'
FAR_FUTURE = '2100-01-01T00:00:00'


def log_setup(work_dir, filename="arbiter.log"):
    try:
        log_file = logging.FileHandler(join(work_dir, filename))
        if filename=='arbiter.log':
            time_fmt = logging.Formatter("%(asctime)s [%(filename)s:%(lineno)s:%(funcName)s()]: %(message)s")
        else:
            time_fmt = logging.Formatter(" - - [%(asctime)s] %(message)s")
        time_fmt.default_msec_format = "%s.%.01s"
        log_file.setFormatter(time_fmt)

        log_cout = logging.StreamHandler()
        log_cout.setLevel(logging.INFO)

        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s: %(message)s',
                            datefmt='%a %d %b %H:%M:%S',
                            handlers=(log_cout, log_file))

    except OSError:
        print("Error: CANNOT OPEN LOG FILE: {}/{}".format(work_dir, filename))


def check_or_create_dir(directory_name):
    """ Проверка или создание каталога
    :param directory_name: Путь к каталогу
    """
    if not os.path.isdir(directory_name):
        if os.path.exists(directory_name):
            os.remove(directory_name)
        logging.debug("Creating dir: " + directory_name)
        os.mkdir(directory_name)


def load_json(filename, default=None, directory=None):
    """ Загрузка данных из JSON-файла
    :param filename: Имя файла JSON или полный путь к нему
    :param default: Значение по умолчанию, используется если файл не найден
    :param directory: Каталог с JSON-файлом
    """
    data = default
    try:
        if directory:
            filename = join(directory, filename)
        raw_file = open(filename, 'rb').read()
        if raw_file.startswith(codecs.BOM_UTF8):
            data_file = open(filename, mode='wb')
            data_file.write(raw_file.decode("utf-8-sig").encode("utf-8"))
            data_file.close()
        data_file = open(filename, encoding='UTF-8')
        data = json.load(data_file, object_pairs_hook=collections.OrderedDict)
        data_file.close()
    except FileNotFoundError:
        if default is None:
            print('File {} not found'.format(filename))
            raise FileNotFoundError
    except ValueError:
        if default is None:
            print('File {} is corrupted'.format(filename))
            raise ValueError
    return data


def save_json(data, filename, directory=None):
    """ Сохранение данных в конфигурационный файл
    :param data: Данные для сохранения
    :param filename: Имя файла JSON или полный путь к нему
    :param directory: Каталог с JSON-файлом
    """
    if directory:
        filename = join(directory, filename)
    data_file = open(filename, mode='w', encoding='UTF-8')
    json.dump(data, data_file, ensure_ascii=False, indent='\t')
    data_file.close()


def moment(str_datetime):
    return datetime.strptime(str_datetime, ISO_DATETIME)


def validate_code(code, codes_list, codename='Код'):
    """ Проверка кода
    :param code:
    :param codes_list:
    :param codename:
    """
    errors = []
    if code == '':
        errors.append(codename + ' не задан')
    if len(code) > 20:
        errors.append(codename + ' не может быть длиннее 20 символов')
    if re.match('^[0-9A-Z_a-z]*$', code) is None:
        errors.append(codename + ' должен состоять из латинских букв, цифр и символов подчеркивания')
    if code in codes_list:
        errors.append(codename + ' уже существует')
    return errors


def results_dir(settings):
    try:
        work_dir = settings.work_dir
    except AttributeError:
        work_dir = settings.config['WORK']
    return join(work_dir, '.results')


def queue_dir(app):
    return join(app.config['WORK'], '.queue')


def admin_required(f):
    """
     Декоратор обязательной авторизации администратора
    :param f: Функция, генерирующая страницу для авторизированных пользователей
    """
    from functools import wraps

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            next_path = request.path if request.path != url_for('admin.admin_login') else ''
            return redirect(url_for('admin.admin_login', next=next_path))
        return f(*args, **kwargs)

    return decorated_function


def get_value(container, key, required_class, default):
    if key in container:
        value = container[key]
        if isinstance(value, str) and required_class == int:
            value = int(value)
        elif isinstance(value, str) and required_class == datetime:
            value = datetime.strptime(value, ISO_DATETIME)
        if isinstance(value, required_class):
            return value
    return default


def load_tests(directory):
    """
    Чтение тестов из каталога
    Имя входного файла теста не должно содержать точек
    Каждому входному файлу должен соответствовать выходной файл
    Имя выходного файла получается добавлением суффикса ".a"
    :param directory: каталог
    :return: список имен файлов
    """
    try:
        names = list(os.listdir(directory))
    except FileNotFoundError:
        return []
    inputs = set(filter(lambda name: '.' not in name, names))
    outputs = filter(lambda name: name.endswith('.a'), names)
    outputs = set(map(lambda name: name[:-2], outputs))
    return sorted(list(inputs & outputs))  # Stay back! I know kung fu!


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]
