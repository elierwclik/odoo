# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from datetime import date, datetime, time, timedelta, timezone
from collections import defaultdict
from dateutil.relativedelta import relativedelta
import pytz

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.addons.resource.models.utils import HOURS_PER_DAY
from odoo.tools.float_utils import float_round


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    leave_manager_id = fields.Many2one(
        'res.users', string='Time Off Approver',
        compute='_compute_leave_manager', store=True, readonly=False,
        domain="[('share', '=', False), ('company_ids', 'in', company_id)]",
        help='Select the user responsible for approving "Time Off" of this employee.\n'
             'If empty, the approval is done by an Administrator or Approver (determined in settings/users).')
    current_leave_id = fields.Many2one('hr.leave.type', compute='_compute_current_leave', string="Current Time Off Type",
                                       groups="hr.group_hr_user")
    current_leave_state = fields.Selection(compute='_compute_leave_status', string="Current Time Off Status",
        selection=[
            ('confirm', 'Waiting Approval'),
            ('refuse', 'Refused'),
            ('validate1', 'Waiting Second Approval'),
            ('validate', 'Approved'),
            ('cancel', 'Cancelled'),
        ], groups="hr.group_hr_user")
    leave_date_from = fields.Date('From Date', compute='_compute_leave_status', groups="hr.group_hr_user")
    leave_date_to = fields.Date('To Date', compute='_compute_leave_status')
    allocation_count = fields.Float('Total number of days allocated.', compute='_compute_allocation_count',
                                    groups="hr.group_hr_user")
    allocations_count = fields.Integer('Total number of allocations', compute="_compute_allocation_count",
                                       groups="hr.group_hr_user")
    show_leaves = fields.Boolean('Able to see Remaining Time Off', compute='_compute_show_leaves')
    is_absent = fields.Boolean('Absent Today', compute='_compute_leave_status', search='_search_absent_employee')
    allocation_display = fields.Char(compute='_compute_allocation_remaining_display')
    allocation_remaining_display = fields.Char(compute='_compute_allocation_remaining_display')
    hr_icon_display = fields.Selection(selection_add=[
        ('presence_holiday_absent', 'On leave'),
        ('presence_holiday_present', 'Present but on leave')])

    def _compute_current_leave(self):
        self.current_leave_id = False

        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('date_from', '<=', fields.Datetime.now()),
            ('date_to', '>=', fields.Datetime.now()),
            ('state', '=', 'validate'),
        ])
        for holiday in holidays:
            employee = self.filtered(lambda e: e.id == holiday.employee_id.id)
            employee.current_leave_id = holiday.holiday_status_id.id

    def _compute_presence_state(self):
        super()._compute_presence_state()
        employees = self.filtered(lambda employee: employee.hr_presence_state != 'present' and employee.is_absent)
        employees.update({'hr_presence_state': 'absent'})

    def _compute_allocation_count(self):
        # Don't get allocations that are expired
        current_date = date.today()
        data = self.env['hr.leave.allocation']._read_group([
            ('employee_id', 'in', self.ids),
            ('holiday_status_id.active', '=', True),
            ('holiday_status_id.requires_allocation', '=', 'yes'),
            ('state', '=', 'validate'),
            ('date_from', '<=', current_date),
            '|',
            ('date_to', '=', False),
            ('date_to', '>=', current_date),
        ], ['employee_id'], ['__count', 'number_of_days:sum'])
        rg_results = {employee.id: (count, days) for employee, count, days in data}
        for employee in self:
            count, days = rg_results.get(employee.id, (0, 0))
            employee.allocation_count = float_round(days, precision_digits=2)
            employee.allocations_count = count

    def _compute_allocation_remaining_display(self):
        current_date = date.today()
        allocations = self.env['hr.leave.allocation'].search([('employee_id', 'in', self.ids)])
        leaves_taken = self._get_consumed_leaves(allocations.holiday_status_id)[0]
        for employee in self:
            employee_remaining_leaves = 0
            employee_max_leaves = 0
            for leave_type in leaves_taken[employee]:
                if leave_type.requires_allocation == 'no' or leave_type.hide_on_dashboard:
                    continue
                for allocation in leaves_taken[employee][leave_type]:
                    if allocation and allocation.date_from <= current_date\
                            and (not allocation.date_to or allocation.date_to >= current_date):
                        virtual_remaining_leaves = leaves_taken[employee][leave_type][allocation]['virtual_remaining_leaves']
                        employee_remaining_leaves += virtual_remaining_leaves\
                            if leave_type.request_unit in ['day', 'half_day']\
                            else virtual_remaining_leaves / (employee.resource_calendar_id.hours_per_day or HOURS_PER_DAY)
                        employee_max_leaves += allocation.number_of_days
            employee.allocation_remaining_display = "%g" % float_round(employee_remaining_leaves, precision_digits=2)
            employee.allocation_display = "%g" % float_round(employee_max_leaves, precision_digits=2)

    def _compute_presence_icon(self):
        super()._compute_presence_icon()
        employees_absent = self.filtered(
            lambda employee: employee.hr_presence_state != 'present' and employee.is_absent)
        employees_absent.update({'hr_icon_display': 'presence_holiday_absent', 'show_hr_icon_display': True})
        employees_present = self.filtered(
            lambda employee: employee.hr_presence_state == 'present' and employee.is_absent)
        employees_present.update({'hr_icon_display': 'presence_holiday_present', 'show_hr_icon_display': True})

    def _get_first_working_interval(self, dt):
        # find the first working interval after a given date
        dt = dt.replace(tzinfo=timezone.utc)
        lookahead_days = [7, 30, 90, 180, 365, 730]
        work_intervals = None
        for lookahead_day in lookahead_days:
            periods = self._get_calendar_periods(dt, dt + timedelta(days=lookahead_day))
            if not periods:
                calendar = self.resource_calendar_id or self.company_id.resource_calendar_id
                work_intervals = calendar._work_intervals_batch(
                    dt, dt + timedelta(days=lookahead_day), resources=self.resource_id)
            else:
                for period in periods[self]:
                    start, end, calendar = period
                    calendar = calendar or self.company_id.resource_calendar_id
                    work_intervals = calendar._work_intervals_batch(
                        start, end, resources=self.resource_id)
            if work_intervals.get(self.resource_id.id) and work_intervals[self.resource_id.id]._items:
                # return start time of the earliest interval
                return work_intervals[self.resource_id.id]._items[0][0]

    def _compute_leave_status(self):
        # Used SUPERUSER_ID to forcefully get status of other user's leave, to bypass record rule
        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', 'in', self.ids),
            ('date_from', '<=', fields.Datetime.now()),
            ('date_to', '>=', fields.Datetime.now()),
            ('state', '=', 'validate'),
        ])
        leave_data = {}
        for holiday in holidays:
            leave_data[holiday.employee_id.id] = {}
            leave_data[holiday.employee_id.id]['leave_date_from'] = holiday.date_from.date()
            back_on = holiday.employee_id._get_first_working_interval(holiday.date_to)
            leave_data[holiday.employee_id.id]['leave_date_to'] = back_on.date() if back_on else None
            leave_data[holiday.employee_id.id]['current_leave_state'] = holiday.state

        for employee in self:
            employee.leave_date_from = leave_data.get(employee.id, {}).get('leave_date_from')
            employee.leave_date_to = leave_data.get(employee.id, {}).get('leave_date_to')
            employee.current_leave_state = leave_data.get(employee.id, {}).get('current_leave_state')
            employee.is_absent = leave_data.get(employee.id) and leave_data.get(employee.id).get('current_leave_state') == 'validate'

    @api.depends('parent_id')
    def _compute_leave_manager(self):
        for employee in self:
            previous_manager = employee._origin.parent_id.user_id
            manager = employee.parent_id.user_id
            if manager and employee.leave_manager_id == previous_manager or not employee.leave_manager_id:
                employee.leave_manager_id = manager
            elif not employee.leave_manager_id:
                employee.leave_manager_id = False

    def _compute_show_leaves(self):
        show_leaves = self.env.user.has_group('hr_holidays.group_hr_holidays_user')
        for employee in self:
            if show_leaves or employee.user_id == self.env.user:
                employee.show_leaves = True
            else:
                employee.show_leaves = False

    def _search_absent_employee(self, operator, value):
        if operator != 'in':
            return NotImplemented
        # This search is only used for the 'Absent Today' filter however
        # this only returns employees that are absent right now.
        today_start = date.today()
        today_end = today_start + timedelta(1)
        holidays = self.env['hr.leave'].sudo().search([
            ('employee_id', '!=', False),
            ('state', '=', 'validate'),
            ('date_from', '<', today_end),
            ('date_to', '>=', today_start),
        ])
        return [('id', 'in', holidays.employee_id.ids)]

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('salary_simulation'):
            return super().create(vals_list)
        approver_group = self.env.ref('hr_holidays.group_hr_holidays_responsible', raise_if_not_found=False)
        group_updates = []
        for vals in vals_list:
            if 'parent_id' in vals:
                manager = self.env['hr.employee'].browse(vals['parent_id']).user_id
                vals['leave_manager_id'] = vals.get('leave_manager_id', manager.id)
            if approver_group and vals.get('leave_manager_id'):
                group_updates.append((4, vals['leave_manager_id']))
        if group_updates:
            approver_group.sudo().write({'user_ids': group_updates})
        return super().create(vals_list)

    def write(self, vals):
        values = vals
        # Prevent the resource calendar of leaves to be updated by a write to
        # employee. When this module is enabled the resource calendar of
        # leaves are determined by those of the contracts.
        self = self.with_context(no_leave_resource_calendar_update=True)  # noqa: PLW0642
        if 'parent_id' in values:
            manager = self.env['hr.employee'].browse(values['parent_id']).user_id
            if manager:
                to_change = self.filtered(lambda e: e.leave_manager_id == e.parent_id.user_id or not e.leave_manager_id)
                to_change.write({'leave_manager_id': values.get('leave_manager_id', manager.id)})

        old_managers = self.env['res.users']
        if 'leave_manager_id' in values:
            old_managers = self.mapped('leave_manager_id')
            if values['leave_manager_id']:
                leave_manager = self.env['res.users'].browse(values['leave_manager_id'])
                old_managers -= leave_manager
                approver_group = self.env.ref('hr_holidays.group_hr_holidays_responsible', raise_if_not_found=False)
                if approver_group and not leave_manager.has_group('hr_holidays.group_hr_holidays_responsible'):
                    leave_manager.sudo().write({'group_ids': [(4, approver_group.id)]})

        res = super().write(values)
        # remove users from the Responsible group if they are no longer leave managers
        old_managers.sudo()._clean_leave_responsible_users()

        # Change the resource calendar of the employee's leaves in the future
        # Other modules can disable this behavior by setting the context key
        # 'no_leave_resource_calendar_update'
        if 'resource_calendar_id' in values and not self.env.context.get('no_leave_resource_calendar_update'):
            try:
                self.env['hr.leave'].search([
                    ('employee_id', 'in', self.ids),
                    ('resource_calendar_id', '!=', int(values['resource_calendar_id'])),
                    ('date_from', '>', fields.Datetime.now())]).write({'resource_calendar_id': values['resource_calendar_id']})
            except ValidationError:
                raise ValidationError(_("Changing this working schedule results in the affected employee(s) not having enough "
                                        "leaves allocated to accomodate for their leaves already taken in the future. Please "
                                        "review this employee's leaves and adjust their allocation accordingly."))

        if 'parent_id' in values or 'department_id' in values:
            today_date = fields.Datetime.now()
            hr_vals = {}
            if values.get('department_id') is not None:
                hr_vals['department_id'] = values['department_id']
            holidays = self.env['hr.leave'].sudo().search([
                '|',
                ('state', '=', 'confirm'),
                ('date_from', '>', today_date),
                ('employee_id', 'in', self.ids),
            ])
            holidays.write(hr_vals)
            if values.get('parent_id') is not None:
                hr_vals['manager_id'] = values['parent_id']
            allocations = self.env['hr.leave.allocation'].sudo().search([
                ('state', '=', 'confirm'),
                ('employee_id', 'in', self.ids),
            ])
            allocations.write(hr_vals)
        return res

    def _get_user_m2o_to_empty_on_archived_employees(self):
        return super()._get_user_m2o_to_empty_on_archived_employees() + ['leave_manager_id']

    def action_time_off_dashboard(self):
        action = self.env['ir.actions.act_window']._for_xml_id('hr_holidays.hr_leave_action_action_approve_department')
        action['context'] = dict(literal_eval(action['context']))
        action['context']['show_dashboard'] = True
        action['context'].pop('search_default_waiting_for_me', False)
        action['context'].pop('search_default_waiting_for_me_manager', False)
        action['context']['default_employee_id'] = self.id
        action['domain'] = [('employee_id', 'in', self.ids)]
        return action

    def get_mandatory_days(self, start_date, end_date):
        all_days = {}

        self = self or self.env.user.employee_id

        mandatory_days = self._get_mandatory_days(start_date, end_date)
        for mandatory_day in mandatory_days:
            num_days = (mandatory_day.end_date - mandatory_day.start_date).days
            for d in range(num_days + 1):
                all_days[str(mandatory_day.start_date + relativedelta(days=d))] = mandatory_day.color

        return all_days

    @api.model
    def get_special_days_data(self, date_start, date_end):
        return {
            'mandatoryDays': self.get_mandatory_days_data(date_start, date_end),
            'bankHolidays': self.get_public_holidays_data(date_start, date_end),
        }

    @api.model
    def get_public_holidays_data(self, date_start, date_end):
        self = self._get_contextual_employee()
        employee_tz = pytz.timezone(self._get_tz() if self else self.env.user.tz or 'utc')
        public_holidays = self._get_public_holidays(date_start, date_end).sorted('date_from')
        return list(map(lambda bh: {
            'id': -bh.id,
            'colorIndex': 0,
            'end': datetime.combine(bh.date_to.astimezone(employee_tz), datetime.max.time()).isoformat(),
            'endType': "datetime",
            'isAllDay': True,
            'start': datetime.combine(bh.date_from.astimezone(employee_tz), datetime.min.time()).isoformat(),
            'startType': "datetime",
            'title': bh.name,
        }, public_holidays))

    @api.model
    def get_time_off_dashboard_data(self, target_date=None):
        dashboard_data = {}
        dashboard_data['has_accrual_allocation'] = self.env['hr.leave.type'].has_accrual_allocation()
        dashboard_data['allocation_data'] = self.env['hr.leave.type'].get_allocation_data_request(target_date, False)
        dashboard_data['allocation_request_amount'] = self.get_allocation_requests_amount()
        return dashboard_data

    @api.model
    def get_allocation_requests_amount(self):
        employee = self._get_contextual_employee()
        return self.env['hr.leave.allocation'].search_count([
            ('employee_id', '=', employee.id),
            ('state', '=', 'confirm'),
        ])

    def _get_public_holidays(self, date_start, date_end):
        domain = [
            ('resource_id', '=', False),
            ('company_id', 'in', self.env.companies.ids),
            ('date_from', '<=', date_end),
            ('date_to', '>=', date_start),
            '|',
            ('calendar_id', '=', False),
            ('calendar_id', '=', self.resource_calendar_id.id),
        ]

        return self.env['resource.calendar.leaves'].search(domain)

    @api.model
    def get_mandatory_days_data(self, date_start, date_end):
        self = self._get_contextual_employee()
        mandatory_days = self._get_mandatory_days(date_start, date_end).sorted('start_date')
        return list(map(lambda sd: {
            'id': -sd.id,
            'colorIndex': sd.color,
            'end': datetime.combine(sd.end_date, datetime.max.time()).isoformat(),
            'endType': "datetime",
            'isAllDay': True,
            'start': datetime.combine(sd.start_date, datetime.min.time()).isoformat(),
            'startType': "datetime",
            'title': sd.name,
        }, mandatory_days))

    def _get_mandatory_days(self, start_date, end_date):
        domain = [
            ('start_date', '<=', end_date),
            ('end_date', '>=', start_date),
            ('company_id', 'in', self.env.companies.ids),
            '|',
            ('resource_calendar_id', '=', False),
            ('resource_calendar_id', '=', self.resource_calendar_id.id),
        ]

        if self.job_id:
            domain += [
                ('job_ids', 'in', [False] + self.job_id.ids),
            ]
        if self.department_id:
            domain += [
                '|',
                ('department_ids', '=', False),
                ('department_ids', 'parent_of', self.department_id.id),
            ]
        else:
            domain += [('department_ids', '=', False)]

        return self.env['hr.leave.mandatory.day'].search(domain)

    @api.model
    def _get_contextual_employee(self):
        ctx = self.env.context
        if self.env.context.get('employee_id') is not None:
            return self.browse(ctx.get('employee_id'))
        if self.env.context.get('default_employee_id') is not None:
            return self.browse(ctx.get('default_employee_id'))
        return self.env.user.employee_id

    def _get_consumed_leaves(self, leave_types, target_date=False, ignore_future=False):
        employees = self or self._get_contextual_employee()
        leaves_domain = [
            ('holiday_status_id', 'in', leave_types.ids),
            ('employee_id', 'in', employees.ids),
            ('state', 'in', ['confirm', 'validate1', 'validate']),
        ]
        if self.env.context.get('ignored_leave_ids'):
            leaves_domain.append(('id', 'not in', self.env.context.get('ignored_leave_ids')))

        if not target_date:
            target_date = fields.Date.today()
        if ignore_future:
            leaves_domain.append(('date_from', '<=', target_date))
        leaves = self.env['hr.leave'].search(leaves_domain)
        leaves_per_employee_type = defaultdict(lambda: defaultdict(lambda: self.env['hr.leave']))
        for leave in leaves:
            leaves_per_employee_type[leave.employee_id][leave.holiday_status_id] |= leave

        allocations = self.env['hr.leave.allocation'].with_context(active_test=False).search([
            ('employee_id', 'in', employees.ids),
            ('holiday_status_id', 'in', leave_types.ids),
            ('state', '=', 'validate'),
        ])
        allocations_per_employee_type = defaultdict(lambda: defaultdict(lambda: self.env['hr.leave.allocation']))
        for allocation in allocations:
            allocations_per_employee_type[allocation.employee_id][allocation.holiday_status_id] |= allocation

        # _get_consumed_leaves returns a tuple of two dictionnaries.
        # 1) The first is a dictionary to map the number of days/hours of leaves taken per allocation
        # The structure is the following:
        # - KEYS:
        # allocation_leaves_consumed
        #  |--employee_id
        #      |--holiday_status_id
        #          |--allocation
        #              |--virtual_leaves_taken
        #              |--leaves_taken
        #              |--virtual_remaining_leaves
        #              |--remaining_leaves
        #              |--max_leaves
        #              |--accrual_bonus
        # - VALUES:
        # Integer representing the number of (virtual) remaining leaves, (virtual) leaves taken or max leaves
        # for each allocation.
        # leaves_taken and remaining_leaves only take into account validated leaves, while the "virtual" equivalent are
        # also based on leaves in "confirm" or "validate1" state.
        # Accrual bonus gives the amount of additional leaves that will have been granted at the given
        # target_date in comparison to today.
        # The unit is in hour or days depending on the leave type request unit
        # 2) The second is a dictionary mapping the remaining days per employee and per leave type that are either
        # not taken into account by the allocations, mainly because accruals don't take future leaves into account.
        # This is used to warn the user if the leaves they takes bring them above their available limit.
        # - KEYS:
        # allocation_leaves_consumed
        #  |--employee_id
        #      |--holiday_status_id
        #          |--to_recheck_leaves
        #          |--excess_days
        #          |--exceeding_duration
        # - VALUES:
        # "to_recheck_leaves" stores every leave that is not yet taken into account by the "allocation_leaves_consumed" dictionary.
        # "excess_days" represents the excess amount that somehow isn't taken into account by the first dictionary.
        # "exceeding_duration" sum up the to_recheck_leaves duration and compares it to the maximum allocated for that time period.
        allocations_leaves_consumed = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: 0))))

        to_recheck_leaves_per_leave_type = defaultdict(lambda:
            defaultdict(lambda: {
                'excess_days': defaultdict(lambda: {
                    'amount': 0,
                    'is_virtual': True,
                }),
                'exceeding_duration': 0,
                'to_recheck_leaves': self.env['hr.leave']
            })
        )
        for allocation in allocations:
            allocation_data = allocations_leaves_consumed[allocation.employee_id][allocation.holiday_status_id][allocation]
            future_leaves = 0
            if allocation.allocation_type == 'accrual':
                future_leaves = allocation._get_future_leaves_on(target_date)
            max_leaves = allocation.number_of_hours_display\
                if allocation.holiday_status_id.request_unit in ['hour']\
                else allocation.number_of_days_display
            max_leaves += future_leaves
            allocation_data.update({
                'max_leaves': max_leaves,
                'accrual_bonus': future_leaves,
                'virtual_remaining_leaves': max_leaves,
                'remaining_leaves': max_leaves,
                'leaves_taken': 0,
                'virtual_leaves_taken': 0,
            })

        for employee in employees:
            for leave_type in leave_types:
                allocations_with_date_to = self.env['hr.leave.allocation']
                allocations_without_date_to = self.env['hr.leave.allocation']
                for leave_allocation in allocations_per_employee_type[employee][leave_type]:
                    if leave_allocation.date_to:
                        allocations_with_date_to |= leave_allocation
                    else:
                        allocations_without_date_to |= leave_allocation
                sorted_leave_allocations = allocations_with_date_to.sorted(key='date_to') + allocations_without_date_to

                if leave_type.request_unit in ['day', 'half_day']:
                    leave_duration_field = 'number_of_days'
                    leave_unit = 'days'
                else:
                    leave_duration_field = 'number_of_hours'
                    leave_unit = 'hours'

                leave_type_data = allocations_leaves_consumed[employee][leave_type]
                for leave in leaves_per_employee_type[employee][leave_type].sorted('date_from'):
                    leave_duration = leave[leave_duration_field]
                    skip_excess = False

                    if sorted_leave_allocations.filtered(lambda alloc: alloc.allocation_type == 'accrual') and leave.date_from.date() > target_date:
                        to_recheck_leaves_per_leave_type[employee][leave_type]['to_recheck_leaves'] |= leave
                        skip_excess = True
                        continue

                    if leave_type.requires_allocation:
                        for allocation in sorted_leave_allocations:
                            # We don't want to include future leaves linked to accruals into the total count of available leaves.
                            # However, we'll need to check if those leaves take more than what will be accrued in total of those days
                            # to give a warning if the total exceeds what will be accrued.
                            if allocation.date_from > leave.date_to.date() or (allocation.date_to and allocation.date_to < leave.date_from.date()):
                                continue
                            interval_start = max(
                                leave.date_from,
                                datetime.combine(allocation.date_from, time.min)
                            )
                            interval_end = min(
                                leave.date_to,
                                datetime.combine(allocation.date_to, time.max)
                                if allocation.date_to else leave.date_to
                            )
                            duration = leave[leave_duration_field]
                            if leave.date_from != interval_start or leave.date_to != interval_end:
                                duration_info = employee._get_calendar_attendances(interval_start.replace(tzinfo=pytz.UTC), interval_end.replace(tzinfo=pytz.UTC))
                                duration = duration_info['hours' if leave_unit == 'hours' else 'days']
                            max_allowed_duration = min(
                                duration,
                                leave_type_data[allocation]['virtual_remaining_leaves']
                            )

                            if not max_allowed_duration:
                                continue

                            allocated_time = min(max_allowed_duration, leave_duration)
                            leave_type_data[allocation]['virtual_leaves_taken'] += allocated_time
                            leave_type_data[allocation]['virtual_remaining_leaves'] -= allocated_time
                            if leave.state == 'validate':
                                leave_type_data[allocation]['leaves_taken'] += allocated_time
                                leave_type_data[allocation]['remaining_leaves'] -= allocated_time

                            leave_duration -= allocated_time
                            if not leave_duration:
                                break
                        if round(leave_duration, 2) > 0 and not skip_excess:
                            to_recheck_leaves_per_leave_type[employee][leave_type]['excess_days'][leave.date_to.date()] = {
                                'amount': leave_duration,
                                'is_virtual': leave.state != 'validate',
                                'leave_id': leave.id,
                            }
                    else:
                        if leave_unit == 'hours':
                            allocated_time = leave.number_of_hours
                        else:
                            allocated_time = leave.number_of_days
                        leave_type_data[False]['virtual_leaves_taken'] += allocated_time
                        leave_type_data[False]['virtual_remaining_leaves'] = 0
                        leave_type_data[False]['remaining_leaves'] = 0
                        if leave.state == 'validate':
                            leave_type_data[False]['leaves_taken'] += allocated_time
        for employee in to_recheck_leaves_per_leave_type:
            for leave_type in to_recheck_leaves_per_leave_type[employee]:
                content = to_recheck_leaves_per_leave_type[employee][leave_type]
                consumed_content = allocations_leaves_consumed[employee][leave_type]
                if content['to_recheck_leaves']:
                    date_to_simulate = max(content['to_recheck_leaves'].mapped('date_from')).date()
                    latest_accrual_bonus = 0
                    date_accrual_bonus = 0
                    virtual_remaining = 0
                    additional_leaves_duration = 0
                    for allocation in consumed_content:
                        latest_accrual_bonus += allocation and allocation._get_future_leaves_on(date_to_simulate)
                        date_accrual_bonus += consumed_content[allocation]['accrual_bonus']
                        virtual_remaining += consumed_content[allocation]['virtual_remaining_leaves']
                    for leave in content['to_recheck_leaves']:
                        additional_leaves_duration += leave.number_of_hours if leave_type.request_unit == 'hour' else leave.number_of_days
                    latest_remaining = virtual_remaining - date_accrual_bonus + latest_accrual_bonus
                    content['exceeding_duration'] = round(min(0, latest_remaining - additional_leaves_duration), 2)

        return (allocations_leaves_consumed, to_recheck_leaves_per_leave_type)

    def _get_hours_per_day(self, date_from):
        ''' Return 24H to handle the case of Fully Flexible (ones without a working calendar)'''
        if not self:
            return 0
        calendars = self._get_calendars(date_from)
        return calendars[self.id].hours_per_day if calendars[self.id] else 24

    def _get_store_avatar_card_fields(self, target):
        return [*super()._get_store_avatar_card_fields(target), "leave_date_to"]
