# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.exceptions import UserError
from odoo.fields import Command
from odoo.tests import tagged, Form

from odoo.addons.product.tests.common import ProductCommon


@tagged('post_install', '-at_install')
class TestPricelist(ProductCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.datacard = cls.env['product.product'].create({'name': 'Office Lamp'})
        cls.usb_adapter = cls.env['product.product'].create({'name': 'Office Chair'})

        cls.sale_pricelist_id = cls.env['product.pricelist'].create({
            'name': 'Sale pricelist',
            'item_ids': [
                Command.create({
                    'compute_price': 'formula',
                    'base': 'list_price',  # based on public price
                    'price_discount': 10,
                    'product_id': cls.usb_adapter.id,
                    'applied_on': '0_product_variant',
                }),
                Command.create({
                    'compute_price': 'formula',
                    'base': 'list_price',  # based on public price
                    'price_surcharge': -0.5,
                    'product_id': cls.datacard.id,
                    'applied_on': '0_product_variant',
                }),
                Command.create({
                    'compute_price': 'formula',
                    'base': 'standard_price',  # based on cost
                    'price_markup': 99.99,
                    'applied_on': '3_global',
                }),
            ],
        })
        # Enable pricelist feature
        cls.env.user.group_ids += cls.env.ref('product.group_product_pricelist')
        cls.uom_ton = cls.env.ref('uom.product_uom_ton')

    def test_10_discount(self):
        # Make sure the price using a pricelist is the same than without after
        # applying the computation manually

        self.assertEqual(
            self.pricelist._get_product_price(self.usb_adapter, 1.0)*0.9,
            self.sale_pricelist_id._get_product_price(self.usb_adapter, 1.0))

        self.assertEqual(
            self.pricelist._get_product_price(self.datacard, 1.0)-0.5,
            self.sale_pricelist_id._get_product_price(self.datacard, 1.0))

        self.assertAlmostEqual(
            self.sale_pricelist_id._get_product_price(self.usb_adapter, 1.0, uom=self.uom_unit)*12,
            self.sale_pricelist_id._get_product_price(self.usb_adapter, 1.0, uom=self.uom_dozen))

        # price_surcharge applies to product default UoM, here "Units", so surcharge will be multiplied
        self.assertAlmostEqual(
            self.sale_pricelist_id._get_product_price(self.datacard, 1.0, uom=self.uom_unit)*12,
            self.sale_pricelist_id._get_product_price(self.datacard, 1.0, uom=self.uom_dozen))

    def test_11_markup(self):
        """Ensure `price_markup` always equals negative `price_discount`."""
        # Check create values
        for item in self.sale_pricelist_id.item_ids:
            self.assertEqual(item.price_markup, -item.price_discount)

        # Overwrite create values, and check again
        self.sale_pricelist_id.item_ids[0].price_discount = 0
        self.sale_pricelist_id.item_ids[1].price_discount = -20.02
        self.sale_pricelist_id.item_ids[2].price_markup = -0.5
        for item in self.sale_pricelist_id.item_ids:
            self.assertEqual(item.price_markup, -item.price_discount)

    def test_20_pricelist_uom(self):
        # Verify that the pricelist rules are correctly using the product's default UoM
        # as reference, and return a result according to the target UoM (as specific in the context)

        tonne_price = 100

        # setup product stored in 'tonnes', with a discounted pricelist for qty > 3 tonnes
        spam = self.env['product.product'].create({
            'name': '1 tonne of spam',
            'uom_id': self.uom_ton.id,
            'list_price': tonne_price,
            'type': 'consu'
        })

        self.env['product.pricelist.item'].create({
            'pricelist_id': self.pricelist.id,
            'applied_on': '0_product_variant',
            'compute_price': 'formula',
            'base': 'list_price',  # based on public price
            'min_quantity': 3,  # min = 3 tonnes
            'price_surcharge': -10,  # -10 EUR / tonne
            'product_id': spam.id
        })

        def test_unit_price(qty, uom_id, expected_unit_price):
            uom = self.env['uom.uom'].browse(uom_id)
            unit_price = self.pricelist._get_product_price(spam, qty, uom=uom)
            self.assertAlmostEqual(unit_price, expected_unit_price, msg='Computed unit price is wrong')

        # Test prices - they are *per unit*, the quantity is only here to match the pricelist rules!
        test_unit_price(2, self.uom_kgm.id, tonne_price / 1000.0)
        test_unit_price(2000, self.uom_kgm.id, tonne_price / 1000.0)
        test_unit_price(3500, self.uom_kgm.id, (tonne_price - 10) / 1000.0)
        test_unit_price(2, self.uom_ton.id, tonne_price)
        test_unit_price(3, self.uom_ton.id, tonne_price - 10)

    def test_30_pricelists_order(self):
        # Verify the order of pricelists after creation

        ProductPricelist = self.env['product.pricelist']
        res_partner = self.env['res.partner'].create({'name': 'Ready Corner'})

        ProductPricelist.search([]).active = False

        pl_first = ProductPricelist.create({'name': 'First Pricelist'})
        res_partner.invalidate_recordset(['property_product_pricelist'])

        self.assertEqual(res_partner.property_product_pricelist, pl_first)

        ProductPricelist.create({'name': 'Second Pricelist'})
        res_partner.invalidate_recordset(['property_product_pricelist'])

        self.assertEqual(res_partner.property_product_pricelist, pl_first)

    def test_pricelists_multi_comp_checks(self):
        first_company = self.env.company
        second_company = self.env['res.company'].create({'name': 'Test Company'})

        shared_pricelist = self.env['product.pricelist'].create({
            'name': 'Test Multi-comp pricelist',
            'company_id': False,
        })
        second_pricelist = self.env['product.pricelist'].create({
            'name': f'Second test pricelist{first_company.name}',
        })

        self.assertEqual(self.pricelist.company_id, first_company)
        self.assertFalse(shared_pricelist.company_id)
        self.assertEqual(second_pricelist.company_id, first_company)

        with self.assertRaises(UserError):
            shared_pricelist.item_ids = [
                Command.create({
                    'compute_price': 'formula',
                    'base': 'pricelist',
                    'base_pricelist_id': self.pricelist.id,
                })
            ]

        self.pricelist.item_ids = [
            Command.create({
                'compute_price': 'formula',
                'base': 'pricelist',
                'base_pricelist_id': shared_pricelist.id,
            }),
            Command.create({
                'compute_price': 'formula',
                'base': 'pricelist',
                'base_pricelist_id': second_pricelist.id,
            })
        ]

        with self.assertRaises(UserError):
            # Should raise because the pricelist would have a rule based on a pricelist
            # from another company
            self.pricelist.company_id = second_company

    def test_pricelists_res_partner_form(self):
        pricelist_europe = self.env['product.pricelist'].create({
            'name': 'Sale pricelist',
            'country_group_ids': self.env.ref('base.europe').ids,
        })

        default_pricelist = self.env['product.pricelist'].search([('name', 'ilike', ' ')], limit=1)

        with Form(self.env['res.partner']) as partner_form:
            partner_form.name = "test"
            self.assertEqual(partner_form.property_product_pricelist, default_pricelist)

            partner_form.country_id = self.env.ref('base.be')
            self.assertEqual(partner_form.property_product_pricelist, pricelist_europe)

            partner_form.property_product_pricelist = self.sale_pricelist_id
            self.assertEqual(partner_form.property_product_pricelist, self.sale_pricelist_id)

            partner = partner_form.save()

        with Form(partner) as partner_form:
            self.assertEqual(partner_form.property_product_pricelist, self.sale_pricelist_id)

    def test_pricelist_change_to_formula_and_back(self):
        pricelist_2 = self.env['product.pricelist'].create({
            'name': 'Sale pricelist 2',
            'item_ids': [
                Command.create({
                    'compute_price': 'percentage',
                    'percent_price': 20,
                    'base': 'pricelist',
                    'base_pricelist_id': self.sale_pricelist_id.id,
                    'applied_on': '3_global',
                }),
            ],
        })
        with Form(pricelist_2.item_ids) as item_form:
            item_form.compute_price = 'formula'
            item_form.compute_price = 'percentage'
            item_form.percent_price = 20
        self.assertFalse(pricelist_2.item_ids.base_pricelist_id.id)
