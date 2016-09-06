# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import StringIO
import time
from voluptuous import Schema
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from tornado.options import options
from xlwt import Workbook
from autumn.utils import json_dumps
from autumn import const
from datetime import datetime, timedelta

list_schema = Schema({
    'partner': str,
    'send_time_start': str,
    'send_time_end': str,
}, extra=True)


class Show(BaseHandler):
    @require()
    def get(self):
        """ 展示页面"""
        sql = """select oi.distributor_goods_no,i.goods_name short_name,count(distinct oi.shipping_info_id) send_count,
                 sum(oi.sales_price) amount from order_item oi,order_shipping_info osi,item i
                 where oi.shipping_info_id = osi.id and i.order_item_id =oi.id and osi.express_number is not null
                 and oi.distributor_shop_id = %s """

        form = Form(self.request.arguments, list_schema)
        params = []

        if form.partner.value:
            #获取不同渠道的分销ID
            distributor = getPartnerInfo(form.partner.value)
            params.append(distributor['id'])
        else:
            distributor = getPartnerInfo("JD")
            form.partner.value = "JD"
            params.append(distributor['id'])

        if form.send_time_start.value:
            sql += "and CAST(i.used_at as Date) >= %s "
            params.append(form.send_time_start.value)
        else:
            #默认显示前一周到现在的发货信息
            sql += "and CAST(i.used_at as Date) >= %s "
            form.send_time_start.value = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            params.append(form.send_time_start.value)

        if form.send_time_end.value:
            sql += "and CAST(i.used_at as Date) <= %s "
            params.append(form.send_time_end.value)

        sql += "group by oi.distributor_goods_no"
        page = Paginator(self, sql, params)

        self.render("real/trackno.html", page=page, form=form)


class Download(BaseHandler):
    @require('operator', 'service')
    def get(self):
        send_time_start = self.get_argument("send_time_start")
        send_time_end = self.get_argument("send_time_end")
        distributor_goods_no = self.get_argument("distributor_goods_no")
        is_download_all = self.get_argument("is_download_all")
        partner = self.get_argument("partner")

        #获取不同渠道的分销名称
        distributor = getPartnerInfo(partner)
        #指定返回的类型
        self.set_header('Content-type', 'application/excel')

        if is_download_all:
            filename = distributor['name'] + time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        else:
            filename = distributor['name'] + distributor_goods_no

        #设定用户浏览器显示的保存文件名
        self.set_header('Content-Disposition', 'attachment; filename=' + filename + '.xls')

        sql = """select oi.id order_item_id,ec.id company_id,ec.name company_name,do.order_no,osi.express_number
                 from order_item oi, order_shipping_info osi,express_company ec,item i,distributor_order do
                 where i.order_item_id =oi.id and oi.shipping_info_id=osi.id and osi.express_company_id = ec.id and
                 do.order_id =oi.order_id and
                 osi.express_number is not null and oi.distributor_shop_id = %s
                 """
        params = [distributor['id']]
        if distributor_goods_no:
            sql += "and oi.distributor_goods_no = %s"
            params.append(distributor_goods_no)

        if send_time_start:
            sql += "and i.used_at >= %s"
            params.append(send_time_start)

        if send_time_end:
            sql += "and i.used_at <= %s"
            params.append(send_time_end)

        order_item_list = self.db.query(sql, *params)
        excel_heads = ['订单号', '配送商', '配送单号', '操作'] if partner == 'YHD' else ['订单号', '运单号', '快递公司']

        order_list_excel = Workbook(encoding='utf-8')
        write_order_list_excel = order_list_excel.add_sheet('0', cell_overwrite_ok=True)

        for i in range(len(excel_heads)):
            write_order_list_excel.write(0, i, excel_heads[i])

        #取得快递信息
        expresses = self.db.query("select id,code,name,distributor_mapping from express_company")
        express_map = {}
        for express in expresses:
            partner_express = express.distributor_mapping.split("\n")
            for e in partner_express:
                if ":" in e:
                    express_item = e.split(":")
                    express_map[express_item[0] + "-" + str(express.id)] = express_item[1]

        if express_map is '':
            return self.write(json_dumps({'error': 1, 'message': u'还没添加快递公司信息，请确认！'}))

        row = 0
        fields = ['order_no', 'express_number', 'express_number'] if partner == 'YHD' else ['order_no', 'express_number']
        item_ids = []
        #转换快递信息
        for order in order_item_list:
            item_ids.append(order.order_item_id)
            express_info = express_map[str(partner) + '-' + str(order['company_id'])]
            if express_info is '':
                return self.write(json_dumps({'error': 1, 'message': u'没有对应的快递编码，请确认！'}))

            row += 1
            for j in range(len(fields)):
                v = order[fields[j]]
                write_order_list_excel.write(row, j, str(v) if v is not None else '')
                if partner == 'YHD':
                    write_order_list_excel.write(row, 1, express_info)
                    write_order_list_excel.write(row, 3, '1')
                else:
                    write_order_list_excel.write(row, 2, express_info)

        stream = StringIO.StringIO()
        order_list_excel.save(stream)

        #最后把相关订单更新未已上传
        self.db.execute("update item set status = %%s where status= %%s and order_item_id in(%s) " %
                        ','.join(['%s'] * len(item_ids)),
                        const.status.UPLOADED, const.status.USED, *item_ids)

        self.write(stream.getvalue())


def getPartnerInfo(partner):
    if partner == 'TB':
        return {'id': options.shop_id_taobao, 'name': '淘宝发货单导出_'}
    elif partner == 'YHD':
        return {'id': options.shop_id_yihaodian, 'name': '一号店发货单导出_'}
    elif partner == 'WB':
        return {'id': options.shop_id_wuba, 'name': '58团发货单导出_'}
    elif partner == 'JD':
        return {'id': options.shop_id_jingdong, 'name': '京东发货单导出_'}




