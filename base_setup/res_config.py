# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Business Applications
#    Copyright (C) 2004-2012 OpenERP S.A. (<http://openerp.com>).
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

from openerp.osv import fields, osv
import re
import os
from openerp.addons.base.res import res_company

class base_config_settings(osv.osv_memory):
    _name = 'base.config.settings'
    _inherit = 'res.config.settings'
    
    def _get_font(self, cr, uid, context=None):
        font_list = res_company.get_font_list()
        return font_list
    
    _columns = {
        'module_multi_company': fields.boolean('Manage multiple companies',
            help="""Work in multi-company environments, with appropriate security access between companies.
                This installs the module multi_company."""),
        'module_share': fields.boolean('Allow documents sharing',
            help="""Share or embbed any screen of openerp."""),
        'module_portal': fields.boolean('Activate the customer portal',
            help="""Give your customers access to their documents."""),
        'module_portal_anonymous': fields.boolean('Activate the public portal',
            help="""Enable the public part of openerp, openerp becomes a public website."""),
        'module_auth_oauth': fields.boolean('Use external authentication providers, sign in with google, facebook, ...'),
        'module_base_import': fields.boolean("Allow users to import data from CSV files"),
        'module_google_drive': fields.boolean('Attach Google documents to any record',
                                              help="""This installs the module google_docs."""),
        'font': fields.selection(_get_font, "Select Font",help="Set your favorite font into company header"),
    }
    
    def open_company(self, cr, uid, ids, context=None):
        user = self.pool.get('res.users').browse(cr, uid, uid, context)
        return {
            'type': 'ir.actions.act_window',
            'name': 'Your Company',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'res.company',
            'res_id': user.company_id.id,
            'target': 'current',
        }

    def _change_header(self, header,font):
        """ Replace default fontname use in header and setfont tag """
        
        default_para = re.sub('fontName.?=.?".*"', 'fontName="%s"'% font,header)
        return re.sub('(<setFont.?name.?=.?)(".*?")(.)', '\g<1>"%s"\g<3>'% font,default_para)
    
    def set_base_defaults(self, cr, uid, ids, context=None):
        ir_model_data = self.pool.get('ir.model.data')
        wizard = self.browse(cr, uid, ids)[0]
        if wizard.font:
            user = self.pool.get('res.users').browse(cr, uid, uid, context)
            user.company_id.write({'rml_header': self._change_header(user.company_id.rml_header,wizard.font), 'rml_header2': self._change_header(user.company_id.rml_header2,wizard.font), 'rml_header3': self._change_header(user.company_id.rml_header3,wizard.font)})
        return {}
# Preferences wizard for Sales & CRM.
# It is defined here because it is inherited independently in modules sale, crm,
# plugin_outlook and plugin_thunderbird.
class sale_config_settings(osv.osv_memory):
    _name = 'sale.config.settings'
    _inherit = 'res.config.settings'
    _columns = {
        'module_web_linkedin': fields.boolean('Get contacts automatically from linkedIn',
            help="""When you create a new contact (person or company), you will be able to load all the data from LinkedIn (photos, address, etc)."""),
        'module_crm': fields.boolean('CRM'),
        'module_sale' : fields.boolean('SALE'),
        'module_plugin_thunderbird': fields.boolean('Enable Thunderbird plug-in',
            help="""The plugin allows you archive email and its attachments to the selected
                OpenERP objects. You can select a partner, or a lead and
                attach the selected mail as a .eml file in
                the attachment of a selected record. You can create documents for CRM Lead,
                Partner from the selected emails.
                This installs the module plugin_thunderbird."""),
        'module_plugin_outlook': fields.boolean('Enable Outlook plug-in',
            help="""The Outlook plugin allows you to select an object that you would like to add
                to your email and its attachments from MS Outlook. You can select a partner,
                or a lead object and archive a selected
                email into an OpenERP mail message with attachments.
                This installs the module plugin_outlook."""),
    }
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

