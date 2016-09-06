# -*- coding: utf-8 -*-

from .. import BaseHandler
from .. import require
from voluptuous import Schema
from autumn.torn.form import Form
from autumn.torn.paginator import Paginator

search_list = Schema({
    'shop': str,
    'product': str,
    'box': str,
})

add_edit_list = Schema({
    'product': str,
    'price': str,
    'box': str,
    'times': str,
    'days': str,
    'action': str,
})


class Show(BaseHandler):
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, search_list)
        sql = """ select kps.*, kp.name,
            (select group_concat(ss.name, ' (', ksps.room_count, ')') from ktv_shop ksps, supplier_shop ss
                where ksps.shop_id = ss.id and ksps.schedule_id = kps.id) as shop_info,
            (select group_concat(kdr.start_day,' 至 ', kdr.end_day)
                from ktv_date_range kdr where kdr.schedule_id = kps.id) as date_range
            from ktv_price_schedule kps, ktv_product kp where kps.product_id = kp.id and kps.supplier_id=%s
        """
        params = [self.current_user.supplier_id]

        if form.shop.value:
            sql += 'and kps.id in (select schedule_id from ktv_shop where shop_id=%s) '
            params.append(form.shop.value)
        if form.product.value:
            sql += 'and kps.product_id=%s '
            params.append(form.product.value)
        if form.box.value:
            sql += 'and kps.room_type=%s '
            params.append(form.box.value)

        sql += 'order by kps.created_at desc'

        page = Paginator(self, sql, params)

        shops = self.db.query('select * from supplier_shop where deleted=0 and supplier_id = %s',
                              self.current_user.supplier_id)
        products = self.db.query('select * from ktv_product where deleted=0 and supplier_id = %s',
                                 self.current_user.supplier_id)

        self.render('ktv/price/show.html', shops=shops, products=products, page=page, form=form)


class Add(BaseHandler):
    @require('manager')
    def get(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'

        shops = self.db.query('select * from supplier_shop where supplier_id = %s', self.current_user.supplier_id)
        products = self.db.query('select * from ktv_product where supplier_id = %s', self.current_user.supplier_id)

        self.render('ktv/price/price.html', form=form, shops=shops, products=products)

    @require('manager')
    def post(self):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'add'
        date_list = form.days.value.split(';')
        shop_list = []
        values = []
        for key in self.request.arguments:
            if key.startswith('shop-'):
                value = self.request.arguments[key][0]
                if value == '0' or value == '':
                    continue
                shop_list.append(key.split('-')[1])
                values.append(value)

        #检测时间碰撞模块
        if time_collision_detection(self.db, form.box.value, shop_list, date_list, form.times.value, form.product.value):
            shops = self.db.query('select * from supplier_shop where supplier_id = %s', self.current_user.supplier_id)
            products = self.db.query('select * from ktv_product where supplier_id = %s', self.current_user.supplier_id)
            return self.render('ktv/price/price.html', form=form, shops=shops, products=products)

        schedule = self.db.execute('insert into ktv_price_schedule(created_at, price, room_type, start_times, '
                                   'product_id, supplier_id, duration) values(NOW(), %s, %s, %s, %s, %s, %s)',
                                   form.price.value, form.box.value, form.times.value, form.product.value,
                                   self.current_user.supplier_id, self.get_argument('duration'))

        for date in date_list:
            split_list = date.split('--')
            self.db.execute('insert into ktv_date_range(end_day, start_day, schedule_id) '
                            'values(%s, %s, %s)', split_list[1], split_list[0], schedule)

        params = [i for tp in zip(values, [schedule]*len(shop_list), shop_list) for i in tp]
        self.db.execute('insert into ktv_shop(room_count, schedule_id, shop_id) '
                        'values %s' % (','.join(['(%s, %s, %s)']*len(shop_list))), *params)

        self.redirect(self.reverse_url('ktv.price.show'))


class Edit(BaseHandler):
    @require('manager')
    def get(self, cid):
        sql = """select kps.room_type box, kps.price, kps.start_times times, kps.id sid,
                 group_concat(kdr.start_day, ',', kdr.end_day) days, kp.id product
                 from ktv_price_schedule kps, ktv_date_range kdr, ktv_product kp
                 where kps.id = kdr.schedule_id and kps.product_id = kp.id and kps.id = %s"""
        schedule = self.db.get(sql, cid)
        form = Form(schedule, add_edit_list)
        form.action.value = 'edit'
        days_list = [item[0:10] for item in form.days.value.split(',')]
        day_str = ''
        for i, day in enumerate(days_list):
            if i % 2 == 0:
                day_str += day + '--'
            else:
                day_str += day + ';'
        form.days.value = day_str[0: len(day_str) - 1]

        shops = self.db.query(
            'select ss.name, ss.id, ksps.room_count from supplier_shop ss '
            'left join ktv_shop ksps on ksps.schedule_id=%s and ss.id=ksps.shop_id  '
            'where supplier_id =%s', cid, self.current_user.supplier_id)

        products = self.db.query('select * from ktv_product where supplier_id = %s', self.current_user.supplier_id)

        self.render('ktv/price/price.html', shops=shops, products=products, form=form, cid=cid)

    @require('manager')
    def post(self, cid):
        form = Form(self.request.arguments, add_edit_list)
        form.action.value = 'edit'
        date_list = form.days.value.split(';')
        shop_list = []
        values = []
        for key in self.request.arguments:
            if key.startswith('shop-'):
                value = self.request.arguments[key][0]
                if value == '0' or value == '':
                    continue
                shop_list.append(key.split('-')[1])
                values.append(value)

        #检测时间碰撞模块
        if time_collision_detection(self.db, form.box.value, shop_list, date_list, form.times.value, form.product.value, cid):
            shops = self.db.query(
                'select ss.name, ss.id, ksps.room_count from supplier_shop ss '
                'left join ktv_shop ksps on ksps.schedule_id=%s and ss.id=ksps.shop_id  '
                'where supplier_id =%s', cid, self.current_user.supplier_id)
            products = self.db.query('select * from ktv_product where supplier_id = %s', self.current_user.supplier_id)
            return self.render('ktv/price/price.html', form=form, shops=shops, products=products, cid=cid)

        self.db.execute('update ktv_price_schedule set price = %s, room_type = %s, start_times = %s, product_id = %s '
                        'where id = %s', form.price.value, form.box.value, form.times.value, form.product.value, cid)

        #把原策略中对应的时间全删除，重新添加
        self.db.execute('delete from ktv_date_range where schedule_id = %s', cid)

        for date in date_list:
            split_list = date.split('--')
            self.db.execute('insert into ktv_date_range(end_day, start_day, schedule_id) '
                            'values(%s, %s, %s)', split_list[1], split_list[0], cid)

        #把原策略中的对应店铺全删除后，重新添加
        self.db.execute('delete from ktv_shop where schedule_id = %s', cid)
        params = [i for tp in zip(values, [cid]*len(shop_list), shop_list) for i in tp]
        self.db.execute('insert into ktv_shop(room_count, schedule_id, shop_id) '
                        'values %s' % (','.join(['(%s, %s, %s)']*len(shop_list))), *params)

        self.redirect(self.reverse_url('ktv.price.show'))


def time_collision_detection(db, room_type, shops, schedule_days, start_times, product_id, pid=-1):
    #查出符合日期要求的所有策略，即day>=start_day, day =< end_day
    #继而找出这些策略中的开始时间段又没有冲突，有冲突则返回冲突策略，反之返回0
    par = [room_type, pid, product_id]
    sql = """select * from ktv_price_schedule kps, ktv_date_range kdr, ktv_shop ksp
             where kps.id = kdr.schedule_id and kps.id = ksp.schedule_id and ksp.shop_id in ({0}) and kps.room_type = %s
             and kps.id != %s and kps.product_id = %s and ( """

    flag = 0
    for day in schedule_days:
        if flag:
            sql += 'or '
        start_and_end_day = day.split('--')
        sql += '(kdr.start_day <= %s and kdr.end_day >= %s) '
        par.append(start_and_end_day[1])
        par.append(start_and_end_day[0])
        flag = 1
    sql += ')'
    sql = sql.format(','.join(['%s']*(len(shops))))

    params = shops + par
    price_schedule = db.query(sql, *params)

    product = db.get('select * from ktv_product where id = %s', product_id)
    for schedule in price_schedule:
        for start_time in schedule.start_times.split(','):
            start = int(start_time) if int(start_time) < 8 else int(start_time) + 24
            for i in start_times.split(','):
                int_i = int(i) if int(i) < 8 else int(i) + 24
                if (start - product.duration) < int_i < (start + product.duration):
                    return schedule

    return 0