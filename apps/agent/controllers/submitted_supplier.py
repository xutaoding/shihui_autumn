#-*- coding:utf-8 -*-
from datetime import datetime
import random
import os
from tornado.options import options
from . import BaseHandler, authenticated
from autumn.torn.paginator import Paginator
from autumn.utils import json_dumps
from autumn.goods import img_url, contract_url
from tornado.web import StaticFileHandler
import tornado.web
from autumn.torn.form import Form
from voluptuous import Schema
from tornado.httputil import url_concat

list_schema = Schema({
    'brand': str,
    'status': str,
    'start_at': str,
    'end_at': str,
}, extra=True)


class List(BaseHandler):
    @authenticated
    def get(self):
        form = Form(self.request.arguments, list_schema)
        params = []
        sql = '''select p.*, a1.name as "city", a2.name as "district"
        from pool_supplier p, area1 a1, area1 a2
        where p.city_id = a1.id and p.district_id = a2.id and p.agent_id = %s and state in (3,4)'''
        params.append(self.current_user.id)
        if form.brand.value:
            sql += ' and brand_name like %s'
            params.append('%'+form.brand.value+'%')
        if form.status.value:
            sql += ' and state = %s'
            params.append(form.status.value)
        if form.start_at.value:
            sql += ' and apply_time > %s'
            params.append(form.start_at.value.strip() + ' 00:00:00')
        if form.end_at.value:
            sql += ' and apply_time <= %s'
            params.append(form.end_at.value.strip() + ' 23:59:59')
        sql += ' order by apply_time desc'
        page = Paginator(self, sql, params)
        self.render('supplier/submitted/list1.html', page=page, form=form)


class Upload(BaseHandler):
    @authenticated
    def post(self):
        if (not self.request.files) or (not 'imgFile' in self.request.files):
            return self.write(json_dumps({'error': 1, 'message': u'请选择文件'}))

        img_file = self.request.files['imgFile'][0]
        o_filename = img_file['filename']

        # 选择上传根目录
        root = self.get_argument('root', '')
        if root:
            upload_root = options['upload_img_path_%s' % root]
        else:
            upload_root = options.upload_img_path

        # 生成文件名
        random_id = int(datetime.now().strftime('%Y%m%d%H%M%S%f')[:19])
        random_id += random.randint(0, 99)
        extension = os.path.splitext(o_filename)[1]
        file_name = '%s%s' % (random_id, extension)

        # 算出目录
        first_dir = random_id >> 20
        second_dir = (~(first_dir << 10)) & (random_id >> 10)
        third_dir = (~((random_id >> 10) << 10)) & random_id
        first_dir %= 1000

        three_level_path = os.path.join(str(first_dir), str(second_dir), str(third_dir))
        file_dir = os.path.join(upload_root, three_level_path)

        # 如果目录不存在，创建之
        if not os.path.exists(file_dir):
            try:
                os.makedirs(file_dir)
            except OSError:
                return self.write(json_dumps({'error': 1, 'message': u'创建目录失败'}))

        # 保存文件
        try:
            with open(os.path.join(file_dir, file_name), 'w') as f:
                f.write(img_file['body'])
        except IOError:
            return self.write(json_dumps({'error': 1, 'message': u'保存文件失败'}))

        # 文件名上加认证信息、水印信息
        masks = ['nw']
        if self.get_argument('source', ''):
            masks.append(self.get_argument('source'))

        if root == 'contract':
            url = contract_url(os.path.join('/', three_level_path, file_name))
        else:
            url = img_url(os.path.join('/', three_level_path, file_name), *masks)
        self.write(json_dumps({'error': 0, 'url': url}))


class Add(BaseHandler):
    @authenticated
    def post(self):
        form = Form(self.request.arguments, list_schema)

        contract_urls = []
        contract_paths = self.get_arguments('contract')

        for path in contract_paths:
            path = path.split('/')
            # '/contract/o/312/636/29/2014011613053055005.jpg' 只提取 '/312/636/29/2014011613053055005.jpg'存储
            url = '/' + '/'.join(path[3:])
            contract_urls.append(url)

        certificate_urls = []
        certificate_paths = self.get_arguments('certificate')

        for path in certificate_paths:
            path = path.split('/')
            # '/contract/o/312/636/29/2014011613053055005.jpg' 只提取 '/312/636/29/2014011613053055005.jpg'存储
            url = '/' + '/'.join(path[3:])
            certificate_urls.append(url)


        contract_images = ','.join(contract_urls)
        certificate_images = ','.join(certificate_urls)

        apply_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        remark = apply_time + ": " + self.get_argument('remark')

        sql = 'update pool_supplier set apply_time=now(), state = 3'
        s_name = self.get_argument('supplier_name')
        phone = self.get_argument('supplier_phone')
        shop_short_name = self.get_argument('shop_short_name')
        remark = self.get_argument('remark')


        params = []
        if s_name:
            sql += ' , name=%s'
            params.append(s_name)
        if phone:
            sql += ' , phone=%s'
            params.append(phone)
        if shop_short_name:
            sql += ' , shop_short_name=%s'
            params.append(shop_short_name)
        if remark:
            sql += ' ,remark=concat(ifnull(remark, ""), now(), ":  ", %s, ",")'
            params.append(remark)
        if contract_images:
            sql += ' , contract=%s'
            params.append(contract_images)
        if certificate_urls:
            sql += ' , certificate=%s'
            params.append(certificate_images)
        sql += ' where agent_id=%s and id=%s'
        params.append(self.current_user.id)
        params.append(self.get_argument('id'))
        self.db.execute(sql, *params)

        self.redirect(url_concat(self.reverse_url('supplier.submitted.list'), {'status': form.status.value,
                      'start_at': form.start_at.value, 'end_at': form.end_at.value, 'brand': form.brand.value}))


class Edit(BaseHandler):
    @authenticated
    def post(self):
        sql = '''select p.*, a1.name as "city", a2.name as "district"
        from pool_supplier p, area1 a1, area1 a2
        where p.city_id = a1.id and p.district_id = a2.id and p.agent_id = %s and p.id = %s'''
        supplier = self.db.get(sql, self.current_user.id, self.get_argument('id'))
        params = {}
        if supplier.contract:
            contract_urls = generate_img_url(supplier.contract)
            params['contract_urls'] = contract_urls
        if supplier.certificate:
            certificate_urls = generate_img_url(supplier.certificate)
            params['certificate_urls'] = certificate_urls
        params['supplier'] = supplier
        self.render('supplier/submitted/add.html', **params)


class Detail(BaseHandler):
    @authenticated
    def get(self):
        sql = '''select p.*, a1.name as "city", a2.name as "district"
        from pool_supplier p, area1 a1, area1 a2
        where p.city_id = a1.id and p.district_id = a2.id and p.id = %s'''
        supplier = self.db.get(sql, self.get_argument('id'))
        params = {}
        if supplier.contract:
            contract_urls = generate_img_url(supplier.contract)
            params['contract_urls'] = contract_urls
        if supplier.certificate:
            certificate_urls = generate_img_url(supplier.certificate)
            params['certificate_urls'] = certificate_urls
        params['supplier'] = supplier
        self.render('supplier/submitted/detail.html', **params)


def generate_img_url(images):
    """把数据库的图片名如：/27/610/148/231323.jpg
    转化成URL如：http://.../contract/o/27/610/148/231323.jpg"""
    image_urls = []
    image_list = images.split(',')
    for image in image_list:
        image_urls.append(contract_url(image))
    return image_urls


class ContractImage(StaticFileHandler):
    """获得合同图片"""
    def get(self, path, include_body=True):
        uid = self.get_secure_cookie('_ag')
        if uid and uid.isdigit():
            if not self.application.db.get('select * from agent where id=%s and deleted=0', uid):
                raise tornado.web.HTTPError(403)
        else:
            raise tornado.web.HTTPError(403)

        super(ContractImage, self).get(path, include_body)