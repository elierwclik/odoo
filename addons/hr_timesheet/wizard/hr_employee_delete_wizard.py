# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import _, api, fields, models


class HrEmployeeDeleteWizard(models.TransientModel):
    _name = 'hr.employee.delete.wizard'
    _description = 'Employee Delete Wizard'

    employee_ids = fields.Many2many('hr.employee', string='Employees', context={'active_test': False}, export_string_translation=False)
    has_active_employee = fields.Boolean(string='Has Active Employee', compute='_compute_has_active_employee', export_string_translation=False)
    has_timesheet = fields.Boolean(string='Has Timesheet', compute='_compute_has_timesheet', compute_sudo=True, export_string_translation=False)

    @api.depends('employee_ids')
    def _compute_has_timesheet(self):
        timesheet_read_group = self.env['account.analytic.line']._read_group([
            ('employee_id', 'in', self.employee_ids.ids)],
            ['employee_id'],
        )
        timesheet_employee_map = {employee.id for [employee] in timesheet_read_group}
        for wizard in self:
            wizard.has_timesheet = timesheet_employee_map & set(wizard.employee_ids.ids)

    @api.depends('employee_ids')
    def _compute_has_active_employee(self):
        unarchived_employees = self.env['hr.employee'].search([('id', '=', self.employee_ids.ids)])
        for wizard in self:
            wizard.has_active_employee = any(emp in wizard.employee_ids for emp in unarchived_employees)

    def action_archive(self):
        self.ensure_one()
        return {
            'name': _('Employee Termination'),
            'type': 'ir.actions.act_window',
            'res_model': 'hr.departure.wizard',
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'active_ids': self.employee_ids.ids,
                'employee_termination': True,
            },
        }

    def action_confirm_delete(self):
        self.ensure_one()
        self.employee_ids.unlink()
        return self.env['ir.actions.act_window']._for_xml_id('hr.open_view_employee_list_my')

    def action_open_timesheets(self):
        self.ensure_one()
        employees = self.with_context(active_test=False).employee_ids
        action = {
           'name': _('Employees\' Timesheets'),
           'type': 'ir.actions.act_window',
           'res_model': 'account.analytic.line',
           'view_mode': 'list,form',
           'views': [(False, 'list'), (False, 'form')],
           'domain': [('employee_id', 'in', employees.ids), ('project_id', '!=', False)],
        }
        if len(employees) == 1:
            action['name'] = _('Timesheets of %(name)s', name=employees.name)
        return action
