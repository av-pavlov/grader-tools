# -*- coding: utf-8 -*=

"""
Языки программирования
Languages - контейнер для языков программирования. В отличие от dict он умеет работать с конфигурационным файлом. Кроме
    того, обход элеменов осуществляется с учетом сортировки по представлению языка программирования.
Language - базовый класс для языков программирования
Классы-наследнки Language - классы конкретного языка программирования. Конструктор каждого такого класса должен уметь
    определять местонахождение компилятора и/или интерпретатора. Наименование каждого такого класса должно заканчиваться
    на суффикс Lang
"""
import os
import subprocess
from abc import ABCMeta, abstractmethod
from ctypes import CDLL, c_char_p, c_uint, byref
from os.path import isdir, isfile, join

from _datetime import datetime

import sys

from multimeter.helpers import load_json, save_json, validate_code, check_or_create_dir


class Languages:
    """ Языки программирования """

    def __init__(self, work_dir=None):
        self.directory = join(work_dir, '.languages')
        self.languages = dict()
        self.filename = join(work_dir, 'languages.json')

        if work_dir:
            self.load(work_dir)

    def load(self, work_dir):
        """ Чтение языков программирования из конфигурационного файла
        :param work_dir: Абсолюбтный путь к рабочему каталогу
        """
        check_or_create_dir(self.directory)
        for filename in os.listdir(self.directory):
            os.remove(join(self.directory, filename))

        self.filename = join(work_dir, 'languages.json')
        data_from_file = load_json(self.filename, {})
        known_classes = [JavaLang, VisualCppLang, VisualBasicLang, VisualCSharpLang, FreePascalLang,
                         PascalABCLang, BorlandDelphi7Lang, Python2Lang, Python3Lang, GccCppLang]
        for class_name, language_data in data_from_file.items():
            cls = Language
            for cur_class in known_classes:
                if class_name == cur_class.__name__:
                    cls = cur_class
            try:
                new_language = cls(class_name, self.directory, language_data)
                self.languages[class_name] = new_language
            except (AttributeError, TypeError, Exception):
                pass

    def autodiscover(self):
        """ Автоматическое определение языков программирования """
        self.languages.clear()
        known_classes = [JavaLang,VisualCppLang, VisualBasicLang, VisualCSharpLang, FreePascalLang, PascalABCLang,
                         BorlandDelphi7Lang, Python2Lang, Python3Lang, GccCppLang]
        for class_name in known_classes:
            try:
                new_language = class_name(class_name.__name__, self.directory)
                self.languages[class_name.__name__] = new_language
            except (AttributeError, TypeError, Exception) as e:
                pass

    def save(self):
        """ Сохранение языков программирования в конфигурационный файл """
        prepared_data = {}
        for class_name, language in self.languages.items():
            prepared_data[class_name] = language.__dict__
        save_json(prepared_data, self.filename)

    def validate(self, code, data, check_uniqueness):
        codes_list = self.languages.keys() if check_uniqueness else []
        errors = validate_code(code, codes_list, 'Код')
        if data.get('name', '') == '':
            errors.append('Наименование не задано')
        return errors

    def verifying(self):
        """ Проверка языков программирования """
        answer = True
        for lang in self.languages.values():
            answer = answer and lang.verify()
        return answer

    def __iter__(self):
        return iter(sorted(self.languages.keys(), key=lambda class_name: str(self.languages[class_name])))

    def __setitem__(self, code, data):
        if isinstance(data, Language):
            self.languages[code] = data
        if isinstance(data, dict):
            self.languages[code] = Language(code, self.directory, data)

    def __getitem__(self, code):
        return self.languages[code]

    def __delitem__(self, code):
        del self.languages[code]

    def __contains__(self, code):
        return code in self.languages


class Language:
    """ Базовый класс для языка программирования """

    def __init__(self, code, directory, data):
        self.name = data['name']
        self.extension = data['extension']
        self.execution = data['execution']
        self.compilation = data['compilation']

        if not self.verify():
            raise Exception('{} verification failed !!!'.format(self.name))

        self.batch = join(directory, code + '.bat')
        batch_file = open(self.batch, "w")
        for command in self.compilation:
            batch_file.write(command + '\n')
        batch_file.close()

    def __repr__(self):
        return self.name

    def verify(self):
        return True

    def compile(self, solution):
        answer = '??'
        try:
            output = subprocess.check_output(self.batch + ' ' + solution, stderr=subprocess.STDOUT)
            answer = ('OK', '')
        except subprocess.CalledProcessError as e:
            msg = e.output.decode('cp866') if type(e.output)==bytes else ''
            print(msg)
            answer = ('CE', e.output.decode('cp866'))
        return answer

    @staticmethod
    def execute(task, solution):
        answer = '??'
        try:
            executable = solution + '.exe'
            executable = c_char_p(executable.encode('utf-8'))
            input_file = c_char_p(task.input_file.encode('utf-8'))
            output_file = c_char_p(b'stdout')
            memory_limit = c_uint(0)
            time_limit = c_uint(int(1000 * task.timeout))
            invoker = CDLL('..\\..\\..\\invoker.dll')
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


class JavaLang(Language):
    def __init__(self, code, directory, data=None):
        self.version = ''
        self.java_home = ''
        self.jvm = ''
        self.compiler = ''

        if data is None:
            paths = ['C:\\Program Files (x86)\\Java', 'C:\\Program Files\\Java']
            for path in paths:
                if not isdir(path):
                    continue
                jdk_list = [jdk for jdk in os.listdir(path) if jdk.lower().startswith('jdk') and isdir(join(path, jdk))]
                if len(jdk_list) == 0:
                    continue
                jdk = sorted(jdk_list)[-1]
                java_home = join(path, jdk)
                jvm = join(java_home, 'bin', 'java.exe')
                compiler = join(java_home, 'bin', 'javac.exe')
                if isdir(java_home) and isfile(jvm) and isfile(compiler):
                    self.version = jdk[3:]
                    self.java_home = java_home
                    self.jvm = jvm
                    self.compiler = compiler
        else:
            self.version = data.get('version', '')
            self.java_home = data.get('java_home', '')
            self.jvm = data.get('jvm', '')
            self.compiler = data.get('compiler', '')

        super().__init__(code, directory, dict(
            name='Java ' + self.version,
            extension='java',
            execution='"' + self.jvm + '" Main',
            compilation=['"' + self.compiler + '" %1.java'],
        ))

    def verify(self):
        return self.version != '' and isdir(self.java_home) and isfile(self.jvm) and isfile(self.compiler)

    def compile(self, solution):
        answer = '??'
        try:
            output = subprocess.check_output(self.batch + ' ' + solution, stderr=subprocess.STDOUT)
            answer = ('OK', '')
        except subprocess.CalledProcessError as e:
            msg = e.output.decode('cp866') if type(e.output)==bytes else ''
            print(msg)
            answer = ('CE', msg)
        return answer

    def execute(self, task, solution):
        answer = '??'
        try:
            start = datetime.now()
            executable = solution + '.' + self.extension
            stdin = open(task.input_file)
            stdout = open('stdout', mode='w')
            subprocess.check_call([self.execution],
                                  timeout=task.timeout, stdin=stdin, stdout=stdout)
            stop = datetime.now()
            delta = stop - start
            if delta.total_seconds() > task.time_limit:
                answer = 'TL'
            else:
                answer = 'OK'
        except subprocess.CalledProcessError:
            answer = 'RE'  # Runtime error
        except OSError:
            answer = 'RE'  # Runtime error
        except subprocess.TimeoutExpired:
            answer = 'TL'  # Time Limit Exceeded
        finally:
            return answer


class VisualStudio(Language, metaclass=ABCMeta):
    product = 'Microsoft Visual Studio'

    @classmethod
    @abstractmethod
    def get_name(cls):
        pass

    @classmethod
    @abstractmethod
    def get_extension(cls):
        pass

    @abstractmethod
    def get_prepare(self, home):
        pass

    @abstractmethod
    def get_new_prepare(self, home):
        pass

    @abstractmethod
    def get_compiler(self):
        pass

    @abstractmethod
    def get_compilation(self):
        pass

    def __init__(self, code, directory, data=None):
        self.version = ''
        self.prepare = ''
        self.compiler = ''

        if data is None:
            paths = ['C:\\Program Files (x86)', 'C:\\Program Files']
            versions = {
                '2008': '9.0',
                '2010': '10.0',
                '2012': '11.0',
                '2013': '12.0',
                '2015': '14.0',
            }
            new_versions = {
                '2017': '15.0'
            }
            new_editions = [
                'Community',
                'Professional'
                'Enterprise',
            ]
            name = self.get_name()
            for path in paths:
                for year, version in versions.items():
                    home = join(path, self.product + ' ' + version)
                    prepare = self.get_prepare(home)
                    compiler = self.get_compiler()
                    if isfile(prepare):
                        self.version = version
                        self.prepare = prepare
                        self.compiler = compiler
                        name = name + ' ' + year
                for year, version in new_versions.items():
                    for edition in new_editions:
                        home = join(path, self.product, year, edition)
                        prepare = self.get_new_prepare(home)
                        compiler = self.get_compiler()
                        if isfile(prepare):
                            self.version = version
                            self.prepare = prepare
                            self.compiler = compiler
                            name = name + ' ' + year
        else:
            self.version = data.get('version', '')
            self.prepare = data.get('prepare', '')
            self.compiler = data.get('compiler', '')
            name = data.get('name', '')

        super().__init__(code, directory, dict(
            name=name,
            extension=self.get_extension(),
            execution='{solution}.exe',
            compilation=self.get_compilation(),
        ))


class VisualCppLang(VisualStudio):
    def verify(self):
        return self.version != '' and isfile(self.prepare)

    def get_prepare(self, home):
        return join(home, 'VC', 'vsvarsall.bat')

    def get_new_prepare(self, home):
        return join(home, 'Common7', 'Tools', 'VsDevCmd.bat')

    def get_compiler(self):
        return 'cl.exe'

    def get_compilation(self):
        return ['pushd .', 'call "' + self.prepare + '"', 'popd', 'cl.exe %1.cpp /O2 /EHsc /F268435456']

    @classmethod
    def get_name(cls):
        return 'MS Visual C++'

    @classmethod
    def get_extension(cls):
        return 'cpp'


class VisualCSharpLang(VisualStudio):
    def verify(self):
        return self.version != '' and isfile(self.prepare)

    def get_prepare(self, home):
        return join(home, 'VC', 'VsVarsAll.bat')

    def get_new_prepare(self, home):
        return join(home, 'Common7', 'Tools', 'VsMSBuildCmd.bat')

    def get_compiler(self):
        return 'csc.exe'

    def get_compilation(self):
        return ['pushd .', 'call "' + self.prepare + '"', 'popd', 'csc.exe %1.cs']

    @classmethod
    def get_name(cls):
        return 'MS Visual C#'

    @classmethod
    def get_extension(cls):
        return 'cs'


class VisualBasicLang(VisualStudio):
    def verify(self):
        return self.version != '' and isfile(self.prepare)

    def get_prepare(self, home):
        return join(home, 'VC', 'VsVarsAll.bat')

    def get_new_prepare(self, home):
        return join(home, 'Common7', 'Tools', 'VsMSBuildCmd.bat')

    def get_compiler(self):
        return 'vbc.exe'

    def get_compilation(self):
        return ['pushd .', 'call "' + self.prepare + '"', 'popd', 'vbc.exe %1.vb']

    @classmethod
    def get_name(cls):
        return 'MS Visual Basic'

    @classmethod
    def get_extension(cls):
        return 'vb'


class FreePascalLang(Language):
    def verify(self):
        return self.version != '' and isfile(self.compiler)

    def __init__(self, code, directory, data=None):
        self.version = ''
        self.compiler = ''
        self.extension = 'pas'
        self.compilation = []

        if data is None:
            versions = [
                '2.2.2', '2.2.4',
                '2.4.0', '2.4.2', '2.4.4',
                '2.6.0', '2.6.2', '2.6.4',
                '3.0.0', '3.0.2', '3.0.4'
            ]
            platforms = ['i386-win32', 'x86_64-win64']
            for version in versions:
                for platform in platforms:
                    compiler = join('C:\\FPC', version, 'bin', platform, 'fpc.exe')
                    if isfile(compiler):
                        self.version = version
                        self.compiler = compiler
                        self.compilation = [self.compiler + ' %1.pas']

            # Встроенный компилятор
            base = join(os.getcwd(), 'langs', 'FPC')
            compiler = join(base, 'bin', 'fpc.exe')
            if isfile(compiler):
                self.version = '3.0.2'
                self.compiler = compiler
                self.compilation = [
                    '"{compiler}" -e"{base}\\bin" -Fu"{base}\\units\\*" %1.{extension}'.format(
                        base=base, compiler=compiler, extension=self.extension
                    )
                ]
        else:
            self.version = data.get('version', '')
            self.compiler = data.get('compiler', '')
            self.compilation = data.get('compilation', '')

        super().__init__(code, directory, dict(
            name='Free Pascal ' + self.version,
            extension=self.extension,
            execution='{solution}.exe',
            compilation=self.compilation,
        ))


class PascalABCLang(Language):
    def verify(self):
        return isfile(self.compiler)

    def __init__(self, code, directory, data=None):
        self.compiler = ''

        if data is None:
            paths = [os.environ['ProgramFiles(x86)'], os.environ['ProgramFiles']]
            for path in paths:
                compiler = join(path, 'PascalABC.NET', 'pabcnetcclear.exe')
                if isfile(compiler):
                    self.compiler = compiler

            # Встроенный компилятор
            compiler = join(os.getcwd(), 'langs', 'PABC', 'pabcnetcclear.exe')
            if isfile(compiler):
                self.compiler = compiler
        else:
            self.compiler = data.get('compiler', '')

        super().__init__(code, directory, dict(
            name='PascalABC.NET',
            extension='pas',
            execution='{solution}.exe',
            compilation=['"' + self.compiler + '" %1.pas'],
        ))


class BorlandDelphi7Lang(Language):
    def verify(self):
        return isfile(self.compiler)

    def __init__(self, code, directory, data=None):
        self.compiler = ''
        self.extension = 'dpr'
        self.compilation = []

        if data is None:
            paths = [os.environ['ProgramFiles(x86)'], os.environ['ProgramFiles']]
            for path in paths:
                compiler = join(path, 'Borland', 'Delphi7', 'Bin', 'DCC32.exe')
                if isfile(compiler):
                    self.compiler = compiler
                    self.compilation = [
                        '"{compiler}" %1.extension'.format(
                            compiler=self.compiler,
                            extension=self.extension,
                        )
                    ]

            # Встроенный компилятор
            base = join(os.getcwd(), 'langs', 'Delphi7')
            compiler = join(base, 'DCC32.exe')
            if isfile(compiler):
                self.compiler = compiler
                self.compilation = [
                    '"{compiler}" -l"{base}" -U"{base}" %1.dpr'.format(
                        base=base,
                        compiler=self.compiler,
                        extension=self.extension,
                    )
                ]

        else:
            self.compiler = data.get('compiler', '')
            self.compilation = data.get('compilation', '')

        super().__init__(code, directory, dict(
            name='Borland Delphi 7',
            extension=self.extension,
            execution='{solution}.exe',
            compilation=self.compilation,
        ))


class Python2Lang(Language):
    def verify(self):
        return self.version != '' and isfile(self.interpreter)

    def __init__(self, code, directory, data=None):
        self.version = ''
        self.interpreter = ''

        if data is None:
            versions = ['2.6', '2.7']
            for version in versions:
                interpreter = join('C:\\Python' + version.replace('.', ''), 'python.exe')
                if isfile(interpreter):
                    self.version = version
                    self.interpreter = interpreter
        else:
            self.version = data.get('version', '')
            self.interpreter = data.get('interpreter', '')

        super().__init__(code, directory, dict(
            name='Python ' + self.version,
            extension='py',
            execution=self.interpreter + ' {solution}.py',
            compilation=['@echo Compilation %1.py'],
        ))

    def execute(self, task, solution):
        answer = '??'
        try:
            start = datetime.now()
            executable = solution + '.' + self.extension
            stdin = open(task.input_file)
            stdout = open('stdout', mode='w')
            subprocess.check_call([self.interpreter, '-E', executable],
                                  timeout=task.timeout, stdin=stdin, stdout=stdout)
            stop = datetime.now()
            delta = stop - start
            if delta.total_seconds() > task.time_limit:
                answer = 'TL'
            else:
                answer = 'OK'
        except subprocess.CalledProcessError:
            answer = 'RE'  # Runtime error
        except OSError:
            answer = 'RE'  # Runtime error
        except subprocess.TimeoutExpired:
            answer = 'TL'  # Time Limit Exceeded
        finally:
            return answer


class Python3Lang(Language):
    def verify(self):
        return self.version != '' and isfile(self.interpreter)

    def __init__(self, code, directory, data=None):
        self.version = ''
        self.interpreter = ''

        if data is None:
            versions = ['3.2', '3.3', '3.4']
            for version in versions:
                interpreter = join('C:\\Python' + version.replace('.', ''), 'python.exe')
                if isfile(interpreter):
                    self.version = version
                    self.interpreter = interpreter

            versions = ['3.5', '3.6']
            platforms = ['32', '64']
            paths = [
                join(os.environ['USERPROFILE'], 'Local Settings', 'Application Data', 'Programs'),
                os.environ['ProgramFiles'],
                os.environ['ProgramFiles(x86)'],
            ]
            for path in paths:
                if isdir(path):
                    for version in versions:
                        for platform in platforms:
                            suffix = version.replace('.', '') + '-' + platform
                            interpreter = join(path, 'Python' + suffix, 'python.exe')
                            if isfile(interpreter):
                                self.version = version
                                self.interpreter = interpreter
        else:
            self.version = data.get('version', '')
            self.interpreter = data.get('interpreter', '')

        super().__init__(code, directory, dict(
            name='Python ' + self.version,
            extension='py',
            execution=self.interpreter + ' -E {solution}.py',
            compilation=['@echo Compilation %1.py'],
        ))

    def execute(self, task, solution):
        answer = '??'
        try:
            start = datetime.now()
            executable = solution + '.' + self.extension
            stdin = open(task.input_file)
            stdout = open('stdout', mode='w')
            subprocess.check_call([self.interpreter, '-E', executable],
                                  timeout=task.timeout, stdin=stdin, stdout=stdout)
            stop = datetime.now()
            delta = stop - start
            if delta.total_seconds() > task.time_limit:
                answer = 'TL'
            else:
                answer = 'OK'
        except subprocess.CalledProcessError:
            answer = 'RE'  # Runtime error
        except OSError:
            answer = 'RE'  # Runtime error
        except subprocess.TimeoutExpired:
            answer = 'TL'  # Time Limit Exceeded
        finally:
            return answer


class GccCppLang(Language):
    def verify(self):
        return isfile(self.compiler)

    def __init__(self, code, directory, data=None):
        self.compiler = ''

        if data is None:
            paths = [
                join(os.environ['ProgramFiles(x86)'], 'CodeBlocks'),
                join(os.environ['ProgramFiles'], 'CodeBlocks'),
                os.environ['SystemDrive'],
            ]
            for path in paths:
                compiler = join(path, 'MinGW', 'bin', 'g++.exe')
                if isfile(compiler):
                    self.compiler = compiler
        else:
            self.compiler = data.get('compiler', '')

        super().__init__(code, directory, dict(
            name='GNU Compiler Collection C++',
            extension='cpp',
            execution='{solution}.exe',
            compilation=['"' + self.compiler + '" %1.cpp -o %1 -O2 -Wl,--stack=268435456'],
        ))
