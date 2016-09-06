# -*- coding: utf-8 -*-
from .. import BaseHandler
from .. import require
import logging
from voluptuous import Schema
from autumn.torn.paginator import Paginator
from autumn.torn.form import Form
from copy import deepcopy
from xlwt import Workbook, Font, Borders, XFStyle, Alignment
import StringIO
from datetime import datetime, timedelta
import rmb

list_schema = Schema({
    'supplier': str,
    'status': str,
    'apply_time_start': str,
    'apply_time_end': str,
}, extra=True)


class WithdrawApproval(BaseHandler):
    @require()
    def get(self):
        """ 提现申请管理 """
        form = Form(self.request.arguments, list_schema)
        sql = 'select wb.*,a.type account_type from withdraw_bill wb, account a where a.id=wb.account_id '

        params = []
        if form.supplier.value:
            supplier = self.db.get('select * from supplier where id =%s and deleted=0', form.supplier.value)
            if supplier.separate_account == '0':
                accounts = [supplier]
            else:
                accounts = self.db.query('select account_id from supplier_shop '
                                         'where deleted=0 and supplier_id=%s', form.supplier.value)
            sql += 'and wb.account_id in (%s) ' % ','.join(['%s'] * len(accounts))
            params = [str(i.account_id) for i in accounts]

        if form.status.value:
            sql += 'and wb.status=%s '
            params.append(form.status.value)

        if form.apply_time_start.value:
            sql += "and wb.applied_at >= %s "
            params.append(form.apply_time_start.value)

        if form.apply_time_end.value:
            sql += "and wb.applied_at <= %s "
            params.append(form.apply_time_end.value)

        sql += " order by wb.applied_at desc"
        page = Paginator(self, sql, params)
        self.render("finance/withdraw/list.html", page=page, form=form)

    @require('finance_mgr')
    def post(self):
        action = self.get_argument("action")
        comment = self.get_argument("comment")
        fee = self.get_argument("fee")
        withdraw_bill = self.db.get('select wb.*,a.type account_type, a.uid from withdraw_bill wb, account a '
                                    'where a.id=wb.account_id and wb.id=%s', self.get_argument('id'))

        if not fee or not fee.isdigit():
            error_info = u'手续费要为数字！'
            self.render("finance/detail.html", withdraw_bill=withdraw_bill, error_info=error_info)

        #如果不是待审批状态，则表示已经处理过
        if withdraw_bill.status != 0:
            logging.info("the withdraw bill has been processed already")
            self.redirect(self.reverse_url('finance.withdraw'))

        if withdraw_bill.account_type == 1:
            accounts = self.db.query('select account_id from supplier_shop where supplier_id=%s', withdraw_bill.uid)
            account_ids = [a.account_id for a in accounts]
        elif withdraw_bill.account_type == 2:
            account_ids = [self.db.get('select account_id from supplier_shop where id=%s',
                                       withdraw_bill.uid).account_id]
        else:
            import tornado.web
            raise tornado.web.HTTPError(403)

        withdraw_bill_status = {'approve': 2, 'reject': 1}[action]
        account_sequence_status = {'approve': 3, 'reject': 1}[action]
        self.db.execute('update withdraw_bill set fee=%s, comment=%s, approver=%s, approve_at=now(), status=%s '
                        'where id =%s', fee, comment, self.current_user.name, withdraw_bill_status, withdraw_bill.id)
        self.db.execute('update account_sequence set status=%%s where status=2 and account_id in (%s)'
                        % ','.join(['%s']*len(account_ids)), account_sequence_status, *account_ids)
        # 拒绝提现，删除补余的2条数据
        if action == 'reject':
            self.db.execute('delete from account_sequence where trade_type=2 and trade_id=%s ', withdraw_bill.id)

        self.redirect(self.reverse_url('finance.withdraw'))


class Detail(BaseHandler):
    @require()
    def get(self, withdraw_bill_id):
        """ 详情"""
        withdraw_bill = self.db.get('select wb.*,a.type account_type, a.uid from withdraw_bill wb, account a '
                                    'where a.id=wb.account_id and wb.id=%s', withdraw_bill_id)
        if withdraw_bill.account_type == 1:
            supplier = self.db.get('select s.id, s.name, s.short_name, s.properties, o.name oname from supplier s '
                                   'left join operator o on s.sales_id = o.id '
                                   'where s.id = %s', withdraw_bill.uid)
        else:
            supplier = self.db.get('select s.id, s.name, s.short_name, s.properties, o.name oname from supplier s '
                                   'left join supplier_user su on s.id = su.supplier_id left '
                                   'join operator o on s.sales_id = o.id where su.shop_id = %s and su.deleted=0',
                                   withdraw_bill.uid)
        types = {'coupon': '电子券', 'ktv': 'ktv产品', 'real': '实物'}
        sales_type = ','.join([v for p in supplier.properties.split(',') for k, v in types.iteritems() if k == p])
        self.render("finance/withdraw/detail.html", withdraw_bill=withdraw_bill, supplier=supplier, sales_type=sales_type,
                    error_info='')


class Download(BaseHandler):
    @require('finance')
    def get(self):
        withdraw_list = str(self.get_argument('withdraw_list', '0')).split(',')
        sql = """select wb.*,a.uid, a.type from withdraw_bill wb, account a
                where a.id = wb.account_id
                and wb.id in (%s) """ % ','.join(['%s'] * len(withdraw_list))
        withdraw_content = self.db.query(sql, *withdraw_list)
        withdraw_excel = Workbook(encoding='utf-8')
        work_excel = withdraw_excel.add_sheet('0')
        withdraw_info = []
        for item in withdraw_content:
            apply_time = item.applied_at.strftime('%Y-%m-%d')
            sales_sql = """select o.name from operator o, supplier s where s.sales_id = o.id and s.id = %s"""
            params = item.uid if item.type == 1 else self.db.get('select supplier_id from supplier_shop where id = %s', item.uid).supplier_id
            sales = self.db.get(sales_sql, params)
            supplier_type = {1: '商户', 2: '门店'}.get(item.type, '') + '(' + item.account_name + ')'
            supplier = '业务员:' + sales.name
            apply = '付款申请人:' + item.applier + '申请日期:' + apply_time
            company = item.user_name
            bank = item.bank_name + item.bank_city + item.sub_bank_name
            account = ''.join([i for i in list(item.card_number) if i != ' '])
            money = item.amount
            #查询商户合同，在2013-9-15之前的为T+3，之后为T+5
            contract = self.db.get('select created_at from contract where uid = %s and type = 1 order by start_at '
                                   'limit 1', params)
            payment_day_type = 'T+3'
            if contract and contract.created_at > datetime.strptime('2013-9-15', '%Y-%m-%d'):
                payment_day_type = 'T+5'
            if payment_day_type == 'T+3':
                date = (item.applied_at + timedelta(pay_date(item.applied_at, 3))).strftime('%Y-%m-%d')
            else:
                date = (item.applied_at + timedelta(pay_date(item.applied_at, 5))).strftime('%Y-%m-%d')

            account_date = '网转   账期：' + payment_day_type
            print_info = '付款申请打印人: ' + self.current_user.name + '   付款申请打印日期:' + datetime.now().strftime('%Y-%m-%d') + '  '
            withdraw_item = {
                'supplier': supplier,
                'supplier_type': supplier_type,
                'apply': apply,
                'applier': item.applier,
                'apply_time': apply_time,
                'company': company,
                'bank': bank,
                'payment_day_type': payment_day_type,
                'date': date,
                'account': account,
                'money': money,
                'china_money': rmb.upper(money),
                'account_date': account_date,
                'print_info': print_info
            }
            withdraw_info.append(withdraw_item)

        create_excel(work_excel, withdraw_info)
        #指定返回的类型
        self.set_header('Content-type', 'application/excel')
        #设定用户浏览器显示的保存文件名
        self.set_header('Content-Disposition', 'attachment; filename=withdraw.xls')

        stream = StringIO.StringIO()
        withdraw_excel.save(stream)
        self.write(stream.getvalue())


def get_withdraw_bill(self):
    return self.db.get(
        'select wb.*,a.type,a.uid from withdraw_bill wb ,account a '
        'where wb.account_id=a.id and wb.id =%s', self.get_argument('id'))


def create_excel(work_excel, withdraw_info=[]):
    title_fnt = Font()
    title_fnt.height = 0x0140
    title_fnt.name = u'宋体'
    title_fnt.bold = True

    brd = Borders()
    brd.bottom = 1
    brd.top = 1
    brd.left = 1
    brd.right = 1

    title_location = Alignment()
    title_location.horz = Alignment.HORZ_CENTER
    title_location.vert = Alignment.VERT_CENTER

    title_style = XFStyle()
    title_style.font = title_fnt
    title_style.alignment = title_location

    style = XFStyle()
    style.font.height = 0x00E0
    style.font.name = u'宋体'
    style.font.bold = False
    style.alignment.horz = Alignment.HORZ_CENTER
    style.alignment.vert = Alignment.VERT_CENTER

    content_title_style = deepcopy(style)
    content_title_style.alignment.horz = Alignment.HORZ_LEFT
    content_title_style.font.height = 0x00E0

    content_style = deepcopy(style)
    content_style.alignment.horz = Alignment.HORZ_LEFT

    center_content_style = deepcopy(style)
    center_content_style.alignment.horz = Alignment.HORZ_CENTER
    center_content_style.borders = brd

    style.borders = brd
    content_style.borders = brd

    merge_up_style = deepcopy(style)
    merge_up_style.borders.bottom = 0

    content_up_style = deepcopy(merge_up_style)
    content_up_style.alignment.horz = Alignment.HORZ_CENTER
    merge_down_style = deepcopy(style)
    merge_down_style.borders.top = 0
    content_down_style = deepcopy(merge_down_style)
    content_down_style.alignment.horz = Alignment.HORZ_RIGHT
    content_down_style.font.height = 0x00CA

    for i, info in enumerate(withdraw_info):
        width = i * 25
        work_excel.write_merge(2 + width, 2 + width, 0, 16, u'商户提现付款申请单', title_style)

        work_excel.write_merge(3 + width, 3 + width, 1, 5, info['supplier_type'], content_title_style)
        work_excel.write_merge(3 + width, 3 + width, 6, 16, info['supplier'], content_title_style)

        work_excel.write(4 + width, 0, u'收款单位名称', style)
        work_excel.write_merge(4 + width, 4 + width, 1, 5, info['company'], content_style)
        work_excel.write(4 + width, 6, u'申请提现帐号', style)
        work_excel.write_merge(4 + width, 4 + width, 7, 16, info['applier'], center_content_style)

        work_excel.write(5 + width, 0, u'开户银行', style)
        work_excel.write_merge(5 + width, 5 + width, 1, 5, info['bank'], content_style)
        work_excel.write(5 + width, 6, u'申请提现日期', style)
        work_excel.write_merge(5 + width, 5 + width, 7, 16, info['apply_time'], center_content_style)

        work_excel.write(6 + width, 0, u'银行帐号', style)
        work_excel.write_merge(6 + width, 6 + width, 1, 5, info['account'], content_style)
        work_excel.write(6 + width, 6, u'合同账期', style)
        work_excel.write_merge(6 + width, 6 + width, 7, 16, info['payment_day_type'], center_content_style)

        work_excel.write(7 + width, 0, u'付款用途', style)
        work_excel.write_merge(7 + width, 7 + width, 1, 5, u'商户提现', content_style)
        work_excel.write(7 + width, 6, u'付款日期', style)
        work_excel.write_merge(7 + width, 7 + width, 7, 16, info['date'], center_content_style)

        units = [u'千', u'百', u'十', u'万', u'千', u'百', u'十', u'元', u'角', u'分']
        digit = list(str(info['money']))
        digit.remove('.')
        digit.reverse()
        for j, unit in enumerate(units):
            work_excel.write(8 + width, 7 + j, unit, content_style)
        for index, value in enumerate(digit):
            work_excel.write(9 + width, 16 - index, value, content_style)
        work_excel.write(9 + width, 16 - index - 1, '￥', content_style)

        work_excel.write_merge(10 + width, 11 + width, 0, 0, u'备注事项', style)
        work_excel.write_merge(10 + width, 10 + width, 1, 6, '', content_style)
        work_excel.write_merge(10 + width, 10 + width, 7, 16, '', style)
        work_excel.write_merge(11 + width, 11 + width, 1, 16, info['print_info'], content_down_style)

        work_excel.write(8 + width, 0, u'付款金额', merge_up_style)
        work_excel.write(9 + width, 0, u'人民币（大写）', merge_down_style)
        work_excel.write_merge(8 + width, 9 + width, 1, 6, info['china_money'], content_style)

        work_excel.write_merge(13 + width, 13 + width, 0, 2, u'部门主管:', content_title_style)
        work_excel.write_merge(13 + width, 13 + width, 3, 5, u'财务经理:', content_title_style)
        work_excel.write_merge(13 + width, 13 + width, 6, 16, u'公司总经理:', content_title_style)
        for row in range(2, 12):
            work_excel.row(row + width).height_mismatch = 1
            work_excel.row(row + width).height = 478
        work_excel.row(2 + width).height_mismatch = 1
        work_excel.row(2 + width).height = 1000

    work_excel.col(0).width = 3871
    work_excel.col(1).width = 1771
    work_excel.col(2).width = 1509
    work_excel.col(3).width = 2348
    work_excel.col(4).width = 840
    work_excel.col(5).width = 3241
    work_excel.col(6).width = 3441
    for col in range(7, 17):
        work_excel.col(col).width = 709


def pay_date(apply_day, days):
    except_day = (5, 6)
    mount = 0
    while days:
        mount += 1
        if (apply_day + timedelta(mount)).weekday() not in except_day:
            days -= 1

    return mount
