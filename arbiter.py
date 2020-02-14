# -*- coding: utf-8 -*-
""" Arbiter - это модуль проверки олимпиадных задач для Multimeter """
import shutil
import sys
import time
import logging
from argparse import ArgumentParser
from collections import OrderedDict

from multimeter import tasks, languages
from multimeter.helpers import *


class Arbiter:
    """ Арбитр для проверки решений """

    def __init__(self):
        """ Установка параметров, проверка каталогов, компиляторов и заданий """
        try:
            parser = ArgumentParser(description='Арбитр для проверки олимпиадных задач по программированию')
            parser.add_argument('-w', '--work', default='work', type=str, help="рабочий каталог")
            params = parser.parse_args()

            self.log_file = log_setup(work_dir=params.work)

            logging.info("Verifying folders...")
            self.base_dir = os.getcwd()
            self.work_dir = join(self.base_dir, params.work)
            if not os.path.isdir(self.work_dir):
                logging.error("Work folder {} not found !!!".format(self.work_dir))
                sys.exit(2)

            self.queue_dir = join(self.work_dir, '.queue')
            check_or_create_dir(self.queue_dir)

            self.results_dir = join(self.work_dir, '.results')
            check_or_create_dir(self.results_dir)

            self.compile_messages_dir = join(self.work_dir, '.compilemsg')
            check_or_create_dir(self.compile_messages_dir)

            logging.info("Verifying languages...")
            languages.verifying()

            logging.info("Verifying tasks:")
            for code, task in tasks.items():
                logging.info('  {}'.format(code))
                task.verify()
                logging.info('  ok.')

            logging.info("Arbiter started.")

        except Exception as error:
            print("ERROR:", error.args[0])
            sys.exit(129)

    def __del__(self):
        try:
            self.log_file.close()
        except AttributeError:
            pass

    @staticmethod
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
            cfn = os.path.join(self.compile_messages_dir, '')
            return answer

        # Предварительная проверка
        passed = True
        for test in task.preliminary:
            test_file = join(task.preliminary_dir, test)
            shutil.copy(test_file, task.input_file)
            logging.info("Preliminary test %s... " % test)
            execution_verdict = language.execute(task, solution)
            if execution_verdict != 'OK':
                verdict = execution_verdict
            else:
                shutil.copy(test_file + '.a', 'answer.txt')
                verdict = task.check()
            answer['preliminary'][test] = verdict
            self.cleanup(task)
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
                test_file = join(task.test_suites_dir, suite_key, test)
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
            source_file = join(self.queue_dir, filename)
            destination_file = join(task.solutions_dir, "{}.{}".format(solution, language.extension))
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
            save_json(result, join(self.results_dir, '{}-{}-{}.json'.format(task_code, username, attempt)))

        return True

    def run_arbiter(self):
        """ Ожидание появления новых решений в очереди """
        try:
            print('Arbiter is ready, press Ctrl+C to stop')
            while self.queue_is_empty():
                time.sleep(1)
        except KeyboardInterrupt:
            logging.info('Arbiter has been stopped')


if __name__ == '__main__':
    arbiter = Arbiter()
    arbiter.run_arbiter()
