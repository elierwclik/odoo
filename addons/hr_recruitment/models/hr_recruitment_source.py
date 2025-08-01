# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class HrRecruitmentSource(models.Model):
    _name = 'hr.recruitment.source'
    _description = "Source of Applicants"
    _inherit = ['utm.source.mixin']

    email = fields.Char(related='alias_id.display_name', string="Email", readonly=True)
    has_domain = fields.Char(compute='_compute_has_domain')
    job_id = fields.Many2one('hr.job', "Job", index=True, ondelete='cascade')
    alias_id = fields.Many2one('mail.alias', "Alias ID", ondelete='restrict')
    medium_id = fields.Many2one('utm.medium', default=lambda self: self.env['utm.medium']._fetch_or_create_utm_medium('website'))

    def _compute_has_domain(self):
        for source in self:
            if source.alias_id:
                source.has_domain = bool(source.alias_id.alias_domain_id)
            else:
                source.has_domain = bool(source.job_id.company_id.alias_domain_id
                                         or self.env.company.alias_domain_id)

    def create_alias(self):
        campaign = self.env.ref('hr_recruitment.utm_campaign_job')
        medium = self.env['utm.medium']._fetch_or_create_utm_medium('email')
        for source in self.filtered(lambda s: not s.alias_id):
            vals = {
                'alias_defaults': {
                    'job_id': source.job_id.id,
                    'campaign_id': campaign.id,
                    'medium_id': medium.id,
                    'source_id': source.source_id.id,
                },
                'alias_domain_id': source.job_id.company_id.alias_domain_id.id or self.env.company.alias_domain_id.id,
                'alias_model_id': self.env['ir.model']._get_id('hr.applicant'),
                'alias_name': f"{source.job_id.alias_name or source.job_id.name}+{source.name}",
                'alias_parent_thread_id': source.job_id.id,
                'alias_parent_model_id': self.env['ir.model']._get_id('hr.job'),
            }

            # check that you can create source before to call mail.alias in sudo with known/controlled vals
            source.check_access('create')
            source.alias_id = self.env['mail.alias'].sudo().create(vals)

    def create_and_get_alias(self):
        self.ensure_one()
        self.create_alias()
        return self.email

    def unlink(self):
        """ Cascade delete aliases to avoid useless / badly configured aliases. """
        aliases = self.alias_id
        res = super().unlink()
        aliases.sudo().unlink()
        return res
