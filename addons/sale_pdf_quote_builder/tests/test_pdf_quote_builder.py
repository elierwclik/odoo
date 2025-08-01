# Part of Odoo. See LICENSE file for full copyright and licensing details.

import json
from base64 import b64encode
from functools import partial
from unittest.mock import patch

from werkzeug.datastructures import FileStorage

from odoo.exceptions import ValidationError
from odoo.fields import Command
from odoo.tests import Form, tagged
from odoo.tools.misc import file_open

from odoo.addons.sale_management.tests.common import SaleManagementCommon
from odoo.addons.sale_pdf_quote_builder.controllers.quotation_document import (
    QuotationDocumentController
)
from .files import forms_pdf, plain_pdf


@tagged('-at_install', 'post_install')
class TestPDFQuoteBuilder(SaleManagementCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.QuotationDocumentController = QuotationDocumentController()

        cls.sale_order.validity_date = '2020-11-04'
        cls.sale_order.partner_id.tz = 'Europe/Brussels'
        cls.env['product.document'].search([]).action_archive()
        cls.env['quotation.document'].search([]).action_archive()

        with file_open(forms_pdf, 'rb') as file:
            forms_pdf_data = b64encode(file.read())

        with file_open(plain_pdf, 'rb') as file:
            plain_pdf_data = b64encode(file.read())

        att_header, att_footer, att_prod_doc = cls.env['ir.attachment'].create([{
            'name': "Header",
            'datas': plain_pdf_data,
        }, {
            'name': "Footer",
            'datas': forms_pdf_data,
        }, {
            'name': "Product Document",
            'datas': forms_pdf_data,
        }])
        cls.header, cls.footer = cls.env['quotation.document'].create([{
            'name': "Header",
            'ir_attachment_id': att_header.id,
            'document_type': 'header',
        }, {
            'name': "Footer",
            'ir_attachment_id': att_footer.id,
            'document_type': 'footer',
        }])
        cls.product_document = cls.env['product.document'].create({
            'name': "Product Document",
            'ir_attachment_id': att_prod_doc.id,
            'attached_on_sale': 'inside',
            'res_model': 'product.product',
            'res_id': cls.product.id,
        })
        cls.internal_user = cls._create_new_internal_user(login='internal.user@test.odoo.com')
        cls.alt_company = cls.env['res.company'].create({'name': "Backup Company"})

    def _create_so_form(self, **values):
        """Default values limited to preexisting ones. No Command"""
        SaleOrder = self.env['sale.order'].with_context(default_partner_id=self.partner.id)
        so_form = Form(SaleOrder)
        for field_name, value in values.items():
            so_form[field_name] = value
        so_form.save()
        return so_form

    def test_compute_customizable_pdf_form_fields_when_no_file(self):
        self.env['quotation.document'].search([]).action_archive()
        self.env['product.document'].search([]).action_archive()
        self.assertEqual(self.sale_order.customizable_pdf_form_fields, False)

    def test_dynamic_fields_mapping_for_quotation_document(self):
        FormField = self.env['sale.pdf.form.field']
        new_form_field = partial(dict, document_type='quotation_document')
        new_form_fields = FormField.create([
            new_form_field(name="boolean_test", path='locked'),
            new_form_field(name="char_test", path='name'),
            new_form_field(name="date_test", path='validity_date'),
            new_form_field(name="datetime_test", path='commitment_date'),
            new_form_field(name="float_test", path='prepayment_percent'),
            new_form_field(name="integer_test", path='company_id.color'),
            new_form_field(name="selection_test", path='state'),
            new_form_field(name="monetary_test", path='amount_total'),

            new_form_field(name="one2many_test", path='order_line'),
            new_form_field(name="many2one_test", path='company_id'),
            new_form_field(name="many2many_test", path='company_id.parent_ids'),
        ])
        sol_1, sol_2 = self.sale_order.order_line
        form_field_expected_value_map = {
            new_form_fields[0]: "No",  # boolean
            new_form_fields[1]: self.sale_order.name,  # char
            new_form_fields[2]: "11/04/2020",  # date
            new_form_fields[3]: "",  # datetime missing
            new_form_fields[4]: "1.0",  # float
            new_form_fields[5]: "1",  # integer
            new_form_fields[6]: "Quotation",  # selection
            new_form_fields[7]: "$\xa0725.00",  # monetary

            new_form_fields[8]: f"{sol_1.display_name}, {sol_2.display_name}",  # one2many
            new_form_fields[9]: f"{self.sale_order.company_id.display_name}",  # many2one
            new_form_fields[10]: f"{self.sale_order.company_id.display_name}",  # many2many
        }
        for form_field, expected_value in form_field_expected_value_map.items():
            result = self.env['ir.actions.report']._get_value_from_path(
                form_field, self.sale_order
            )
            self.assertEqual(result, expected_value)

    def test_dynamic_fields_mapping_for_product_document(self):
        self.sale_order.commitment_date = '2121-12-21 12:21:12'
        sol_1, sol_2 = self.sale_order.order_line
        sol_1.update({
            'discount': 4.99,
            'tax_ids': [
                Command.create({'name': "test tax1"}),
                Command.create({'name': "test tax2"}),
            ],
        })
        new_form_field = partial(dict, document_type='product_document')
        new_form_fields = self.env['sale.pdf.form.field'].create([
            new_form_field(name="boolean_test", path='order_id.locked'),
            new_form_field(name="char_test", path='order_id.name'),
            new_form_field(name="date_test", path='order_id.validity_date'),
            new_form_field(name="datetime_test", path='order_id.commitment_date'),
            new_form_field(name="float_test", path='discount'),
            new_form_field(name="integer_test", path='sequence'),
            new_form_field(name="selection_test", path='order_id.state'),
            new_form_field(name="monetary_test", path='order_id.amount_total'),

            new_form_field(name="one2many_test", path='order_id.order_line'),
            new_form_field(name="many2one_test", path='order_id.company_id'),
            new_form_field(name="many2many_test", path='tax_ids'),
        ])
        expected = {
            'boolean_test': "No",
            'char_test': self.sale_order.name,
            'date_test': "11/04/2020",
            'datetime_test': "12/21/2121 01:21:12 PM",
            'float_test': "4.99",
            'integer_test': "10",
            'selection_test': "Quotation",
            'monetary_test': self.sale_order.currency_id.format(720.01),

            'one2many_test': f"{sol_1.display_name}, {sol_2.display_name}",
            'many2one_test': self.sale_order.company_id.display_name,
            'many2many_test': "test tax1, test tax2",
        }
        for form_field in new_form_fields:
            result = self.env['ir.actions.report']._get_value_from_path(
                form_field, self.sale_order, sol_1
            )
            self.assertEqual(' '.join(result.split()), ' '.join(expected[form_field.name].split()))

    def test_product_document_dialog_params_access(self):
        sale_order_internal_user = self.sale_order.copy({'user_id': self.internal_user.id})
        dialog_param = sale_order_internal_user.with_user(
            self.internal_user.id
        ).get_update_included_pdf_params()
        # should return all document data regardless of access
        self.assertEqual('Header', dialog_param['headers']['files'][0]['name'])
        self.assertEqual('Product > Test Product', dialog_param['lines'][0]['name'])

    def test_quotation_document_is_removed_on_template_change(self):
        so_tmpl = self.env['sale.order.template'].create({
            'name': "test1",
            'quotation_document_ids': [Command.link(self.header.id)],
        })
        so_tmpl_2 = self.env['sale.order.template'].create({'name': "test2"})

        self.sale_order.write({
            'sale_order_template_id': so_tmpl.id,
            'quotation_document_ids': [Command.link(self.header.id)],
        })

        self.assertEqual(self.sale_order.quotation_document_ids, self.header)

        so_form = Form(self.sale_order)
        so_form.sale_order_template_id = so_tmpl_2
        so_form.save()

        self.assertNotIn(self.header, self.sale_order.available_quotation_document_ids)
        self.assertEqual(len(self.sale_order.quotation_document_ids), 0)

    def test_non_pdf_attachment_inside_quote_form_save(self):
        non_pdf_att = self.env['ir.attachment'].create({
            'name': 'Not a PDF',
            'datas': b64encode(b"hello"),
            'mimetype': 'text/plain',
        })

        product_document = self.product_document

        product_document.write({
            'ir_attachment_id': non_pdf_att.id,
        })
        with self.assertRaises(ValidationError):
            with Form(product_document) as doc_form:
                doc_form.attached_on_sale = 'inside'

    def test_onchange_product_removes_previously_selected_documents(self):
        """ Check that changing a line that has a selected document unselect said document. """

        available_doc = self.sale_order.order_line[0].available_product_document_ids
        self.sale_order.order_line[0].product_document_ids = available_doc  # select the document

        self.assertTrue(available_doc, msg="Default order line should have an available document.")
        msg = "The available document should have been selected."
        self.assertEqual(
            self.sale_order.order_line[0].product_document_ids, available_doc, msg=msg
        )

        so_form = Form(self.sale_order)
        with so_form.order_line.edit(0) as line:
            line.product_id = self._create_product()
        so_form.save()

        msg = "There shouldn't be any available product documents."
        self.assertFalse(self.sale_order.order_line[0].available_product_document_ids, msg=msg)
        msg = "There shouldn't be any selected product documents left."
        self.assertFalse(self.sale_order.order_line[0].product_document_ids, msg=msg)

    def test_quotation_document_upload_no_template(self):
        """Check that uploading quotation documents get assigned the active company."""
        if 'website' not in self.env:
            self.skipTest("Module `website` not found")
        else:
            from odoo.addons.http_routing.tests.common import MockRequest  # noqa: PLC0415

        # Upload document without Sale Order Template
        with (
            MockRequest(self.env) as request,
            file_open(plain_pdf, 'rb') as file,
            patch.object(request.httprequest.files, 'getlist', lambda _key: [FileStorage(file)]),
        ):
            res = self.QuotationDocumentController.upload_document(
                ufile=FileStorage(file),
                allowed_company_ids=json.dumps([self.alt_company.id, self.env.company.id]),
            )
            self.assertEqual(res.status_code, 200, "Upload should be successful")

        quotation_document = self.env['quotation.document'].search([
            ('name', '=', plain_pdf),
        ], limit=1)
        self.assertTrue(quotation_document, "A new quotation document should be created")
        self.assertEqual(
            quotation_document.company_id,
            self.alt_company,
            "Quotation document company should be the currently active company",
        )

    def test_quotation_document_upload_for_template(self):
        """Check that uploading quotation documents get assigned the the quotation company."""
        if 'website' not in self.env:
            self.skipTest("Module `website` not found")
        else:
            from odoo.addons.http_routing.tests.common import MockRequest  # noqa: PLC0415

        # Upload a document for a Sale Order Template without company id
        self.empty_order_template.company_id = False
        with (
            MockRequest(self.env) as request,
            file_open(forms_pdf, 'rb') as file,
            patch.object(request.httprequest.files, 'getlist', lambda _key: [FileStorage(file)]),
        ):
            res = self.QuotationDocumentController.upload_document(
                ufile=FileStorage(file),
                sale_order_template_id=str(self.empty_order_template.id),
                allowed_company_ids=json.dumps([self.alt_company.id, self.env.company.id]),
            )
            self.assertEqual(res.status_code, 200, "Upload should be successful")

        quotation_document = self.env['quotation.document'].search([
            ('name', '=', forms_pdf),
        ], limit=1)
        self.assertTrue(quotation_document, "A new quotation document should be created")
        self.assertFalse(
            quotation_document.company_id,
            "Quotation document shouldn't have a company id",
        )

    def _test_custom_content_kanban_like(self):
        # TODO VCR finish tour and uncomment
        self.start_tour(
            f'/odoo/sales/{self.sale_order.id}',
            'custom_content_kanban_like_tour',
            login='admin',
        )
        # Assert documents are selected

    def test_quotation_document_is_added_iff_default(self):
        self.assertFalse(self._create_so().quotation_document_ids)

        self.header.add_by_default = True

        self.assertEqual(self._create_so().quotation_document_ids, self.header)

    def test_default_quotation_document_is_added_iff_available(self):
        # header is default but only for quote_tmpl
        so_tmpl = self.env['sale.order.template'].create({'name': 'Awesome Template'})
        self.header.write({
            'add_by_default': True,
            'quotation_template_ids': [Command.link(so_tmpl.id)],
        })

        sof_without_tmpl = self._create_so_form()
        sof_with_tmpl = self._create_so_form(sale_order_template_id=so_tmpl)

        self.assertFalse(sof_without_tmpl.record.quotation_document_ids)
        self.assertEqual(sof_with_tmpl.record.quotation_document_ids, self.header)

    def test_quotation_document_is_removed_if_unavailable(self):
        so_tmpl = self.env['sale.order.template'].create({'name': "Awesome Template"})
        self.header.write({
            'add_by_default': True,
            'quotation_template_ids': [Command.link(so_tmpl.id)],
        })
        sof = self._create_so_form(sale_order_template_id=so_tmpl)
        self.assertEqual(sof.record.quotation_document_ids, self.header)

        sof.sale_order_template_id = self.env['sale.order.template']
        sof.save()

        self.assertFalse(sof.record.quotation_document_ids)
