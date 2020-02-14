# -*- coding: utf-8 -*-
import os
from collections import Sized
from multimeter.helpers import load_json, save_json, validate_code


class Users(Sized):
    def __init__(self, settings):
        self._settings = settings
        self.filename = os.path.join(settings.work_dir, 'users.json')
        self.users = dict()
        self.load()

    def __len__(self):
        return self.users.__len__()

    def __setitem__(self, key, value):
        self.users.__setitem__(key, value)

    def __getitem__(self, item):
        return self.users.__getitem__(item)

    def __contains__(self, item):
        return self.users.__contains__(item)

    def __iter__(self):
        return self.users.__iter__()

    def __delitem__(self, key):
        del self.users[key]

    def keys(self):
        return self.users.keys()

    def clear(self):
        self.users.clear()

    def load(self):
        self.users = load_json(self.filename, {})

    def save(self):
        save_json(self.users, self.filename)

    def validate_user(self, username, data, confirm, check_uniqueness):
        """ Проверка пользователя
        :param username: Имя пользователя
        :param data: Данные пользователя
        :param confirm: Подтверждение пароля пользователя
        :param check_uniqueness: Нужно ли проверять уникальность имени пользователя
        """
        # TODO: Нужно добавить проверку наличия обязательных полей пользователя (фамилия, имя, дата рождения и т.д.)
        users_list = self.users if check_uniqueness else []
        errors = validate_code(username, users_list, 'Логин')
        password = data.get('password', '')
        if password == '':
            errors.append('Пароль не задан')
        if len(password) > 20:
            errors.append('Пароль длинее 20 символов')
        if password != confirm:
            errors.append('Пароли не совпадают')
        return errors
