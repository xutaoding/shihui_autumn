# -*- coding: utf-8 -*-

from .. import BaseHandler
import urllib2
import json
from autumn.utils import json_hook


class Oauth(BaseHandler):
    def get(self):
        code = self.get_argument('code', '-1')
        action = self.get_argument('state', '-1')
        subhost = self.request.host.split('.')[0].split(':')[0]

        app_id_val = self.db.get('select * from supplier_property where sp_id = %s and name = "app_id"', subhost)
        app_id = app_id_val.value if app_id_val else ''
        app_secret_val = self.db.get('select * from supplier_property where sp_id = %s and name = "app_secret"', subhost)
        app_secret = app_secret_val.value if app_secret_val else ''

        oauth_url = 'https://api.weixin.qq.com/sns/oauth2/access_token?appid=%s&secret=%s&code=%s&grant_type=authorization_code' % (app_id, app_secret, code)
        response = urllib2.urlopen(oauth_url)
        oauth_info = json.loads(response.read(), object_hook=json_hook)

        open_id = oauth_info.openid

        url = 'http://%s.quanfx.com/%s?wx_id=%s' % (subhost, action, open_id)
        self.redirect(url)
