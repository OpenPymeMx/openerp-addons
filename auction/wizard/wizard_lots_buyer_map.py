##############################################################################
#
# Copyright (c) 2004 TINY SPRL. (http://tiny.be) All Rights Reserved.
#                    Fabien Pinckaers <fp@tiny.Be>
#
# WARNING: This program as such is intended to be used by professional
# programmers who take the whole responsability of assessing all potential
# consequences resulting from its eventual inadequacies and bugs
# End users who are looking for a ready-to-use solution with commercial
# garantees and support are strongly adviced to contract a Free Software
# Service Company
#
# This program is Free Software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#
##############################################################################

import wizard
import netsvc
import pooler
import sql_db

buyer_map = '''<?xml version="1.0"?>
<form title="Buyer Map">
	<field name="ach_login"/>
	<newline/>
	<field name="ach_uid"/>
</form>'''

buyer_map_fields = {
	'ach_login': {'string':'Buyer Username', 'type':'char', 'size':64, 'required':True},
	'ach_uid': {'string':'Buyer', 'type':'many2one', 'required':True, 'relation':'res.partner'},
}


#
# Try to find an object not mapped
#
def _state_check(self, cr, uid, data, context):
	pool = pooler.get_pool(cr.dbname)
	cr.execute('select id from auction_lots where (ach_uid is null and ach_login is not null)  ')
	v_ids=[x[0] for x in cr.fetchall()]
	#ids_not_mapped=pool.get('auction.lots').search(cr,uid,[('rec.ach_uid','=',False)])
	for rec in pool.get('auction.lots').browse(cr,uid,v_ids,context):
	#	if not rec.ach_uid and not rec.ach_login:
	#		raise wizard.except_wizard ('Error','No username is associated to this lot!')
		if (not rec.ach_uid or not rec.ach_login):
			return 'check'
	return 'done'

def _start(self,cr,uid,datas,context):
	pool = pooler.get_pool(cr.dbname)
	for rec in pool.get('auction.lots').browse(cr,uid,datas['ids'],context):
		if (len(datas['ids'])==1) and (not rec.ach_uid and not rec.ach_login):
			raise wizard.except_wizard('Error', 'No buyer setted for this lot')
		if not rec.ach_uid and rec.ach_login:
			return {'ach_login': rec.ach_login}

	for rec in pool.get('auction.lots').browse(cr,uid,datas['ids'],context):
		if (not rec.ach_uid and rec.ach_login):
			return {'ach_login': rec.ach_login}
	return {}

def _buyer_map_set(self,cr, uid, datas,context):
	pool = pooler.get_pool(cr.dbname)
	recs=pool.get('auction.lots').browse(cr,uid,datas['ids'],context)
	for rec in recs:
		if rec.ach_login==datas['form']['ach_login']:
			pool.get('auction.lots').write(cr, uid, [rec.id], {'ach_uid':  datas['form']['ach_uid']}, context=context)
			cr.commit()
	return {'ach_login':False, 'ach_uid':False}

class wiz_auc_lots_buyer_map(wizard.interface):
	states = {
		'init': {
			'actions': [],
			'result': {'type': 'choice', 'next_state':_state_check}
		},
		'check': {
			'actions': [_start],
			'result': {'type': 'form', 'arch':buyer_map, 'fields': buyer_map_fields, 'state':[('end','Exit'),('set_buyer', 'Update')]}
		},
		'set_buyer': {
			'actions': [_buyer_map_set],
			'result': {'type': 'state', 'state':'init'}
		},
		'done': {
			'actions': [_start],
			'result': {
				'type': 'form',
				'arch':'''<?xml version="1.0"?>
				<form title="Mapping result">
					<label string="All objects are assigned to buyers !"/>
				</form>''',
				'fields': {},
				'state':[('end','Close')]}
		}
	}

wiz_auc_lots_buyer_map('auction.lots.buyer_map')

