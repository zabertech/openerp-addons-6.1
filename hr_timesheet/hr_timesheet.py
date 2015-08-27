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

import time

from osv import fields
from osv import osv
from tools.translate import _

class hr_employee(osv.osv):
    _name = "hr.employee"
    _inherit = "hr.employee"
    _columns = {
        'product_id': fields.many2one('product.product', 'Product', help="Specifies employee's designation as a product with type 'service'."),
        'journal_id': fields.many2one('account.analytic.journal', 'Analytic Journal'),
        'uom_id': fields.related('product_id', 'uom_id', type='many2one', relation='product.uom', string='UoM', store=True, readonly=True)
    }

    def _getAnalyticJournal(self, cr, uid, context=None):
        md = self.pool.get('ir.model.data')
        try:
            result = md.get_object_reference(cr, uid, 'hr_timesheet', 'analytic_journal')
            return result[1]
        except ValueError:
            pass
        return False

    def _getEmployeeProduct(self, cr, uid, context=None):
        md = self.pool.get('ir.model.data')
        try:
            result = md.get_object_reference(cr, uid, 'product', 'product_consultant')
            return result[1]
        except ValueError:
            pass
        return False

    _defaults = {
        'journal_id': _getAnalyticJournal,
        'product_id': _getEmployeeProduct
    }
hr_employee()


class hr_analytic_timesheet(osv.osv):
    _name = "hr.analytic.timesheet"
    _table = 'hr_analytic_timesheet'
    _description = "Timesheet Line"
    _inherits = {'account.analytic.line': 'line_id'}
    _order = "id desc"
    _columns = {
        'line_id': fields.many2one('account.analytic.line', 'Analytic Line', ondelete='cascade', required=True),
        'partner_id': fields.related('account_id', 'partner_id', type='many2one', string='Partner', relation='res.partner', store=True),
    }

    def unlink(self, cr, uid, ids, context=None):
        toremove = {}
        for obj in self.browse(cr, uid, ids, context=context):
            toremove[obj.line_id.id] = True
        return self.pool.get('account.analytic.line').unlink(cr, uid, toremove.keys(), context=context)

    def on_change_unit_amount(self, cr, uid, id, prod_id, unit_amount, company_id, unit=False, journal_id=False, context=None):
        res = {'value':{}}
        if prod_id and unit_amount:
            # find company
            company_id = self.pool.get('res.company')._company_default_get(cr, uid, 'account.analytic.line', context=context)
            r = self.pool.get('account.analytic.line').on_change_unit_amount(cr, uid, id, prod_id, unit_amount, company_id, unit, journal_id, context=context)
            if r:
                res.update(r)
        # update unit of measurement
        if prod_id:
            uom = self.pool.get('product.product').browse(cr, uid, prod_id, context=context)
            if uom.uom_id:
                res['value'].update({'product_uom_id': uom.uom_id.id})
        else:
            res['value'].update({'product_uom_id': False})
        return res

    def _getEmployeeProduct(self, cr, uid, context=None):
        if context is None:
            context = {}
        emp_obj = self.pool.get('hr.employee')
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', context.get('user_id', uid))], context=context)
        if emp_id:
            emp = emp_obj.browse(cr, uid, emp_id[0], context=context)
            if emp.product_id:
                return emp.product_id.id
        return False

    def _getEmployeeUnit(self, cr, uid, context=None):
        emp_obj = self.pool.get('hr.employee')
        if context is None:
            context = {}
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', context.get('user_id', uid))], context=context)
        if emp_id:
            emp = emp_obj.browse(cr, uid, emp_id[0], context=context)
            if emp.product_id:
                return emp.product_id.uom_id.id
        return False

    def _getGeneralAccount(self, cr, uid, context=None):
        emp_obj = self.pool.get('hr.employee')
        if context is None:
            context = {}
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', context.get('user_id', uid))], context=context)
        if emp_id:
            emp = emp_obj.browse(cr, uid, emp_id[0], context=context)
            if bool(emp.product_id):
                a = emp.product_id.product_tmpl_id.property_account_expense.id
                if not a:
                    a = emp.product_id.categ_id.property_account_expense_categ.id
                if a:
                    return a
        return False

    def _getAnalyticJournal(self, cr, uid, context=None):
        emp_obj = self.pool.get('hr.employee')
        if context is None:
            context = {}
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', context.get('user_id', uid))], context=context)
        if emp_id:
            emp = emp_obj.browse(cr, uid, emp_id[0], context=context)
            if emp.journal_id:
                return emp.journal_id.id
        return False


    _defaults = {
        'product_uom_id': _getEmployeeUnit,
        'product_id': _getEmployeeProduct,
        'general_account_id': _getGeneralAccount,
        'journal_id': _getAnalyticJournal,
        'date': lambda self, cr, uid, ctx: ctx.get('date', fields.date.context_today(self,cr,uid,context=ctx)),
        'user_id': lambda obj, cr, uid, ctx: ctx.get('user_id', uid),
    }
    def on_change_account_id(self, cr, uid, ids, account_id):
        return {'value':{}}

    def on_change_date(self, cr, uid, ids, date):
        if ids:
            new_date = self.read(cr, uid, ids[0], ['date'])['date']
            if date != new_date:
                warning = {'title':'User Alert!','message':'Changing the date will let this entry appear in the timesheet of the new date.'}
                return {'value':{},'warning':warning}
        return {'value':{}}

    def create(self, cr, uid, vals, context=None):
        if context is None:
            context = {}
        emp_obj = self.pool.get('hr.employee')
        emp_id = emp_obj.search(cr, uid, [('user_id', '=', context.get('user_id', uid))], context=context)
        ename = ''
        if emp_id:
            ename = emp_obj.browse(cr, uid, emp_id[0], context=context).name
        if not vals.get('journal_id',False):
           raise osv.except_osv(_('Warning !'), _('Analytic journal is not defined for employee %s \nDefine an employee for the selected user and assign an analytic journal!')%(ename,))
        if not vals.get('account_id',False):
           raise osv.except_osv(_('Warning !'), _('No analytic account defined on the project.\nPlease set one or we can not automatically fill the timesheet.'))
        return super(hr_analytic_timesheet, self).create(cr, uid, vals, context=context)

    def write(self, cr, uid, ids, vals, context=None):
        # #1081 send an email to employee when HR changes the analytic code in a
        # timesheet line of that employee

        # surely there's a better way to figure out what user's changes to
        # capture, using actual user roles, say
        HR_USER_IDS = [
            35, # Denise
            # FOR TESTING: 119, # sutracy
        ]

        if uid in HR_USER_IDS and 'account_id' in vals:
            for old_analytic_ts in self.browse(cr, uid, ids, context=context):
                if old_analytic_ts.sheet_id.user_id != uid \
                        and old_analytic_ts.sheet_id.state in ('confirm') \
                        and old_analytic_ts.account_id.id != vals['account_id']:
                    # doing this the easy way....just send an email for every change
                    # nicer way would be to collect all changes for each
                    # user...
                    self.send_analytic_change_email(cr, uid, context, old_analytic_ts, vals['account_id'])
        return super(hr_analytic_timesheet, self).write(cr, uid, ids, vals, context=context)

    def send_analytic_change_email(self, cr, uid, context, old_analytic_ts, new_account_id):
        # create a customer case entry to immediately notify user
        helpdesk_obj = self.pool.get('crm.helpdesk')
        section_obj = self.pool.get('crm.case.section')
        employee_obj = self.pool.get('hr.employee')
        analytic_obj = self.pool.get('account.analytic.account')
        sales_team_code = 'hrp'

        # Select a sales team to assign this case to
        try:
            section_id = section_obj.search(cr, uid, [('code', '=', sales_team_code)])[0]
        except IndexError:
            raise osv.except_osv('Error', 'You must configure a sales team with the code "hrp" in order to notify employees of a timesheet line analytic change.')
        section = section_obj.browse(cr, uid, section_id, context=None)
        subject = u"Timesheet Analytic Updated"

        # Get information needed to send email
        employee = employee_obj.browse(cr, uid, old_analytic_ts.sheet_id.employee_id.id)
        partner_address_id = employee.address_id.id
        partner_id = 1 # Zaber partner
        new_account_name = analytic_obj.browse(cr, uid, new_account_id, context).name
        res_user = self.pool.get('res.users').browse(cr, uid, uid)

        # Search for customer case by subject
        case_id = helpdesk_obj.search(cr, uid, [('name', '=', subject),
                                                ('partner_id', '=', partner_id)])

        if case_id:
            case_id = case_id[0]
        else:
            # if the case doesn't exist, create it
            case_id = helpdesk_obj.create(cr, uid,
                                          {'name': subject,
                                           'email_from': section.user_id.user_email,
                                           'partner_id': partner_id,
                                           'state': 'done',
                                           'description': subject,
                                           'partner_address_id': partner_address_id,
                                           'section_id': section_id,
                                           })
        # Fetch the case obj so we can get its particulars
        case = helpdesk_obj.browse(cr, uid, case_id, context=context)

        body = u"I changed the analytic code for a timesheet line on " + \
               old_analytic_ts.line_id.date + \
               u" with description\n  \"" + \
               old_analytic_ts.line_id.name + \
               u"\"\nfrom " + \
               old_analytic_ts.account_id.name + \
               u" to " + new_account_name + \
               u".\n\nPlease see me if you have any questions." + \
               u"\n\n[This email was automatically generated.]"

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
                res_user.user_email, # from-email
                [old_analytic_ts.sheet_id.employee_id.work_email], # to-email
                subject,
                body,
                model='crm.helpdesk',
                reply_to=res_user.user_email,
                res_id=case.id,
                context=context)

    def on_change_user_id(self, cr, uid, ids, user_id):
        if not user_id:
            return {}
        context = {'user_id': user_id}
        return {'value': {
            'product_id': self. _getEmployeeProduct(cr, uid, context),
            'product_uom_id': self._getEmployeeUnit(cr, uid, context),
            'general_account_id': self._getGeneralAccount(cr, uid, context),
            'journal_id': self._getAnalyticJournal(cr, uid, context),
        }}

hr_analytic_timesheet()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
