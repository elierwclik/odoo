# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from datetime import timedelta

from odoo import Command, fields
from odoo.tests import Form
from odoo.addons.mrp.tests.common import TestMrpCommon
from odoo.exceptions import UserError


class TestProcurement(TestMrpCommon):

    def test_procurement(self):
        """This test case when create production order check procurement is create"""
        # Update BOM
        self.bom_3.bom_line_ids.filtered(lambda x: x.product_id == self.product_5).unlink()
        self.bom_1.bom_line_ids.filtered(lambda x: x.product_id == self.product_1).unlink()
        # Update route
        self.warehouse_1.mto_pull_id.route_id.active = True
        self.warehouse_1.mto_pull_id.procure_method = "make_to_order"
        self.warehouse_1.manufacture_mto_pull_id.procure_method = "make_to_order"
        route_manufacture = self.warehouse_1.manufacture_pull_id.route_id.id
        route_mto = self.warehouse_1.mto_pull_id.route_id.id
        self.product_4.write({'route_ids': [(6, 0, [route_manufacture, route_mto])]})
        # Create production order
        # -------------------------
        # Product6 Unit 24
        #    Product4 8 Dozen
        #    Product2 12 Unit
        # -----------------------

        production_form = Form(self.env['mrp.production'])
        production_form.product_id = self.product_6
        production_form.bom_id = self.bom_3
        production_form.product_qty = 24
        production_form.product_uom_id = self.product_6.uom_id
        production_product_6 = production_form.save()
        production_product_6.action_confirm()
        production_product_6.action_assign()

        # check production state is Confirmed
        self.assertEqual(production_product_6.state, 'confirmed')

        # Check procurement for product 4 created or not.
        # Check it created a purchase order

        move_raw_product4 = production_product_6.move_raw_ids.filtered(lambda x: x.product_id == self.product_4)
        produce_product_4 = self.env['mrp.production'].search([('product_id', '=', self.product_4.id),
                                                               ('move_dest_ids', '=', move_raw_product4[0].id)])
        # produce product
        self.assertEqual(produce_product_4.reservation_state, 'confirmed', "Consume material not available")

        # Create production order
        # -------------------------
        # Product 4  96 Unit
        #    Product2 48 Unit
        # ---------------------
        # Update Inventory
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product_2.id,
            'inventory_quantity': 48,
            'location_id': self.warehouse_1.lot_stock_id.id,
        }).action_apply_inventory()
        produce_product_4.action_assign()
        self.assertEqual(produce_product_4.product_qty, 96, "Wrong quantity of finish product.")
        self.assertEqual(produce_product_4.product_uom_id, self.uom_unit, "Wrong quantity of finish product.")
        self.assertEqual(produce_product_4.reservation_state, 'assigned', "Consume material not available")

        # produce product4
        # ---------------

        mo_form = Form(produce_product_4)
        mo_form.qty_producing = produce_product_4.product_qty
        produce_product_4 = mo_form.save()
        # Check procurement and Production state for product 4.
        produce_product_4.button_mark_done()
        self.assertEqual(produce_product_4.state, 'done', 'Production order should be in state done')

        # Produce product 6
        # ------------------

        # Update Inventory
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product_2.id,
            'inventory_quantity': 12,
            'location_id': self.warehouse_1.lot_stock_id.id,
        }).action_apply_inventory()
        production_product_6.action_assign()

        # ------------------------------------

        self.assertEqual(production_product_6.reservation_state, 'assigned', "Consume material not available")
        mo_form = Form(production_product_6)
        mo_form.qty_producing = production_product_6.product_qty
        production_product_6 = mo_form.save()
        # Check procurement and Production state for product 6.
        production_product_6.button_mark_done()
        self.assertEqual(production_product_6.state, 'done', 'Production order should be in state done')
        self.assertEqual(self.product_6.qty_available, 24, 'Wrong quantity available of finished product.')

    def test_procurement_2(self):
        """Check that a manufacturing order create the right procurements when the route are set on
        a parent category of a product"""
        all_categ_id = self.env['product.category'].create({
            'name': 'All',
        })
        child_categ_id = self.env['product.category'].create({
            'name': 'Child',
            'parent_id': all_categ_id.id,
        })

        # set the product of `self.bom_1` to this child category
        for bom_line_id in self.bom_1.bom_line_ids:
            # check that no routes are defined on the product
            self.assertEqual(len(bom_line_id.product_id.route_ids), 0)
            # set the category of the product to a child category
            bom_line_id.product_id.categ_id = child_categ_id

        # set the MTO route to the parent category (all)
        mto_route = self.warehouse_1.mto_pull_id.route_id
        mto_route.active = True
        mto_route.product_categ_selectable = True
        all_categ_id.write({'route_ids': [(6, 0, [mto_route.id])]})

        # create MO, but check it raises error as components are in make to order and not everyone has
        with self.assertRaises(UserError):
            production_form = Form(self.env['mrp.production'])
            production_form.product_id = self.product_4
            production_form.product_uom_id = self.product_4.uom_id
            production_form.product_qty = 1
            production_product_4 = production_form.save()
            production_product_4.action_confirm()

    def test_procurement_3(self):
        warehouse = self.warehouse_1
        warehouse.reception_steps = 'three_steps'
        warehouse.mto_pull_id.route_id.active = True
        self.env['stock.location']._parent_store_compute()
        warehouse.reception_route_id.rule_ids.filtered(
            lambda p: p.location_src_id == warehouse.wh_input_stock_loc_id and
            p.location_dest_id == warehouse.wh_qc_stock_loc_id).write({
                'action': 'pull',
                'location_dest_from_rule': True,
                'procure_method': 'make_to_stock',
            })
        warehouse.reception_route_id.rule_ids.filtered(
            lambda p: p.location_src_id == warehouse.wh_qc_stock_loc_id and
            p.location_dest_id == warehouse.lot_stock_id).write({
                'action': 'pull',
                'location_dest_from_rule': True,
            })

        finished_product = self.env['product.product'].create({
            'name': 'Finished Product',
            'is_storable': True,
        })
        component = self.env['product.product'].create({
            'name': 'Component',
            'is_storable': True,
            'route_ids': [Command.link(warehouse.mto_pull_id.route_id.id)],
        })
        self.env['stock.quant']._update_available_quantity(component, warehouse.wh_input_stock_loc_id, 100)
        bom = self.env['mrp.bom'].create({
            'product_id': finished_product.id,
            'product_tmpl_id': finished_product.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1.0}),
            ]})
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = finished_product
        mo_form.bom_id = bom
        mo_form.product_qty = 5
        mo_form.product_uom_id = finished_product.uom_id
        mo_form.location_src_id = warehouse.lot_stock_id
        mo = mo_form.save()
        mo.action_confirm()
        pickings = self.env['stock.picking'].search([('product_id', '=', component.id)])
        self.assertEqual(len(pickings), 2.0)
        picking_input_to_qc = pickings.filtered(lambda p: p.location_id == warehouse.wh_input_stock_loc_id)
        picking_qc_to_stock = pickings - picking_input_to_qc
        self.assertTrue(picking_input_to_qc)
        self.assertTrue(picking_qc_to_stock)
        picking_input_to_qc.action_assign()
        self.assertEqual(picking_input_to_qc.state, 'assigned')
        picking_input_to_qc.move_ids.write({'quantity': 5.0, 'picked': True})
        picking_input_to_qc._action_done()
        picking_qc_to_stock.action_assign()
        self.assertEqual(picking_qc_to_stock.state, 'assigned')
        picking_qc_to_stock.move_ids.write({'quantity': 3.0, 'picked': True})
        picking_qc_to_stock.with_context(skip_backorder=True, picking_ids_not_to_backorder=picking_qc_to_stock.ids).button_validate()
        self.assertEqual(picking_qc_to_stock.state, 'done')
        mo.action_assign()
        self.assertEqual(mo.move_raw_ids.quantity, 3.0)
        produce_form = Form(mo)
        produce_form.qty_producing = 3.0
        mo = produce_form.save()
        self.assertEqual(mo.move_raw_ids.quantity, 3.0)
        picking_qc_to_stock.move_line_ids.quantity = 5.0
        self.assertEqual(mo.move_raw_ids.quantity, 3.0)

    def test_link_date_mo_moves(self):
        """ Check link of shedule date for manufaturing with date stock move."""

        # create a product with manufacture route
        product_1 = self.env['product.product'].create({
            'name': 'AAA',
            'route_ids': [Command.link(self.warehouse_1.manufacture_pull_id.route_id.id)],
        })

        component_1 = self.env['product.product'].create({
            'name': 'component',
        })

        self.env['mrp.bom'].create({
            'product_id': product_1.id,
            'product_tmpl_id': product_1.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component_1.id, 'product_qty': 1}),
            ]})

        # create a move for product_1 from stock to output and reserve to trigger the
        # rule
        move_dest = self.env['stock.move'].create({
            'product_id': product_1.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.output_location.id,
            'product_uom_qty': 10,
            'procure_method': 'make_to_order'
        })

        move_dest._action_confirm()
        mo = self.env['mrp.production'].search([
            ('product_id', '=', product_1.id),
            ('state', '=', 'confirmed')
        ])

        self.assertAlmostEqual(mo.move_finished_ids.date, mo.move_raw_ids.date + timedelta(hours=1), delta=timedelta(seconds=1))

        self.assertEqual(len(mo), 1, 'the manufacture order is not created')

        mo_form = Form(mo)
        self.assertEqual(mo_form.product_qty, 10, 'the quantity to produce is not good relative to the move')

        mo = mo_form.save()

        # Confirming mo create finished move
        move_orig = self.env['stock.move'].search([
            ('move_dest_ids', 'in', move_dest.ids)
        ], limit=1)

        self.assertEqual(len(move_orig), 1, 'the move orig is not created')
        self.assertEqual(move_orig.product_qty, 10, 'the quantity to produce is not good relative to the move')

        new_date_start = fields.Datetime.to_datetime(mo.date_start) + timedelta(days=5)
        mo.date_start = new_date_start

        self.assertAlmostEqual(mo.move_raw_ids.date, mo.date_start, delta=timedelta(seconds=1))
        self.assertAlmostEqual(mo.move_finished_ids.date, mo.date_finished, delta=timedelta(seconds=1))

    def test_finished_move_cancellation(self):
        """Check state of finished move on cancellation of raw moves. """
        product_bottle = self.env['product.product'].create({
            'name': 'Plastic Bottle',
            'route_ids': [Command.link(self.warehouse_1.manufacture_pull_id.route_id.id)],
        })

        component_mold = self.env['product.product'].create({
            'name': 'Plastic Mold',
        })

        self.env['mrp.bom'].create({
            'product_id': product_bottle.id,
            'product_tmpl_id': product_bottle.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component_mold.id, 'product_qty': 1}),
            ]})

        move_dest = self.env['stock.move'].create({
            'product_id': product_bottle.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.output_location.id,
            'product_uom_qty': 10,
            'procure_method': 'make_to_order',
        })

        move_dest._action_confirm()
        mo = self.env['mrp.production'].search([
            ('product_id', '=', product_bottle.id),
            ('state', '=', 'confirmed')
        ])
        mo.move_raw_ids[0]._action_cancel()
        self.assertEqual(mo.state, 'cancel', 'Manufacturing order should be cancelled.')
        self.assertEqual(mo.move_finished_ids[0].state, 'cancel', 'Finished move should be cancelled if mo is cancelled.')
        self.assertEqual(mo.move_dest_ids[0].state, 'confirmed', 'Destination move should not be cancelled if prapogation cancel is False on manufacturing rule.')

    def test_procurement_with_empty_bom(self):
        """Ensure that a procurement request using a product with an empty BoM
        will create an empty MO in draft state that can be completed afterwards.
        """
        route_manufacture = self.warehouse_1.manufacture_pull_id.route_id.id
        route_mto = self.warehouse_1.mto_pull_id.route_id.id
        product = self.env['product.product'].create({
            'name': 'Clafoutis',
            'route_ids': [(6, 0, [route_manufacture, route_mto])]
        })
        self.env['mrp.bom'].create({
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
        })
        move_dest = self.env['stock.move'].create({
            'product_id': product.id,
            'product_uom': self.uom_unit.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.output_location.id,
            'product_uom_qty': 10,
            'procure_method': 'make_to_order',
        })
        move_dest._action_confirm()

        production = self.env['mrp.production'].search([('product_id', '=', product.id)])
        self.assertTrue(production)
        self.assertFalse(production.move_raw_ids)
        self.assertEqual(production.state, 'draft')

        comp1 = self.env['product.product'].create({
            'name': 'egg',
        })
        move_values = production._get_move_raw_values(comp1, 40.0, self.uom_unit)
        self.env['stock.move'].create(move_values)

        production.action_confirm()
        produce_form = Form(production)
        produce_form.qty_producing = production.product_qty
        production = produce_form.save()
        production.button_mark_done()

        move_dest._action_assign()
        self.assertEqual(move_dest.quantity, 10.0)

    def test_auto_assign(self):
        """ When auto reordering rule exists, check for when:
        1. There is not enough of a manufactured product to assign (reserve for) a picking => auto-create 1st MO
        2. There is not enough of a manufactured component to assign the created MO => auto-create 2nd MO
        3. Add an extra manufactured component (not in stock) to 1st MO => auto-create 3rd MO
        4. When 2nd MO is completed => auto-assign to 1st MO
        5. When 1st MO is completed => auto-assign to picking
        6. Additionally check that a MO that has component in stock auto-reserves when MO is confirmed (since default setting = 'at_confirm')"""

        self.picking_type_out.reservation_method = 'at_confirm'
        route_manufacture = self.warehouse_1.manufacture_pull_id.route_id

        product_1 = self.env['product.product'].create({
            'name': 'Cake',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id])]
        })
        product_2 = self.env['product.product'].create({
            'name': 'Cake Mix',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id])]
        })
        product_3 = self.env['product.product'].create({
            'name': 'Flour',
            'type': 'consu',
        })

        bom1 = self.env['mrp.bom'].create({
            'product_id': product_1.id,
            'product_tmpl_id': product_1.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': product_2.id, 'product_qty': 1}),
            ]})

        self.env['mrp.bom'].create({
            'product_id': product_2.id,
            'product_tmpl_id': product_2.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': product_3.id, 'product_qty': 1}),
            ]})

        # extra manufactured component added to 1st MO after it is already confirmed
        product_4 = self.env['product.product'].create({
            'name': 'Flavor Enchancer',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id])]
        })
        product_5 = self.env['product.product'].create({
            'name': 'MSG',
            'type': 'consu',
        })

        self.env['mrp.bom'].create({
            'product_id': product_4.id,
            'product_tmpl_id': product_4.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': product_5.id, 'product_qty': 1}),
            ]})

        # setup auto orderpoints (reordering rules)
        self.env['stock.warehouse.orderpoint'].create({
            'name': 'Cake RR',
            'location_id': self.stock_location.id,
            'product_id': product_1.id,
            'product_min_qty': 0,
            'product_max_qty': 5,
        })

        self.env['stock.warehouse.orderpoint'].create({
            'name': 'Cake Mix RR',
            'location_id': self.stock_location.id,
            'product_id': product_2.id,
            'product_min_qty': 0,
            'product_max_qty': 5,
        })

        self.env['stock.warehouse.orderpoint'].create({
            'name': 'Flavor Enchancer RR',
            'location_id': self.stock_location.id,
            'product_id': product_4.id,
            'product_min_qty': 0,
            'product_max_qty': 5,
        })

        # create picking output to trigger creating MO for reordering product_1
        pick_output = self.env['stock.picking'].create({
            'name': 'Cake Delivery Order',
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
            'move_ids': [Command.create({
                'product_id': product_1.id,
                'product_uom': product_1.uom_id.id,
                'product_uom_qty': 10.00,
                'procure_method': 'make_to_stock',
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
            })],
        })
        pick_output.action_confirm()  # should trigger orderpoint to create and confirm 1st MO
        pick_output.action_assign()

        mo = self.env['mrp.production'].search([
            ('product_id', '=', product_1.id),
            ('state', '=', 'confirmed')
        ])

        self.assertEqual(len(mo), 1, "Manufacture order was not automatically created")
        mo.action_assign()
        mo.is_locked = False
        self.assertEqual(mo.move_raw_ids.quantity, 0, "No components should be reserved yet")
        self.assertEqual(mo.product_qty, 15, "Quantity to produce should be picking demand + reordering rule max qty")

        # 2nd MO for product_2 should have been created and confirmed when 1st MO for product_1 was confirmed
        mo2 = self.env['mrp.production'].search([
            ('product_id', '=', product_2.id),
            ('state', '=', 'confirmed')
        ])

        self.assertEqual(len(mo2), 1, 'Second manufacture order was not created')
        self.assertEqual(mo2.product_qty, 20, "Quantity to produce should be MO's 'to consume' qty + reordering rule max qty")
        mo2_form = Form(mo2)
        mo2_form.qty_producing = 20
        mo2 = mo2_form.save()
        mo2.button_mark_done()

        self.assertEqual(mo.move_raw_ids.quantity, 15, "Components should have been auto-reserved")

        # add new component to 1st MO
        mo_form = Form(mo)
        with mo_form.move_raw_ids.new() as line:
            line.product_id = product_4
            line.product_uom_qty = 1
        mo_form.save()  # should trigger orderpoint to create and confirm 3rd MO

        mo3 = self.env['mrp.production'].search([
            ('product_id', '=', product_4.id),
            ('state', '=', 'confirmed')
        ])

        self.assertEqual(len(mo3), 1, 'Third manufacture order for added component was not created')
        self.assertEqual(mo3.product_qty, 6, "Quantity to produce should be 1 + reordering rule max qty")

        mo_form = Form(mo)
        mo.move_raw_ids.quantity = 15
        mo_form.qty_producing = 15
        mo = mo_form.save()
        mo.button_mark_done()

        self.assertEqual(pick_output.move_ids_without_package.quantity, 10, "Completed products should have been auto-reserved in picking")

        # make sure next MO auto-reserves components now that they are in stock since
        # default reservation_method = 'at_confirm'
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_1
        mo_form.bom_id = bom1
        mo_form.product_qty = 5
        mo_form.product_uom_id = product_1.uom_id
        mo_assign_at_confirm = mo_form.save()
        mo_assign_at_confirm.action_confirm()

        self.assertEqual(mo_assign_at_confirm.move_raw_ids.quantity, 5, "Components should have been auto-reserved")

    def test_check_update_qty_mto_chain(self):
        """ Simulate a mto chain with a manufacturing order. Updating the
        initial demand should also impact the initial move but not the
        linked manufacturing order.
        Secondary test: set the MTO route company-specific and ensure that make
        sure no new routes have been created
        """
        def create_run_procurement(product, product_qty, values=None):
            if not values:
                values = {
                    'warehouse_id': self.warehouse_1,
                    'action': 'pull_push',
                    'group_id': procurement_group,
                }
            return self.env['procurement.group'].run([self.env['procurement.group'].Procurement(
                product, product_qty, self.uom_unit, vendor.property_stock_customer,
                product.name, '/', self.env.company, values)
            ])

        vendor = self.env['res.partner'].create({
            'name': 'Roger'
        })
        # This needs to be tried with MTO route activated
        mto_route = self.warehouse_1.mto_pull_id.route_id
        mto_route.action_unarchive()
        mto_route.rule_ids.procure_method = "make_to_order"
        # Setup for the secondary test
        routes_count = self.env['stock.route'].search_count([])
        mto_route.rule_ids.search([('company_id', 'not in', (False, self.env.company.id))]).unlink()
        mto_route.company_id = self.env.company
        # Define products requested for this BoM.
        product = self.env['product.product'].create({
            'name': 'product',
            'is_storable': True,
            'route_ids': [
                Command.link(self.warehouse_1.mto_pull_id.route_id.id),
                Command.link(self.warehouse_1.manufacture_pull_id.route_id.id),
            ],
        })
        component = self.env['product.product'].create({
            'name': 'component',
            'is_storable': True,
        })
        self.env['mrp.bom'].create({
            'product_id': product.id,
            'product_tmpl_id': product.product_tmpl_id.id,
            'product_uom_id': product.uom_id.id,
            'product_qty': 1.0,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 1}),
            ]
        })

        procurement_group = self.env['procurement.group'].create({
            'move_type': 'direct',
            'partner_id': vendor.id
        })
        # Create initial procurement that will generate the initial move and its picking.
        create_run_procurement(product, 10, {
            'group_id': procurement_group,
            'warehouse_id': self.warehouse_1,
            'partner_id': vendor,
        })
        customer_move = self.env['stock.move'].search([('group_id', '=', procurement_group.id)])
        manufacturing_order = self.env['mrp.production'].search([('product_id', '=', product.id)])
        self.assertTrue(manufacturing_order, 'No manufacturing order created.')

        # Check manufacturing order data.
        self.assertEqual(manufacturing_order.product_qty, 10, 'The manufacturing order qty should be the same as the move.')

        # Create procurement to decrease quantity in the initial move but not in the related MO.
        create_run_procurement(product, -5.00)
        self.assertEqual(customer_move.product_uom_qty, 5, 'The demand on the initial move should have been decreased when merged with the procurement.')
        self.assertEqual(manufacturing_order.product_qty, 10, 'The demand on the manufacturing order should not have been decreased.')

        # Create procurement to increase quantity on the initial move and should create a new MO for the missing qty.
        create_run_procurement(product, 2.00)
        self.assertEqual(customer_move.product_uom_qty, 5, 'The demand on the initial move should not have been increased since it should be a new move.')
        self.assertEqual(manufacturing_order.product_qty, 10, 'The demand on the initial manufacturing order should not have been increased.')
        manufacturing_orders = self.env['mrp.production'].search([('product_id', '=', product.id)])
        self.assertEqual(len(manufacturing_orders), 2, 'A new MO should have been created for missing demand.')

        # Secondary test
        self.assertEqual(self.env['stock.route'].search_count([]), routes_count)

    def test_rr_with_dependance_between_bom(self):
        route_mto = self.warehouse_1.mto_pull_id.route_id
        route_mto.active = True
        route_manufacture = self.warehouse_1.manufacture_pull_id.route_id
        product_1 = self.env['product.product'].create({
            'name': 'Product A',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id])]
        })
        product_2 = self.env['product.product'].create({
            'name': 'Product B',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id, route_mto.id])]
        })
        product_3 = self.env['product.product'].create({
            'name': 'Product B',
            'is_storable': True,
            'route_ids': [(6, 0, [route_manufacture.id])]
        })
        product_4 = self.env['product.product'].create({
            'name': 'Product C',
            'type': 'consu',
        })

        op1 = self.env['stock.warehouse.orderpoint'].create({
            'name': 'Product A',
            'location_id': self.stock_location.id,
            'product_id': product_1.id,
            'product_min_qty': 1,
            'product_max_qty': 20,
        })

        op2 = self.env['stock.warehouse.orderpoint'].create({
            'name': 'Product B',
            'location_id': self.stock_location.id,
            'product_id': product_3.id,
            'product_min_qty': 5,
            'product_max_qty': 50,
        })

        self.env['mrp.bom'].create({
            'product_id': product_1.id,
            'product_tmpl_id': product_1.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [Command.create({'product_id': product_2.id, 'product_qty': 1})]
        })

        self.env['mrp.bom'].create({
            'product_id': product_2.id,
            'product_tmpl_id': product_2.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [Command.create({'product_id': product_3.id, 'product_qty': 1})]
        })

        self.env['mrp.bom'].create({
            'product_id': product_3.id,
            'product_tmpl_id': product_3.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1,
            'consumption': 'flexible',
            'type': 'normal',
            'bom_line_ids': [Command.create({'product_id': product_4.id, 'product_qty': 1})]
        })

        (op1 | op2)._procure_orderpoint_confirm()
        mo1 = self.env['mrp.production'].search([('product_id', '=', product_1.id)])
        mo3 = self.env['mrp.production'].search([('product_id', '=', product_3.id)])

        self.assertEqual(len(mo1), 1)
        self.assertEqual(len(mo3), 1)
        self.assertEqual(mo1.product_qty, 20)
        self.assertEqual(mo3.product_qty, 50)

    def test_several_boms_same_finished_product(self):
        """
        Suppose a product with two BoMs, each one based on a different operation type
        This test ensures that, when running the scheduler, the generated MOs are based
        on the correct BoMs
        """
        # Required for `picking_type_id` to be visible in the view
        self.env.user.group_ids += self.env.ref('stock.group_adv_location')

        stock_location01 = self.stock_location
        stock_location02 = stock_location01.copy()

        manu_operation01 = self.picking_type_manu
        manu_operation02 = manu_operation01.copy()
        with Form(manu_operation02) as form:
            form.name = 'Manufacturing 02'
            form.sequence_code = 'MO2'
            form.default_location_dest_id = stock_location02

        manu_rule01 = self.warehouse_1.manufacture_pull_id
        manu_route = manu_rule01.route_id
        manu_rule02 = manu_rule01.copy()
        with Form(manu_rule02) as form:
            form.picking_type_id = manu_operation02
        manu_route.rule_ids = [(6, 0, (manu_rule01 + manu_rule02).ids)]

        compo01, compo02, finished = self.env['product.product'].create([{
            'name': 'compo 01',
            'type': 'consu',
        }, {
            'name': 'compo 02',
            'type': 'consu',
        }, {
            'name': 'finished',
            'is_storable': True,
            'route_ids': [(6, 0, manu_route.ids)],
        }])

        bom01_form = Form(self.env['mrp.bom'])
        bom01_form.product_tmpl_id = finished.product_tmpl_id
        bom01_form.code = '01'
        bom01_form.picking_type_id = manu_operation01
        with bom01_form.bom_line_ids.new() as line:
            line.product_id = compo01
        bom01 = bom01_form.save()

        bom02_form = Form(self.env['mrp.bom'])
        bom02_form.product_tmpl_id = finished.product_tmpl_id
        bom02_form.code = '02'
        bom02_form.picking_type_id = manu_operation02
        with bom02_form.bom_line_ids.new() as line:
            line.product_id = compo02
        bom02 = bom02_form.save()

        self.env['stock.warehouse.orderpoint'].create([{
            'warehouse_id': self.warehouse_1.id,
            'location_id': stock_location01.id,
            'product_id': finished.id,
            'product_min_qty': 1,
            'product_max_qty': 1,
        }, {
            'warehouse_id': self.warehouse_1.id,
            'location_id': stock_location02.id,
            'product_id': finished.id,
            'product_min_qty': 2,
            'product_max_qty': 2,
        }])

        self.env['procurement.group'].run_scheduler()

        mos = self.env['mrp.production'].search([('product_id', '=', finished.id)], order='origin')
        self.assertRecordValues(mos, [
            {'product_qty': 1, 'bom_id': bom01.id, 'picking_type_id': manu_operation01.id, 'location_dest_id': stock_location01.id},
            {'product_qty': 2, 'bom_id': bom02.id, 'picking_type_id': manu_operation02.id, 'location_dest_id': stock_location02.id},
        ])

    def test_update_mo_component_qty(self):
        """ After Confirming MO, updating component qty should run procurement
            to update orig move qty
        """
        # 2 steps Manufacture
        self.warehouse_1.manufacture_steps = 'pbm'
        mo, *_ = self.generate_mo(qty_final=2, qty_base_1=1, qty_base_2=2)
        self.assertEqual(mo.state, 'confirmed', 'MO should be confirmed at this point')
        self.assertEqual(mo.product_qty, 2, 'MO qty to produce should be 2')
        self.assertEqual(mo.move_raw_ids.mapped('product_uom_qty'), [4, 2], 'Comp2 qty should be 4 and comp1 should be 2')
        self.assertEqual(mo.picking_ids.move_ids.mapped('product_uom_qty'), [4, 2], 'Comp moves should have same qty as MO')
        # decrease comp2 qty, should reflect in picking
        mo.move_raw_ids[0].product_uom_qty = 2
        self.assertEqual(mo.picking_ids.move_ids[0].product_uom_qty, 2, 'Comp2 move should have same qty as MO')

        # add a third component, should reflect in picking
        comp3 = self.env['product.product'].create({
            'name': 'Comp3',
            'is_storable': True,
        })
        mo.write({
            'move_raw_ids': [Command.create({
                'product_id': comp3.id,
                'product_uom_qty': 3
            })]
        })
        self.assertEqual(len(mo.picking_ids.move_ids), 3, 'Picking should have 3 moves')
        self.assertEqual(mo.picking_ids.move_ids[2].product_uom_qty, 3, 'Comp3 move should have same qty as MO')
        # change its qty
        mo.move_raw_ids[2].product_uom_qty = 4
        self.assertEqual(mo.picking_ids.move_ids[2].product_uom_qty, 4, 'Comp3 move should have same qty as MO')

        # increase qty to produce
        wiz = self.env['change.production.qty'].create({
            'mo_id': mo.id,
            'product_qty': 4
        })
        wiz.change_prod_qty()
        self.assertEqual(mo.product_qty, 4, 'MO qty to produce should be 4')
        # each move qty should be doubled
        self.assertEqual(mo.picking_ids.move_ids.mapped('product_uom_qty'), [4, 4, 8], 'Comps move should have same qty as MO')

    def test_update_merged_mo_component_qty(self):
        """ After Confirming two MOs merge then and change their component qtys,
            Procurements should run and any new moves should be merged with old ones
        """
        # 2 steps Manufacture
        self.warehouse_1.manufacture_steps = 'pbm'

        super_product = self.env['product.product'].create({
            'name': 'Super Product',
            'is_storable': True,
        })
        comp1 = self.env['product.product'].create({
            'name': 'Comp1',
            'is_storable': True,
        })
        comp2 = self.env['product.product'].create({
            'name': 'Comp2',
            'is_storable': True,
        })
        bom = self.env['mrp.bom'].create({
            'product_id': super_product.id,
            'product_tmpl_id': super_product.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'consumption': 'flexible',
            'bom_line_ids': [
                Command.create({'product_id': comp1.id, 'product_qty': 1}),
                Command.create({'product_id': comp2.id, 'product_qty': 2}),
            ]
        })
        # MO 1
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = super_product
        mo_form.bom_id = bom
        mo_form.product_qty = 1
        mo_1 = mo_form.save()
        mo_1.action_confirm()

        # MO 2
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = super_product
        mo_form.bom_id = bom
        mo_form.product_qty = 1
        mo_2 = mo_form.save()
        mo_2.action_confirm()

        res_mo_id = (mo_1 | mo_2).action_merge()['res_id']
        mo = self.env['mrp.production'].browse(res_mo_id)
        self.assertEqual(mo.product_qty, 2, 'Qty to produce should be 2')
        self.assertEqual(mo.move_raw_ids.mapped('product_uom_qty'), [2, 4], 'Comp1 qty should be 2 and comp2 should be 4')
        self.assertEqual(mo.picking_ids[0].move_ids.mapped('product_uom_qty'), [1, 2], 'Comp moves should have same qty as old MO')
        # increase Comp1 qty by 1 in MO
        mo.move_raw_ids[0].product_uom_qty = 3

        # any required qty is added to first picking by procurement
        self.assertEqual(mo.picking_ids[0].move_ids[0].product_uom_qty, 2, 'Comp1 qty increase should reflect in picking')

        # add new comp3
        comp3 = self.env['product.product'].create({
            'name': 'Comp3',
            'is_storable': True,
        })
        mo.write({
            'move_raw_ids': [Command.create({
                'product_id': comp3.id,
                'product_uom_qty': 2,
            })]
        })
        self.assertEqual(len(mo.picking_ids[0].move_ids), 3, 'Picking should have 3 moves')
        self.assertEqual(mo.picking_ids[0].move_ids[2].product_uom_qty, 2, 'Comp3 move should have same qty as MO')

        # increase qty to produce
        wiz = self.env['change.production.qty'].create({
            'mo_id': mo.id,
            'product_qty': 4
        })
        wiz.change_prod_qty()
        self.assertEqual(mo.product_qty, 4, 'MO qty to produce should be 4')
        # extra quantities are all added to first picking moves
        # comp1 (2 + 3 extra) = 5
        # comp2 (2 + 4 extra) = 6
        # comp3 (2 + 2 extra) = 4
        self.assertEqual(mo.picking_ids[0].move_ids.mapped('product_uom_qty'), [5, 6, 4], 'Comp qty do not match expected')

    def test_pbm_and_additionnal_components(self):
        """
        2-steps manufacturring.
        When adding a new component to a confirmed MO, it should add an SM in
        the PBM picking. Also, it should be possible to define the to-consume
        qty of the new line even if the MO is locked
        """
        self.warehouse_1.manufacture_steps = 'pbm'

        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = self.bom_4
        mo = mo_form.save()
        mo.action_confirm()

        if not mo.is_locked:
            mo.action_toggle_is_locked()

        with Form(mo) as mo_form:
            with mo_form.move_raw_ids.new() as raw_line:
                raw_line.product_id = self.product_2
                raw_line.product_uom_qty = 2.0

        move_vals = mo._get_move_raw_values(self.product_3, 0, self.product_3.uom_id)
        mo.move_raw_ids = [Command.create(move_vals)]
        mo.move_raw_ids[-1].product_uom_qty = 3.0

        expected_vals = [
            {'product_id': self.product_1.id, 'product_uom_qty': 1.0},
            {'product_id': self.product_2.id, 'product_uom_qty': 2.0},
            {'product_id': self.product_3.id, 'product_uom_qty': 3.0},
        ]
        self.assertRecordValues(mo.move_raw_ids, expected_vals)
        self.assertRecordValues(mo.picking_ids.move_ids, expected_vals)

    def test_consecutive_pickings(self):
        """ Test that when we generate several procurements for a product in a raw
            we do not create demand for the same quantities several times """

        route_manufacture = self.warehouse_1.manufacture_pull_id.route_id

        # Create a product with manufacture route
        product_1 = self.env['product.product'].create({
            'name': 'AAA',
            'route_ids': [(6, 0, [route_manufacture.id])],
        })

        component_1 = self.env['product.product'].create({
            'name': 'component',
            'type': 'consu',
        })

        self.env['mrp.bom'].create({
            'product_id': product_1.id,
            'product_tmpl_id': product_1.product_tmpl_id.id,
            'product_uom_id': self.uom_unit.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component_1.id, 'product_qty': 1}),
            ],
            'operation_ids': [
                Command.create({'name': 'OP1', 'workcenter_id': self.workcenter_2.id}),
            ],
        })

        self.env['stock.warehouse.orderpoint'].create({
            'product_id': product_1.id,
            'product_min_qty': 0.0,
            'product_max_qty': 0.0,
            'route_id': route_manufacture.id,
        })

        # Create 3 pickings and confirm them one by one
        bob = self.env['res.partner'].create({
            'name': 'Bob',
        })

        def delta_hours(td):
            return td.days * 24 + td.seconds // 3600

        mo = False
        for i in range(1, 4):
            picking = self.env['stock.picking'].create({
                'location_id': self.stock_location.id,
                'location_dest_id': self.customer_location.id,
                'partner_id': bob.id,
                'picking_type_id': self.picking_type_out.id,
                'move_ids': [Command.create({
                    'state': 'draft',
                    'location_id': self.stock_location.id,
                    'location_dest_id': self.customer_location.id,
                    'product_id': product_1.id,
                    'product_uom_qty': 15,
                    'product_uom': self.uom_unit.id,
                })],
            })
            picking.action_confirm()
            if not mo:
                mo = self.env['mrp.production'].search([('product_id', '=', product_1.id)])
            self.assertEqual(delta_hours(mo.date_finished - mo.date_start), i * 15)

        # Check the generated MO
        self.assertEqual(mo.product_qty, 45)
