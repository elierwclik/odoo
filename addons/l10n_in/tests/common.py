from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo import Command


class L10nInTestInvoicingCommon(AccountTestInvoicingCommon):
    @classmethod
    @AccountTestInvoicingCommon.setup_country('in')
    def setUpClass(cls):
        super().setUpClass()

        cls.maxDiff = None

        # === Countries === #
        cls.country_in = cls.env.ref('base.in')
        cls.country_us = cls.env.ref('base.us')

        # === States === #
        cls.state_in_gj = cls.env.ref('base.state_in_gj')
        cls.state_in_mh = cls.env.ref('base.state_in_mh')
        cls.state_in_hp = cls.env.ref('base.state_in_hp')

        # === Companies === #
        cls.default_company = cls.company_data['company']
        cls.default_company.write({
            'name': "Default Company",
            'state_id': cls.state_in_gj.id,
            'vat': "24AAGCC7144L6ZE",
            'street': "Khodiyar Chowk",
            'street2': "Sala Number 3",
            'city': "Amreli",
            'zip': "365220",
            'l10n_in_is_gst_registered': True,
            'l10n_in_tds_feature': True,
            'l10n_in_tcs_feature': True,
        })

        cls.outside_in_company = cls._create_company(
            name='Outside India Company',
            country_id=cls.country_us.id,
        )

        cls.user.write({
            'company_ids': [cls.default_company.id, cls.outside_in_company.id],
            'company_id': cls.default_company.id,
        })

        # === Partners === #
        cls.partner_a.write({
            'name': "Partner Intra State",
            'vat': '24ABCPM8965E1ZE',
            'state_id': cls.default_company.state_id.id,
            'country_id': cls.country_in.id,
            'street': "Karansinhji Rd",
            'street2': "Karanpara",
            'city': "Rajkot",
            'zip': "360001",
        })

        cls.partner_b.write({
            'vat': '27DJMPM8965E1ZE',
            'state_id': cls.state_in_mh.id,
            'country_id': cls.country_in.id,
            'street': "Sangeet Samrat Naushad Ali Rd",
            'city': "Mumbai",
            'zip': "400052",
        })

        cls.partner_foreign = cls.env['res.partner'].create({
            'name': "Foreign Partner",
            'country_id': cls.country_us.id,
            'state_id': cls.env.ref("base.state_us_1").id,
            'street': "351 Horner Chapel Rd",
            'city': "Peebles",
            'zip': "45660",
        })

        cls.partner_foreign_no_state = cls.env['res.partner'].create({
            'name': "Foreign Partner Without State",
            'country_id': cls.country_us.id,
            # No state_id defined
        })

        # === Taxes === #
        cls.sgst_sale_5 = cls.env["account.chart.template"].ref('sgst_sale_5')
        cls.sgst_purchase_5 = cls.env["account.chart.template"].ref('sgst_purchase_5')
        cls.igst_sale_5 = cls.env["account.chart.template"].ref('igst_sale_5')
        cls.igst_sale_18 = cls.env["account.chart.template"].ref('igst_sale_18')
        cls.sgst_sale_18 = cls.env["account.chart.template"].ref('sgst_sale_18')
        cls.gst_with_cess = (
            cls.env['account.chart.template'].ref("sgst_sale_12")
            + cls.env['account.chart.template'].ref("cess_5_plus_1591_sale")
        )

        # === Products === #
        cls.product_a.write({
            "l10n_in_hsn_code": "111111",
            'taxes_id': cls.sgst_sale_5,
            'supplier_taxes_id': cls.sgst_purchase_5,
        })

        cls.product_b.write({
            "l10n_in_hsn_code": "111111",
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'lst_price': 1000.0,
            'standard_price': 1000.0,
            'taxes_id': cls.sgst_sale_5.ids,
            'supplier_taxes_id': cls.sgst_purchase_5.ids,
        })
        cls.product_with_cess = cls.env["product.product"].create({
            "name": "product_with_cess",
            "uom_id": cls.env.ref("uom.product_uom_unit").id,
            "lst_price": 1000.0,
            "standard_price": 800.0,
            "property_account_income_id": cls.company_data["default_account_revenue"].id,
            "property_account_expense_id": cls.company_data["default_account_expense"].id,
            "taxes_id": [Command.set(cls.gst_with_cess.ids)],
            "supplier_taxes_id": [Command.set(cls.sgst_purchase_5.ids)],
            "l10n_in_hsn_code": "333333",
        })

        # === Fiscal Positions === #
        cls.fp_in_intra_state = cls.env["account.chart.template"].ref('fiscal_position_in_intra_state')
        cls.fp_in_inter_state = cls.env["account.chart.template"].ref('fiscal_position_in_inter_state')
        cls.fp_in_export = cls.env["account.chart.template"].ref('fiscal_position_in_export_sez_in')

        # === Invoices === #
        cls.invoice_a = cls.init_invoice(
            move_type='out_invoice',
            partner=cls.partner_a,
            amounts=[110, 500],
            taxes=cls.igst_sale_18,
        )

        cls.invoice_b = cls.init_invoice(
            move_type='out_invoice',
            partner=cls.partner_b,
            amounts=[250, 600],
            taxes=cls.igst_sale_18,
        )

        cls.invoice_c = cls.init_invoice(
            move_type='out_invoice',
            partner=cls.partner_foreign,
            amounts=[300, 740],
            taxes=cls.igst_sale_18,
        )

        cls.invoice_d = cls.init_invoice(
            move_type='out_invoice',
            partner=cls.partner_foreign_no_state,
            amounts=[100, 200],
            taxes=cls.igst_sale_18,
        )
