from osv import fields, osv
from tools import config
import datetime

class hr_contract_apply_raise(osv.osv_memory):
    CONTRACT_REF = "Raise"
    HR_EMAIL = "hr@zaber.com"
    EMAIL_SUBJECT = "Raise notification"
    EMAIL_FORMAT_STRING = \
"""This is an automatic notification that {user_name} has confirmed the following raise in ZERP:

Name: {employee_name}
Raise: ${increase_amount}
Effective date: {effective_date}"""

    _name = 'hr.contract.apply.raise'
    _rec_name = 'employee_id'
    _columns = {
        'employee_id': fields.many2one('hr.employee', string='Employee', readonly=True, ondelete='CASCADE'),
        'contract_id': fields.many2one('hr.contract', string='Contract', readonly=True),
        'current_wage': fields.float('Current Wage', digits=(16,2), readonly=True),
        'effective_date': fields.date('Effective Date', required=True),
        'increase_amount': fields.float('Increase Amount', digits=(16,2), required=True),
        'email_to': fields.char('Send To', size=480, readonly=True),
        'email_from': fields.char('From', size=480, readonly=True),
        'email_subject': fields.char('Subject', size=480, readonly=True),
        'email_body': fields.text('Email Text'),
    }

    # get emails for employee's manager, their manger's manager, their manager's manager's
    # manager, and so on till you get to someone with no manager
    def _get_notification_addr(self, cr, uid, employee_id, context):
        emp_obj = self.pool.get('hr.employee')
        emp_info = emp_obj.browse(cr, uid, employee_id, context=context)
        emails = [self.HR_EMAIL]
        manager= emp_info.parent_id
        while manager:
            emails.append(manager.work_email)
            manager = manager.parent_id
        return ", ".join(emails)

    def _get_user_addr(self, cr, uid):
        return self.pool.get('res.users').read(cr, uid, uid, ['user_email'])['user_email']

    _defaults = {
        'contract_id': lambda self, cr, uid, context: context['active_ids'][0],
        'employee_id': lambda self, cr, uid, context: context['employee_id'][0],
        'current_wage': lambda self, cr, uid, context: context['wage'],
        'email_to': lambda self, cr, uid, context: self._get_notification_addr(cr, uid, context['employee_id'][0], context),
        'email_from': lambda self, cr, uid, context: self._get_user_addr(cr, uid),
        'email_subject': EMAIL_SUBJECT
    }

    def onchange_set_email(self, cr, uid, ids, employee_id, effective_date, increase_amount):
        employee_name = self.pool.get('hr.employee').read(cr, uid, employee_id, ['name'])['name']
        user_name = self.pool.get('res.users').read(cr, uid, uid, ['name'])['name']

        if not effective_date:
            effective_date = "______"
        if not increase_amount:
            increase_amount = "______"
        else:
            increase_amount = '{:.2f}'.format(float(increase_amount))
        email_body = self.EMAIL_FORMAT_STRING.format(
                user_name = user_name,
                employee_name = employee_name,
                increase_amount = increase_amount,
                effective_date = effective_date)
        return {'value': {'email_body': email_body}}

    def apply_raise(self, cr, uid, ids, context=None):
        contract_obj = self.pool.get('hr.contract')
        type_obj = self.pool.get('hr.contract.type')
        mail_obj = self.pool.get('ir.mail_server')

        form_data = self.read(cr, uid, ids[0])

        (contract_id, contract_ref) = form_data['contract_id']
        type_id = contract_obj.read(cr, uid, contract_id, ['type_id'])['type_id'][0]

        # remove anything in brackets from the existing contract reference and
        # tag it onto the new contract ref
        edited_contract_ref = contract_ref
        new_contract_ref = self.CONTRACT_REF
        if contract_ref.endswith(')') and contract_ref.count(' (') == 1:
            edited_contract_ref = contract_ref[:contract_ref.index(' (')]
            new_contract_ref += contract_ref[contract_ref.index(' ('):]

        # compute the existing contract end date
        contract_end_date = datetime.datetime.strptime(form_data['effective_date'], "%Y-%m-%d").date() \
                - datetime.timedelta(1)

        new_wage = form_data['current_wage'] + form_data['increase_amount']

        # update the existing contract
        contract_obj.write(cr, uid, [contract_id], {
                'name': edited_contract_ref,
                'date_end': contract_end_date,})

        # create the new contract
        new_contract_id = contract_obj.copy(cr, uid, contract_id, {
                'name': new_contract_ref,
                'date_start': form_data['effective_date'],
                'date_end': None,
                'wage': new_wage,
                'annualized_wage': new_annualized_wage,
                'provider_updated': False})

        # send email notification
        sender = form_data['email_from']
        recipients = form_data['email_to']
        subject = form_data['email_subject']
        body = form_data['email_body']

        # for debugging, send emails to email in config, and edit the body
        mailto = config.get('hr_contract_force_emails_to', recipients)
        if mailto != recipients:
            body = "THIS IS A TEST\nmailto: " + recipients + "\n\n" + body

        # build_emails wants a list of addresses, but our form data already put
        # them into a comma separated string
        mail_message = mail_obj.build_email(sender, mailto.split(", "), subject, body)

        try:
            mail_obj.send_email(cr, uid, mail_message)
        except Exception as err:
            raise osv.except_osv('Error', "Could not send notification email.\n\n" + str(err))

        return {'type': 'ir.actions.act_window_close'}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
