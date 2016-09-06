# -*- coding: utf-8 -*-
import os
import errno
import re
import hashlib
import logging
from PIL import Image, ImageEnhance
from tornado import ioloop, web
from tornado.web import StaticFileHandler, HTTPError, RequestHandler
from tornado.options import options, define
from conf import load_app_options
from autumn.goods import img_sign


class AraleHandler(StaticFileHandler):
    """
        对形如 'http://static.alipayobjects.com/seajs/??seajs/2.1.1/sea.js,seajs-combo/1.0.0/seajs-combo.js'
        的 URL 取 seajs 目录下的 seajs/2.1.1/sea.js 和 seajs-combo/1.0.0/seajs-combo.js 两个文件进行合并

        对形如'http://static.alipayobjects.com/??seajs/2.1.1/sea.js,seajs-combo/1.0.0/seajs-combo.js'
        的 URL 取根目录下的 seajs/2.1.1/sea.js 和 seajs-combo/1.0.0/seajs-combo.js 两个文件进行合并

        合并后的文件，放到 tmp目录下，文件名为 uri 主体部分的md5值

    """
    def get(self, path, include_body=True):
        uri = self.request.uri  # /seajs/??seajs/2.1.1/sea.js,seajs-combo/1.0.0/seajs-combo.js
        uri_path = self.request.path  # /seajs/
        path_len = len(uri_path)

        if uri[path_len: path_len+2] == '??':
            uri = uri[path_len+2:]  # seajs/2.1.1/sea.js,seajs-combo/1.0.0/seajs-combo.js
            q_index = uri.find('?')
            file_paths = uri[:q_index if q_index >= 0 else len(uri)].split(',')

            if len(file_paths) == 0:
                raise HTTPError(404)

            file_extension = os.path.splitext(file_paths[0])[1]
            if file_extension not in ('.js', '.css'):
                raise HTTPError(404)

            new_file_path = os.path.join(sea_tmp_path, hashlib.md5(uri).hexdigest()+file_extension)

            if not os.path.exists(new_file_path):
                lines = []
                for file_path in file_paths:
                    if '..' in file_path:
                        raise HTTPError(404)
                    file_path = os.path.join(self.root, path if path else '', file_path)
                    if not os.path.exists(file_path):
                        raise HTTPError(404)
                    with open(file_path, 'rb') as fi:
                        lines.append(fi.read())

                with open(new_file_path, 'w') as f:
                    f.write('\n'.join(lines))
            self.root = sea_path
            super(AraleHandler, self).get(new_file_path[len(self.root)+1:], include_body)
        else:
            super(AraleHandler, self).get(path, include_body)


class ClearHandler(RequestHandler):
    def get(self):
        for name in os.listdir(sea_tmp_path):
            if name != '.gitignore':
                os.remove(os.path.join(sea_tmp_path, name))
        self.write('temporary directory cleared.')


img_name_pattern = re.compile(r'([a-z0-9]{8})_([^_]+)(_.+)*\.((?i)(jpg|jpeg|png|gif))$')
size_pattern = re.compile(r'.+_([0-9]+)x([0-9]+)(_.+)*\.((?i)(jpg|jpeg|png|gif))$')
jd_pattern = re.compile(r'.+_jd[\._].+')
max_width_patten = re.compile(r'.+_max(\d+)[\._].+')


class CDNHandler(StaticFileHandler):
    def get(self, path, include_body=True):
        path = self.request.uri[1:]

        if path.startswith('o/'):
            # 请求原始图片
            super(CDNHandler, self).get(path, include_body)
            return

        target_path = os.path.join(options.cdn_root, path)
        if os.path.exists(target_path):
            # 有已经生成的图片
            super(CDNHandler, self).get(path, include_body)
            return

        file_dir = os.path.dirname(path)
        file_name = os.path.basename(path)
        img_name_matches = img_name_pattern.match(file_name)
        if not img_name_matches:
            # URL 格式不对
            raise HTTPError(404)

        # 分解URL
        sign = img_name_matches.group(1)
        raw_name = img_name_matches.group(2)
        fix_name = img_name_matches.group(3)
        fix_name = fix_name if fix_name else ''
        ext = img_name_matches.group(4)

        if sign != img_sign(raw_name+fix_name+'.'+ext):
            #  签名不对
            raise HTTPError(403)

        origin_path = os.path.join(options.upload_img_path, file_dir[file_dir.find('/')+1:], raw_name+'.'+ext)
        if not os.path.exists(origin_path):
            #  无原图
            raise HTTPError(404)

        origin_img = Image.open(origin_path)

        size_matches = size_pattern.match(file_name)
        if size_matches:
            #  根据分辨率参数缩放
            origin_img.thumbnail(map(int, size_matches.groups()[:2]), Image.ANTIALIAS)

        width_match = max_width_patten.match(file_name)
        if width_match:
            #  压缩图片满足最大宽度
            base_width = int(width_match.groups()[0])
            width_percent = (base_width/float(origin_img.size[0]))
            height = int((float(origin_img.size[1])*float(width_percent)))
            origin_img.thumbnail((base_width, height), Image.ANTIALIAS)

        if jd_pattern.match(file_name):
            #  京东水印
            origin_img.paste(jd_logo_mask, (origin_img.size[0]-jd_logo_mask.size[0],
                                            origin_img.size[1]-jd_logo_mask.size[1]), jd_logo_mask)

        full_dir = os.path.join(options.cdn_root, file_dir)
        if not os.path.exists(full_dir):
            os.makedirs(full_dir)
        origin_img.save(target_path, ext if ext.lower() != 'jpg' else 'jpeg', quantity=100)
        super(CDNHandler, self).get(path, include_body)


sea_path = os.path.join(os.path.dirname(__file__), 'sea-modules')
sea_tmp_path = os.path.join(sea_path, 'tmp')


def prepare_jd_mask():
    """ 准备京东的水印  """
    im = Image.open(os.path.join(os.path.dirname(__file__), 'static/img/jd_logo.png'))
    if im.mode != 'RGBA':
        im = im.convert('RGBA')
    else:
        im = im.copy()
    #已经直接存成了半透明的文件，就不需要在这里再做一次半透明了
    #alpha = im.split()[3]
    #alpha = ImageEnhance.Brightness(alpha).enhance(0.5)
    #im.putalpha(alpha)
    return im

jd_logo_mask = prepare_jd_mask()


if __name__ == '__main__':
    define('app_path', os.path.dirname(os.path.abspath(__file__)))  # app.py所在目录
    define('app_port', 8101)

    load_app_options()  # 加载配置

    handlers = [
        (r'/arale/clear', ClearHandler),
        (r'/[op]/(.*)', CDNHandler, dict(path=options.cdn_root)),
        (r'/n/(.*)', AraleHandler, dict(path=options.cdn_root)),
        (r'/(.*)', AraleHandler, dict(path=sea_path)),
    ]
    application = web.Application(handlers, debug=True)
    application.listen(options.app_port)
    logging.info('application started on port: %s', options.app_port)
    ioloop.IOLoop.instance().start()