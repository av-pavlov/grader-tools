# -*- coding: utf-8 -*-

""" Проверка задачи на тестах из папки, запись результатов в файл """

import os, shutil, sys, time, logging, glob, re, datetime
from argparse import ArgumentParser
from collections import OrderedDict

from multimeter._tasks import Task
from ctypes import CDLL, c_char_p, c_uint, byref

DEFAULT_SOLUTION_MASK = 'Debug/*.exe'

cfg = {}
invoker = None


class ArbiterError(Exception):
    pass


def logsetup():
    """ Настройка логирования"""
    try:
        log_cout = logging.StreamHandler()
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s: %(levelname)s: %(message)s',
                            datefmt='%a %d/%m %H:%M:%S',
                            handlers=(log_cout,))
    except Exception as error:
        print("ERROR setting up loggers:", error.args[0])
        raise ArbiterError('FL')

def argparse():
    """ Установка параметров командной строки """
    try:
        parser = ArgumentParser(description='Арбитр для проверки задач по программированию')
        parser.add_argument('-w', '--workdir', default='.', 
                            type=str, help='рабочий каталог, по умолчанию текущий каталог')
        parser.add_argument('-t', '--testdir', default='test', 
                            type=str, help='каталог с тестами, по умолчанию test в рабочем каталоге')
        parser.add_argument('-r', '--resultsdir', default='.', 
                            type=str, help='каталог для записи результатов, по умолчанию рабочий')
        parser.add_argument('-s', '--solution', default=DEFAULT_SOLUTION_MASK, 
                            type=str, help='исполняемый файл для тестирования, по умолчанию ищет в Debug в рабочем каталоге')
        return vars(parser.parse_args())
    except Exception as error:
        logging.error(f'Не удалось прочесть аргументы командной строки: {error.args[0]}')
        raise ArbiterError('FL') from None

def check_writable(directory):
    """ Проверка, что в каталог с конфиг-названием directory можно писать """
    global cfg
    try:
        fn = os.path.join(cfg[directory], '###qqq@@.json')
        open(fn, 'w').close()
        os.remove(fn)
    except OSError as error:
        logging.error(f'Не удалась попытка записи в {directory}-каталог "{cfg[directory]}"!!!')
        raise ArbiterError('FL') from None

def check_dirs():
    """ проверка наличия и доступности всех каталогов"""
    global cfg
    for _ in ('workdir', 'testdir', 'resultsdir'):
        base_dir = os.getcwd() if _=='workdir' else cfg['workdir']
        directory = cfg[_] = os.path.join(base_dir, cfg[_])
        if not os.path.isdir(directory):
            logging.error(f'Не удалось найти {_}-каталог "{directory}"!!!')
            raise ArbiterError('FL')

    try:
        os.chdir(cfg['workdir'])
    except OSError as error:
        logging.error(f'Не удалось войти в рабочий каталог: "{cfg["workdir"]}"!!!')
        raise ArbiterError('FL') from None

    check_writable('workdir')
    check_writable('resultsdir')

def check_solution_exists():
    """ Проверка наличия файла решений """
    global cfg
    fn = None
    msg = 'Solution file not found!'
    if cfg['solution'] == DEFAULT_SOLUTION_MASK:
        fn = glob.glob(os.path.join(cfg['workdir'], DEFAULT_SOLUTION_MASK))
        if len(fn) == 1:
            fn = fn[0]
        else:
            msg = 'Если файл решения не указан явно, он должен быть единственным exe-файлом в каталоге Debug!'
            fn = None
    else:
        fn = os.path.join(cfg['workdir'], cfg['solution'])
    if not (fn and os.path.isfile(fn)):
        logging.error(msg)
        raise ArbiterError('FL')
    cfg['solution'] = fn

def check_checker_exists():
    """ Проверка наличия файла решений """
    global cfg
    fn = os.path.join(cfg['testdir'], 'check.exe')
    if not os.path.isfile(fn):
        logging.error('Чекер должен находиться в папке с тестами и называться check.exe')
        raise ArbiterError('FL')
    cfg['checker'] = fn

def check_invoker_exists():
    """ Проверка наличия invoker.dll """
    global cfg, invoker
    dllpath = os.path.abspath(os.path.join(cfg['checktoolsdir'], 'invoker.dll'))
    if not os.path.isfile(dllpath):
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не найдена!')
        raise ArbiterError('FL')
    try:
        invoker = CDLL(dllpath)
    except OSError:
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не может быть загружена!')
        raise ArbiterError('FL') from None


class PatchedTask(Task):
    @property
    def checker(self):
        global cfg
        return cfg['checker']


def cleanup(task):
    """ Очистка старых выходных данных перед запуском """
    global cfg
    cleanup_list = glob.glob(os.path.join(cfg['testdir'], '*.o'))
    while cleanup_list:
        filename = cleanup_list.pop()
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass
        except PermissionError:
            logging.error('Не могу удалить файл выходных данных задачи: ' + filename)
            sys.exit(2)

def execute(task):
    global cfg
    answer = '??'
    try:
        executable = cfg['solution']
        executable = c_char_p(executable.encode('utf-8'))
        input_file = c_char_p(task.input_file.encode('utf-8'))
        output_file = c_char_p(b'stdout')
        memory_limit = c_uint(0)
        time_limit = c_uint(int(1000 * task.timeout))

        invoker.console(executable, input_file, output_file, byref(memory_limit), byref(time_limit))

        if memory_limit.value > task.memory_limit * 1024 * 1024:
            answer = 'ML'
        elif time_limit.value > task.time_limit * 1000:
            answer = 'TL'
        else:
            answer = 'OK'
    except subprocess.CalledProcessError:
        answer = 'RE'  # Runtime error
    except OSError:
        answer = 'RE'  # Runtime error
    except subprocess.TimeoutExpired:
        if sys.getwindowsversion().major > 5:
            subprocess.call("TaskKill /IM {}.exe /F".format(solution))
        else:
            subprocess.call("tskill {}".format(solution))  # Windows XP
        answer = 'TL'  # Time Limit Exceeded
    finally:
        return answer

def check_solution():
    """ Проверка решения """
    global cfg
    answer = {
        "datetime": datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        "language": "VisualCppLang",
        "compilation": "FL",
        "results": OrderedDict()
    }

    code = re.sub('[^A-Za-z0-9_.]', '' , os.path.basename(cfg['workdir']))
    task = PatchedTask(code, cfg['workdir'])

    logging.info("Переходим в рабочий каталог " + cfg['workdir'])
    os.chdir(cfg['workdir'])

    # Проверка на тестах
    results = []
    testmask = os.path.join(cfg['testdir'], '??')
    tests = sorted([os.path.basename(fn) for fn in glob.glob(testmask)])
    logging.info("Найдены тесты: "+' '.join(tests))
    suite_key = '.' # на будущее мб папки для позадач
    answer['results'][suite_key] = OrderedDict()
    for test in tests:
        test_file = os.path.join(cfg['testdir'], suite_key, test)
        shutil.copy(test_file, task.input_file)
        logging.info(f'Запуск на тесте {test}:')
        execution_verdict = execute(task)
        if execution_verdict != 'OK':
            verdict = execution_verdict
        else:
            shutil.copy(test_file + '.a', 'answer.txt')
            verdict = task.check()
        answer['results'][suite_key][test] = verdict
        cleanup(task)
        logging.info(f'{test}: {verdict}')

    return answer


if __name__ == '__main__':
    logsetup()
    cfg = argparse()
    cfg['checktoolsdir'] = os.path.split(os.path.abspath(__loader__.path))[0]    
    check_dirs()
    check_checker_exists()
    check_solution_exists()
    check_invoker_exists()
    logging.info("Arbiter started.")
    check_solution()
