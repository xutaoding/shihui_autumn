# -*- coding: utf-8 -*-
import signal
import redis
import torndb
import logging
from tornado.options import options
from conf import load_app_options

RUNNING = True


def running():
    if not RUNNING:
        logging.info('Stopped by deploy!')
    return RUNNING


def redis_client():
    return redis.StrictRedis(host=options.redis_host, port=options.redis_port, db=options.redis_db)


def db_client():
    return torndb.Connection(
        host=options.mysql_host, database=options.mysql_database,
        user=options.mysql_user, password=options.mysql_password)


def set_up():
    load_app_options()  # 加载配置

    def signal_received(signum, stack):
        global RUNNING
        RUNNING = False

    signal.signal(signal.SIGUSR1, signal_received)
