import time
from datetime import datetime
from dateutil.relativedelta import relativedelta

from osv import fields, osv

class hr_employee(osv.osv):
    _name = "hr.employee"
    _description = "Employee"
    _inherit = "hr.employee"

    def _get_latest_contract(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        obj_contract = self.pool.get('hr.contract')
        for emp in self.browse(cr, uid, ids, context=context):
            contract_ids = obj_contract.search(cr, uid, [('employee_id','=',emp.id),], order='date_start', context=context)
            if contract_ids:
                res[emp.id] = contract_ids[-1:][0]
            else:
                res[emp.id] = False
        return res

    _columns = {
        'manager': fields.boolean('Is a Manager'),
        'medic_exam': fields.date('Medical Examination Date'),
        'place_of_birth': fields.char('Place of Birth', size=30),
        'children': fields.integer('Number of Children'),
        'vehicle': fields.char('Company Vehicle', size=64),
        'vehicle_distance': fields.integer('Home-Work Distance', help="In kilometers"),
        'contract_ids': fields.one2many('hr.contract', 'employee_id', 'Contracts'),
        'contract_id':fields.function(_get_latest_contract, string='Contract', type='many2one', relation="hr.contract", help='Latest contract of the employee'),
    }

hr_employee()

class hr_contract_type(osv.osv):
    _name = 'hr.contract.type'
    _description = 'Contract Type'
    _columns = {
        'name': fields.char('Contract Type', size=32, required=True),
        'payroll_business_number': fields.char('Payroll Business Number', size=20),
    }
hr_contract_type()

class hr_contract(osv.osv):
    _name = 'hr.contract'
    _description = 'Contract'

    def _calculate_annualized_wage(self, cr, uid, ids, field_name, args, context=None):
        res = {}
        for contract in self.browse(cr, uid, ids, context=context):
            res[contract.id] = contract.wage * contract.benefits_weekly_hours * 52
        return res

    def onchange_benefits_wage(self, cr, uid, ids, hours, wage, context=None):
        return {'value': {'annualized_wage': wage * hours * 52}}

    _columns = {
        'name': fields.char('Contract Reference', size=64, required=True),
        'employee_id': fields.many2one('hr.employee', "Employee", required=True),
        'department_id': fields.related('employee_id','department_id', type='many2one', relation='hr.department', string="Department", readonly=True),
        'type_id': fields.many2one('hr.contract.type', "Contract Type", required=True),
        'job_id': fields.many2one('hr.job', 'Job Title'),
        'date_start': fields.date('Start Date', required=True),
        'date_end': fields.date('End Date'),
        'trial_date_start': fields.date('Trial Start Date'),
        'trial_date_end': fields.date('Trial End Date'),
        'working_hours': fields.many2one('resource.calendar','Working Schedule'),
        'wage': fields.float('Wage', digits=(16,2), required=True, help="Basic Salary of the employee"),
        'benefits_weekly_hours': fields.float('Expected Weekly Hours', digits=(16,2),
                help="For benefits purposes only.\nExpected number of hours per week."),
        'annualized_wage': fields.function(_calculate_annualized_wage, readonly=False,
                string='Annualized Wage', type='float', digits=(16,2),
                help="For benefits purposes only.\nCalculated as Wage * Expected Weekly Hours * 52"),
        'provider_updated': fields.boolean('Provider Updated',
                help="Has the benefits provider been updated for the new contract wage?"),
        'advantages': fields.text('Advantages'),
        'notes': fields.text('Notes'),
        'permit_no': fields.char('Work Permit No', size=256, required=False, readonly=False),
        'visa_no': fields.char('Visa No', size=64, required=False, readonly=False),
        'visa_expire': fields.date('Visa Expire Date'),
    }

    def _get_type(self, cr, uid, context=None):
        type_ids = self.pool.get('hr.contract.type').search(cr, uid, [('name', '=', 'Employee')])
        return type_ids and type_ids[0] or False

    _defaults = {
        'type_id': _get_type
    }

    def _check_dates(self, cr, uid, ids, context=None):
        for contract in self.read(cr, uid, ids, ['date_start', 'date_end'], context=context):
             if contract['date_start'] and contract['date_end'] and contract['date_start'] > contract['date_end']:
                 return False
        return True

    def onchange_date_start(self, cr, uid, ids, date_start, name, context=None):
        # only populate name if there isn't anything already there
        # and only if date_start has actually been filled out
        if not date_start or name:
            return {}
        # change Contract Reference to show:
        #   Hire (rev3: yyyymmdd, rev6: yyyymmdd)
        # where rev3 gives start date + 90 and rev6 gives start date + 180 days
        date_start = datetime.strptime(date_start, "%Y-%m-%d").date()
        rev3 = date_start + relativedelta(days=90)
        rev6 = date_start + relativedelta(days=180)
        rev3str = datetime.strftime(rev3, "%Y%m%d")
        rev6str = datetime.strftime(rev6, "%Y%m%d")
        return {'value': {'name': 'Hire (rev3: %s, rev6: %s)' % (rev3str, rev6str)}}

    def action_raise(self, cr, uid, ids, context=None):
        if len(ids) > 1:
            raise osv.except_osv('Error',
                    'Apply raise can only be run on one record at a time')
        if context is None: context={}
        contract_info = self.read(cr, uid, ids[0], ['employee_id', 'wage'])
        context = dict(context, active_ids=ids, active_model=self._name,
                employee_id=contract_info['employee_id'],
                wage=contract_info['wage'])
        return {
            'name':"Apply Raise",
            'view_mode': 'form',
            'view_id': False,
            'view_type': 'form',
            'res_model': 'hr.contract.apply.raise',
            'type': 'ir.actions.act_window',
            'nodestroy': True,
            'target': 'new',
            'domain': '[]',
            'context': context,
        }

    _constraints = [
        (_check_dates, 'Error! contract start-date must be lower then contract end-date.', ['date_start', 'date_end'])
    ]
hr_contract()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
