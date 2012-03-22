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

from osv import fields, osv
import pooler
from tools.translate import _

class mrp_config_settings(osv.osv_memory):
    _name = 'mrp.config.settings'
    _inherit = 'res.config.settings'

    _columns = {
        'module_stock_planning': fields.boolean('Track work order planning',
            help ="""This allows to create a manual procurement plan apart of the normal MRP scheduling,
                which works automatically based on minimum stock rules.
                This installs the module stock_planning."""),
        'module_mrp_repair': fields.boolean("Track products repair",
            help="""Allows to manage all products repairs.
                    * Add/remove products in the reparation
                    * Impact for stocks
                    * Invoicing (products and/or services)
                    * Warranty concept
                    * Repair quotation report
                    * Notes for the technician and for the final customer.
                This installs the module mrp_repair."""),
        'module_mrp_operations': fields.boolean("Track dates in work order operations",
            help="""This allows to add state, date_start,date_stop in production order operation lines (in the "Work Centers" tab).
                This installs the module mrp_operations."""),
        'module_mrp_subproduct': fields.boolean("Produce several products from one production",
            help="""You can configure sub-products in the bill of material.
                Without this module: A + B + C -> D.
                With this module: A + B + C -> D + E.
                This installs the module mrp_subproduct."""),
        'module_stock_location': fields.boolean("Allow push/pull flows by product",
            help="""Allows to implement Push and Pull inventory flows.
                Typically this could be used to:
                    * Manage product manufacturing chains
                    * Manage default locations per product
                    * Define routes within your warehouse according to business needs, such as:
                        - Quality Control
                        - After Sales Services
                        - Supplier Returns.
                This installs the module stock_location."""),
        'module_mrp_jit': fields.boolean("Allow just in time scheduling",
            help="""This allows Just In Time computation of procurement orders.
                All procurement orders will be processed immediately, which could in some
                cases entail a small performance impact.
                This installs the module mrp_jit."""),
        'module_mrp_operations': fields.boolean("Track dates in work order operations",
            help="""This allows to add state, date_start,date_stop in production order operation lines (in the "Work Centers" tab).
                This installs the module mrp_operations."""),
        'group_mrp_routings': fields.boolean("Manage manufacturing operations ",
            implied_group='base.group_mrp_routings',
            help="""Routings allow you to create and manage the manufacturing operations that should be followed
                within your work centers in order to produce a product. They are attached to bills of materials
                that will define the required raw materials."""),
        'group_mrp_properties': fields.boolean("Allow different properties per product in your order",
            implied_group='base.group_mrp_properties',
            help="""Allows to define specific property that can be assigned to your bill of materials."""),
    }

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
