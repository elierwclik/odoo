from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    hr_expense_alias_prefix = fields.Char(
        'Default Alias Name for Expenses',
        compute='_compute_hr_expense_alias_prefix',
        store=True,
        readonly=False)
    hr_expense_alias_domain_id = fields.Many2one(
        comodel_name='mail.alias.domain',
        compute='_compute_hr_expense_alias_domain_id',
        inverse='_inverse_hr_expense_alias_domain_id',
        readonly=False)
    hr_expense_use_mailgateway = fields.Boolean(string='Let your employees record expenses by email',
                                             config_parameter='hr_expense.use_mailgateway')
    module_hr_payroll_expense = fields.Boolean(string='Reimburse Expenses in Payslip')
    module_hr_expense_extract = fields.Boolean(string='Send bills to OCR to generate expenses')

    # This module is not installable yet, but will be in the following weeks
    module_hr_expense_stripe = fields.Boolean(string='Link your stripe issuing account to manage company credit cards for your employees through Odoo')

    expense_journal_id = fields.Many2one('account.journal', related='company_id.expense_journal_id', readonly=False, check_company=True, domain="[('type', '=', 'purchase')]")
    company_expense_allowed_payment_method_line_ids = fields.Many2many(
        comodel_name='account.payment.method.line',
        check_company=True,
        related='company_id.company_expense_allowed_payment_method_line_ids',
        readonly=False,
    )

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        expense_alias = self.env.ref('hr_expense.mail_alias_expense', raise_if_not_found=False)
        res.update(
            hr_expense_alias_prefix=expense_alias.alias_name if expense_alias else False,
            hr_expense_alias_domain_id=expense_alias.alias_domain_id if expense_alias else False,
        )
        return res

    def set_values(self):
        super().set_values()
        expense_alias = self.env.ref('hr_expense.mail_alias_expense', raise_if_not_found=False)
        if not expense_alias and self.hr_expense_alias_prefix:
            # create data again
            alias = self.env['mail.alias'].sudo().create({
                'alias_contact': 'employees',
                'alias_domain_id': self.env.company.alias_domain_id.id,
                'alias_model_id': self.env['ir.model']._get_id('hr.expense'),
                'alias_name': self.hr_expense_alias_prefix,
            })
            self.env['ir.model.data'].sudo().create({
                'name': 'mail_alias_expense',
                'module': 'hr_expense',
                'model': 'mail.alias',
                'noupdate': True,
                'res_id': alias.id,
            })
        elif expense_alias and expense_alias.alias_name != self.hr_expense_alias_prefix:
            expense_alias.alias_name = self.hr_expense_alias_prefix

    @api.depends('hr_expense_use_mailgateway')
    def _compute_hr_expense_alias_prefix(self):
        self.filtered(lambda w: not w.hr_expense_use_mailgateway).hr_expense_alias_prefix = False

    @api.depends('hr_expense_use_mailgateway')
    def _compute_hr_expense_alias_domain_id(self):
        self.filtered(lambda w: not w.hr_expense_use_mailgateway).hr_expense_alias_domain_id = False

    def _inverse_hr_expense_alias_domain_id(self):
        expense_alias = self.env.ref('hr_expense.mail_alias_expense', raise_if_not_found=False)
        for record in self:
            if expense_alias and expense_alias.alias_domain_id != record.hr_expense_alias_domain_id:
                expense_alias.alias_domain_id = record.hr_expense_alias_domain_id
