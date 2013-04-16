# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from datetime import date
from dateutil.relativedelta import relativedelta
from openerp.osv import osv, fields
from openerp.tools.translate import _


class sale_order(osv.osv):
    _inherit = 'sale.order'
    _columns = {
        'section_id': fields.many2one('crm.case.section', 'Sales Team'),
        'categ_ids': fields.many2many('crm.case.categ', 'sale_order_category_rel', 'order_id', 'category_id', 'Categories', \
            domain="['|',('section_id','=',section_id),('section_id','=',False), ('object_id.model', '=', 'crm.lead')]")
    }


class crm_case_section(osv.osv):
    _inherit = 'crm.case.section'

    def _get_sum_duration_invoice(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids, 0)
        obj = self.pool.get('account.invoice.report')

        previous_month = {
            "monthly": 0,
            "semesterly": 2,
            "semiannually": 5,
            "annually": 11
        }
        for section in self.browse(cr, uid, ids, context=context):
            when = date.today().replace(day=1) + relativedelta(months=-previous_month[section.target_invoice_duration])

            invoice_ids = obj.search(cr, uid, [("section_id", "=", section.id), ('state', 'not in', ['draft', 'cancel']), ('date', '>=', when)], context=context)
            for invoice in obj.browse(cr, uid, invoice_ids, context=context):
                res[section.id] += invoice.price_total
        return res

    def _get_target_invoice_duration_txt(self, cr, uid, ids, field_name, arg, context=None):
        res = dict.fromkeys(ids, "")

        duration_txt = {
            "monthly": _("this month"),
            "semesterly": _("this semester"),
            "semiannually": _("this semi"),
            "annually": _("this year")
        }
        for section in self.browse(cr, uid, ids, context=context):
            res[section.id] = duration_txt[section.target_invoice_duration]
        return res

    _columns = {
        'quotation_ids': fields.one2many('sale.order', 'section_id',
            string='Quotations', readonly=True,
            domain=[('state', 'in', ['draft', 'sent', 'cancel'])]),
        'sale_order_ids': fields.one2many('sale.order', 'section_id',
            string='Sale Orders', readonly=True,
            domain=[('state', 'not in', ['draft', 'sent', 'cancel'])]),
        'invoice_ids': fields.one2many('account.invoice', 'section_id',
            string='Invoices', readonly=True,
            domain=[('state', 'not in', ['draft', 'cancel'])]),
        'sum_duration_invoice': fields.function(_get_sum_duration_invoice,
            string='Total invoiced',
            type='integer', readonly=True),
        'forcasted': fields.integer(string='Total forcasted'),
        'target_invoice': fields.integer(string='Target Invoice'),
        'target_invoice_duration': fields.selection([("monthly", "Monthly"), ("semesterly", "Semesterly"), ("semiannually", "Semiannually"), ("annually", "Annually")],
            string='Report duration view', required=True),
        'target_invoice_duration_txt': fields.function(_get_target_invoice_duration_txt,
            string='Duration',
            type="string", readonly=True),
    }
    _defaults = {
        'target_invoice_duration': "monthly",
    }

    def action_forcasted(self, cr, uid, id, value, context=None):
        return self.write(cr, uid, [id], {'forcasted': value}, context=context)

class res_users(osv.Model):
    _inherit = 'res.users'
    _columns = {
        'default_section_id': fields.many2one('crm.case.section', 'Default Sales Team'),
    }


class account_invoice(osv.osv):
    _inherit = 'account.invoice'
    _columns = {
        'section_id': fields.many2one('crm.case.section', 'Sales Team'),
    }
    _defaults = {
        'section_id': lambda self, cr, uid, c=None: self.pool.get('res.users').browse(cr, uid, uid, c).default_section_id.id or False,
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
