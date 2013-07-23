# -*- coding: utf-8 -*-

import simplejson
from openerp.addons.web import http
from openerp.addons.web.http import request
from openerp.addons.website.controllers.main import template_values


class Ecommerce(http.Controller):

    def get_cr_uid(self):
        cr = request.cr
        uid = request.uid

        if request.session._uid:
            request.httprequest.session['ecommerce_partner_id'] = False
            partner_id = request.registry.get('res.users').browse(cr, uid, request.session._uid).partner_id.id
        else:
            partner_id = request.httprequest.session.get('ecommerce_partner_id', False)
            if partner_id and not request.registry.get('res.partner').search(cr, uid, [('id', '=', partner_id)]):
                partner_id = None
        return (cr, uid, partner_id)

    def get_values(self):
        cr, uid, partner_id = self.get_cr_uid()
        order_obj = request.registry.get('sale.order')
        category_obj = request.registry.get('pos.category')
        context = {}

        order_id = request.httprequest.session.get('ecommerce_order')
        # check if order allready exists
        try:
            order_obj.browse(cr, uid, order_id).pricelist_id
        except:
            order_id = None

        if not order_id:
            fields = [k for k, v in order_obj._columns.items()]
            order_value = order_obj.default_get(cr, uid, fields, context=context)
            order_value['partner_id'] = partner_id or request.registry.get('res.users').browse(cr, uid, uid).partner_id.id
            order_value.update(order_obj.onchange_partner_id(cr, uid, [], uid, context=context)['value'])
            order_id = order_obj.create(cr, uid, order_value, context=context)
            request.httprequest.session['ecommerce_order'] = order_id

        category_ids = category_obj.search(cr, uid, [('parent_id', '=', False)])

        values = template_values()
        values.update({
            'temp': 0,
            'res_company': request.registry['res.company'].browse(request.cr, uid, 1, context=context),
            'order': order_obj.browse(cr, uid, order_id),
            'categories': category_obj.browse(cr, uid, category_ids),
        })
        return values

    @http.route(['/shop', '/shop/category/<cat_id>'], type='http', auth="admin")
    def category(self, cat_id=0, offset=0, **post):
        values = self.get_values()
        cr, uid, partner_id = self.get_cr_uid()

        domain = []
        if post.get("search"):
            domain += ['|', '|', ('name', 'ilike', "%%%s%%" % post.get("search")), ('description', 'ilike', "%%%s%%" % post.get("search")), ('pos_categ_id.name', 'ilike', "%%%s%%" % post.get("search"))]
        if cat_id:
            cat_id = cat_id and int(cat_id) or 0
            domain = [('pos_categ_id.id', 'child_of', cat_id)] + domain

        category_obj = request.registry.get('pos.category')
        product_obj = request.registry.get('product.product')
        category_ids = category_obj.search(cr, uid, [('parent_id', '=', False)])
        product_ids = product_obj.search(cr, uid, domain or [(1, '=', 1)], limit=20, offset=offset)

        values.update({
            'current_category': cat_id,
            'categories': category_obj.browse(cr, uid, category_ids),
            'products': product_obj.browse(cr, uid, product_ids),
            'search': post.get("search"),
        })
        html = request.registry.get("ir.ui.view").render(cr, uid, "website_sale.products", values)
        return html

    @http.route(['/shop/product/<product_id>'], type='http', auth="admin")
    def product(self, cat_id=0, product_id=0):
        values = self.get_values()
        cr, uid, partner_id = self.get_cr_uid()

        product_id = product_id and int(product_id) or 0
        product_obj = request.registry.get('product.product')

        line = [line for line in values['order'].order_line if line.product_id.id == product_id]
        quantity = line and int(line[0].product_uom_qty) or 0

        values.update({
            'product': product_obj.browse(cr, uid, product_id),
            'quantity': quantity,
            'recommended_products': self.recommended_product([product_id]),
        })
        html = request.registry.get("ir.ui.view").render(cr, uid, "website_sale.product", values)
        return html

    def recommended_product(self, my_pids):
        if not my_pids:
            return []
        cr, uid, partner_id = self.get_cr_uid()
        my_pids = str(my_pids)[1:-1]
        product_ids = []
        query = """
            SELECT      sol.product_id
            FROM        sale_order_line as my
            LEFT JOIN   sale_order_line as sol
            ON          sol.order_id = my.order_id
            WHERE       my.product_id in (%s)
            AND         sol.product_id not in (%s)
            GROUP BY    sol.product_id
            ORDER BY    COUNT(sol.order_id) DESC
            LIMIT 8
        """ % (my_pids, my_pids)
        cr.execute(query)
        for p in cr.fetchall():
            product_ids.append(p[0])
        return request.registry.get('product.product').browse(cr, uid, product_ids)

    @http.route(['/shop/mycart'], type='http', auth="admin")
    def mycart(self, **post):
        cr, uid, partner_id = self.get_cr_uid()
        values = self.get_values()

        if post.get('code'):
            pricelist_obj = request.registry.get('product.pricelist')
            order_obj = request.registry.get('sale.order')
            pricelist_ids = pricelist_obj.search(cr, uid, [('code', '=', post.get('code'))])
            if pricelist_ids:
                values["order"].write({'pricelist_id': pricelist_ids[0]})

        my_pids = [line.product_id.id for line in values['order'].order_line]
        values["recommended_products"] = self.recommended_product(my_pids)

        html = request.registry.get("ir.ui.view").render(cr, uid, "website_sale.mycart", values)
        return html

    @http.route(['/shop/add_cart'], type='http', auth="admin")
    def add_cart(self, product_id=0, remove=False):
        cr, uid, partner_id = self.get_cr_uid()
        values = self.get_values()
        context = {}

        order_obj = request.registry.get('sale.order')
        order_line_obj = request.registry.get('sale.order.line')

        product_id = product_id and int(product_id) or 0
        order = values['order']

        quantity = 0

        # values initialisation
        order_line_ids = order_line_obj.search(cr, uid, [('order_id', '=', order.id), ('product_id', '=', product_id)], context=context)
        values = {}
        if order_line_ids:
            order_line = order_line_obj.read(cr, uid, order_line_ids, [], context=context)[0]
            quantity = order_line['product_uom_qty'] + (remove and -1 or 1)
            if quantity <= 0:
                order_line_obj.unlink(cr, uid, order_line_ids, context=context)
        else:
            fields = [k for k, v in order_line_obj._columns.items()]
            values = order_line_obj.default_get(cr, uid, fields, context=context)
            quantity = 1
        values['product_uom_qty'] = quantity
        values['product_id'] = product_id
        values['order_id'] = order.id

        # change and record value
        if quantity:
            pricelist_id = order.pricelist_id and order.pricelist_id.id or False
            values.update(order_line_obj.product_id_change(cr, uid, [], pricelist_id, product_id,
                partner_id=partner_id or request.registry.get('res.users').browse(cr, uid, uid).partner_id.id,
                context=context)['value'])
            if order_line_ids:
                order_line_obj.write(cr, uid, order_line_ids, values, context=context)
            else:
                order_line_id = order_line_obj.create(cr, uid, values, context=context)
                order.write({'order_line': [(4, order_line_id)]}, context=context)

        html = request.registry.get("ir.ui.view").render(cr, uid, "website_sale.total", self.get_values())

        return simplejson.dumps({"quantity": quantity, "totalHTML": html})

    @http.route(['/shop/remove_cart'], type='http', auth="admin")
    def remove_cart(self, product_id=0):
        return self.add_cart(product_id=product_id, remove=True)

    @http.route(['/shop/checkout'], type='http', auth="admin")
    def checkout(self, *arg, **post):
        cr, uid, partner_id = self.get_cr_uid()
        values = self.get_values()
        partner_obj = request.registry.get('res.partner')
        user_obj = request.registry.get('res.users')

        values['partner'] = False

        if post.get("login"):
            user_id = user_obj.login(cr, post.get("login"), post.get("password"))
            partner_id = user_obj.browse(cr, uid, user_id).partner_id.id

        if partner_id:
            values['partner'] = partner_obj.browse(cr, uid, partner_id)

        return request.registry.get("ir.ui.view").render(cr, uid, "website_sale.checkout", values)

    @http.route(['/shop/confirm_order'], type='http', auth="admin")
    def confirm_order(self, *arg, **post):
        cr, uid, partner_id = self.get_cr_uid()
        partner_obj = request.registry.get('res.partner')
        obj_data = request.registry.get('ir.model.data')

        # check values
        json = {'error': []}
        required_field = ['tel', 'zip', 'email', 'state', 'street', 'city', 'name']
        for key in required_field:
            if not post[key]:
                json['error'].append(key)
            if 'shipping_name' in post and key != 'email' and not post["shipping_%s" % key]:
                json['error'].append("shipping_%s" % key)
        if json['error']:
            return simplejson.dumps(json)

        # search or create company
        if post['company']:
            pass
        if 'shipping_company' in post and post['shipping_company']:
            pass

        partner_value = {
            'fax': post['fax'],
            'tel': post['tel'],
            'zip': post['zip'],
            'email': post['email'],
            'state': post['state'],
            'street': post['street'],
            'city': post['city'],
            'name': post['name'],
        }
        if partner_id:
            partner_obj.write(cr, uid, [partner_id], partner_value)
        else:
            partner_id = partner_obj.create(cr, uid, partner_value)

        if 'shipping_name' in post:
            shipping_value = {
                'fax': post['shipping_fax'],
                'tel': post['shipping_tel'],
                'zip': post['shipping_zip'],
                'state': post['shipping_state'],
                'street': post['shipping_street'],
                'city': post['shipping_city'],
                'name': post['shipping_name'],
                'parent_id': partner_id,
                'category_id': (4, shipping_category_id)
            }
            shipping_category_id = obj_data.get_object_reference(cr, uid, 'website_sale', 'shipping_address')[1]
            shipping_ids = partner_obj.search(cr, uid, [("parent_id", "=", partner_id), ("category_id", "=", shipping_category_id)])
            shipping_id = shipping_ids and shipping_ids[0] or None
            if shipping_id:
                partner_obj.write(cr, uid, [shipping_id], shipping_value)
            else:
                partner_obj.create(cr, uid, shipping_value)

        return simplejson.dumps(json)

        cr, uid, partner_id = self.get_cr_uid()
        if uid == 1:
            return customer()
        values = self.get_values()
        values['order'].write({'state': 'progress'})
        values['partner'] = request.registry.get('res.partner').browse(cr, uid, partner_id)
        html = request.registry.get("ir.ui.view").render(cr, uid, "website_sale.thanks", values)
        request.httprequest.session['ecommerce_order'] = None
        return html

# vim:expandtab:tabstop=4:softtabstop=4:shiftwidth=4:
