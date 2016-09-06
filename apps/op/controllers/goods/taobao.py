# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
import json
import tornado.gen
import os
from autumn.utils import json_dumps
from autumn.api.taobao import Taobao
from autumn.goods import alloc_distributor_goods, img_url
from autumn.utils import json_hook
from tornado.options import options
from autumn.goods import jd_logo_url_replace
import re


class ShowCategory(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def get(self, goods_id):
        shop_id = self.get_argument('shop_id')
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        taobao_nick = distributor_shop.taobao_nick
        # 获取店铺类型
        request = Taobao('taobao.user.seller.get')
        request.set_app_info(app_info.app_key, app_info.app_secret_key)
        request.set_session(app_info.session)
        response = yield request(fields=','.join([taobao_nick, 'type']))
        request.parse_response(response.body)
        # C店，B店不同流程
        # todo B店部分推送的商品必须有一个对应的产品
        self.render('goods/distributor/taobao/category.html', goods_id=goods_id, shop_id=self.get_argument('shop_id'),
                    user_type=request.message.user.type)


class PictureReplace(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def get(self):
        goods_id = self.get_argument('goods_id')
        shop = self.get_argument('shop')
        shop_id = {'tm': options.shop_id_tmall, 'tb': options.shop_id_taobao}.get(shop, 0)
        goods = self.db.get('select * from goods where id = %s', goods_id)
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        goods.detail = yield replace_with_taobao_img(goods.detail, app_info)
        goods.supplier_intro = yield replace_with_taobao_img(goods.supplier_intro, app_info)

        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        self.write({'detail': goods.detail, 'supplier_intro': goods.supplier_intro})


@tornado.gen.coroutine
def replace_with_taobao_img(content, app_info):
    """替换淘宝推送时详情中的图片为淘宝的图片"""
    img_tag_ptn = re.compile("""<img[^>]*src=["']([^"^']*)""")
    cdn_o_ptn = re.compile("""(.+)%s/o/(\d+)/(\d+)/(\d+)/(.+)""" % options.img_host)
    cdn_p_ptn = re.compile("""(.+)%s/p/(\d+)/(\d+)/(\d+)/(.+)""" % options.img_host)
    # 找出所有的<img> tag
    img_tags = re.findall(img_tag_ptn, content)
    for tag in img_tags:
        m = cdn_p_ptn.match(tag)
        file_path = 'p'
        # 匹配的图片
        if not m:
            m = cdn_o_ptn.match(tag)
            file_path = 'o'
        if m:
            file_path += '/%s/%s/%s/%s' % (m.group(2), m.group(3), m.group(4), m.group(5))
            file_path = os.path.join(options.cdn_root, file_path)
            fo = open(file_path, 'rb')
            request = Taobao('taobao.picture.upload')
            request.set_app_info(app_info.app_key, app_info.app_secret_key)
            request.set_session(app_info.session)
            request.add_file('img', fo.name, fo.read())

            response = yield request(picture_category_id='0', image_input_title=fo.name.encode('utf-8'))
            request.parse_response(response.body)
            if request.is_ok():
                new_src = request.message.picture.picture_path
            else:
                continue
            content = content.decode('utf-8') if isinstance(content, str) else content
            # 替换
            content = re.sub(tag, new_src, content)
    raise tornado.gen.Return(content)


class TBEdit(BaseHandler):
    @require('operator')
    @tornado.gen.coroutine
    def get(self):
        """C 店推送商品编辑页面"""
        goods_id = self.get_argument('goods_id')
        shop_id = self.get_argument('shop_id', '')
        cid = self.get_argument('category', '0')
        goods = self.db.get('select g.* from goods g where g.id = %s', goods_id)
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        # 适用门店
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            goods_id, goods_id
        )
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        taobao_nick = distributor_shop.taobao_nick

        # 获取所有类目属性
        attributes = yield get_category_props(cid, app_info)

        # 获取本店类目
        item_cats = yield get_shop_category(app_info, taobao_nick)

        # goods.detail = yield replace_with_taobao_img(goods.detail, app_info)
        # goods.supplier_intro = yield replace_with_taobao_img(goods.supplier_intro, app_info)

        self.render('goods/distributor/taobao/tb_push.html', cid=cid, goods=goods, shop_id=shop_id, shops=shops,
                    attributes=attributes, item_cats=item_cats, jd_logo_url_replace=jd_logo_url_replace)


class TMEdit(BaseHandler):
    """B 店推送编辑页面"""
    @require('operator')
    @tornado.gen.coroutine
    def get(self):
        goods_id = self.get_argument('goods_id')
        shop_id = self.get_argument('shop_id', '')
        cid = self.get_argument('category', '0')
        goods = self.db.get('select g.* from goods g where g.id = %s', goods_id)
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        # 适用门店
        shops = self.db.query(
            'select ss.* from supplier_shop ss,goods g where ss.supplier_id=g.supplier_id and g.id=%s and ss.deleted=0 '
            'and (g.all_shop=1 or ss.id in (select supplier_shop_id from goods_supplier_shop where goods_id=%s) ) ',
            goods_id, goods_id
        )
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        taobao_nick = distributor_shop.taobao_nick

        # 获取所有类目属性
        attributes = yield get_category_props(cid, app_info)

        # 获取本店类目
        item_cats = yield get_shop_category(app_info, taobao_nick)

        # goods.detail = yield replace_with_taobao_img(goods.detail, app_info)
        # goods.supplier_intro = yield replace_with_taobao_img(goods.supplier_intro, app_info)

        self.render('goods/distributor/taobao/tm_push.html', cid=cid, goods=goods, shop_id=shop_id, shops=shops,
                    attributes=attributes, item_cats=item_cats)


class Push(BaseHandler):
    """发送淘宝推送请求"""
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        props = ''
        args = self.request.arguments.copy()
        shop_id = args.pop('shop_id')[0]

        input_pids = ''
        input_str = ''
        if 'attr-name' in args:
            for pid in args.pop('attr-name'):
                if pid in args:
                    for v in args.pop(pid):
                        if v == '_custom_':
                            input_pids += '%s,' % pid
                            input_str += '%s,' % args.pop('%s_custom' % pid)[0]
                            break
                        props += '%s:%s;' % (pid, v)

        if 'seller_cids' in args:
            seller_cids = ','.join(args.pop('seller_cids'))
            args['seller_cids'] = seller_cids
        args = dict([(key, args[key][0]) for key in args])
        args['props'] = props
        args['input_str'] = input_str
        args['input_pids'] = input_pids
        goods_id = args.pop('goods_id')
        dg = alloc_distributor_goods(self.db, goods_id, shop_id)
        args['outer_id'] = dg.goods_link_id

        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                              shop_id).taobao_api_info, object_hook=json_hook)
        goods_push = Taobao('taobao.item.add')
        goods_push.set_app_info(app_info.app_key, app_info.app_secret_key)
        goods_push.set_session(app_info.session)

        response = yield goods_push(**args)
        goods_push.parse_response(response.body)

        ok = 0
        num_iid = ''
        if goods_push.is_ok():
            ok = 1
            num_iid = goods_push.message.item.num_iid
            message = '发布成功'
            self.db.execute('update goods_distributor_shop set status="PENDING", created_by=%s, created_at=NOW(), '
                            'distributor_goods_id=%s where goods_id=%s and distributor_shop_id=%s and goods_link_id=%s',
                            self.current_user.name, num_iid, goods_id, shop_id, dg.goods_link_id)
        else:
            err_msg = goods_push.error.sub_msg if 'sub_msg' in goods_push.error else goods_push.error.msg
            message = '发布失败：' + err_msg.encode('utf-8')

        img_paths = self.db.get('select img_paths from goods where id=%s', goods_id).img_paths
        img_paths = json.loads(img_paths) if img_paths else dict()

        self.render('goods/distributor/taobao/result.html', message=message, ok=ok,
                    num_iid=num_iid, shop_id=shop_id, img_paths=img_paths, img_url=img_url)


class UploadMajorImage(BaseHandler):
    """ 淘宝上传图片"""
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        num_iid = self.get_argument('num_iid').encode('utf-8')
        arg_img_url = self.get_argument('img_url')
        shop_id = self.get_argument('shop_id')
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        img_path = os.path.join(options.upload_img_path, arg_img_url[1:])
        try:
            fo = open(img_path, 'rb')
        except IOError:
            self.write(json_dumps({'error': "没有找到图片文件"}))
            return
        request = Taobao('taobao.item.img.upload')
        request.set_app_info(app_info.app_key, app_info.app_secret_key)
        request.set_session(app_info.session)
        request.add_file('image', fo.name, fo.read())
        fo.close()
        response = yield request(num_iid=num_iid, is_major='true')
        request.parse_response(response.body)
        if request.is_ok():
            self.write(json_dumps({'success': '图片上传成功'}))
        else:
            err_msg = request.error.sub_msg if 'sub_msg' in request.error else request.error.msg
            self.write(json_dumps({'error': err_msg}))


class UploadTaobaoImage(BaseHandler):
    """ 淘宝上传图片"""
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        if (not self.request.files) or (not 'imgFile' in self.request.files):
            return

        img_file = self.request.files['imgFile'][0]
        o_filename = img_file['filename']
        shop_id = self.get_argument('shop_id', '13')
        distributor_shop = self.db.get('select taobao_api_info, taobao_nick from distributor_shop where id = %s',
                                       shop_id)
        app_info = json.loads(distributor_shop.taobao_api_info, object_hook=json_hook)
        try:
            request = Taobao('taobao.picture.upload')
            request.set_app_info(app_info.app_key, app_info.app_secret_key)
            request.set_session(app_info.session)
            request.add_file('img', o_filename, img_file['body'])
            response = yield request(picture_category_id='0', image_input_title=o_filename.encode('utf-8'))
            request.parse_response(response.body)
            if request.is_ok():
                self.write({'error': 0, 'url': request.message.picture.picture_path})
            else:
                err_msg = request.error.sub_msg if 'sub_msg' in request.error else request.error.msg
                self.write(json_dumps({'error': err_msg}))
        except IOError:
            self.write(json_dumps({'error': "没有找到图片文件"}))
            return


class CategoryAjax(BaseHandler):
    """ 淘宝分类 用于响应 zTree 发起的 ajax 请求 """
    @require('operator')
    @tornado.gen.coroutine
    def post(self):
        app_info = json.loads(self.db.get('select taobao_api_info from distributor_shop where id = %s',
                              self.get_argument('shop_id')).taobao_api_info, object_hook=json_hook)
        parent_id = self.get_argument('id', '0')

        # 第一次请求的类目不同，天猫请求授权类目，淘宝请求所有标准类目
        user_type = self.get_argument('user_type')
        if parent_id == '0' and user_type == u'B':
            taobao = Taobao('taobao.itemcats.authorize.get')
            taobao.add_fields(fields='item_cat.cid,item_cat.name,item_cat.parent_cid,item_cat.is_parent')
        else:
            taobao = Taobao('taobao.itemcats.get')
            taobao.add_fields(parent_cid=parent_id, fields='cid,name,is_parent')

        taobao.set_app_info(app_info.app_key, app_info.app_secret_key)
        taobao.set_session(app_info.session)
        response = yield taobao()
        self.set_header('Content-Type', 'application/json; charset=UTF-8')
        taobao.parse_response(response.body)

        if parent_id == '0' and user_type == u'B':
            item_cats = taobao.message.seller_authorize.item_cats.item_cat
        else:
            item_cats = taobao.message.item_cats.item_cat

        if taobao.is_ok():
            result = []
            for node in item_cats:
                result.append({
                    'id': node.cid,
                    'name': node.name,
                    'isParent': node.is_parent,
                })
            self.write(json_dumps(result))
        else:
            self.write('[]')


@tornado.gen.coroutine
def get_category_props(cid, app_info):
    """获取标准类目的属性"""
    attribute_request = Taobao('taobao.itemprops.get')
    attribute_request.set_app_info(app_info.app_key, app_info.app_secret_key)
    attribute_request.set_session(app_info.session)
    response = yield attribute_request(cid=cid, fields='pid,name,must,multi,prop_values,is_input_prop,features')
    attribute_request.parse_response(response.body)

    attributes = []
    if attribute_request.is_ok() and 'item_props' in attribute_request.message:
        if 'item_prop' in attribute_request.message.item_props:
            attributes = attribute_request.message.item_props.item_prop
    raise tornado.gen.Return(attributes)


@tornado.gen.coroutine
def get_shop_category(app_info, taobao_nick):
    """获取店内目录"""
    category_request = Taobao('taobao.sellercats.list.get')
    category_request.set_app_info(app_info.app_key, app_info.app_secret_key)
    category_request.set_session(app_info.session)
    category_response = yield category_request(nick=taobao_nick)
    category_request.parse_response(category_response.body)
    item_cats = []
    if category_request.is_ok() and 'seller_cat' in category_request.message.seller_cats:
        item_cats = category_request.message.seller_cats.seller_cat

    raise tornado.gen.Return(item_cats)
