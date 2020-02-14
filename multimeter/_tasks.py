# -*- coding: utf-8 -*=
import sys
import subprocess
from collections import OrderedDict
from os import listdir, stat
from os.path import isdir, join, isfile

from .helpers import load_json, save_json, validate_code, check_or_create_dir, load_tests


class Tasks:
    """ Массив олимпиадных задач """

    def __init__(self, settings, languages):
        self._settings = settings
        self._languages = languages
        self.tasks = dict()
        self.load()

    def __len__(self):
        return len(self.tasks)

    def __setitem__(self, key, value):
        self.tasks[key] = value

    def __getitem__(self, item):
        return self.tasks[item]

    def __delitem__(self, key):
        del self.tasks[key]

    def __contains__(self, item):
        return item in self.tasks

    def __iter__(self):
        return self.tasks.__iter__()

    def items(self):
        return self.tasks.items()

    def keys(self):
        return sorted(self.tasks.keys())

    def load(self):
        """ Загрузить олимпиадные задачи из подкаталогов рабочего каталога """

        # Просмотрим подкаталоги рабочего каталога
        for name in listdir(self._settings.work_dir):
            path = join(self._settings.work_dir, name)
            if isdir(path) and name[0:1] != '.':
                try:
                    self.tasks[name] = Task(name, path)
                    self.tasks[name].load()
                except (TypeError, FileNotFoundError, UnicodeDecodeError):
                    # Если не удалось прочитать описание задачи - игнорируем этот подкаталог
                    pass

    def save(self):
        """ Сохранить описания олимпиадных задач в их подкаталогах """
        for task in self.tasks:
            task.save()

    def get_results(self, task_code, username, attempt=None):
        """ Получить результаты проверки решений олимпиадной задачи определенным пользователем """
        answer = []

        # Начнем просмотр файлов результатов в каталоге .results
        results_dir = join(self._settings.work_dir, '.results')
        for filename in listdir(results_dir):

            # Только только JSON-файлы
            if filename[-5:] != '.json':
                continue

            name = filename[:-5]
            (_task_code, _username, _attempt) = name.split('-')

            # Только выбранная олимпиадная задача
            if task_code != _task_code:
                continue

            # Только задачи определенного пользователя
            if username != _username:
                continue

            # Если была выбрана попытка, то нужна только определенная попытка
            if attempt is not None and attempt != _attempt:
                continue

            # Прочитаем результат проверки и добавим в номер попытки
            res = load_json(filename, {}, results_dir)
            res['attempt'] = int(_attempt)
            answer.append(res)

        import pprint; pprint.pprint(answer)

        return sorted(answer, key=lambda x: x['attempt'])

    def validate_task(self, code, data, check_uniqueness):
        """ Проверка задания
        :param check_uniqueness:
        :param data:
        :param code:
        """
        codes_list = self.tasks if check_uniqueness else []
        errors = validate_code(code, codes_list, 'Код задания')
        if not data.get('name'):
            errors.append('Наименование не задано')
        return errors


class TestSuite:
    # Стратегия отображения результатов
    BRIEF = 'brief'
    FULL = 'full'
    ERROR = 'error'
    RESULTS = (
        (BRIEF, 'Отображаются только баллы за подзадачу целом'),
        (FULL, 'Отображаются баллы за каждый тест'),
        (ERROR, 'Отображаются баллы за подзадачу в целом либо результат первой ошибки'),
    )

    # Стратегия начисления баллов
    PARTIAL = 'partial'
    ENTIRE = 'entire'
    SCORING = (
        (PARTIAL, 'Баллы начисляются пропорционально'),
        (ENTIRE, 'Подзадача оценивается как единое целое'),
    )

    task = None
    code = ''
    ts_dir = ''
    name = ''
    results = FULL
    scoring = PARTIAL
    test_score = 0
    total_score = 0
    depends = []

    def __init__(self, task, code, data):
        self.task = task
        self.code = code
        self.ts_dir = join(task.test_suites_dir, code)
        self.name = data['name']
        self.scoring = data['scoring']
        self.results = data['results']
        self.test_score = data.get('test_score', 0)
        self.total_score = data.get('total_score', 0)
        self.tests = load_tests(self.ts_dir)
        self.depends = data.get('depends', self.depends)


class Task:
    # Важные атрибуты
    code = ''  # Код
    task_dir = ''  # Каталог

    # Атрибуты из конфигурационного файла
    name = ''  # Имя
    timeout = 2.0  # Предельное время выполнения в секундах, при превышении - работа программа будет завершена
    time_limit = 1.0  # Лимит времени выполнения в секундах, при превышении - вердикт TL
    memory_limit = 256  # Лимит по количеству памяти в Мб, при превышении - вердикт ML
    input_file = 'input.txt'  # Имя выходного файла
    output_file = 'output.txt'  # Имя выходного файла

    # Атрибуты заполняемые из файлов
    statement = ''  # Условия задачи
    preliminary = []  # Список примеров для предварительной проверки решения
    test_suites = OrderedDict()  # Словарь подзадач, подзадача - это список тестов

    def __init__(self, code, task_dir):
        """
        Создание задачи по каталогу
        :param code: код задачи
        :param task_dir: каталог задачи
        """
        self.code = code
        self.task_dir = task_dir

    @property
    def brief_name(self):
        return '%s. %s' % (self.code, self.name)

    @property
    def full_name(self):
        return 'Задача %s. %s' % (self.code, self.name)

    @property
    def config_file(self):
        return join(self.task_dir, 'task.json')

    @property
    def statements_file(self):
        return join(self.task_dir, 'task.html')

    @property
    def checker(self):
        return join(self.task_dir, 'check.exe')

    @property
    def solutions_dir(self):
        return join(self.task_dir, 'solutions')

    @property
    def preliminary_dir(self):
        return join(self.task_dir, 'tests', 'samples')

    @property
    def test_suites_dir(self):
        return join(self.task_dir, 'tests')

    def load(self):
        """ Читаем описание задачи из конфигурационных файлов """

        # Загружаем атрибуты задачи из конфигурационного файла
        config = load_json(self.config_file, {})

        if 'name' in config:
            self.name = str(config['name'])

        if 'timeout' in config:
            self.timeout = float(config['timeout'])

        if 'time_limit' in config:
            self.time_limit = float(config['time_limit'])

        if 'memory_limit' in config:
            self.memory_limit = float(config['memory_limit'])

        if 'input_file' in config:
            self.input_file = str(config['input_file'])

        if 'output_file' in config:
            self.output_file = str(config['output_file'])

        if 'test_suites' in config:
            tss_from_file = config['test_suites']
            if isinstance(tss_from_file, OrderedDict):
                self.test_suites = OrderedDict()
                for code, ts in tss_from_file.items():
                    self.test_suites[code] = TestSuite(self, code, ts)

        # Загружаем условия задачи
        try:
            statement = open(self.statements_file, encoding='utf-8')
            self.statement = statement.read()
        except FileNotFoundError:
            # Если файла нет - молча ничего не делаем
            pass

        # Загружаем примеры
        self.preliminary = load_tests(self.preliminary_dir)

    def save(self):
        """ Сохранение задачи в task.json в каталоге задачи """
        keys = ['name', 'brief_name', 'timeout', 'input_file', 'output_file', 'test_suites']
        config = dict(zip(keys, [self.__dict__[k] for k in keys]))
        save_json(config, self.config_file)

        with open(self.statements_file, mode='w', encoding='utf-8') as f:
            f.write(self.statement)
            f.close()

    def verify(self):
        if not isdir(self.task_dir):
            raise Exception('Task {} folder not found: {}'.format(self.code, self.task_dir))
        check_or_create_dir(self.solutions_dir)
        check_or_create_dir(self.test_suites_dir)

        for test in self.preliminary:
            self.verify_test(test)

        total_score = 0
        for suite_code, suite in self.test_suites.items():
            if suite.scoring == TestSuite.ENTIRE:
                total_score += suite.total_score
            elif suite.scoring == TestSuite.PARTIAL:
                total_score += suite.test_score * len(suite.tests)

            for test in suite.tests:
                self.verify_test(test, suite_code)

        if total_score != 100:
            raise Exception('Sum of tests score of task {} not equal 100 !!!'.format(self.code))

    def verify_test(self, test, suite_code=None):
        """ Проверка теста
        :param test: имя теста
        :param suite_code:
        """
        if suite_code is None:
            test_name = "Preliminary test {}".format(test)
            input_file = join(self.preliminary_dir, test)
        else:
            test_name = "Test {} in {}".format(test, suite_code)
            input_file = join(self.test_suites_dir, suite_code, test)
        answer_file = input_file + '.a'
        if not isfile(input_file):
            raise Exception('{} for task {} not found !!!'.format(test_name, self.code))
        if not isfile(answer_file):
            raise Exception('{} for task {} don\'t have answer !!!'.format(test_name, self.code))

        try:
            output = subprocess.check_output(
                [self.checker, input_file, answer_file, answer_file],
                stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            raise Exception('Checker for task {} is not found !!!'.format(self.code))
        except subprocess.CalledProcessError as e:
            raise Exception('Checker for task {} is not working !!!\n{}'.format(self.code, e))

    def check(self):
        """ Проверка ответа участника """
        answer = '??'
        try:
            output_file = 'stdout'
            if isfile(self.output_file) and stat(self.output_file).st_size > 0:
                output_file = self.output_file
            subprocess.check_call([
                self.checker,
                self.input_file,
                output_file,
                'answer.txt',
            ])
            answer = 'OK'
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                answer = 'WA'  # Wrong answer
            elif error.returncode == 2:
                answer = 'PE'  # Presentation error
        finally:
            return answer
