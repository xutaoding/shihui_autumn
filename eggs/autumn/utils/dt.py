# -*- coding: utf-8 -*-
from datetime import timedelta


def truncate(datetime):
    return datetime.replace(hour=0, minute=0, second=0, microsecond=0)


def ceiling(datetime, today=False):
    dt = truncate(datetime + timedelta(days=1))
    if today:
        dt = dt + timedelta(seconds=-1)
    return dt
