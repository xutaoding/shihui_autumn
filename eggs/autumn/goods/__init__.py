# -*- coding: utf-8 -*-

import os
import hashlib
import logging
import re
from tornado.options import options


def img_sign(filename):
    return hashlib.md5(filename + '-' + options.img_key).hexdigest()[-8:]


def img_url(img_path, *masks):
    """ img_path 接受 型如 /334/812/639/20130913104511.png 这样的参数
        返回ur中自动加上 标记信息和签名
    """
    if not img_path:
        return ''
    dir_name = os.path.dirname(img_path)
    file_name = os.path.basename(img_path)
    base_name, extension = os.path.splitext(file_name)
    if masks:
        base_name += '_' + '_'.join(masks)
    file_name = base_name + extension
    file_name = img_sign(file_name) + '_' + file_name

    return 'http://%s/p%s' % (options.img_host, os.path.join(dir_name, file_name))


def contract_url(img_path):
    """ img_path 接受 型如 /334/812/639/20130913104511.png 这样的参数
        合同图片返回url中直接取 /o 文件夹下到原图，不加标记信息和签名
    """
    if not img_path:
        return ''
    url = '/contract/o%s' % (img_path.encode('utf-8'))
    logging.info('eggs/autumn/goods/__init__: 生成合同图片路径 %s' % url)
    return url


def alloc_distributor_goods(db, goods_id, shop_id):
    dg = db.get('select * from goods_distributor_shop where goods_id=%s and distributor_shop_id=%s '
                'and status="PREPARE" and deleted=0', goods_id, shop_id)
    if not dg:
        dg_id = db.execute('insert into goods_distributor_shop(goods_id, distributor_goods_id, distributor_shop_id, '
                           'goods_link_id,created_at, created_by, status) values (%s, 0, %s, 0, NOW(), "","PREPARE")',
                           goods_id, shop_id)
        db.execute('update goods_distributor_shop set goods_link_id=%s where id=%s', dg_id+20000, dg_id)
        dg = db.get('select * from goods_distributor_shop where goods_id=%s and distributor_shop_id=%s '
                    'and status="PREPARE" and deleted=0', goods_id, shop_id)

    return dg


def jd_logo_url_replace(detail):
    """替换京东推送时详情中的图片为带京东水印的图片"""
    img_tag_ptn = re.compile("""<img[^>]*src=["']([^"^']*)""")
    cdn_o_ptn = re.compile("""(.+)%s/o/(\d+)/(\d+)/(\d+)/[a-z0-9]{8}_(.+)""" % options.img_host)
    cdn_p_ptn = re.compile("""(.+)%s/p/(\d+)/(\d+)/(\d+)/[a-z0-9]{8}_(.+)""" % options.img_host)

    if not detail:
        return detail

    # 找出所有的<img> tag
    img_tags = re.findall(img_tag_ptn, detail)
    for tag in img_tags:
        m = cdn_p_ptn.match(tag)
        # 匹配的图片
        if not m:
            m = cdn_o_ptn.match(tag)
        if m:
            file_name = m.group(5)
            base_name, extension = os.path.splitext(file_name)
            new_name = base_name+"_jd_max420"+extension
            sign = img_sign(new_name)
            new_src = m.group(1)+options.img_host+'/p/'+m.group(2)+'/'+m.group(3)+'/'+m.group(4)+'/'+sign+'_'+new_name
            # 替换
            detail = re.sub(tag, new_src, detail)
    return detail


def html_font_size_replace(content, o_size, t_size):
    """<span style="font-size:14px;">
    """
    if not content:
        return content

    font_size_tag = re.compile(r'["; ](font-size:%spx)' % o_size)
    tags = re.findall(font_size_tag, content)
    for tag in tags:
        content = re.sub(tag, 'font-size:%spx' % t_size, content)
    return content
