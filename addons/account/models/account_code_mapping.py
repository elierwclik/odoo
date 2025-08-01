from odoo import fields, models, api
from odoo.fields import Domain
from odoo.tools import Query

COMPANY_OFFSET = 10000


class AccountCodeMapping(models.Model):
    # This model is used purely for UI, to display the account codes for each company.
    # It is not stored in DB. Instead, records are only populated in cache by the
    # `_search` override when accessing the One2many on `account.account`.

    _name = 'account.code.mapping'
    _description = "Mapping of account codes per company"
    _auto = False
    _table_query = '0'

    account_id = fields.Many2one(
        comodel_name='account.account',
        string="Account",
        compute='_compute_account_id',
        # suppress warning about field not being searchable (due to being used in depends);
        # searching is actually implemented in the `_search` override.
        search=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string="Company",
        compute='_compute_company_id',
        readonly=False,  # TODO remove in master (kept in stable because of view change)
    )
    code = fields.Char(
        string="Code",
        compute='_compute_code',
        inverse='_inverse_code',
    )

    @api.model_create_multi
    def create(self, vals_list):
        mappings = self.browse([
            vals['account_id'] * COMPANY_OFFSET + vals['company_id']
            for vals in vals_list
        ])
        for mapping, vals in zip(mappings, vals_list):
            mapping.code = vals['code']
        return mappings

    def _search(self, domain, offset=0, limit=None, order=None, **kw) -> Query:
        account_ids = []

        def get_accounts(condition):
            if not account_ids and condition.field_expr == 'account_id' and condition.operator == 'in':
                account_ids.extend(condition.value)
                return Domain(bool(condition.value))
            return condition

        remaining_domain = Domain(domain).map_conditions(get_accounts)
        if not account_ids:
            raise NotImplementedError
        return self.browse([
            account_id * COMPANY_OFFSET + company.id
            for account_id in account_ids
            for company in self.env.user.with_context(active_test=True).company_ids.sorted(lambda c: (c.sequence, c.name))
        ]).filtered_domain(remaining_domain)._as_query()

    def _compute_account_id(self):
        for record in self:
            record.account_id = record._origin.id // COMPANY_OFFSET

    def _compute_company_id(self):
        for record in self:
            record.company_id = record._origin.id % COMPANY_OFFSET

    @api.depends('account_id.code')
    def _compute_code(self):
        for record in self:
            account = record.account_id.with_company(record.company_id._origin)
            record.code = account.code

    def _inverse_code(self):
        for record in self:
            record.account_id.with_company(record.company_id).write({'code': record.code})
