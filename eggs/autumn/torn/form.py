# -*- coding: utf-8 -*-
from autumn.utils import PropDict, EmptyDict
from voluptuous import MultipleInvalid
from datetime import datetime, date


def Datetime(fmt='%Y-%m-%d'):
    return lambda v: datetime.strptime(v, fmt) if v else v


def Date(fmt='%Y-%m-%d'):
    return lambda v: datetime.strptime(v, fmt).date() if v else v


def Unique():
    return lambda v: list(set(v)) if v else v


def Decode(charset='UTF-8'):
    return lambda v: v.decode(charset) if v else v


def Encode(charset='UTF-8'):
    return lambda v: v.encode(charset) if v else v


def Strip():
    return lambda v: v.strip() if v else v


def ListCoerce(t):
    return lambda vs: [t(v) for v in vs] if t else []


def EmptyList():
    return lambda v: [] if not v else v


def EmptyNone():
    return lambda v: None if not v else v


class Form():
    def __init__(self, arguments, schema):
        self.arguments = PropDict()
        self.errors = {}
        self.schema = schema
        for name in schema.schema:
            key = str(name)
            if key in arguments:
                value = arguments[key][0] if type(arguments[key]) == list else arguments[key]
                self.arguments[key] = EmptyDict({'value': value})
            elif (key+'[]') in arguments:
                self.arguments[key] = EmptyDict({'value': arguments[key+'[]']})
            else:
                self.arguments[key] = EmptyDict()

    def __getattr__(self, item):
        return self.arguments[item] if item in self.arguments else None

    def validate(self):
        try:
            result = self.schema(dict([(key, self.arguments[key].value) for key in self.arguments]))
            for key in result:
                self.arguments[key]['value'] = result[key]
            return True
        except MultipleInvalid as e:
            for error in e.errors:
                name = str(error.path[0] if type(error.path) == list else error.path)
                self.arguments[name]['error'] = error
                self.errors[name] = str(error)
            return False
