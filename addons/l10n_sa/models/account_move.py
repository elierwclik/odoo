# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64

from odoo import api, fields, models
from odoo.tools import float_repr, format_datetime

ADJUSTMENT_REASONS = [
    ("BR-KSA-17-reason-1", "Cancellation or suspension of the supplies after its occurrence either wholly or partially"),
    ("BR-KSA-17-reason-2", "In case of essential change or amendment in the supply, which leads to the change of the VAT due"),
    ("BR-KSA-17-reason-3", "Amendment of the supply value which is pre-agreed upon between the supplier and consumer"),
    ("BR-KSA-17-reason-4", "In case of goods or services refund"),
    ("BR-KSA-17-reason-5", "In case of change in Seller's or Buyer's information"),
]


class AccountMove(models.Model):
    _inherit = 'account.move'

    l10n_sa_qr_code_str = fields.Char(string='Zatka QR Code', compute='_compute_qr_code_str')
    l10n_sa_show_reason = fields.Boolean(compute="_compute_show_l10n_sa_reason")
    l10n_sa_reason = fields.Selection(string="ZATCA Reason", selection=ADJUSTMENT_REASONS, copy=False)
    l10n_sa_confirmation_datetime = fields.Datetime(string='Confirmation Date',
                                                    readonly=True,
                                                    copy=False,
                                                    help="""Date when the invoice is confirmed and posted.
                                                    In other words, it is the date on which the invoice is generated as final document (after securing all internal approvals).""")

    @api.depends('country_code', 'move_type')
    def _compute_show_delivery_date(self):
        # EXTENDS 'account'
        super()._compute_show_delivery_date()
        for move in self:
            if move.country_code == 'SA':
                move.show_delivery_date = move.is_sale_document()

    @api.depends('amount_total_signed', 'amount_tax_signed', 'l10n_sa_confirmation_datetime', 'company_id', 'company_id.vat')
    def _compute_qr_code_str(self):
        """ Generate the qr code for Saudi e-invoicing. Specs are available at the following link at page 23
        https://zatca.gov.sa/ar/E-Invoicing/SystemsDevelopers/Documents/20210528_ZATCA_Electronic_Invoice_Security_Features_Implementation_Standards_vShared.pdf
        """
        def get_qr_encoding(tag, field):
            company_name_byte_array = field.encode()
            company_name_tag_encoding = tag.to_bytes(length=1, byteorder='big')
            company_name_length_encoding = len(company_name_byte_array).to_bytes(length=1, byteorder='big')
            return company_name_tag_encoding + company_name_length_encoding + company_name_byte_array

        for record in self:
            qr_code_str = ''
            if record.l10n_sa_confirmation_datetime and record.company_id.vat:
                seller_name_enc = get_qr_encoding(1, record.company_id.display_name)
                company_vat_enc = get_qr_encoding(2, record.company_id.vat)
                time_sa = fields.Datetime.context_timestamp(self.with_context(tz='Asia/Riyadh'), record.l10n_sa_confirmation_datetime)
                timestamp_enc = get_qr_encoding(3, time_sa.isoformat())
                totals = record._get_l10n_sa_totals()
                invoice_total_enc = get_qr_encoding(4, float_repr(abs(totals['total_amount']), 2))
                total_vat_enc = get_qr_encoding(5, float_repr(abs(totals['total_tax']), 2))

                str_to_encode = seller_name_enc + company_vat_enc + timestamp_enc + invoice_total_enc + total_vat_enc
                qr_code_str = base64.b64encode(str_to_encode).decode()
            record.l10n_sa_qr_code_str = qr_code_str

    def _post(self, soft=True):
        res = super()._post(soft)
        for move in self:
            if move.country_code == 'SA' and move.is_sale_document():
                vals = {}
                if not move.l10n_sa_confirmation_datetime:
                    vals['l10n_sa_confirmation_datetime'] = fields.Datetime.now()
                if not move.delivery_date:
                    vals['delivery_date'] = move.invoice_date
                move.write(vals)
        return res

    def get_l10n_sa_confirmation_datetime_sa_tz(self):
        self.ensure_one()
        return format_datetime(self.env, self.l10n_sa_confirmation_datetime, tz='Asia/Riyadh', dt_format='Y-MM-dd\nHH:mm:ss')

    def _l10n_sa_reset_confirmation_datetime(self):
        for move in self.filtered(lambda m: m.country_code == 'SA'):
            move.l10n_sa_confirmation_datetime = False

    def button_draft(self):
        self._l10n_sa_reset_confirmation_datetime()
        super().button_draft()

    def _l10n_sa_get_adjustment_reason(self):
        self.ensure_one()
        readable_zatca_reason = dict(self._fields['l10n_sa_reason'].selection).get(self.l10n_sa_reason)
        return readable_zatca_reason if self.l10n_sa_show_reason else self.ref

    def _compute_show_l10n_sa_reason(self):
        for record in self:
            record.l10n_sa_show_reason = record.country_code == 'SA' and (record.move_type == 'out_refund' or (record.move_type == 'out_invoice' and record.debit_origin_id))

    def _get_l10n_sa_totals(self):
        self.ensure_one()
        return {
            'total_amount': self.amount_total_signed,
            'total_tax': self.amount_tax_signed,
        }
