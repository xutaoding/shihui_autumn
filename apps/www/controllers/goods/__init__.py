# -*- coding: utf-8 -*-

from .. import BaseHandler


class About(BaseHandler):
    def get(self):
        category = self.get_argument('category', '')

        self.render('about.html', category=category)