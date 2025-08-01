# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, tools, _


class HrLeaveEmployeeTypeReport(models.Model):
    _name = 'hr.leave.employee.type.report'
    _description = 'Time Off Summary / Report'
    _auto = False
    _order = "date_from DESC, employee_id"

    employee_id = fields.Many2one('hr.employee', string="Employee", readonly=True)
    active_employee = fields.Boolean(readonly=True)
    number_of_days = fields.Float('Number of Days', readonly=True, aggregator="sum")
    number_of_hours = fields.Float('Number of Hours', readonly=True, aggregator="sum")
    department_id = fields.Many2one('hr.department', string='Department', readonly=True)
    leave_type = fields.Many2one("hr.leave.type", string="Time Off Type", readonly=True)
    holiday_status = fields.Selection([
        ('taken', 'Taken'), #taken = validated
        ('left', 'Left'),
        ('planned', 'Planned')
    ])
    state = fields.Selection([
        ('cancel', 'Cancelled'),
        ('confirm', 'To Approve'),
        ('refuse', 'Refused'),
        ('validate1', 'Second Approval'),
        ('validate', 'Approved')
        ], string='Status', readonly=True)
    date_from = fields.Datetime('Start Date', readonly=True)
    date_to = fields.Datetime('End Date', readonly=True)
    company_id = fields.Many2one('res.company', string="Company", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'hr_leave_employee_type_report')

        self.env.cr.execute("""
            CREATE or REPLACE view hr_leave_employee_type_report as (
                SELECT row_number() over(ORDER BY leaves.employee_id) as id,
                leaves.employee_id as employee_id,
                leaves.active_employee as active_employee,
                leaves.number_of_days as number_of_days,
                leaves.number_of_hours as number_of_hours,
                leaves.department_id as department_id,
                leaves.leave_type as leave_type,
                leaves.holiday_status as holiday_status,
                leaves.state as state,
                leaves.date_from as date_from,
                leaves.date_to as date_to,
                leaves.company_id as company_id
                FROM (SELECT
                    allocation.employee_id as employee_id,
                    employee.active as active_employee,
                    CASE
                        WHEN allocation.id = min_allocation_id.min_id
                            THEN aggregate_allocation.number_of_days - COALESCE(aggregate_leave.number_of_days, 0)
                            ELSE 0
                    END as number_of_days,
                    CASE
                        WHEN allocation.id = min_allocation_id.min_id
                            THEN aggregate_allocation.number_of_hours - COALESCE(aggregate_leave.number_of_hours, 0)
                            ELSE 0
                    END as number_of_hours,
                    v.department_id as department_id,
                    allocation.holiday_status_id as leave_type,
                    allocation.state as state,
                    allocation.date_from as date_from,
                    allocation.date_to as date_to,
                    'left' as holiday_status,
                    allocation.employee_company_id as company_id
                FROM hr_leave_allocation as allocation
                INNER JOIN hr_employee as employee ON (allocation.employee_id = employee.id)
                LEFT JOIN hr_version v ON v.id = employee.current_version_id

                /* Obtain the minimum id for a given employee and type of leave */
                LEFT JOIN
                    (SELECT employee_id, holiday_status_id, min(id) as min_id
                    FROM hr_leave_allocation GROUP BY employee_id, holiday_status_id) min_allocation_id
                on (allocation.employee_id=min_allocation_id.employee_id and allocation.holiday_status_id=min_allocation_id.holiday_status_id)

                /* Obtain the sum of allocations (validated) */
                LEFT JOIN
                    (SELECT employee_id, holiday_status_id,
                        sum(CASE WHEN state = 'validate' THEN number_of_days ELSE 0 END) as number_of_days,
                        sum(CASE WHEN state = 'validate' THEN number_of_hours_display ELSE 0 END) as number_of_hours
                    FROM hr_leave_allocation
                    GROUP BY employee_id, holiday_status_id) aggregate_allocation
                on (allocation.employee_id=aggregate_allocation.employee_id and allocation.holiday_status_id=aggregate_allocation.holiday_status_id)

                /* Obtain the sum of requested leaves (validated) */
                LEFT JOIN
                    (SELECT employee_id, holiday_status_id,
                        sum(CASE WHEN state IN ('validate', 'validate1') THEN number_of_days ELSE 0 END) as number_of_days,
                        sum(CASE WHEN state IN ('validate', 'validate1') THEN number_of_hours ELSE 0 END) as number_of_hours
                    FROM hr_leave

                    GROUP BY employee_id, holiday_status_id) aggregate_leave
                on (allocation.employee_id=aggregate_leave.employee_id and allocation.holiday_status_id = aggregate_leave.holiday_status_id)

                UNION ALL SELECT
                    request.employee_id as employee_id,
                    employee.active as active_employee,
                    request.number_of_days as number_of_days,
                    request.number_of_hours as number_of_hours,
                    v.department_id as department_id,
                    request.holiday_status_id as leave_type,
                    request.state as state,
                    request.date_from as date_from,
                    request.date_to as date_to,
                    CASE
                        WHEN request.state IN ('validate1', 'validate') THEN 'taken'
                        WHEN request.state = 'confirm' THEN 'planned'
                    END as holiday_status,
                    request.employee_company_id as company_id
                FROM hr_leave as request
                INNER JOIN hr_employee as employee ON (request.employee_id = employee.id)
                LEFT JOIN hr_version v ON v.id = employee.current_version_id
                WHERE request.state IN ('confirm', 'validate', 'validate1')) leaves
            );
        """)

    @api.model
    def action_time_off_analysis(self):
        domain = [('company_id', 'in', self.env.companies.ids)]
        if self.env.context.get('active_ids'):
            domain = [('employee_id', 'in', self.env.context.get('active_ids', [])),
                      ('state', '!=', 'cancel')]

        return {
            'name': _('Balance'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.leave.employee.type.report',
            'view_mode': 'pivot',
            'search_view_id': [self.env.ref('hr_holidays.view_search_hr_holidays_employee_type_report').id],
            'domain': domain,
            'help': _("""
                <p class="o_view_nocontent_empty_folder">
                    No Balance yet!
                </p>
                <p>
                    Why don't you start by <a type="action" class="text-link" name="%d">Allocating Time off</a> ?
                </p>
            """, self.env.ref("hr_holidays.hr_leave_allocation_action_form").id),
            'context': {
                'search_default_year': True,
                'search_default_company': True,
                'search_default_employee': True,
                'group_expand': True,
            }
        }
