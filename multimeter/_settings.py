# -*- coding: utf-8 -*=
import os
import sys
from argparse import ArgumentParser
from datetime import datetime

from collections import OrderedDict
from multimeter.helpers import load_json, get_value, save_json


class Settings:
    def __init__(self, work=None):
        # Значения по умолчанию
        self.start_time = datetime(1, 1, 1)  # время начала олимпиады
        self.freeze_time = datetime(2100, 1, 1)  # время заморозки таблицы результатов
        self.end_time = datetime(2100, 1, 1)  # время завершения олимпиады
        self.password = ''  # пароль администратора
        self.registration_enabled = False  # регистрация пользователей
        self.show_results = False  # показывать результаты участникам
        self.statement_file = ''  # файл с результатами
        self.title = ''  # заголовок системы
        self.users_attributes = OrderedDict()  # дополнительные атрибуты пользователей
        self.results_format = 'individual'  # индивидуальный / командный режим выдачи результатов

        # Запуск из тестов
        self.port = 80  # номер TCP-порта для входящих соединений
        self.work = '' if not work else work  # рабочий каталог
        self.waitress = False  # запуск в сервера режиме Waitress
        self.development = False  # отладочный режим
        self.url_prefix = ''  # префикс URL

        if sys.argv[0][-9:].lower() == 'server.py' or sys.argv[0][-10:].lower() == 'arbiter.py':
            # Разбор параметров командной строки
            parser = ArgumentParser(description='Веб-сервер для проверки олимпиадных задач по программированию')
            parser.add_argument('-p', '--port', default=80, type=int, help="номер TCP-порта для входящих соединений")
            parser.add_argument('-w', '--work', default='work', type=str, help="рабочий каталог")
            parser.add_argument('-ws', '--waitress', action="store_true", help="запуск сервера в режиме Waitress")
            parser.add_argument('-d', '--development', action="store_true", help="отладочный режим")
            parser.add_argument('-up', '--url_prefix', default='', help="префикс URL")
            parser.parse_args(namespace=self)
            if self.url_prefix and not self.url_prefix.startswith('/'):
                self.url_prefix = '/' + self.url_prefix

        self.work_dir = os.path.join(os.getcwd(), self.work)  # Рабочий каталог
        self.load()

    def __setitem__(self, key, value):
        self.__dict__[key] = value

    def __getitem__(self, item):
        return self.__dict__.get(item, None)

    def __contains__(self, item):
        return item in self.__dict__

    def load(self):
        settings = load_json('settings.json', {}, self.work_dir)
        attr_types = {"start_time": datetime, "freeze_time": datetime,  "end_time": datetime,
                      "registration_enabled": bool, "show_results": bool,
                      "users_attributes": OrderedDict}
        for key, val in settings.items():
            attr_type = attr_types.get(key, str)
            attr_value = attr_type(val) if attr_type != datetime else datetime(1,1,1)
            setattr(self, key, get_value(settings, key, attr_type, attr_value if attr_value else attr_type()))
        self.results_format = get_value(settings, 'results_format', str, 'individual')

    def save(self):
        settings = dict(
            start_time=self.start_time.isoformat(),
            freeze_time=self.freeze_time.isoformat(),
            end_time=self.end_time.isoformat(),
            password=self   .password,
            registration_enabled=self.registration_enabled,
            show_results=self.show_results,
            statement_file=self.statement_file,
            title=self.title,
            users_attributes=self.users_attributes,
            results_format=self.results_format
        )
        save_json(settings, 'settings.json', self.work_dir)
