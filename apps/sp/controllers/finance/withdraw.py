# -*- coding: utf-8 -*-
from .. import BaseHandler
import datetime
from .. import require
import logging
from autumn.torn.paginator import Paginator
from autumn.utils import json_dumps
from decimal import Decimal


class List(BaseHandler):
    @require('finance')
    def get(self):
        # 查找申请提现的账户ID
        if self.current_user.separate_account == '1':
            withdraw_account_id = self.db.get('select account_id from supplier_shop where id=%s',
                                              self.current_user.shop_id).account_id
        else:
            withdraw_account_id = self.current_user.sp_account_id

        sql = 'select * from withdraw_bill where account_id =%s order by applied_at desc'

        page = Paginator(self, sql, [withdraw_account_id])
        self.render('finance/withdraw/list.html', page=page)


class Preview(BaseHandler):
    @require('finance')
    def get(self):
        end_date = self.get_argument('end_date', '')
        if not end_date:
            end_date = datetime.date.today()

        if self.current_user.separate_account == '1':
            #  account_sequence 中的哪些账户算入可提现账户
            seq_account_ids = [self.db.get('select account_id from supplier_shop where id=%s',
                                           self.current_user.shop_id).account_id]
        else:
            #  account_sequence 中的哪些账户算入可提现账户
            accounts = self.db.query('select account_id from supplier_shop where supplier_id=%s',
                                     self.current_user.supplier_id)
            seq_account_ids = [i.account_id for i in accounts]

        #  钱款统计截止至当天凌晨
        sql = 'select * from account_sequence where status=1 and created_at<%%s and account_id in (%s) ' \
              'order by id desc' % ','.join(['%s'] * len(seq_account_ids))

        page = Paginator(self, sql, [end_date]+seq_account_ids)
        self.render('finance/withdraw/preview.html', page=page)


class QueryAmount(BaseHandler):
    @require('finance')
    def post(self):
        """根据日期查询可体现金额"""
        end_date = datetime.date.today().strftime('%Y-%m-%d')

        if self.current_user.separate_account == '1':
            #  account_sequence 中的哪些账户算入可提现账户
            seq_account_ids = [self.db.get('select account_id from supplier_shop where id=%s',
                                           self.current_user.shop_id).account_id]
        else:
            #  account_sequence 中的哪些账户算入可提现账户
            accounts = self.db.query('select account_id from supplier_shop where supplier_id=%s',
                                     self.current_user.supplier_id)
            seq_account_ids = [i.account_id for i in accounts]
            #  钱款统计截止至当天凌晨
        withdraw_amount = self.db.get(
            'select sum(amount) amount from account_sequence '
            'where status=1 and created_at<%%s and account_id in (%s)'
            % ','.join(['%s']*len(seq_account_ids)), end_date, *seq_account_ids).amount
        # 判断最大可提现金额
        max_amount = withdraw_amount
        remark = ''
        if 'max_withdraw' in self.current_user.sp_props:
            max_withdraw = Decimal(self.current_user.sp_props.max_withdraw)
            if max_withdraw < withdraw_amount:
                max_amount = max_withdraw
                remark = u'如有疑问，请联系销售'

        return self.write(json_dumps({'amount': withdraw_amount, 'end_date': end_date, 'max_amount': max_amount,
                                      'remark': remark},
                                     decimal_fmt=float))


class Apply(BaseHandler):
    @require('finance')
    def get(self):
        """ 申请提现"""
        if self.current_user.separate_account == '1':
            #  account_sequence 中的哪些账户算入可提现账户
            seq_account_ids = [self.db.get('select account_id from supplier_shop where id=%s',
                                           self.current_user.shop_id).account_id]
            #  银行账户
            withdraw_accounts = self.db.query('select * from withdraw_account where deleted=0 '
                                              'and type="SUPPLIER_SHOP" and uid=%s', self.current_user.shop_id)
            #  待审批的提现申请
            pending_withdraw_bill = self.db.query('select * from withdraw_bill where status=0 and account_id=%s',
                                                  seq_account_ids[0])
        else:
            #  account_sequence 中的哪些账户算入可提现账户
            accounts = self.db.query('select account_id from supplier_shop where supplier_id=%s',
                                     self.current_user.supplier_id)
            seq_account_ids = [i.account_id for i in accounts]
            #  银行账户
            withdraw_accounts = self.db.query('select * from withdraw_account where deleted=0 '
                                              'and type="SUPPLIER" and uid=%s', self.current_user.supplier_id)
            #  待审批的提现申请
            pending_withdraw_bill = self.db.query('select * from withdraw_bill where status=0 and account_id=%s',
                                                  self.current_user.sp_account_id)

        self.render("finance/withdraw/apply.html", withdraw_accounts=withdraw_accounts, end_date=datetime.date.today(),
                    pending_withdraw_bill=pending_withdraw_bill, error_info='')

    @require('finance')
    def post(self):
        """ 申请提现"""
        # 没选提现账号，返回
        if not self.get_argument('withdraw_account_id', ''):
            return self.redirect('apply')
        # 截止日期
        end_date = datetime.date.today().strftime('%Y-%m-%d')

        withdraw_account = self.db.get('select * from withdraw_account where id=%s',
                                       self.get_argument('withdraw_account_id'))
        if self.current_user.separate_account == '1':
            #  account_sequence 中的哪些账户算入可提现账户
            supplier_shop = self.db.get('select * from supplier_shop where id=%s', self.current_user.shop_id)
            seq_account_ids = [supplier_shop.account_id]
            #  银行账户
            withdraw_accounts = self.db.query('select * from withdraw_account where deleted=0 '
                                              'and type="SUPPLIER_SHOP" and uid=%s', self.current_user.shop_id)
            #  待审批的提现申请
            pending_withdraw_bill = self.db.query('select * from withdraw_bill where status=0 and account_id=%s',
                                                  seq_account_ids[0])
            account_name = self.current_user.supplier_short_name + ":" + supplier_shop.name
            apply_account_id = supplier_shop.account_id
        else:
            #  account_sequence 中的哪些账户算入可提现账户
            accounts = self.db.query('select account_id from supplier_shop where supplier_id=%s',
                                     self.current_user.supplier_id)
            seq_account_ids = [i.account_id for i in accounts]
            #  银行账户
            withdraw_accounts = self.db.query('select * from withdraw_account where deleted=0 '
                                              'and type="SUPPLIER" and uid=%s', self.current_user.supplier_id)
            #  待审批的提现申请
            pending_withdraw_bill = self.db.query('select * from withdraw_bill where status=0 and account_id=%s',
                                                  self.current_user.sp_account_id)
            account_name = self.current_user.supplier_short_name
            apply_account_id = self.current_user.sp_account_id

        if pending_withdraw_bill:
            error_info = u'您有一笔待审批的提现申请'
            self.render("finance/withdraw/apply.html", withdraw_accounts=withdraw_accounts, end_date=end_date,
                        pending_withdraw_bill=pending_withdraw_bill, error_info=error_info)
            return

        withdraw_amount = 0
        if withdraw_accounts and not pending_withdraw_bill:
            #  钱款统计截止至当天凌晨
            withdraw_amount = self.db.get(
                'select sum(amount) amount from account_sequence '
                'where status=1 and created_at<%%s and account_id in (%s)'
                % ','.join(['%s']*len(seq_account_ids)), end_date, *seq_account_ids).amount
        if not withdraw_account:
            error_info = u'请选择提现的银行账户'
            self.render("finance/withdraw/apply.html", withdraw_accounts=withdraw_accounts, end_date=end_date,
                        pending_withdraw_bill=pending_withdraw_bill, error_info=error_info)
            return

        if withdraw_amount <= 10:
            error_info = u'提现金额不能小于10元'
            self.render("finance/withdraw/apply.html", withdraw_accounts=withdraw_accounts, end_date=end_date,
                        pending_withdraw_bill=pending_withdraw_bill, error_info=error_info)
            return
        # 可以提现，确认最大提现额度
        max_withdraw = Decimal(0)
        if 'max_withdraw' in self.current_user.sp_props:
            max_withdraw = Decimal(self.current_user.sp_props.max_withdraw)

        if max_withdraw != Decimal(0) and max_withdraw < withdraw_amount:
            # 超过最大可提现金额需要特殊处理
            logging.info('exceed max_withdraw amount, special process for sp=%s',
                         self.current_user.supplier_id)
            withdraw_sequence = self.db.query(
                'select id, amount from account_sequence '
                'where status=1 and created_at<%%s and account_id in (%s) order by id asc'
                % ','.join(['%s']*len(seq_account_ids)), end_date, *seq_account_ids)
            withdraws = [(s.id, s.amount) for s in withdraw_sequence]
            valid_ids = []  # 记录可以体现的account_sequence id
            current_amount = Decimal('0')  # 记录累加的金额
            # 开始统计
            for aid, amount in withdraws:
                # 会多结算一笔
                if current_amount >= max_withdraw:
                    break
                else:
                    current_amount += amount
                    valid_ids.append(aid)
            diff = current_amount - max_withdraw
            # 插入一条提现记录
            withdraw_bill_id = self.db.execute(
                'insert into withdraw_bill (amount,applier,bank_city,bank_name,card_number,sub_bank_name,user_name,'
                'account_id,account_name,status,applied_at) '
                'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())', max_withdraw, self.current_user.login_name,
                withdraw_account.bank_city, withdraw_account.bank_name, withdraw_account.card_number,
                withdraw_account.sub_bank_name, withdraw_account.user_name, apply_account_id, account_name, '0')
            # 如果有差价，插入2条平账数据, 正数状态为1, 负数状态为2
            if not diff.is_zero():
                self.db.execute('insert into account_sequence (type, account_id, trade_id, trade_type, created_at, '
                                'amount,' 'remark, status) values(1, %s, %s, 2, NOW(), %s, %s, 1)', seq_account_ids[0],
                                withdraw_bill_id, diff,
                                '提现补余 %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                self.db.execute('insert into account_sequence (type, account_id, trade_id, trade_type, created_at, '
                                'amount,' 'remark, status) values(1, %s, %s, 2, NOW(), %s, %s, 2)', seq_account_ids[0],
                                withdraw_bill_id, -diff,
                                '提现补余 %s' % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            # 改变已结算的account_sequence status
            self.db.execute(
                'update account_sequence set status=2 '
                'where status=1 and created_at<%%s and id in (%s)'
                % ','.join(['%s']*len(valid_ids)), end_date, *valid_ids)
        else:
            # 正常提现
            self.db.execute(
                'insert into withdraw_bill (amount,applier,bank_city,bank_name,card_number,sub_bank_name,user_name,'
                'account_id,account_name,status,applied_at) '
                'values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now())', withdraw_amount, self.current_user.login_name,
                withdraw_account.bank_city, withdraw_account.bank_name, withdraw_account.card_number,
                withdraw_account.sub_bank_name, withdraw_account.user_name, apply_account_id, account_name, '0')

            #查找商户门店对应的账户信息
            self.db.execute(
                'update account_sequence set status=2 '
                'where status=1 and created_at<%%s and account_id in (%s)'
                % ','.join(['%s']*len(seq_account_ids)), end_date, *seq_account_ids)
            # 记录订单日志 同时插入信息表
            # self.db.execute('insert into journal (created_at, type, created_by, message, iid)'
            #                 'values (NOW(), 6, %s, %s, %s)',
            #                 self.current_user.name, "申请提现", account_id)
        self.redirect(self.reverse_url('finance.withdraw'))


class Detail(BaseHandler):
    @require('finance')
    def get(self):
        """ 详情"""
        withdraw_bill = self.db.get('select * from withdraw_bill where id =%s', self.get_argument('id'))
        self.render("finance/withdraw/detail.html", withdraw_bill=withdraw_bill)
