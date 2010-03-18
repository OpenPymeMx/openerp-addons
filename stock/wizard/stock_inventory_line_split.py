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
from service import web_services
from tools.misc import UpdateableStr, UpdateableDict
from tools.translate import _
import netsvc
import pooler
import time
import wizard

class stock_inventory_line_split(osv.osv_memory):
    _inherit = "stock.move.split"
    _name = "stock.inventory.line.split"
    _description = "Split inventory lines"

    
    def default_get(self, cr, uid, fields, context):
        """ 
             To check the availability of production lot. 
            
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param fields: List of fields for which we want default values 
             @param context: A standard dictionary 
             
             @return: A dictionary which of fields with values. 
        
        """        
        res = {}
        record_id = context and context.get('active_id',False)
        res = super(stock_inventory_line_split, self).default_get(cr, uid, fields, context=context)
        if not record_id:
           return res

        lot=  self.pool.get('stock.inventory.line').browse(cr, uid, record_id)
        res['product_id']=line.product_id.id
        return res
    
    

    def split(self, cr, uid, ids, line_ids, context=None):
        """ 
             To split stock inventory lines according to production lot
            
             @param self: The object pointer.
             @param cr: A database cursor
             @param uid: ID of the user currently logged in
             @param ids: the ID or list of IDs if we want more than one 
             @param line_ids: the ID or list of IDs of inventory lines we want to split
             @param context: A standard dictionary 
             
             @return: 
        
        """                    
        prodlot_obj = self.pool.get('stock.production.lot')
        ir_sequence_obj = self.pool.get('ir.sequence')
        line_obj = self.pool.get('stock.inventory.line')
        new_line = []        
        for data in self.browse(cr, uid, ids):
            for inv_line in line_obj.browse(cr, uid, line_ids):
                line_qty = inv_line.product_qty
                quantity_rest = inv_line.product_qty                
                new_line = []                            
                for line in data.line_ids:
                    quantity = line.quantity
                    

                    if quantity <= 0 or line_qty == 0:
                        continue
                    quantity_rest -= quantity                    
                    if quantity_rest <= 0:
                        quantity_rest = quantity
                        break
                    default_val = {
                        'product_qty': quantity,                         
                    }
                    current_line = line_obj.copy(cr, uid, inv_line.id, default_val)
                    new_line.append(current_line)
                    prodlot_id = False
                    if line.use_exist and line.name:
                        prodlot_id = prodlot_obj.search(cr, uid, [('prefix','=',line.name),('product_id','=',data.product_id.id)])
                        if prodlot_id:
                            prodlot_id = prodlot_id[0]                    
                    if not prodlot_id:
                        sequence = ir_sequence_obj.get(cr, uid, 'stock.lot.serial')
                        prodlot_id = prodlot_obj.create(cr, uid, {'name': sequence, 'prefix' : line.name}, 
                                                 {'product_id': data.product_id.id})                    
                    line_obj.write(cr, uid, [current_line], {'prod_lot_id': prodlot_id})
                    prodlot = prodlot_obj.browse(cr, uid, prodlot_id)                    
                    
                    update_val = {}
                    if quantity_rest > 0:                        
                        update_val['product_qty'] = quantity_rest                                            
                        line_obj.write(cr, uid, [inv_line.id], update_val)

                    
        return new_line
stock_inventory_line_split()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

