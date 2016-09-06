# -*- coding: utf-8 -*-
import logging
from tornado import ioloop
import time
import signal


MAX_WAIT_SECONDS_BEFORE_SHUTDOWN = 2


def register_terminal_handler(server, application):

    def sig_handler(sig, frame):
        logging.warning('Caught signal: %s', sig)
        ioloop.IOLoop.instance().add_callback(shutdown)

    def shutdown():
        logging.info('Stopping http server')
        server.stop()

        logging.info('Will shutdown in %s seconds ...', MAX_WAIT_SECONDS_BEFORE_SHUTDOWN)
        io_loop_instance = ioloop.IOLoop.instance()

        deadline = time.time() + MAX_WAIT_SECONDS_BEFORE_SHUTDOWN

        def stop_loop():
            now = time.time()
            if now < deadline:
                io_loop_instance.add_timeout(now + 1, stop_loop)
            else:
                io_loop_instance.stop()
                logging.info('Close database connection')
                if hasattr(application, 'db'):
                    application.db.close()
                    logging.info('Shutdown')
        stop_loop()

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGQUIT, sig_handler)
