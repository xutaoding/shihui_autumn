# -*- coding: utf-8 -*-
from .. import BaseHandler


class OlderIE(BaseHandler):
    def get(self):
        self.render('welcome/older_ie.html')
