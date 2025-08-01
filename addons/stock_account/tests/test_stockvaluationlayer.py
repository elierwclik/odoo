# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

""" Implementation of "INVENTORY VALUATION TESTS (With valuation layers)" spreadsheet. """

from odoo import Command
from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.addons.stock_account.tests.test_stockvaluation import _create_accounting_data
from odoo.exceptions import ValidationError
from odoo.tests import Form, tagged
from odoo.tests.common import TransactionCase


class TestStockValuationCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super(TestStockValuationCommon, cls).setUpClass()
        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')
        cls.supplier_location = cls.env.ref('stock.stock_location_suppliers')
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product1 = cls.env['product.product'].create({
            'name': 'product1',
            'is_storable': True,
            'categ_id': cls.env.ref('product.product_category_goods').id,
        })
        cls.picking_type_in = cls.env.ref('stock.picking_type_in')
        cls.picking_type_out = cls.env.ref('stock.picking_type_out')
        cls.env.ref('base.EUR').active = True

    def setUp(self):
        super(TestStockValuationCommon, self).setUp()
        # Counter automatically incremented by `_make_in_move` and `_make_out_move`.
        self.days = 0

    def _make_in_move(self, product, quantity, unit_cost=None, create_picking=False, loc_dest=None, pick_type=None, lot_ids=False):
        """ Helper to create and validate a receipt move.
        """
        unit_cost = unit_cost or product.standard_price
        loc_dest = loc_dest or self.stock_location
        pick_type = pick_type or self.picking_type_in
        in_move = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': loc_dest.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'price_unit': unit_cost,
            'picking_type_id': pick_type.id,
        })

        if create_picking:
            picking = self.env['stock.picking'].create({
                'picking_type_id': in_move.picking_type_id.id,
                'location_id': in_move.location_id.id,
                'location_dest_id': in_move.location_dest_id.id,
                })
            in_move.write({'picking_id': picking.id})

        in_move._action_confirm()
        if lot_ids:
            in_move.move_line_ids.unlink()
            in_move.move_line_ids = [Command.create({
                'location_id': self.supplier_location.id,
                'location_dest_id': loc_dest.id,
                'quantity': quantity / len(lot_ids),
                'product_id': product.id,
                'lot_id': lot.id,
            }) for lot in lot_ids]
        else:
            in_move._action_assign()

        in_move.picked = True
        in_move._action_done()

        self.days += 1
        return in_move.with_context(svl=True)

    def _make_out_move(self, product, quantity, force_assign=None, create_picking=False, loc_src=None, pick_type=None, lot_ids=False):
        """ Helper to create and validate a delivery move.
        """
        loc_src = loc_src or self.stock_location
        pick_type = pick_type or self.picking_type_out
        out_move = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': loc_src.id,
            'location_dest_id': self.customer_location.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'picking_type_id': pick_type.id,
        })

        if create_picking:
            picking = self.env['stock.picking'].create({
                'picking_type_id': out_move.picking_type_id.id,
                'location_id': out_move.location_id.id,
                'location_dest_id': out_move.location_dest_id.id,
                })
            out_move.write({'picking_id': picking.id})

        out_move._action_confirm()
        out_move._action_assign()
        if force_assign:
            self.env['stock.move.line'].create({
                'move_id': out_move.id,
                'product_id': out_move.product_id.id,
                'product_uom_id': out_move.product_uom.id,
                'location_id': out_move.location_id.id,
                'location_dest_id': out_move.location_dest_id.id,
            })
        if lot_ids:
            out_move.move_line_ids.unlink()
            out_move.move_line_ids = [Command.create({
                'location_id': loc_src.id,
                'location_dest_id': self.customer_location.id,
                'quantity': quantity / len(lot_ids),
                'product_id': product.id,
                'lot_id': lot.id,
            }) for lot in lot_ids]
        else:
            out_move.move_line_ids.quantity = quantity
        out_move.picked = True
        out_move._action_done()

        self.days += 1
        return out_move.with_context(svl=True)

    def _make_dropship_move(self, product, quantity, unit_cost=None, lot_ids=False):
        dropshipped = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.customer_location.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'picking_type_id': self.picking_type_out.id,
        })
        if unit_cost:
            dropshipped.price_unit = unit_cost
        dropshipped._action_confirm()
        dropshipped._action_assign()
        if lot_ids:
            dropshipped.move_line_ids = [Command.clear()]
            dropshipped.move_line_ids = [Command.create({
                'location_id': self.supplier_location.id,
                'location_dest_id': self.customer_location.id,
                'quantity': quantity / len(lot_ids),
                'product_id': product.id,
                'lot_id': lot.id,
            }) for lot in lot_ids]
        else:
            dropshipped.move_line_ids.quantity = quantity
        dropshipped.picked = True
        dropshipped._action_done()
        return dropshipped

    def _make_return(self, move, quantity_to_return):
        stock_return_picking = Form(self.env['stock.return.picking']\
            .with_context(active_ids=[move.picking_id.id], active_id=move.picking_id.id, active_model='stock.picking'))
        stock_return_picking = stock_return_picking.save()
        stock_return_picking.product_return_moves.quantity = quantity_to_return
        stock_return_picking_action = stock_return_picking.action_create_returns()
        return_pick = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
        return_pick.move_ids[0].move_line_ids[0].quantity = quantity_to_return
        return_pick.move_ids[0].picked = True
        return_pick._action_done()
        return return_pick.move_ids


class TestStockValuationStandard(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        cls.product1.product_tmpl_id.standard_price = 10

    def test_normal_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 15)

        self.assertEqual(self.product1.value_svl, 50)
        self.assertEqual(self.product1.quantity_svl, 5)

    def test_change_in_past_increase_in_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 15)
        move1.move_line_ids.quantity = 15

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_decrease_in_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 15)
        move1.move_line_ids.quantity = 5

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_change_in_past_add_ml_in_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 15)
        self.env['stock.move.line'].create({
            'move_id': move1.id,
            'product_id': move1.product_id.id,
            'quantity': 5,
            'product_uom_id': move1.product_uom.id,
            'location_id': move1.location_id.id,
            'location_dest_id': move1.location_dest_id.id,
        })

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_increase_out_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_out_move(self.product1, 1)
        move2.move_line_ids.quantity = 5

        self.assertEqual(self.product1.value_svl, 50)
        self.assertEqual(self.product1.quantity_svl, 5)

    def test_change_in_past_decrease_out_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_out_move(self.product1, 5)
        move2.move_line_ids.quantity = 1

        self.assertEqual(self.product1.value_svl, 90)
        self.assertEqual(self.product1.quantity_svl, 9)

    def test_change_standard_price_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 15)

        # change cost from 10 to 15
        self.product1.standard_price = 15.0

        self.assertEqual(self.product1.value_svl, 75)
        self.assertEqual(self.product1.quantity_svl, 5)
        self.assertEqual(self.product1.stock_valuation_layer_ids.sorted()[-1].description, 'Product value manually modified (from 10.0 to 15.0)')

    def test_negative_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_out_move(self.product1, 15)
        self.env['stock.move.line'].create({
            'move_id': move1.id,
            'product_id': move1.product_id.id,
            'quantity': 10,
            'product_uom_id': move1.product_uom.id,
            'location_id': move1.location_id.id,
            'location_dest_id': move1.location_dest_id.id,
        })

        self.assertEqual(self.product1.value_svl, 50)
        self.assertEqual(self.product1.quantity_svl, 5)

    def test_dropship_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_dropship_move(self.product1, 10)

        valuation_layers = self.product1.stock_valuation_layer_ids
        self.assertEqual(len(valuation_layers), 2)
        self.assertEqual(valuation_layers[0].value, 100)
        self.assertEqual(valuation_layers[1].value, -100)
        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_change_in_past_increase_dropship_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_dropship_move(self.product1, 10)
        move1.move_line_ids.quantity = 15

        valuation_layers = self.product1.stock_valuation_layer_ids
        self.assertEqual(len(valuation_layers), 4)
        self.assertEqual(valuation_layers[0].value, 100)
        self.assertEqual(valuation_layers[1].value, -100)
        self.assertEqual(valuation_layers[2].value, 50)
        self.assertEqual(valuation_layers[3].value, -50)
        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_empty_stock_move_valorisation(self):
        product1 = self.env['product.product'].create({
            'name': 'p1',
            'is_storable': True,
            'categ_id': self.env.ref('product.product_category_expenses').id,
        })
        product2 = self.env['product.product'].create({
            'name': 'p2',
            'is_storable': True,
            'categ_id': self.env.ref('product.product_category_expenses').id,
        })
        picking = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_in.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
        })
        for product in (product1, product2):
            product.standard_price = 10
            in_move = self.env['stock.move'].create({
                'product_id': product.id,
                'location_id': self.supplier_location.id,
                'location_dest_id': self.stock_location.id,
                'product_uom': self.uom_unit.id,
                'product_uom_qty': 2,
                'price_unit': 10,
                'picking_type_id': self.picking_type_in.id,
                'picking_id': picking.id
            })

        picking.action_confirm()
        # set quantity done only on one move
        in_move.move_line_ids.quantity = 2
        in_move.picked = True
        res_dict = picking.button_validate()
        wizard = self.env[(res_dict.get('res_model'))].with_context(res_dict.get('context')).browse(res_dict.get('res_id'))
        wizard.process()

        self.assertTrue(product2.stock_valuation_layer_ids)
        self.assertFalse(product1.stock_valuation_layer_ids)

    def test_currency_precision_and_standard_svl_value(self):
        currency = self.env['res.currency'].create({
            'name': 'Odoo',
            'symbol': 'O',
            'rounding': 1,
        })
        new_company = self.env['res.company'].create({
            'name': 'Super Company',
            'currency_id': currency.id,
        })

        old_company = self.env.user.company_id
        try:
            self.env.user.company_id = new_company
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', new_company.id)])
            product = self.product1.with_company(new_company)
            product.standard_price = 3

            self._make_in_move(product, 0.5, loc_dest=warehouse.lot_stock_id, pick_type=warehouse.in_type_id)
            self._make_out_move(product, 0.5, loc_src=warehouse.lot_stock_id, pick_type=warehouse.out_type_id)

            self.assertEqual(product.value_svl, 0.0)
        finally:
            self.env.user.company_id = old_company

    def test_change_qty_and_locations_of_done_sml(self):
        sub_stock_loc = self.env['stock.location'].create({
            'name': 'shelf1',
            'usage': 'internal',
            'location_id': self.stock_location.id,
        })

        move_in = self._make_in_move(self.product1, 25)
        self.assertEqual(self.product1.value_svl, 250)
        self.assertEqual(self.product1.qty_available, 25)

        move_in.move_line_ids.write({
            'location_dest_id': sub_stock_loc.id,
            'quantity': 30,
        })
        self.assertEqual(self.product1.value_svl, 300)
        self.assertEqual(self.product1.qty_available, 30)

        sub_loc_quant = self.product1.stock_quant_ids.filtered(lambda q: q.location_id == sub_stock_loc)
        self.assertEqual(sub_loc_quant.quantity, 30)

        with self.assertRaises(ValidationError):
            move_in.move_line_ids.location_id = self.stock_location


class TestStockValuationAVCO(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product1.product_tmpl_id.categ_id.property_cost_method = 'average'

    def test_normal_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        self.assertEqual(self.product1.standard_price, 10)
        self.assertEqual(move1.stock_valuation_layer_ids.value, 100)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        self.assertEqual(self.product1.standard_price, 15)
        self.assertEqual(move2.stock_valuation_layer_ids.value, 200)
        move3 = self._make_out_move(self.product1, 15)
        self.assertEqual(self.product1.standard_price, 15)
        self.assertEqual(move3.stock_valuation_layer_ids.value, -225)

        self.assertEqual(self.product1.value_svl, 75)
        self.assertEqual(self.product1.quantity_svl, 5)

    def test_change_in_past_increase_in_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        move1.move_line_ids.quantity = 15

        self.assertEqual(self.product1.value_svl, 125)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_decrease_in_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        move1.move_line_ids.quantity = 5

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_change_in_past_add_ml_in_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        self.env['stock.move.line'].create({
            'move_id': move1.id,
            'product_id': move1.product_id.id,
            'quantity': 5,
            'product_uom_id': move1.product_uom.id,
            'location_id': move1.location_id.id,
            'location_dest_id': move1.location_dest_id.id,
        })

        self.assertEqual(self.product1.value_svl, 125)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(self.product1.standard_price, 12.5)

    def test_change_in_past_add_move_in_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10, create_picking=True)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        self.env['stock.move.line'].create({
            'product_id': move1.product_id.id,
            'quantity': 5,
            'product_uom_id': move1.product_uom.id,
            'location_id': move1.location_id.id,
            'location_dest_id': move1.location_dest_id.id,
            'state': 'done',
            'picking_id': move1.picking_id.id,
        })

        self.assertEqual(self.product1.value_svl, 150)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(self.product1.standard_price, 15)

    def test_change_in_past_increase_out_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        move3.move_line_ids.quantity = 20

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)
        self.assertEqual(self.product1.standard_price, 15)

    def test_change_in_past_decrease_out_1(self):
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)
        move3.move_line_ids.quantity = 10

        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 10)
        self.assertEqual(self.product1.value_svl, 150)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(self.product1.standard_price, 15)

    def test_negative_1(self):
        """ Ensures that, in AVCO, the `remaining_qty` field is computed and the vacuum is ran
        when necessary.
        """
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 30)
        self.assertEqual(move3.stock_valuation_layer_ids.remaining_qty, -10)
        move4 = self._make_in_move(self.product1, 10, unit_cost=30)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 0)
        move5 = self._make_in_move(self.product1, 10, unit_cost=40)

        self.assertEqual(self.product1.value_svl, 400)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_negative_2(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.standard_price = 10
        move1 = self._make_out_move(self.product1, 1, force_assign=True)
        move2 = self._make_in_move(self.product1, 1, unit_cost=15)

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_negative_3(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_out_move(self.product1, 2, force_assign=True)
        self.assertEqual(move1.stock_valuation_layer_ids.value, 0)
        move2 = self._make_in_move(self.product1, 20, unit_cost=3.33)
        self.assertEqual(move1.stock_valuation_layer_ids[1].value, -6.66)

        self.assertEqual(self.product1.standard_price, 3.33)
        self.assertEqual(self.product1.value_svl, 59.94)
        self.assertEqual(self.product1.quantity_svl, 18)

    def test_return_receipt_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10, create_picking=True)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)
        move4 = self._make_return(move1, 1)

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)
        self.assertEqual(self.product1.standard_price, 15)

    def test_return_delivery_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1, create_picking=True)
        move4 = self._make_return(move3, 1)

        self.assertEqual(self.product1.value_svl, 30)
        self.assertEqual(self.product1.quantity_svl, 2)
        self.assertEqual(self.product1.standard_price, 15)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 2)

    def test_rereturn_receipt_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10, create_picking=True)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)
        move4 = self._make_return(move1, 1)  # -15, current avco
        move5 = self._make_return(move4, 1)  # +10, original move's price unit

        self.assertEqual(self.product1.value_svl, 15)
        self.assertEqual(self.product1.quantity_svl, 1)
        self.assertEqual(self.product1.standard_price, 15)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 1)

    def test_rereturn_delivery_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1, create_picking=True)
        move4 = self._make_return(move3, 1)
        move5 = self._make_return(move4, 1)

        self.assertEqual(self.product1.value_svl, 15)
        self.assertEqual(self.product1.quantity_svl, 1)
        self.assertEqual(self.product1.standard_price, 15)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 1)

    def test_dropship_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_dropship_move(self.product1, 1, unit_cost=10)

        self.assertEqual(self.product1.value_svl, 30)
        self.assertEqual(self.product1.quantity_svl, 2)
        self.assertEqual(self.product1.standard_price, 15)

    def test_rounding_slv_1(self):
        self._make_in_move(self.product1, 1, unit_cost=1.00)
        self._make_in_move(self.product1, 1, unit_cost=1.00)
        self._make_in_move(self.product1, 1, unit_cost=1.01)

        self.assertAlmostEqual(self.product1.value_svl, 3.01)

        move_out = self._make_out_move(self.product1, 3, create_picking=True)

        self.assertIn('Rounding Adjustment: -0.01', move_out.stock_valuation_layer_ids.description)

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)
        self.assertEqual(self.product1.standard_price, 1.00)

    def test_rounding_slv_2(self):
        self._make_in_move(self.product1, 1, unit_cost=1.02)
        self._make_in_move(self.product1, 1, unit_cost=1.00)
        self._make_in_move(self.product1, 1, unit_cost=1.00)

        self.assertAlmostEqual(self.product1.value_svl, 3.02)

        move_out = self._make_out_move(self.product1, 3, create_picking=True)

        self.assertIn('Rounding Adjustment: +0.01', move_out.stock_valuation_layer_ids.description)

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)
        self.assertEqual(self.product1.standard_price, 1.01)

    def test_rounding_svl_3(self):
        self._make_in_move(self.product1, 1000, unit_cost=0.17)
        self._make_in_move(self.product1, 800, unit_cost=0.23)

        self.assertEqual(self.product1.standard_price, 0.20)

        self._make_out_move(self.product1, 1000, create_picking=True)
        self._make_out_move(self.product1, 800, create_picking=True)

        self.assertEqual(self.product1.value_svl, 0)

    def test_rounding_svl_4(self):
        """
        The first 2 In moves result in a rounded standard_price at 3.4943, which is rounded at 3.49.
        This test ensures that no rounding error is generated with small out quantities.
        """
        self.product1.categ_id.property_cost_method = 'average'
        self._make_in_move(self.product1, 2, unit_cost=4.63)
        self._make_in_move(self.product1, 5, unit_cost=3.04)
        self.assertEqual(self.product1.standard_price, 3.49)

        for _ in range(70):
            self._make_out_move(self.product1, 0.1)

        self.assertEqual(self.product1.quantity_svl, 0)
        self.assertEqual(self.product1.value_svl, 0)

    def test_rounding_svl_5(self):
        self.product1.categ_id.property_cost_method = 'average'
        self._make_in_move(self.product1, 10, unit_cost=16.83)
        self._make_in_move(self.product1, 10, unit_cost=20)
        self.assertEqual(self.product1.standard_price, 18.42)

        self._make_out_move(self.product1, 10)
        out_move = self._make_out_move(self.product1, 9)
        self.assertEqual(out_move.stock_valuation_layer_ids[0].value, -165.73)

        self.assertEqual(self.product1.value_svl, 18.42)
        self.assertEqual(self.product1.quantity_svl, 1)

        self._make_out_move(self.product1, 1)
        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_return_delivery_2(self):
        self.product1.write({"standard_price": 1})
        move1 = self._make_out_move(self.product1, 10, create_picking=True, force_assign=True)
        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_return(move1, 10)

        self.assertEqual(self.product1.value_svl, 20)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(self.product1.standard_price, 2)

    def test_return_delivery_rounding(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.write({"standard_price": 1})
        self._make_in_move(self.product1, 1, unit_cost=13.13)
        self._make_in_move(self.product1, 1, unit_cost=12.20)
        move3 = self._make_out_move(self.product1, 2, create_picking=True)
        move4 = self._make_return(move3, 2)

        self.assertAlmostEqual(abs(move3.stock_valuation_layer_ids[0].value), abs(move4.stock_valuation_layer_ids[0].value))
        self.assertAlmostEqual(self.product1.value_svl, 25.33)
        self.assertEqual(self.product1.quantity_svl, 2)

    def test_inventory_adjustment_valuation_with_lot(self):
        """
        Check the new stock valuation layers created to counter balance
        a move history change.
        """
        product_lot = self.product1
        product_lot.write({'tracking': 'lot', 'standard_price': 5.0})
        product_lot.categ_id.property_cost_method = 'average'
        self.env['stock.quant'].create({
            'location_id':  self.ref('stock.stock_location_stock'),
            'product_id': product_lot.id,
            'inventory_quantity_auto_apply': 10.0,
            'lot_id': False,
        }).with_context(inventory_mode=True)._set_inventory_quantity()
        initial_svl = self.env['stock.valuation.layer'].search([('product_id', '=', product_lot.id)])
        self.assertRecordValues(initial_svl, [
            {'quantity': 10.0, 'value': 50.0},
        ])
        lot = self.env['stock.lot'].create({
            'product_id': product_lot.id,
            'name': 'LOT007',
        })
        sml = self.env['stock.move.line'].search([('product_id', '=', product_lot.id)], limit=1)
        sml.write({
            'quantity': 3.0,
            'lot_id': lot.id,
        })
        svl = self.env['stock.valuation.layer'].search([('product_id', '=', product_lot.id)])
        self.assertRecordValues(svl.sorted('quantity'), [
            {'quantity': -10, 'value': -50},
            {'quantity': 3, 'value': 15},
            {'quantity': 10, 'value': 50},
        ])

    def test_change_quantity_from_other_company(self):
        """
        checks that a move on company A from a user logged in company B creates a svl with correct values (the ones from company A)
        """
        # Give user access of company A + B, with default A
        company_A = self.env.company
        company_B = self.env['res.company'].create({
            'name': 'Super Company',
        })
        self.env.user.write({'company_ids': [(6, 0, [company_A.id, company_B.id])], 'company_id': company_A.id})
        warehouse_B = self.env.user.with_company(company_B)._get_default_warehouse_id()
        if not warehouse_B:
            warehouse_B = self.env['stock.warehouse'].sudo().create({'name': 'WH', 'code': 'WH-B', 'company_id': company_B.id})
            self.assertEqual(self.env.user.with_company(company_B)._get_default_warehouse_id(), warehouse_B)
        warehouse_A = self.env.user.with_company(company_A)._get_default_warehouse_id()
        # set product1 property cost method also in comp B
        self.product1.with_company(company_B).product_tmpl_id.categ_id.property_cost_method = 'average'
        # make both in moves so that the product has a standard price of 100 in comp A and 10 in comp B
        self.env.user.company_id = company_A
        move_comp_A = self._make_in_move(self.product1, 1, unit_cost=100)
        self.assertEqual(self.env['stock.valuation.layer'].search([('stock_move_id', '=', move_comp_A.id)]).value, 100)
        self.env.user.company_id = company_B
        move_comp_B = self._make_in_move(self.product1, 1, unit_cost=10, create_picking=True, loc_dest=warehouse_B.lot_stock_id, pick_type=warehouse_B.in_type_id)
        self.assertEqual(self.env['stock.valuation.layer'].search([('stock_move_id', '=', move_comp_B.id)]).value, 10)
        # make the cross move
        picking = self.env['stock.picking'].create({
            'picking_type_id': warehouse_A.in_type_id.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': warehouse_A.lot_stock_id.id,
            'move_ids': [Command.create({
                'product_id': self.product1.id,
                'location_id': self.supplier_location.id,
                'location_dest_id': warehouse_A.lot_stock_id.id,
                'product_uom': self.uom_unit.id,
                'product_uom_qty': 1,
                'picking_type_id': warehouse_A.in_type_id.id,
                'company_id': company_A.id,
            })],
        })
        cross_move = picking.move_ids[0]
        picking.action_confirm()
        picking.action_assign()
        cross_move.picked = True
        picking._action_done()
        self.assertEqual(self.env['stock.valuation.layer'].search([('stock_move_id', '=', cross_move.id)]).value, 100)


class TestStockValuationFIFO(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'

    def test_normal_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 15)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 5)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 5)

    def test_negative_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 30)
        self.assertEqual(move3.stock_valuation_layer_ids.remaining_qty, -10)
        move4 = self._make_in_move(self.product1, 10, unit_cost=30)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 0)
        move5 = self._make_in_move(self.product1, 10, unit_cost=40)

        self.assertEqual(self.product1.value_svl, 400)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_decrease_in_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 20, unit_cost=10)
        move2 = self._make_out_move(self.product1, 10)
        move1.move_line_ids.quantity = 10

        self.assertEqual(self.product1.value_svl, 0)
        self.assertEqual(self.product1.quantity_svl, 0)

    def test_change_in_past_decrease_in_2(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 20, unit_cost=10)
        move2 = self._make_out_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 10)
        move1.move_line_ids.quantity = 10
        move4 = self._make_in_move(self.product1, 20, unit_cost=15)

        self.assertEqual(self.product1.value_svl, 150)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_increase_in_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=15)
        move3 = self._make_out_move(self.product1, 20)
        move1.move_line_ids.quantity = 20

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_change_in_past_increase_in_2(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=12)
        move3 = self._make_out_move(self.product1, 15)
        move4 = self._make_out_move(self.product1, 20)
        move5 = self._make_in_move(self.product1, 100, unit_cost=15)
        move1.move_line_ids.quantity = 20

        self.assertEqual(self.product1.value_svl, 1375)
        self.assertEqual(self.product1.quantity_svl, 95)

    def test_change_in_past_increase_out_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 20, unit_cost=10)
        move2 = self._make_out_move(self.product1, 10)
        move3 = self._make_in_move(self.product1, 20, unit_cost=15)
        move2.move_line_ids.quantity = 25

        self.assertEqual(self.product1.value_svl, 225)
        self.assertEqual(self.product1.quantity_svl, 15)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 15)

    def test_change_in_past_decrease_out_1(self):
        """ Decrease the quantity of an outgoing stock.move.line will act like
        an inventory adjustement and not a return. It will take the standard price
        of the product in order to set the value and not the move's layers.
        """
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 20, unit_cost=10)
        move2 = self._make_out_move(self.product1, 15)
        move3 = self._make_in_move(self.product1, 20, unit_cost=15)
        move2.move_line_ids.quantity = 5

        self.assertEqual(self.product1.value_svl, 490)
        self.assertEqual(self.product1.quantity_svl, 35)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 35)

    def test_change_in_past_add_ml_out_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 20, unit_cost=10)
        move2 = self._make_out_move(self.product1, 10)
        move3 = self._make_in_move(self.product1, 20, unit_cost=15)
        self.env['stock.move.line'].create({
            'move_id': move2.id,
            'product_id': move2.product_id.id,
            'quantity': 5,
            'product_uom_id': move2.product_uom.id,
            'location_id': move2.location_id.id,
            'location_dest_id': move2.location_dest_id.id,
        })

        self.assertEqual(self.product1.value_svl, 350)
        self.assertEqual(self.product1.quantity_svl, 25)
        self.assertEqual(sum(self.product1.stock_valuation_layer_ids.mapped('remaining_qty')), 25)

    def test_return_delivery_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_out_move(self.product1, 10, create_picking=True)
        move3 = self._make_in_move(self.product1, 10, unit_cost=20)
        move4 = self._make_return(move2, 10)

        self.assertEqual(self.product1.value_svl, 300)
        self.assertEqual(self.product1.quantity_svl, 20)

    def test_return_receipt_1(self):
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        move1 = self._make_in_move(self.product1, 10, unit_cost=10, create_picking=True)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_return(move1, 2)

        self.assertEqual(self.product1.value_svl, 280)
        self.assertEqual(self.product1.quantity_svl, 18)

    def test_rereturn_receipt_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10, create_picking=True)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)
        move4 = self._make_return(move1, 1)
        move5 = self._make_return(move4, 1)

        self.assertEqual(self.product1.value_svl, 20)
        self.assertEqual(self.product1.quantity_svl, 1)

    def test_rereturn_delivery_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1, create_picking=True)
        move4 = self._make_return(move3, 1)
        move5 = self._make_return(move4, 1)

        self.assertEqual(self.product1.value_svl, 10)
        self.assertEqual(self.product1.quantity_svl, 1)

    def test_dropship_1(self):
        move1 = self._make_in_move(self.product1, 1, unit_cost=10)
        move2 = self._make_in_move(self.product1, 1, unit_cost=20)
        move3 = self._make_dropship_move(self.product1, 1, unit_cost=10)

        self.assertEqual(self.product1.value_svl, 30)
        self.assertEqual(self.product1.quantity_svl, 2)
        self.assertAlmostEqual(self.product1.standard_price, 15)

    def test_return_delivery_2(self):
        self._make_in_move(self.product1, 1, unit_cost=10)
        self.product1.standard_price = 0
        self._make_in_move(self.product1, 1, unit_cost=0)

        self._make_out_move(self.product1, 1)
        out_move02 = self._make_out_move(self.product1, 1, create_picking=True)

        returned = self._make_return(out_move02, 1)
        self.assertEqual(returned.stock_valuation_layer_ids.value, 0)

    def test_return_delivery_3(self):
        self.product1.write({"standard_price": 1})
        move1 = self._make_out_move(self.product1, 10, create_picking=True, force_assign=True)
        self._make_in_move(self.product1, 10, unit_cost=2)
        self._make_return(move1, 10)

        self.assertEqual(self.product1.value_svl, 20)
        self.assertEqual(self.product1.quantity_svl, 10)

    def test_currency_precision_and_fifo_svl_value(self):
        currency = self.env['res.currency'].create({
            'name': 'Odoo',
            'symbol': 'O',
            'rounding': 1,
        })
        new_company = self.env['res.company'].create({
            'name': 'Super Company',
            'currency_id': currency.id,
        })

        old_company = self.env.user.company_id
        try:
            self.env.user.company_id = new_company
            product = self.product1.with_company(new_company)
            product.product_tmpl_id.categ_id.property_cost_method = 'fifo'
            warehouse = self.env['stock.warehouse'].search([('company_id', '=', new_company.id)])

            self._make_in_move(product, 0.5, loc_dest=warehouse.lot_stock_id, pick_type=warehouse.in_type_id, unit_cost=3)
            self._make_out_move(product, 0.5, loc_src=warehouse.lot_stock_id, pick_type=warehouse.out_type_id)

            self.assertEqual(product.value_svl, 0.0)
        finally:
            self.env.user.company_id = old_company


class TestStockValuationChangeCostMethod(TestStockValuationCommon):
    def test_standard_to_fifo_1(self):
        """ The accounting impact of this cost method change is neutral.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.product_tmpl_id.standard_price = 10

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'
        self.assertEqual(self.product1.value_svl, 190)
        self.assertEqual(self.product1.quantity_svl, 19)

        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 5)
        for svl in self.product1.stock_valuation_layer_ids.sorted()[-2:]:
            self.assertEqual(svl.description, 'Costing method change for product category Goods: from standard to fifo.')

    def test_standard_to_fifo_2(self):
        """ We want the same result as `test_standard_to_fifo_1` but by changing the category of
        `self.product1` to another one, not changing the current one.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.product_tmpl_id.standard_price = 10

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 1)

        cat2 = self.env['product.category'].create({'name': 'fifo'})
        cat2.property_cost_method = 'fifo'
        self.product1.product_tmpl_id.categ_id = cat2
        self.assertEqual(self.product1.value_svl, 190)
        self.assertEqual(self.product1.quantity_svl, 19)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 5)

    def test_avco_to_fifo(self):
        """ The accounting impact of this cost method change is neutral.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'average'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'
        self.assertEqual(self.product1.value_svl, 285)
        self.assertEqual(self.product1.quantity_svl, 19)

    def test_fifo_to_standard(self):
        """ The accounting impact of this cost method change is not neutral as we will use the last
        fifo price as the new standard price.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.assertEqual(self.product1.value_svl, 289.94)
        self.assertEqual(self.product1.quantity_svl, 19)

    def test_fifo_to_avco(self):
        """ The accounting impact of this cost method change is not neutral as we will use the last
        fifo price as the new AVCO.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'average'
        self.assertEqual(self.product1.value_svl, 289.94)
        self.assertEqual(self.product1.quantity_svl, 19)

    def test_avco_to_standard(self):
        """ The accounting impact of this cost method change is neutral.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'average'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        move1 = self._make_in_move(self.product1, 10, unit_cost=10)
        move2 = self._make_in_move(self.product1, 10, unit_cost=20)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.assertEqual(self.product1.value_svl, 285)
        self.assertEqual(self.product1.quantity_svl, 19)

    def test_standard_to_avco(self):
        """ The accounting impact of this cost method change is neutral.
        """
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.product_tmpl_id.standard_price = 10

        move1 = self._make_in_move(self.product1, 10)
        move2 = self._make_in_move(self.product1, 10)
        move3 = self._make_out_move(self.product1, 1)

        self.product1.product_tmpl_id.categ_id.property_cost_method = 'average'
        self.assertEqual(self.product1.value_svl, 190)
        self.assertEqual(self.product1.quantity_svl, 19)


@tagged('post_install', '-at_install', 'change_valuation')
class TestStockValuationChangeValuation(TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super(TestStockValuationChangeValuation, cls).setUpClass()
        cls.stock_input_account, cls.stock_output_account, cls.stock_valuation_account, cls.expense_account, cls.income_account, cls.stock_journal = _create_accounting_data(cls.env)
        cls.product1.categ_id.property_valuation = 'real_time'
        cls.product1.write({
            'property_account_expense_id': cls.expense_account.id,
        })
        cls.product1.categ_id.write({
            'property_stock_account_input_categ_id': cls.stock_input_account.id,
            'property_stock_account_output_categ_id': cls.stock_output_account.id,
            'property_stock_valuation_account_id': cls.stock_valuation_account.id,
            'property_stock_journal': cls.stock_journal.id,
        })

    def test_standard_manual_to_auto_1(self):
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.product_tmpl_id.standard_price = 10
        move1 = self._make_in_move(self.product1, 10)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 0)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 1)

        self.product1.product_tmpl_id.categ_id.write({
            'property_valuation': 'real_time',
            'property_stock_account_input_categ_id': self.stock_input_account.id,
            'property_stock_account_output_categ_id': self.stock_output_account.id,
            'property_stock_valuation_account_id': self.stock_valuation_account.id,
        })

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        # An accounting entry should only be created for the replenish now that the category is perpetual.
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 1)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 3)
        for svl in self.product1.stock_valuation_layer_ids.sorted()[-2:]:
            self.assertEqual(svl.description, 'Valuation method change for product category Goods: from manual_periodic to real_time.')

    def test_standard_manual_to_auto_2(self):
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'
        self.product1.product_tmpl_id.standard_price = 10
        move1 = self._make_in_move(self.product1, 10)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 0)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 1)

        cat2 = self.env['product.category'].create({'name': 'standard auto'})
        cat2.property_cost_method = 'standard'
        cat2.property_valuation = 'real_time'
        cat2.write({
            'property_stock_account_input_categ_id': self.stock_input_account.id,
            'property_stock_account_output_categ_id': self.stock_output_account.id,
            'property_stock_valuation_account_id': self.stock_valuation_account.id,
            'property_stock_journal': self.stock_journal.id,
        })

        # Try to change the product category with a `default_type` key in the context and
        # check it doesn't break the account move generation.
        self.product1.with_context(default_is_storable=True).categ_id = cat2
        self.assertEqual(self.product1.categ_id, cat2)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        # An accounting entry should only be created for the replenish now that the category is perpetual.
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 1)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 3)

    def test_standard_auto_to_manual_1(self):
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'real_time'
        self.product1.product_tmpl_id.standard_price = 10
        move1 = self._make_in_move(self.product1, 10)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 1)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 1)

        self.product1.product_tmpl_id.categ_id.property_valuation = 'manual_periodic'

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        # An accounting entry should only be created for the emptying now that the category is manual.
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 2)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 3)

    def test_standard_auto_to_manual_2(self):
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'standard'
        self.product1.product_tmpl_id.categ_id.property_valuation = 'real_time'
        self.product1.product_tmpl_id.standard_price = 10
        move1 = self._make_in_move(self.product1, 10)

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 1)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 1)

        cat2 = self.env['product.category'].create({'name': 'fifo'})
        cat2.property_cost_method = 'standard'
        cat2.property_valuation = 'manual_periodic'
        self.product1.with_context(debug=True).categ_id = cat2

        self.assertEqual(self.product1.value_svl, 100)
        self.assertEqual(self.product1.quantity_svl, 10)
        # An accounting entry should only be created for the emptying now that the category is manual.
        self.assertEqual(len(self.product1.stock_valuation_layer_ids.mapped('account_move_id')), 2)
        self.assertEqual(len(self.product1.stock_valuation_layer_ids), 3)

    def test_return_delivery_fifo(self):
        self.product1.product_tmpl_id.categ_id.property_cost_method = 'fifo'
        self.env['decimal.precision'].search([
            ('name', '=', 'Product Price'),
        ]).digits = 4
        self.product1.standard_price = 280.8475

        move1 = self._make_out_move(self.product1, 4, create_picking=True, force_assign=True)
        move2 = self._make_return(move1, 4)

        for move in [move1, move2]:
            self.assertEqual(len(move.stock_valuation_layer_ids), 1)
            self.assertAlmostEqual(move.stock_valuation_layer_ids.unit_cost, self.product1.standard_price)
            self.assertAlmostEqual(abs(move.stock_valuation_layer_ids.value), 1123.39)

@tagged('post_install', '-at_install')
class TestAngloSaxonAccounting(AccountTestInvoicingCommon, TestStockValuationCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.ref('base.EUR').active = True
        cls.company_data['company'].anglo_saxon_accounting = True
        cls.stock_location = cls.env['stock.location'].create({
            'name': 'stock location',
            'usage': 'internal',
        })
        cls.customer_location = cls.env['stock.location'].create({
            'name': 'customer location',
            'usage': 'customer',
        })
        cls.supplier_location = cls.env['stock.location'].create({
            'name': 'supplier location',
            'usage': 'supplier',
        })
        cls.warehouse_in = cls.env['stock.warehouse'].create({
            'name': 'warehouse in',
            'company_id': cls.company_data['company'].id,
            'code': '1',
        })
        cls.warehouse_out = cls.env['stock.warehouse'].create({
            'name': 'warehouse out',
            'company_id': cls.company_data['company'].id,
            'code': '2',
        })
        cls.picking_type_in = cls.env['stock.picking.type'].create({
            'name': 'pick type in',
            'sequence_code': '1',
            'code': 'incoming',
            'company_id': cls.company_data['company'].id,
            'warehouse_id': cls.warehouse_in.id,
        })
        cls.picking_type_out = cls.env['stock.picking.type'].create({
            'name': 'pick type in',
            'sequence_code': '2',
            'code': 'outgoing',
            'company_id': cls.company_data['company'].id,
            'warehouse_id': cls.warehouse_out.id,
        })
        cls.stock_input_account = cls.env['account.account'].create({
            'name': 'Stock Input',
            'code': 'StockIn',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.stock_output_account = cls.env['account.account'].create({
            'name': 'Stock Output',
            'code': 'StockOut',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.stock_valuation_account = cls.env['account.account'].create({
            'name': 'Stock Valuation',
            'code': 'StockValuation',
            'account_type': 'asset_current',
            'reconcile': True,
        })
        cls.expense_account = cls.env['account.account'].create({
            'name': 'Expense Account',
            'code': 'ExpenseAccount',
            'account_type': 'expense',
            'reconcile': True,
        })
        cls.uom_unit = cls.env.ref('uom.product_uom_unit')
        cls.product1 = cls.env['product.product'].create({
            'name': 'product1',
            'is_storable': True,
            'categ_id': cls.env.ref('product.product_category_goods').id,
            'property_account_expense_id': cls.expense_account.id,
        })
        cls.product1.categ_id.write({
            'property_valuation': 'real_time',
            'property_stock_account_input_categ_id': cls.stock_input_account.id,
            'property_stock_account_output_categ_id': cls.stock_output_account.id,
            'property_stock_valuation_account_id': cls.stock_valuation_account.id,
            'property_stock_journal': cls.company_data['default_journal_misc'].id,
        })

    def _make_in_move(self, product, quantity, unit_cost=None, create_picking=False, loc_dest=None, pick_type=None):
        """ Helper to create and validate a receipt move.
        """
        unit_cost = unit_cost or product.standard_price
        loc_dest = loc_dest or self.stock_location
        pick_type = pick_type or self.picking_type_in
        in_move = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': loc_dest.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'price_unit': unit_cost,
            'picking_type_id': pick_type.id,
        })

        if create_picking:
            picking = self.env['stock.picking'].create({
                'picking_type_id': in_move.picking_type_id.id,
                'location_id': in_move.location_id.id,
                'location_dest_id': in_move.location_dest_id.id,
            })
            in_move.write({'picking_id': picking.id})

        in_move._action_confirm()
        in_move._action_assign()
        in_move.move_line_ids.quantity = quantity
        in_move.picked = True
        in_move._action_done()

        return in_move.with_context(svl=True)

    def _make_dropship_move(self, product, quantity, unit_cost=None):
        dropshipped = self.env['stock.move'].create({
            'product_id': product.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.customer_location.id,
            'product_uom': self.uom_unit.id,
            'product_uom_qty': quantity,
            'picking_type_id': self.picking_type_out.id,
        })
        if unit_cost:
            dropshipped.price_unit = unit_cost
        dropshipped._action_confirm()
        dropshipped._action_assign()
        dropshipped.move_line_ids.quantity = quantity
        dropshipped.picked = True
        dropshipped._action_done()
        return dropshipped

    def _make_return(self, move, quantity_to_return):
        stock_return_picking = Form(self.env['stock.return.picking']\
            .with_context(active_ids=[move.picking_id.id], active_id=move.picking_id.id, active_model='stock.picking'))
        stock_return_picking = stock_return_picking.save()
        stock_return_picking.product_return_moves.quantity = quantity_to_return
        stock_return_picking_action = stock_return_picking.action_create_returns()
        return_pick = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
        return_pick.move_ids[0].move_line_ids[0].quantity = quantity_to_return
        return_pick.move_ids.picked = True
        return_pick._action_done()
        return return_pick.move_ids

    def test_avco_and_credit_note(self):
        """
        When reversing an invoice that contains some anglo-saxo AML, the new anglo-saxo AML should have the same value
        """
        # Required for `account_id` to be visible in the view
        self.env.user.group_ids += self.env.ref('account.group_account_readonly')
        self.product1.categ_id.property_cost_method = 'average'

        self._make_in_move(self.product1, 2, unit_cost=10)

        invoice_form = Form(self.env['account.move'].with_context(default_move_type='out_invoice'))
        invoice_form.partner_id = self.env['res.partner'].create({'name': 'Super Client'})
        with invoice_form.invoice_line_ids.new() as invoice_line_form:
            invoice_line_form.product_id = self.product1
            invoice_line_form.quantity = 2
            invoice_line_form.price_unit = 25
            invoice_line_form.account_id = self.company_data['default_journal_purchase'].default_account_id
            invoice_line_form.tax_ids.clear()
        invoice = invoice_form.save()
        invoice.action_post()

        self._make_in_move(self.product1, 2, unit_cost=20)
        self.assertEqual(self.product1.standard_price, 15)

        refund_wizard = self.env['account.move.reversal'].with_context(active_model="account.move", active_ids=invoice.ids).create({
            'journal_id': invoice.journal_id.id,
        })
        action = refund_wizard.refund_moves()
        reverse_invoice = self.env['account.move'].browse(action['res_id'])
        with Form(reverse_invoice) as reverse_invoice_form:
            with reverse_invoice_form.invoice_line_ids.edit(0) as line:
                line.quantity = 1
        reverse_invoice.action_post()

        anglo_lines = reverse_invoice.line_ids.filtered(lambda l: l.display_type == 'cogs')
        self.assertEqual(len(anglo_lines), 2)
        self.assertEqual(abs(anglo_lines[0].balance), 10)
        self.assertEqual(abs(anglo_lines[1].balance), 10)

    def test_return_delivery_storno(self):
        """ When using STORNO accounting, reverse accounting moves should have negative values for credit/debit.
        """
        self.env.company.account_storno = True
        self.product1.categ_id.property_cost_method = 'fifo'

        self._make_in_move(self.product1, 10, unit_cost=10)
        out_move = self._make_out_move(self.product1, 10, create_picking=True)
        return_move = self._make_return(out_move, 10)

        valuation_line = out_move.account_move_ids.line_ids.filtered(lambda l: l.account_id == self.stock_valuation_account)
        stock_out_line = out_move.account_move_ids.line_ids.filtered(lambda l: l.account_id == self.stock_output_account)

        self.assertEqual(valuation_line.credit, 100)
        self.assertEqual(valuation_line.debit, 0)
        self.assertEqual(stock_out_line.credit, 0)
        self.assertEqual(stock_out_line.debit, 100)

        valuation_line = return_move.account_move_ids.line_ids.filtered(lambda l: l.account_id == self.stock_valuation_account)
        stock_out_line = return_move.account_move_ids.line_ids.filtered(lambda l: l.account_id == self.stock_output_account)

        self.assertEqual(valuation_line.credit, -100)
        self.assertEqual(valuation_line.debit, 0)
        self.assertEqual(stock_out_line.credit, 0)
        self.assertEqual(stock_out_line.debit, -100)

    def test_dropship_return_accounts_1(self):
        """
        When returning a dropshipped move, make sure the correct accounts are used
        """
        # pylint: disable=bad-whitespace
        self.product1.categ_id.property_cost_method = 'fifo'
        move1 = self._make_dropship_move(self.product1, 2, unit_cost=10)
        move2 = self._make_return(move1, 2)

        # First: Input -> Valuation
        # Second: Valuation -> Output
        origin_svls = move1.stock_valuation_layer_ids.sorted('quantity', reverse=True)
        # First: Output -> Valuation
        # Second: Valuation -> Input
        return_svls = move2.stock_valuation_layer_ids.sorted('quantity', reverse=True)
        self.assertEqual(len(origin_svls), 2)
        self.assertEqual(len(return_svls), 2)

        acc_in, acc_out, acc_valuation = self.stock_input_account, self.stock_output_account, self.stock_valuation_account

        # Dropshipping should be: Input -> Output
        self.assertRecordValues(origin_svls[0].account_move_id.line_ids, [
            {'account_id': acc_in.id,        'debit': 0,  'credit': 20},
            {'account_id': acc_valuation.id, 'debit': 20, 'credit': 0},
        ])
        self.assertRecordValues(origin_svls[1].account_move_id.line_ids, [
            {'account_id': acc_valuation.id, 'debit': 0,  'credit': 20},
            {'account_id': acc_out.id,       'debit': 20, 'credit': 0},
        ])
        # Return should be: Output -> Input
        self.assertRecordValues(return_svls[0].account_move_id.line_ids, [
            {'account_id': acc_out.id,       'debit': 0,  'credit': 20},
            {'account_id': acc_valuation.id, 'debit': 20, 'credit': 0},
        ])
        self.assertRecordValues(return_svls[1].account_move_id.line_ids, [
            {'account_id': acc_valuation.id, 'debit': 0,  'credit': 20},
            {'account_id': acc_in.id,        'debit': 20, 'credit': 0},
        ])

    def test_dropship_return_accounts_2(self):
        """
        When returning a dropshipped move, make sure the correct accounts are used
        """
        # pylint: disable=bad-whitespace
        self.product1.categ_id.property_cost_method = 'fifo'

        move1 = self._make_dropship_move(self.product1, 2, unit_cost=10)

        # return to WH/Stock
        stock_return_picking = Form(self.env['stock.return.picking']\
            .with_context(active_ids=[move1.picking_id.id], active_id=move1.picking_id.id, active_model='stock.picking'))
        stock_return_picking = stock_return_picking.save()
        stock_return_picking.product_return_moves.quantity = 2
        stock_return_picking_action = stock_return_picking.action_create_returns()
        return_pick = self.env['stock.picking'].browse(stock_return_picking_action['res_id'])
        return_pick.location_dest_id = self.stock_location
        return_pick.move_ids[0].move_line_ids[0].quantity = 2
        return_pick.move_ids[0].picked = True
        return_pick._action_done()
        move2 = return_pick.move_ids

        # First: Input -> Valuation
        # Second: Valuation -> Output
        origin_svls = move1.stock_valuation_layer_ids.sorted('quantity', reverse=True)
        # Only one: Output -> Valuation
        return_svl = move2.stock_valuation_layer_ids
        self.assertEqual(len(origin_svls), 2)
        self.assertEqual(len(return_svl), 1)

        acc_in, acc_out, acc_valuation = self.stock_input_account, self.stock_output_account, self.stock_valuation_account

        # Dropshipping should be: Input -> Output
        self.assertRecordValues(origin_svls[0].account_move_id.line_ids, [
            {'account_id': acc_in.id,        'debit': 0,  'credit': 20},
            {'account_id': acc_valuation.id, 'debit': 20, 'credit': 0},
        ])
        self.assertRecordValues(origin_svls[1].account_move_id.line_ids, [
            {'account_id': acc_valuation.id, 'debit': 0,  'credit': 20},
            {'account_id': acc_out.id,       'debit': 20, 'credit': 0},
        ])
        # Return should be: Output -> Valuation
        self.assertRecordValues(return_svl.account_move_id.line_ids, [
            {'account_id': acc_out.id,       'debit': 0,  'credit': 20},
            {'account_id': acc_valuation.id, 'debit': 20, 'credit': 0},
        ])
