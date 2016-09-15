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

from osv import osv
from tools.translate import _

class invoice(osv.osv):
    _inherit = 'account.invoice'

    def invoice_pay_customer(self, cr, uid, ids, context=None):
        if not ids: return []
        inv = self.browse(cr, uid, ids[0], context=context)
        default_amount = inv.residual
        if inv.type in ('out_refund', 'in_refund'):
            default_amount *= -1
        return {
            'name':_("Pay Invoice"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'domain': '[]',
            'context': {
                'default_partner_id': inv.partner_id.id,
                'default_amount': default_amount,
                'default_name':inv.name,
                'close_after_process': True,
                'invoice_type':inv.type,
                'invoice_id':inv.id,
                'default_type': inv.type in ('out_invoice','out_refund') and 'receipt' or 'payment',
                'type': inv.type in ('out_invoice','out_refund') and 'receipt' or 'payment'
                }
        }

    def invoice_pay_multiple(self, cr, uid, ids, context=None):
        if not ids:
            return []

        partner_id = None
        invoice_type = None
        default_amount = 0
        for invoice in self.browse(cr, uid, ids, context=context):
            if not partner_id:
                partner_id = invoice.partner_id.id
            elif partner_id != invoice.partner_id.id:
                #raise TODO
                pass
            if not invoice_type:
                invoice_type = invoice.type
            elif invoice_type != invoice.type:
                #raise TODO
                pass

            default_amount += invoice.residual
            # see if name edit from 2411 kicks in, else gather invoice.name

        if invoice_type in ('out_refund', 'in_refund'):
            default_amount *= -1
        return {
            'name':_("Pay Invoice"),
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'account.voucher',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'current',
            'domain': '[]',
            'context': {
                'default_partner_id': partner_id,
                'default_amount': default_amount,
                'close_after_process': True,
                'invoice_type': invoice_type,
                'invoice_id': ids[0], # used in recompute voucher lines and to grab the currency
                'default_type': invoice_type in ('out_invoice','out_refund') and 'receipt' or 'payment',
                'type': invoice_type in ('out_invoice','out_refund') and 'receipt' or 'payment'
                }
        }

invoice()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
