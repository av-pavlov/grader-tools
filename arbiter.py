# -*- coding: utf-8 -*-

""" Проверка задачи на тестах из папки, запись результатов в файл """

import os, shutil, sys, time, logging, glob, re, datetime, subprocess, traceback
from os.path import abspath, basename, split as pathsplit, join as pathjoin, isfile, isdir
from argparse import ArgumentParser
from collections import OrderedDict
from ctypes import CDLL, c_char_p, c_uint, byref

from multimeter._tasks import Task

LOG_FILENAME = 'arbiter.log'
DEFAULT_SOLUTION_MASK = 'Debug/*.exe'
INPUT_FILENAME  = 'putin1.txt'
OUTPUT_FILENAME = 'putout.txt'
ANSWER_FILENAME = 'putans.txt'
TMPFILE_MASK    = 'put???.txt'

cfg = {}
invoker = None


class ArbiterError(Exception):
    pass


class PatchedTask(Task):
    input_file = INPUT_FILENAME
    output_file = OUTPUT_FILENAME
    time_limit = 3.5                 # FOR GITHUB ACTIONS

    @property
    def checker(self):
        global cfg
        return cfg['checker']

    def check(self, answer_file=ANSWER_FILENAME):
        """ Проверка ответа участника """
        answer = ['FL', '']
        try:
            output = subprocess.check_output([
                self.checker,
                self.input_file,
                self.output_file,
                answer_file,
            ], stderr=subprocess.STDOUT)
            answer = ['OK', output]
        except subprocess.CalledProcessError as error:
            if error.returncode == 1:
                answer = ['WA', error.output]  # Wrong answer
            elif error.returncode == 2:
                answer = ['WA', error.output]  # Presentation error
            else:
                logging.error("CHECKER FAILED:")
                logging.error(error.output)
                logging.error(error)
        except Exception as e:
            logging.error(e)
            logging.error(traceback.format_exc())
            answer = ['FL', '']
        return answer


def setup_logging():
    """ Настройка логирования"""
    global LOG_FILENAME
    try:
        log_cout = logging.FileHandler(pathjoin(os.getcwd(), LOG_FILENAME), mode='w', encoding='utf-8')
        logging.basicConfig(level=logging.DEBUG,
                            format='[%(asctime)s] %(levelname)s: %(message)s',
                            handlers=(log_cout,))
    except Exception as error:
        print("ERROR setting up loggers:", error.args[0])
        raise ArbiterError('FL')

def read_arguments():
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
    logging.debug('НАЙДЕНО РЕШЕНИЕ: ' + cfg['solution'])

def get_known_checkers():
    exe_mask = '*.exe' if sys.platform == 'win32' else '*'
    path_mask = pathjoin(cfg['checktoolsdir'], 'checkers', sys.platform, exe_mask)
    checkers = {os.path.splitext(basename(fn))[0]: abspath(fn) 
                for fn in glob.glob(path_mask) 
                if is_executable(fn)}
    logging.debug(f'НАЙДЕНЫ СТАНДАРТНЫЕ ЧЕКЕРЫ ({path_mask}): ' + 
                  repr([basename(fn) for fn in checkers]))
    return checkers

def is_executable(fn):
    return shutil.which(abspath(fn)) is not None

def is_known_checker_name(fn):
    global cfg
    return os.path.splitext(basename(fn))[0] in cfg['known_checkers']

def check_checker_exists():
    """ Проверка наличия файла проверяющей программы """
    global cfg
    testdir_mask = pathjoin(cfg['testdir'], '*') 
    candidates = list(map(basename, glob.glob(testdir_mask)))
    logging.debug('Файлы в папке с тестами: ' + ', '.join(candidates))
    candidates = [fn for fn in candidates 
                  if is_known_checker_name(fn) or fn.lower() == 'check.exe']
    logging.debug(f'Из них годятся в чекеры: {candidates}')
    if len(candidates) == 1 and isfile(candidates[0]):
        fn = candidates[0]
        if fn == 'check.exe':
            src = abspath(pathjoin(cfg['testdir'], fn))
        else:
            src = cfg['known_checkers'][os.path.splitext(fn)[0]]
        shutil.copy(src, cfg['workdir'])
        cfg['checker'] = abspath(pathjoin(cfg['workdir'], fn))
        logging.debug('НАЙДЕН ЧЕКЕР: ' + cfg['checker'])
        if sys.platform == 'win32':
            src = f"{cfg['checktoolsdir']}\\checkers\\win32\\msvcr110.dll"  
            shutil.copy(src, cfg['workdir'])
            subprocess.run(f'cmd /c dir {cfg["workdir"]}')
    else:
        logging.error('В папке с тестами должен быть ЛИБО:')
        logging.error('    1) файл с названием, как у стандартного чекера, ЛИБО ')
        logging.error('    2) чекер с названием check.exe')
        logging.error(f'    кандидаты: {candidates}')
        raise ArbiterError('FL')
    
def check_invoker_loads():
    """ Проверка наличия invoker.dll """
    global cfg, invoker
    dllpath = abspath(pathjoin(cfg['checktoolsdir'], 'invoker.dll'))
    if not isfile(dllpath):
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не найдена!')
        raise ArbiterError('FL')
    try:
        invoker = CDLL(dllpath)
    except OSError as e:
        logging.error(f'Библиотека для запуска решений invoker.DLL ({dllpath}) не может быть загружена!')
        logging.error(e)
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

def execute_one_test(task):
    """ Запуск решения на одном тесте """
    global cfg
    answer = 'FL'

    files = [c_char_p(fn.encode('utf-8')) 
             for fn in (cfg['solution'], task.input_file, task.output_file)]
    memory_limit = c_uint(0)
    time_limit = c_uint(int(1000 * task.time_limit))
        
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

def run_tests():
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
    logging.debug('НАЙДЕНЫ ТЕСТЫ: ' + ' '.join(tests))
    
    suite_key = '.' # на будущее мб папки для позадач
    answer['results'][suite_key] = OrderedDict()
    
    first_run_timelimit = 3
    task.time_limit, task.timeout = first_run_timelimit, 2*first_run_timelimit
    for test in tests:
        test_file = pathjoin(cfg['testdir'], suite_key, test)
        shutil.copy(test_file, task.input_file)
        execution_verdict = execute_one_test(task)
        logging.info(f'Запускаю тест {test}:') 
        if execution_verdict != 'OK':
            logging.info(f'  Программа завершилась некорректно') 
            verdict, output = execution_verdict, None
        else:
            logging.info(f'  Программа отработала, запускаю проверку результатов:') 
            verdict, output = task.check(answer_file=test_file + '.a')
        answer['results'][suite_key][test] = verdict
        cleanup(task)
        if output:
            try:
                logging.info('  Вывод проверки: ' + output.decode('cp1251'), end='')
            except:
                logging.info('  Вывод проверки: ' + output, end='')
        logging.info(f'  Вердикт: {verdict}')

        if verdict != 'OK':
            logging.info('Останавливаю тестирование.')
            raise ArbiterError(verdict)
        task.time_limit, task.timeout = 1.5, 3
    return verdict

if __name__ == '__main__':
    original_dir = os.getcwd()
    try:
        setup_logging()
        cfg = read_arguments()
        cfg['checktoolsdir'] = os.path.split(abspath(__loader__.path))[0]
        cfg['taskname'] = re.sub('[^A-Za-z0-9_.]', '' , basename(abspath(cfg['workdir'])))

        check_dirs()
        cfg['known_checkers'] = get_known_checkers()
        check_checker_exists()
        check_solution_exists()
        check_invoker_loads()
        
        logging.info(f'=== Тестирование задачи {cfg["taskname"]} начато ===')
        result = run_tests() 
    except ArbiterError as e:
        result = e.args[0]
    try:
        logging.info(f'=== Тестирование задачи {cfg["taskname"]} завершено, ВЕРДИКТ: {result} ===')
        open(pathjoin(cfg['resultsdir'], cfg['taskname']+'.res'), 'w').write(result)
        os.chdir(original_dir)
        subprocess.call("type " + LOG_FILENAME, shell=True)        
        sys.exit(0 if result == 'OK' else -2)
    except Exception as e:
        print(e)
        sys.exit(-1)
