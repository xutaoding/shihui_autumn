# -*- coding: utf-8 -*-
import common


def main_loop():
    db = common.db_client()

    real_ids = db.query('select oi.id, oi.buy_number, oi.return_count, oi.sale_price from reeb.order_items oi, '
                        'reeb.goods g where oi.goods_id=g.id and '
                        'g.material_type ="REAL" and oi.status != "CANCELED" and oi.status != "UNPAID"')
    num = 0
    for t in real_ids:
        last_row_id = None
        # 插入实物 item
        for i in range(t.buy_number):
            last_row_id = db.execute("""insert into item(status, goods_name, goods_id, distr_id, distr_shop_id, sp_id, sp_shop_id, sales_id, order_item_id, order_id, order_no, face_value, payment, discount, sales_price, purchase_price, refund_value,cheat_value,
            created_at, used_at, refund_at, cheat_at)
            select case oi.status when 'PAID' then 1 when 'SENT' then 2 when 'RETURNED' then 3 when 'PREPARED' then 4 when 'UPLOADED' then 5 when 'RETURNING' then 7 end,
            oi.goods_name, oi.goods_id, case when o.user_id in (13,31,33,34,39,48,49,50,51) then 13 else o.user_id end , o.user_id, g.supplier_id, NULL, s.sales_id, oi.id, oi.order_id, o.order_no, oi.face_value, oi.sale_price, 0,
            oi.sale_price, oi.original_price, 0.00, 0.00, oi.created_at, oi.send_at, NULL, NULL
            from reeb.order_items oi, reeb.goods g, reeb.orders o, reeb.suppliers s where oi.goods_id=g.id and oi.order_id = o.id and g.supplier_id=s.id and oi.id=%s;
            """, t.id)
            num += 1
        # 根据real_goods_return_entry 更新退款
        return_entry = db.query("""select * from reeb.real_goods_return_entry where order_item_id=%s""", t.id)
        if return_entry:
            refund = return_entry[0]
            if refund.partial_refund_price:
                db.execute("""update item i set i.refund_value=%s, i.refund_at=%s where i.id=%s""", refund.partial_refund_price, refund.created_at, last_row_id)
            else:
                for j in range(refund.returned_count):
                    db.execute("""update item i set i.refund_value=%s, i.refund_at=%s where i.id=%s""", t.sale_price, refund.created_at, last_row_id)
                    last_row_id -= 1

    print '插入条数:', num


if __name__ == '__main__':
    common.set_up()
    main_loop()
