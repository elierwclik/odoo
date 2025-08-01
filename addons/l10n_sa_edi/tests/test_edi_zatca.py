# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import datetime
from freezegun import freeze_time
import logging
from pytz import timezone

from odoo import Command
from odoo.tests import tagged
from odoo.tools import misc

from .common import TestSaEdiCommon

_logger = logging.getLogger(__name__)


@tagged('post_install_l10n', '-at_install', 'post_install')
class TestEdiZatca(TestSaEdiCommon):

    def testInvoiceStandard(self):

        with freeze_time(datetime(year=2022, month=9, day=5, hour=8, minute=20, second=2, tzinfo=timezone('Etc/GMT-3'))):
            standard_invoice = misc.file_open('l10n_sa_edi/tests/compliance/standard/invoice.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(standard_invoice)
            expected_tree = self.with_applied_xpath(expected_tree, self.invoice_applied_xpath)

            self.partner_us.vat = 'US12345677'
            move = self._create_invoice(name='INV/2022/00014', date='2022-09-05', date_due='2022-09-22', partner_id=self.partner_us,
                                        product_id=self.product_a, price=320.0)
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testInvoiceWithDownpayment(self):

        if 'sale' not in self.env["ir.module.module"]._installed():
            self.skipTest("Sale module is not installed")

        def test_generated_file(move, test_file, xpath_to_apply):
            move.with_context(skip_readonly_check=True).write({
                'invoice_date': '2022-09-05',
                'invoice_date_due': '2022-09-22',
                'state': 'posted',
                'l10n_sa_confirmation_datetime': datetime.now(),
            })
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            expected_file = misc.file_open(f'l10n_sa_edi/tests/test_files/{test_file}.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(expected_file)
            expected_tree = self.with_applied_xpath(expected_tree, xpath_to_apply)

            self.assertXmlTreeEqual(current_tree, expected_tree)

        retention_tax = self.env['account.tax'].create({
            'l10n_sa_is_retention': True,
            'name': 'Retention Tax',
            'amount_type': 'percent',
            'amount': -5.0,
        })

        with freeze_time(datetime(year=2022, month=9, day=5, hour=8, minute=20, second=2, tzinfo=timezone('Etc/GMT-3'))):
            self.partner_us.vat = 'US12345677'

            pricelist = self.env['product.pricelist'].create({'name': 'SAR', 'currency_id': self.env.ref('base.SAR').id})
            sale_order = self.env['sale.order'].sudo().create({
                'partner_id': self.partner_us.id,
                'pricelist_id': pricelist.id,
                'order_line': [
                    Command.create({
                        'product_id': self.product_a.id,
                        'price_unit': 1000,
                        'product_uom_qty': 1,
                        'tax_ids': [Command.set(self.tax_15.ids)],
                    })
                ]
            }).sudo(False)
            sale_order.action_confirm()

            context = {
                'active_model': 'sale.order',
                'active_ids': [sale_order.id],
                'active_id': sale_order.id,
                'default_journal_id': self.company_data['default_journal_sale'].id,
            }
            downpayment = self.env['sale.advance.payment.inv'].with_context(context).sudo().create({
                'advance_payment_method': 'fixed',
                'fixed_amount': 115,
            })._create_invoices(sale_order).sudo(False)
            final = self.env['sale.advance.payment.inv'].with_context(context).sudo().create({})._create_invoices(sale_order).sudo(False)
            final.invoice_line_ids.filtered('is_downpayment').write({
                'name': 'Down payment',
            })
            final.invoice_line_ids.filtered(lambda l: l.product_id == self.product_a).tax_ids = [(Command.link(retention_tax.id))]

            for move, test_file in (
                (downpayment, "downpayment_invoice"),
                (final, "final_invoice")
            ):
                with self.subTest(move=move, test_file=test_file):
                    test_generated_file(move, test_file, self.invoice_applied_xpath)

            for move, test_file in (
                (downpayment, "downpayment_credit_note"),
                (final, "final_credit_note")
            ):
                with self.subTest(move=move, test_file=test_file):
                    wiz_context = {
                        'active_model': 'account.move',
                        'active_ids': [move.id],
                        'default_journal_id': move.journal_id.id,
                    }
                    refund_invoice_wiz = self.env['account.move.reversal'].with_context(wiz_context).create({
                        'l10n_sa_reason': 'BR-KSA-17-reason-4',
                        'date': '2022-09-05',
                    })
                    refund_invoice = self.env['account.move'].browse(refund_invoice_wiz.reverse_moves()['res_id'])
                    test_generated_file(refund_invoice, test_file, self.credit_note_applied_xpath)

    def testInvoiceWithGlobalDiscount(self):
        with freeze_time(datetime(year=2022, month=9, day=5, hour=8, minute=20, second=2, tzinfo=timezone('Etc/GMT-3'))):
            move = self._create_invoice(
                name='INV/2022/00014',
                date='2022-09-05',
                date_due='2022-09-22',
                partner_id=self.partner_us,
                invoice_line_ids=[
                    Command.create({
                        'product_id': self.product_a.id,
                        'price_unit': 320.0,
                        'quantity': 1.0,
                        'tax_ids': [Command.set(self.tax_15.ids)],
                    }),
                    Command.create({
                        'name': 'Global Discount',
                        'price_unit': -100.0,
                        'quantity': 1.0,
                        'tax_ids': [Command.set(self.tax_15.ids)],
                    })
                ]
            )
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            with misc.file_open('l10n_sa_edi/tests/test_files/invoice_global_discount.xml', 'rb') as f:
                expected_tree = self.get_xml_tree_from_string(f.read())

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testCreditNoteStandard(self):

        with freeze_time(datetime(year=2022, month=9, day=5, hour=9, minute=39, second=15, tzinfo=timezone('Etc/GMT-3'))):
            applied_xpath = self.credit_note_applied_xpath + \
            '''
                <xpath expr="(//*[local-name()='AdditionalDocumentReference']/*[local-name()='UUID'])[1]" position="replace">
                    <cbc:UUID xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">___ignore___</cbc:UUID>
                </xpath>
            '''

            standard_credit_note = misc.file_open('l10n_sa_edi/tests/compliance/standard/credit.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(standard_credit_note)
            expected_tree = self.with_applied_xpath(expected_tree, applied_xpath)

            credit_note = self._create_credit_note(name='INV/2022/00014', date='2022-09-05', date_due='2022-09-22',
                                                   partner_id=self.partner_us, product_id=self.product_a, price=320.0)
            credit_note._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(credit_note)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testDebitNoteStandard(self):
        with freeze_time(datetime(year=2022, month=9, day=5, hour=9, minute=45, second=27, tzinfo=timezone('Etc/GMT-3'))):
            applied_xpath = self.debit_note_applied_xpath + \
            '''
                <xpath expr="(//*[local-name()='AdditionalDocumentReference']/*[local-name()='UUID'])[1]" position="replace">
                    <cbc:UUID xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">___ignore___</cbc:UUID>
                </xpath>
            '''

            standard_debit_note = misc.file_open('l10n_sa_edi/tests/compliance/standard/debit.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(standard_debit_note)
            expected_tree = self.with_applied_xpath(expected_tree, applied_xpath)

            debit_note = self._create_debit_note(name='INV/2022/00001', date='2022-09-05', date_due='2022-09-22',
                                                 partner_id=self.partner_us, product_id=self.product_b, price=15.80)
            debit_note._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(debit_note)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testInvoiceSimplified(self):
        with freeze_time(datetime(year=2023, month=3, day=10, hour=14, minute=56, second=55, tzinfo=timezone('Etc/GMT-3'))):
            simplified_invoice = misc.file_open('l10n_sa_edi/tests/compliance/simplified/invoice.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(simplified_invoice)
            expected_tree = self.with_applied_xpath(expected_tree, self.invoice_applied_xpath)

            move = self._create_invoice(name='INV/2023/00034', date='2023-03-10', date_due='2023-03-10', partner_id=self.partner_sa_simplified,
                                        product_id=self.product_burger, price=265.00, quantity=3.0)
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testCreditNoteSimplified(self):
        with freeze_time(datetime(year=2023, month=3, day=10, hour=14, minute=59, second=38, tzinfo=timezone('Etc/GMT-3'))):
            simplified_credit_note = misc.file_open('l10n_sa_edi/tests/compliance/simplified/credit.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(simplified_credit_note)
            expected_tree = self.with_applied_xpath(expected_tree, self.credit_note_applied_xpath)

            move = self._create_credit_note(name='INV/2023/00034', date='2023-03-10', date_due='2023-03-10',
                                            partner_id=self.partner_sa_simplified, product_id=self.product_burger,
                                            price=265.00, quantity=3.0)
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def testDebitNoteSimplified(self):
        with freeze_time(datetime(year=2023, month=3, day=10, hour=15, minute=1, second=46, tzinfo=timezone('Etc/GMT-3'))):
            simplified_credit_note = misc.file_open('l10n_sa_edi/tests/compliance/simplified/debit.xml', 'rb').read()
            expected_tree = self.get_xml_tree_from_string(simplified_credit_note)
            expected_tree = self.with_applied_xpath(expected_tree, self.debit_note_applied_xpath)

            move = self._create_debit_note(name='INV/2023/00034', date='2023-03-10', date_due='2023-03-10',
                                           partner_id=self.partner_sa_simplified, product_id=self.product_burger,
                                           price=265.00, quantity=2.0)
            move._l10n_sa_generate_unsigned_data()
            generated_file = self.env['account.edi.format']._l10n_sa_generate_zatca_template(move)
            current_tree = self.get_xml_tree_from_string(generated_file)
            current_tree = self.with_applied_xpath(current_tree, self.remove_ubl_extensions_xpath)

            self.assertXmlTreeEqual(current_tree, expected_tree)

    def test_invoice_tax_amount_calculation(self):
        taxes = self.env['account.tax'].create([
            {
                'l10n_sa_is_retention': True,
                'name': "Retention 10%",
                'amount': -10
            },
            {
                'name': "15% sales",
                'amount': 15
            },
        ])

        invoice = self.init_invoice('out_invoice', amounts=[1000], taxes=taxes)
        self.assertRecordValues(invoice.line_ids.filtered(lambda l: l.display_type == 'product'), [{
            'l10n_gcc_invoice_tax_amount': 150
        }])
