# -*- coding: utf-8 -*-

""" Проверка задачи на тестах из папки, запись результатов в файл """

import os, shutil, sys, time, logging, glob
from argparse import ArgumentParser
from collections import OrderedDict

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
        sys.exit(129)

def argparse():
    """ Установка параметров командной строки """
    try:
        parser = ArgumentParser(description='Арбитр для проверки задач по программированию')
        parser.add_argument('-w', '--workdir', default='.', type=str, help="рабочий каталог")
        parser.add_argument('-t', '--testdir', default='test', type=str, help="каталог с тестами")
        parser.add_argument('-r', '--resultsdir', default='.', type=str, help="каталог для записи результатов")
        parser.add_argument('-s', '--solution', default='Debug/*.exe', type=str, help="исполняемый файл для тестирования")
        return vars(parser.parse_args())
    except Exception as error:
        logging.error(f"Не удалось прочесть аргументы командной строки: {error.args[0]}")
        sys.exit(129)

def check_writable(directory):
    global cfg
    try:
        fn = os.path.join(cfg[directory], '###qqq@@.json')
        open(fn, 'w').close()
        os.remove(fn)
    except OSError as error:
        logging.error(f'Не удалась попытка записи в {directory}-каталог "{cfg[directory]}"!!!')
        sys.exit(2)


def check_dirs(cfg):
    base_dir = os.getcwd()

    for _ in ('workdir', 'testdir', 'resultsdir'):
        directory = cfg[_] = os.path.join(base_dir, cfg[_])
        if not os.path.isdir(directory):
            logging.error(f'Не удалось найти {_}-каталог "{directory}"!!!')
            sys.exit(2)

    try:
        os.chdir(cfg['workdir'])
    except OSError as error:
        logging.error(f'Не удалось войти в рабочий каталог: "{cfg["workdir"]}"!!!')

    check_writable('workdir')
    check_writable('resultsdir')


def cleanup(task):
        """ Очистка после проверки теста """
        cleanup_list = [task.input_file, task.output_file, 'answer.txt', 'stdout']
        while len(cleanup_list) > 0:
            for filename in cleanup_list:
                try:
                    os.remove(filename)
                    cleanup_list.remove(filename)
                except FileNotFoundError:
                    cleanup_list.remove(filename)
                except PermissionError:
                    pass


def check_test(self, task, language, solution, test):
    pass

def check_solution(self, task, language, solution):
    """ Проверка решений """
    answer = {
        "datetime": datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
        "language": language.name,
        "compilation": "CE",
        "preliminary": OrderedDict(),
        "results": OrderedDict()
    }

    logging.info('')
    logging.info("================================================================================")
    logging.info("Popped from queue problem: %s, solution: %s, language: %s" % (task.code, solution, language.name))

    os.chdir(task.solutions_dir)

    # Компиляция
    logging.info("Compiling... ")
    answer['compilation'] = language.compile(solution)
    if answer['compilation'][0] == 'OK':
        logging.info("Compile OK")
    else:
        logging.info("Compile failed")
        cfn = os.path.join(compile_messages_dir, '')
        return answer

    # Предварительная проверка
    passed = True
    for test in task.preliminary:
        test_file = os.path.join(task.preliminary_dir, test)
        shutil.copy(test_file, task.input_file)
        logging.info("Preliminary test %s... " % test)
        execution_verdict = language.execute(task, solution)
        if execution_verdict != 'OK':
            verdict = execution_verdict
        else:
            shutil.copy(test_file + '.a', 'answer.txt')
            verdict = task.check()
        answer['preliminary'][test] = verdict
        cleanup(task)
        logging.info(verdict)
        if verdict != 'OK':
            passed = False
    if not passed:
        return answer

    # Проверка на основных тестах
    for suite_key, suite_value in task.test_suites.items():
        logging.info("Test suite " + suite_key)

        # Костыль про зависимость подзадач
        if suite_value.depends:
            shall_not_pass = False
            for dependency in suite_value.depends:
                for test, verdict in answer['results'][dependency].items():
                    if verdict != 'OK':
                        shall_not_pass = True
                        break
                if shall_not_pass:
                    break
            if shall_not_pass:
                continue

        answer['results'][suite_key] = OrderedDict()
        for test in suite_value.tests:
            test_file = os.path.join(task.test_suites_dir, suite_key, test)
            shutil.copy(test_file, task.input_file)
            logging.info("  checking test %s..." % test)
            execution_verdict = language.execute(task, solution)
            if execution_verdict != 'OK':
                verdict = execution_verdict
            else:
                shutil.copy(test_file + '.a', 'answer.txt')
                verdict = task.check()
            answer['results'][suite_key][test] = verdict
            self.cleanup(task)
            logging.info(verdict)

    return answer

def queue_is_empty(self):
    """ Компиляция и проверка загруженных решений """
    for filename in os.listdir(self.queue_dir):
        print(filename)
        (task_code, username, lang_code, attempt) = filename.split('-')
        task = tasks[task_code]
        language = languages[lang_code]
        solution = '{}-{}'.format(username, attempt)

        # Перемещение файла из очереди в папку решений
        source_file = os.path.join(self.queue_dir, filename)
        destination_file = os.path.join(task.solutions_dir, "{}.{}".format(solution, language.extension))
        shutil.move(source_file, destination_file)

        result = self.check_solution(task, language, solution)

        total = 0
        for key, values in result['results'].items():
            settings = task.test_suites[key]

            if settings.scoring == 'entire':
                # Если подзадача оценивается по принципу "все или ничего"
                correct = all([v == 'OK' for v in values.values()])
                total += settings.total_score if correct else 0

            elif settings.scoring == 'partial':
                # Если подзадача оценивается пропорционально
                correct = [settings.test_score for v in values.values() if v == 'OK']
                total += sum(correct)

        result['total'] = total

        os.chdir(self.base_dir)
        save_json(result, os.path.join(self.results_dir, '{}-{}-{}.json'.format(task_code, username, attempt)))

    return True


if __name__ == '__main__':
    logsetup()
    cfg = argparse()
    check_dirs(cfg)
    logging.info("Arbiter started.")

