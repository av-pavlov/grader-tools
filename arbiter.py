# -*- coding: utf-8 -*-

""" Проверка задачи на тестах из папки, запись результатов в файл """

import os, shutil, sys, time, logging, glob, re, datetime, subprocess
from os.path import abspath, basename, split as pathsplit, join as pathjoin, isfile, isdir
from argparse import ArgumentParser
from collections import OrderedDict
from ctypes import CDLL, c_char_p, c_uint, byref

from multimeter._tasks import Task

DEFAULT_SOLUTION_MASK = 'Debug/*.exe'
INPUT_FILENAME  = 'putin1.txt'
OUTPUT_FILENAME = 'putout.txt'
ANSWER_FILENAME = 'putans.txt'
TMPFILE_MASK =    'put???.txt'

cfg = {}
invoker = None


class ArbiterError(Exception):
    pass


class PatchedTask(Task):
    input_file = INPUT_FILENAME
    output_file = OUTPUT_FILENAME

    @property
    def checker(self):
        global cfg
        return cfg['checker']

    def check(self):
        """ Проверка ответа участника """
        answer = 'FL'
        try:
            subprocess.check_call([
                self.checker,
                self.input_file,
                self.output_file,
                ANSWER_FILENAME,
            ])
            answer = 'OK'
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                answer = 'WA'  # Wrong answer
            elif error.returncode == 2:
                answer = 'PE'  # Presentation error
        return answer


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
        solution = pathjoin(cfg[directory], '###qqq@@.json')
        open(solution, 'w').close()
        os.remove(solution)
    except OSError as error:
        logging.error(f'Не удалась попытка записи в {directory}-каталог "{cfg[directory]}"!!!')
        raise ArbiterError('FL') from None

def check_dirs():
    """ проверка наличия и доступности всех каталогов"""
    global cfg
    for _ in ('workdir', 'testdir', 'resultsdir'):
        base_dir = os.getcwd() if _=='workdir' else cfg['workdir']
        directory = cfg[_] = pathjoin(base_dir, cfg[_])
        if not isdir(directory):
            logging.error(f'Не удалось найти {_}-каталог "{directory}"!!!')
            raise ArbiterError('FL')
    try:
        os.chdir(cfg['workdir'])
    except OSError as error:
        logging.error(f'Не удалось войти в рабочий каталог: "{cfg["workdir"]}"!!!')
        raise ArbiterError('FL') from None

    try:
        os.chdir(cfg['testdir'])
        if not glob.glob('./??'):
            logging.error(f'Не удалось найти тесты в папке {cfg["testdir"]}, проверьте, что проект называется правильно')
            raise ArbiterError('NT')
    except OSError as error:
        logging.error(f'Не удалось войти в каталог тестов: "{cfg["testdir"]}"!!!')
        raise ArbiterError('FL') from None

    check_writable('workdir')
    check_writable('resultsdir')
    cfg['taskname'] = re.sub('[^A-Za-z0-9_.]', '' , basename(cfg['workdir']))

def check_solution_exists():
    """ Проверка наличия файла решений """
    global cfg
    solpath = pathjoin(cfg['workdir'], cfg['solution'])
    solution = None
    msg = 'Solution file not found!'
    if cfg['solution'] == DEFAULT_SOLUTION_MASK:
        fns = glob.glob(solpath)
        if len(fns) == 1:
            solution = fns[0]
        elif not fns:
            msg = f'Файл решения не найден ({solpath})'
        else:
            msg = 'Если файл решения не указан явно, он должен быть единственным exe-файлом в каталоге Debug!'
    else:
        solution = solpath
    if not (solution and isfile(solution)):
        logging.error(msg)
        raise ArbiterError('FL')
    cfg['solution'] = solution

def check_checker_exists():
    """ Проверка наличия файла решений """
    global cfg
    fn = os.path.join(cfg['testdir'], 'check.exe')
    if not os.path.isfile(fn):
        logging.error('Чекер должен находиться в папке с тестами и называться check.exe')
        raise ArbiterError('FL')
    cfg['checker'] = fn

def check_invoker_loads():
    """ Проверка наличия invoker.dll """
    global cfg, invoker
    dllpath = abspath(pathjoin(cfg['checktoolsdir'], 'invoker.dll'))
    if not isfile(dllpath):
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не найдена!')
        raise ArbiterError('FL')
    try:
        invoker = CDLL(dllpath)
    except OSError:
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не может быть загружена!')
        raise ArbiterError('FL') from None

def cleanup(task):
    """ Очистка старых выходных данных перед запуском """
    global cfg
    cleanup_list = glob.glob(pathjoin(cfg['workdir'], TMPFILE_MASK))
    while cleanup_list:
        filename = cleanup_list.pop()
        try:
            os.remove(filename)
        except FileNotFoundError:
            pass
        except PermissionError:
            logging.error('Не могу удалить временные файл(ы) теста: ' + filename)
            raise ArbiterError('FL') from None

def execute(task):
    global cfg
    answer = 'FL'

    files = [c_char_p(fn.encode('utf-8')) 
             for fn in (cfg['solution'], task.input_file, task.output_file)]
    memory_limit = c_uint(0)
    time_limit = c_uint(int(1000 * task.timeout))
        
    try:
        invoker.console(*files, byref(memory_limit), byref(time_limit))

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
    return answer

def check_solution():
    """ Проверка решения """
    global cfg
    answer = {
        'datetime': datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        'language': 'VisualCppLang',
        'compilation': 'FL',
        'results': OrderedDict()
    }
    
    task = PatchedTask(cfg['taskname'], cfg['workdir'])
    task.input_file

    logging.info('Переходим в рабочий каталог ' + cfg['workdir'])
    os.chdir(cfg['workdir'])

    # Проверка на тестах
    results = []
    testmask = pathjoin(cfg['testdir'], '??')
    tests = sorted([basename(fn) for fn in glob.glob(testmask)])
    logging.info('Найдены тесты: ' + ' '.join(tests))
    
    suite_key = '.' # на будущее мб папки для позадач
    answer['results'][suite_key] = OrderedDict()
    
    first_run_timelimit = 3
    task.time_limit, task.timeout = first_run_timelimit, 2*first_run_timelimit
    for test in tests:
        test_file = pathjoin(cfg['testdir'], suite_key, test)
        shutil.copy(test_file, task.input_file)
        execution_verdict = execute(task)
        if execution_verdict != 'OK':
            verdict = execution_verdict
        else:
            shutil.copy(test_file + '.a', ANSWER_FILENAME)
            verdict = task.check()
        answer['results'][suite_key][test] = verdict
        cleanup(task)
        logging.info(f'Тест {test}: {verdict}')
        if verdict != 'OK':
            logging.info('Останавливаю тестирование.')
            raise ArbiterError(verdict)
        task.time_limit, task.timeout = 1.5, 3
    logging.info('=== Тестирование завершено ===\nРезультаты:\n' + pprint.pformat(answer))
    return verdict

if __name__ == '__main__':
    try:
        logsetup()
        cfg = argparse()
        cfg['checktoolsdir'] = os.path.split(abspath(__loader__.path))[0]
        cfg['taskname'] = re.sub('[^A-Za-z0-9_.]', '' , basename(abspath(cfg['workdir'])))

        check_dirs()
        check_checker_exists()
        check_solution_exists()
        check_invoker_loads()
        
        logging.info(f'=== Тестирование задачи {cfg["taskname"]} начато ===')
        result = check_solution() 
    except ArbiterError as e:
        result = e.args[0]
    logging.info(f'=== Тестирование задачи {cfg["taskname"]} завершено: {result} ===')
    try:
        open(pathjoin(cfg['resultsdir'], cfg['taskname']+'.res'), 'w').write(result)
    except:
        pass
