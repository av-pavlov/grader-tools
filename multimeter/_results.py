# -*- coding: utf-8 -*=
import os
from datetime import datetime
from os.path import join
from multimeter.helpers import load_json, get_value, check_or_create_dir


def sort_rows(rows):
    # Сортировка строк
    rows.sort(
        key=lambda cur_row: (-cur_row['total_maximum_points'], cur_row['total_penalty_time'], cur_row['name']))
    rank = 1
    for row in rows:
        row['rank'] = rank
        rank += 1
    # по фио
    rows.sort(key=lambda r:r['name'])


class Result:
    def __init__(self, filename, attempt):
        cur_result = load_json(filename)
        if cur_result is None or len(cur_result) == 0:
            raise TypeError

        self.attempt = attempt
        self.compilation = get_value(cur_result, 'compilation', str, '')
        self.datetime = get_value(cur_result, 'datetime', datetime, datetime(1, 1, 1))
        self.language = get_value(cur_result, 'language', str, '')
        self.preliminary = get_value(cur_result, 'preliminary', list, list())
        self.results = get_value(cur_result, 'results', dict, dict())
        self.revealed = get_value(cur_result, 'revealed', bool, False)
        self.total = get_value(cur_result, 'total', int, 0)

    def __getattr__(self, item):
        return self.__dict__.get(item)

    def __getitem__(self, item):
        return self.__dict__.get(item)


class Results:
    """ Результаты участников """

    def __init__(self, results_dir, tasks, users, settings):
        """ Конструктор
        :return: None
        """
        self.cols = list()
        self.rows = list()
        self.frozen_rows = list()
        self.cells = dict()
        self.frozen_cells = dict()
        self.freeze_time = ''
        self.results_dir = results_dir
        self.settings = settings
        self.tasks = tasks
        self.users = users
        self.results = {u: {} for u in self.users }
        self.reload()

    def reload(self):
        """ Чтение и анализ результатов участников
        :return: None
        """
        check_or_create_dir(self.results_dir)
        for filename in os.listdir(self.results_dir):
            if filename[-5:] != '.json':
                continue

            try:
                (task, user, attempt) = filename[:-5].split('-')
                attempt = int(attempt)
                if user not in self.users:
                    raise ValueError
                if task not in self.tasks:
                    raise ValueError
            except ValueError:
                print('Cannot parse results filename "{filename}" in {results_dir}'
                      .format(filename=filename, results_dir=self.results_dir))
                continue

            if user not in self.results:
                self.results[user] = {}

            if task not in self.results[user]:
                self.results[user][task] = []

            if attempt not in [res['attempt'] for res in self.results[user][task]]:
                try:
                    cur_result = Result(join(self.results_dir, filename), attempt)
                    self.results[user][task].append(cur_result)
                except TypeError:
                    pass

        self.sort_attempts()
        self.cells = self.calculate_cells(False)
        self.rows = self.calculate_rows(self.cells)
        sort_rows(self.rows)
        self.frozen_cells = self.calculate_cells(True)
        self.frozen_rows = self.calculate_rows(self.frozen_cells)
        sort_rows(self.frozen_rows)

    def sort_attempts(self):
        """ Сортировка попыток пользователя по заданию
        :return: None
        """
        for user in self.results:
            for task in self.results[user]:
                self.results[user][task].sort(key=lambda result: result['attempt'])

    def calculate_cells(self, frozen, users=[]):
        """ Расчет значений для ячеек таблицы результатов
        :param frozen:
        :return: None
        """
        start_time = self.settings['start_time']
        cells = {}
        for user, user_results in self.results.items():
            cells[user] = {}
            for task, task_data in user_results.items():
                cur_cell = cells[user][task] = {
                    'penalty_time': 0,  # Штрафное время
                    'maximum_points': 0,  # Максимальный балл
                    'last_points': 0,  # Последний балл
                    'accepted': False,  # Принята ли задача
                    'attempts': 0,  # Количество попыток
                    'attempts_before_accept': 0,  # Количество попыток до успешного решения
                    'accept_time': 0,  # Время успешного решения
                }
                for attempt in task_data:
                    if frozen and attempt['datetime'] > self.settings['freeze_time']:
                        continue

                    if cur_cell['maximum_points'] < attempt['total']:
                        cur_cell['maximum_points'] = attempt['total']

                    cur_cell['last_points'] = attempt['total']

                    if not cur_cell['accepted']:
                        if attempt['total'] >= 100:
                            time_passed = attempt['datetime'] - start_time
                            cur_cell['penalty_time'] = cur_cell['accept_time'] = int(time_passed.total_seconds()) // 60
                            cur_cell['penalty_time'] += cur_cell['attempts_before_accept'] * 20
                            cur_cell['accepted'] = True
                        else:
                            cur_cell['attempts_before_accept'] += 1

                    cur_cell['attempts'] += 1
        return cells

    def calculate_rows(self, cells):
        """ Расчет значений для строк таблицы результатов
        :param cells:
        :return:
        """
        rows = []
        for user, user_results in cells.items():
            cur_row = {
                'user': user,
                'region': self.users[user].get('region', ''),
                'name': self.users[user].get('last_name', '')
                + ' ' + self.users[user].get('first_name', '')
                + ' ' + self.users[user].get('middle_name', ''),
                'total_penalty_time': 0,  # Общее штрафное время
                'total_maximum_points': 0,  # Сумма максимальных баллов
                'total_attempts_before_accept': 0,  # Сумма максимальных баллов
                'total_accepts': 0,
            }
            for task, task_data in user_results.items():
                cur_row['total_penalty_time'] += task_data['penalty_time']
                cur_row['total_maximum_points'] += task_data['maximum_points']
                cur_row['total_attempts_before_accept'] += task_data['attempts_before_accept']
                cur_row['total_accepts'] += 1 if task_data['accepted'] else 0
            rows.append(cur_row)

        rows.sort(key=lambda r: r['name'])
        return rows
