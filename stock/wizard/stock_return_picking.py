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

import netsvc
import time

from osv import osv,fields
from tools.translate import _
import decimal_precision as dp

class stock_return_picking_memory(osv.osv_memory):
    _name = "stock.return.picking.memory"
    _rec_name = 'product_id'
    _columns = {
        'product_id' : fields.many2one('product.product', string="Product", required=True),
        'quantity' : fields.float("Quantity", digits_compute=dp.get_precision('Product UoM'), required=True),
        'wizard_id' : fields.many2one('stock.return.picking', string="Wizard"),
        'move_id' : fields.many2one('stock.move', "Move"),
    }

stock_return_picking_memory()


class stock_return_picking(osv.osv_memory):
    _name = 'stock.return.picking'
    _description = 'Return Picking'
    _columns = {
        'product_return_moves' : fields.one2many('stock.return.picking.memory', 'wizard_id', 'Moves'),
        'invoice_state': fields.selection([('2binvoiced', 'To be refunded/invoiced'), ('none', 'No invoicing')], 'Invoicing',required=True),
     }

    def default_get(self, cr, uid, fields, context=None):
        """
         To get default values for the object.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param fields: List of fields for which we want default values
         @param context: A standard dictionary
         @return: A dictionary with default values for all field in ``fields``
        """
        result1 = []
        if context is None:
            context = {}
        res = super(stock_return_picking, self).default_get(cr, uid, fields, context=context)
        record_id = context and context.get('active_id', False) or False
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        if pick:
            if 'invoice_state' in fields:
                if pick.invoice_state=='invoiced':
                    res.update({'invoice_state': '2binvoiced'})
                else:
                    res.update({'invoice_state': 'none'})
            return_history = self.get_return_history(cr, uid, record_id, context)       
            for line in pick.move_lines:
                qty = line.product_qty - return_history[line.id]
                if qty > 0:
                    result1.append({'product_id': line.product_id.id, 'quantity': qty,'move_id':line.id})
            if 'product_return_moves' in fields:
                res.update({'product_return_moves': result1})
        return res

    def view_init(self, cr, uid, fields_list, context=None):
        """
         Creates view dynamically and adding fields at runtime.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param context: A standard dictionary
         @return: New arch of view with new columns.
        """
        if context is None:
            context = {}
        res = super(stock_return_picking, self).view_init(cr, uid, fields_list, context=context)
        record_id = context and context.get('active_id', False)
        if record_id:
            pick_obj = self.pool.get('stock.picking')
            pick = pick_obj.browse(cr, uid, record_id, context=context)
            if pick.state not in ['done','confirmed','assigned']:
                raise osv.except_osv(_('Warning !'), _("You may only return pickings that are Confirmed, Available or Done!"))
            valid_lines = 0
            return_history = self.get_return_history(cr, uid, record_id, context)
            for m  in pick.move_lines:
                if (return_history.get(m.id) is not None) and (m.product_qty * m.product_uom.factor > return_history[m.id]):
                        valid_lines += 1
            if not valid_lines:
                raise osv.except_osv(_('Warning !'), _("There are no products to return (only lines in Done state and not fully returned yet can be returned)!"))
        return res
    
    def get_return_history(self, cr, uid, pick_id, context=None):
        """ 
         Get  return_history.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param pick_id: Picking id
         @param context: A standard dictionary
         @return: A dictionary which of values.
        """
        pick_obj = self.pool.get('stock.picking')
        pick = pick_obj.browse(cr, uid, pick_id, context=context)
        return_history = {}
        for m  in pick.move_lines:
            if m.state == 'done':
                return_history[m.id] = 0
                for rec in m.move_history_ids2:
                    # only take into account 'product return' moves, ignoring any other
                    # kind of upstream moves, such as internal procurements, etc.
                    # a valid return move will be the exact opposite of ours:
                    #     (src location, dest location) <=> (dest location, src location))
                    if rec.location_dest_id.id == m.location_id.id \
                        and rec.location_id.id == m.location_dest_id.id:
                        return_history[m.id] += (rec.product_qty * rec.product_uom.factor)
        return return_history

    def create_returns(self, cr, uid, ids, context=None):
        """
         Creates return picking.
         @param self: The object pointer.
         @param cr: A database cursor
         @param uid: ID of the user currently logged in
         @param ids: List of ids selected
         @param context: A standard dictionary
         @return: A dictionary which of fields with values.
        """
        if context is None:
            context = {}
        record_id = context and context.get('active_id', False) or False
        move_obj = self.pool.get('stock.move')
        pick_obj = self.pool.get('stock.picking')
        uom_obj = self.pool.get('product.uom')
        data_obj = self.pool.get('stock.return.picking.memory')
        wf_service = netsvc.LocalService("workflow")
        pick = pick_obj.browse(cr, uid, record_id, context=context)
        data = self.read(cr, uid, ids[0], context=context)
        new_picking = None
        date_cur = time.strftime('%Y-%m-%d %H:%M:%S')
        set_invoice_state_to_none = True
        returned_lines = 0

#        Create new picking for returned products
        if pick.type=='out':
            new_type = 'in'
        elif pick.type=='in':
            new_type = 'out'
        else:
            new_type = 'internal'
        seq_obj_name = 'stock.picking.' + new_type
        new_pick_name = self.pool.get('ir.sequence').get(cr, uid, seq_obj_name)
        new_picking = pick_obj.copy(cr, uid, pick.id, {'name':'%s-%s-return' % (new_pick_name, pick.name),
                'move_lines':[], 'state':'draft', 'type':new_type,
                'date':date_cur, 'invoice_state':data['invoice_state'],})

        val_id = data['product_return_moves']
        for v in val_id:
            data_get = data_obj.browse(cr, uid, v, context=context)
            mov_id = data_get.move_id.id
            new_qty = data_get.quantity
            move = move_obj.browse(cr, uid, mov_id, context=context)
            new_location = move.location_dest_id.id
            returned_qty = move.product_qty
            for rec in move.move_history_ids2:
                returned_qty -= rec.product_qty

            if returned_qty != new_qty:
                set_invoice_state_to_none = False
            if new_qty:
                returned_lines += 1
                new_move=move_obj.copy(cr, uid, move.id, {
                    'product_qty': new_qty,
                    'product_uos_qty': uom_obj._compute_qty(cr, uid, move.product_uom.id,
                        new_qty, move.product_uos.id),
                    'picking_id':new_picking, 'state':'draft',
                    'location_id':new_location, 'location_dest_id':move.location_id.id,
                    'date':date_cur,})
                move_obj.write(cr, uid, [move.id], {'move_history_ids2':[(4,new_move)]})
        if not returned_lines:
            raise osv.except_osv(_('Warning !'), _("Please specify at least one non-zero quantity!"))

        #
        # #1238 create a customer case entry to immediately notify accounting
        # of a returned product (on incoming shipments only)
        if pick.type=='in':
            helpdesk_obj = self.pool.get('crm.helpdesk')
            section_obj = self.pool.get('crm.case.section')
            employee_obj = self.pool.get('hr.employee')
            sales_team_code = 'acct'

            # Select a sales team to assign this case to
            try:
                section_id = section_obj.search(cr, uid, [('code', '=', sales_team_code)])[0]
            except IndexError:
                raise osv.except_osv('Error', 'You must configure a sales team with the code "acct" in order to notify accounting of returned products.')
            section = section_obj.browse(cr, uid, section_id, context=None)
            subject = u"Return Products to Supplier Alert"

            # get address id
            employee_id = employee_obj.search(cr, uid, [('user_id', '=', section.user_id.id)])[0]
            employee = employee_obj.browse(cr, uid, employee_id)
            partner_address_id = employee.address_id.id
            partner_id = 1 # Zaber

            # search for customer case by subject
            case_id = helpdesk_obj.search(cr, uid, [('name', '=', subject),
                                                    ('partner_id', '=', partner_id)]);
            # if the case doesn't exist, create it
            if case_id:
                case_id = case_id[0]
            else:
                case_id = helpdesk_obj.create(cr, uid,
                                              {'name': subject,
                                               'email_from': section.user_id.user_email,
                                               'partner_id': partner_id,
                                               'state': 'done',
                                               'description': subject,
                                               'partner_address_id': partner_address_id,
                                               'section_id': section_id
                                              })
            # Fetch the case obj so we can get its particulars
            case = helpdesk_obj.browse(cr, uid, case_id, context=context)

            # Create a list of emails we're going to send this alert to
            emails = [section.user_id.user_email] + (case.email_cc or '').split(',')
            emails = filter(None, emails)
            if not emails:
                emails = [section.user_id.user_email]

            body = u"The following Incoming Shipment has had products\n"\
                   u"returned.  Please check before paying the related\n"\
                   u"invoice.\n\n"
            body += u"Reference: {}\n".format(pick.name)
            body += u"PO: {}\n".format(pick.purchase_id.name)
            body += u"\n\n[This email was automatically generated by ZERP.]"

            # get the current user's particulars
            res_user = self.pool.get('res.users').browse(cr, uid, uid)

            # Add this correspondence to the new case
            self.pool.get('mail.message').create(cr, uid, {'model': 'crm.helpdesk',
                                         'res_id': case_id,
                                         'user_id': res_user.id,
                                         'subject': 'Historize',
                                         'date': time.strftime('%Y-%m-%d %H:%M:%S'),
                                         'body_text': body,
                                         'state': 'received'})

            # Send the email
            self.pool.get('mail.message').schedule_with_attach(cr, uid,
                    res_user.user_email, # sender
                    emails,
                    subject,
                    body,
                    model='crm.helpdesk',
                    reply_to=res_user.user_email,
                    res_id=case.id,
                    context=context)

        #
        # end customer case entry
        #

        if set_invoice_state_to_none:
            pick_obj.write(cr, uid, [pick.id], {'invoice_state':'none'})
        wf_service.trg_validate(uid, 'stock.picking', new_picking, 'button_confirm', cr)
        pick_obj.force_assign(cr, uid, [new_picking], context)
        # Update view id in context, lp:702939
        view_list = {
                'out': 'view_picking_out_tree',
                'in': 'view_picking_in_tree',
                'internal': 'vpicktree',
            }
        data_obj = self.pool.get('ir.model.data')
        res = data_obj.get_object_reference(cr, uid, 'stock', view_list.get(new_type, 'vpicktree'))
        context.update({'view_id': res and res[1] or False})
        return {
            'domain': "[('id', 'in', ["+str(new_picking)+"])]",
            'name': 'Picking List',
            'view_type':'form',
            'view_mode':'tree,form',
            'res_model':'stock.picking',
            'type':'ir.actions.act_window',
            'context':context,
        }

stock_return_picking()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:

