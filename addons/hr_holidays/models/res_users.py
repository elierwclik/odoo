# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, Command, _
from odoo.tools import format_date


class ResUsers(models.Model):
    _inherit = "res.users"

    leave_manager_id = fields.Many2one(related='employee_id.leave_manager_id')
    show_leaves = fields.Boolean(related='employee_id.show_leaves')
    allocation_count = fields.Float(related='employee_id.allocation_count')
    leave_date_to = fields.Date(related='employee_id.leave_date_to')
    current_leave_state = fields.Selection(related='employee_id.current_leave_state')
    is_absent = fields.Boolean(related='employee_id.is_absent')
    allocation_remaining_display = fields.Char(related='employee_id.allocation_remaining_display')
    allocation_display = fields.Char(related='employee_id.allocation_display')
    hr_icon_display = fields.Selection(related='employee_id.hr_icon_display')

    @property
    def SELF_READABLE_FIELDS(self):
        return super().SELF_READABLE_FIELDS + [
            'leave_manager_id',
            'show_leaves',
            'allocation_count',
            'leave_date_to',
            'current_leave_state',
            'is_absent',
            'allocation_remaining_display',
            'allocation_display',
            'hr_icon_display',
        ]

    @property
    def SELF_WRITEABLE_FIELDS(self):
        return super().SELF_WRITEABLE_FIELDS + [
            'leave_manager_id',
        ]

    def _compute_im_status(self):
        super()._compute_im_status()
        on_leave_user_ids = self._get_on_leave_ids()
        for user in self:
            if user.id in on_leave_user_ids:
                if user.im_status == 'online':
                    user.im_status = 'leave_online'
                elif user.im_status == 'away':
                    user.im_status = 'leave_away'
                elif user.im_status == 'busy':
                    user.im_status = 'leave_busy'
                elif user.im_status == 'offline':
                    user.im_status = 'leave_offline'

    @api.model
    def _get_on_leave_ids(self, partner=False):
        now = fields.Datetime.now()
        field = 'partner_id' if partner else 'id'
        self.flush_model(['active'])
        self.env['hr.leave'].flush_model(['user_id', 'state', 'date_from', 'date_to'])
        self.env.cr.execute('''SELECT res_users.%s FROM res_users
                            JOIN hr_leave ON hr_leave.user_id = res_users.id
                            AND hr_leave.state = 'validate'
                            AND res_users.active = 't'
                            AND hr_leave.date_from <= %%s AND hr_leave.date_to >= %%s''' % field, (now, now))
        return [r[0] for r in self.env.cr.fetchall()]

    def _clean_leave_responsible_users(self):
        # self = old bunch of leave responsibles
        # This method compares the current leave managers
        # and remove the access rights to those who don't
        # need them anymore
        approver_group = 'hr_holidays.group_hr_holidays_responsible'
        if not any(u.has_group(approver_group) for u in self):
            return

        res = self.env['hr.employee']._read_group(
            [('leave_manager_id', 'in', self.ids)],
            ['leave_manager_id'])
        responsibles_to_remove_ids = set(self.ids) - {leave_manager.id for [leave_manager] in res}
        if responsibles_to_remove_ids:
            self.browse(responsibles_to_remove_ids).write({
                'group_ids': [Command.unlink(self.env.ref(approver_group).id)],
            })

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        users.sudo()._clean_leave_responsible_users()
        return users

    @api.depends('leave_date_to')
    @api.depends_context('formatted_display_name')
    def _compute_display_name(self):
        super()._compute_display_name()
        for user in self:
            if user.env.context.get("formatted_display_name") and user.leave_date_to:
                name = "%s \t ✈ --%s %s--" % (user.name, _("Back on"), format_date(self.env, user.leave_date_to, self.env.user.lang, "medium"))
                user.display_name = name.strip()
