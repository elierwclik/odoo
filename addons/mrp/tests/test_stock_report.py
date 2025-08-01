# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import Form
from odoo.addons.stock.tests.test_report import TestReportsCommon
from odoo import Command


class TestMrpStockReports(TestReportsCommon):
    def test_report_forecast_1_mo_count(self):
        """ Creates and configures a product who could be produce and could be a component.
        Plans some producing and consumming MO and check the report values.
        """
        # Create a variant attribute.
        product_chocolate = self.env['product.product'].create({
            'name': 'Chocolate',
            'type': 'consu',
            'standard_price': 10
        })
        product_chococake = self.env['product.product'].create({
            'name': 'Choco Cake',
            'is_storable': True,
        })
        product_double_chococake = self.env['product.product'].create({
            'name': 'Double Choco Cake',
            'is_storable': True,
        })
        byproduct = self.env['product.product'].create({
            'name': 'by-product',
            'is_storable': True,
        })

        # Creates two BOM: one creating a regular slime, one using regular slimes.
        bom_chococake = self.env['mrp.bom'].create({
            'product_id': product_chococake.id,
            'product_tmpl_id': product_chococake.product_tmpl_id.id,
            'product_uom_id': product_chococake.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': product_chocolate.id, 'product_qty': 4}),
            ],
            'byproduct_ids':
                [(0, 0, {'product_id': byproduct.id, 'product_qty': 2, 'cost_share': 1.8})],
        })
        bom_double_chococake = self.env['mrp.bom'].create({
            'product_id': product_double_chococake.id,
            'product_tmpl_id': product_double_chococake.product_tmpl_id.id,
            'product_uom_id': product_double_chococake.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': product_chococake.id, 'product_qty': 2}),
            ],
        })

        # Creates two MO: one for each BOM.
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_chococake
        mo_form.bom_id = bom_chococake
        mo_form.product_qty = 10
        mo_1 = mo_form.save()
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_double_chococake
        mo_form.bom_id = bom_double_chococake
        mo_form.product_qty = 2
        mo_2 = mo_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_chococake.product_tmpl_id.ids)
        draft_picking_qty = docs['draft_picking_qty']
        draft_production_qty = docs['draft_production_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(draft_production_qty['in'], 10)
        self.assertEqual(draft_production_qty['out'], 4)

        # Confirms the MO and checks the report lines.
        mo_1.action_confirm()
        mo_2.action_confirm()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_chococake.product_tmpl_id.ids)
        draft_picking_qty = docs['draft_picking_qty']
        draft_production_qty = docs['draft_production_qty']
        self.assertEqual(len(lines), 2, "Must have two line.")
        line_1 = lines[0]
        line_2 = lines[1]
        self.assertEqual(line_1['document_in']['id'], mo_1.id)
        self.assertEqual(line_1['quantity'], 4)
        self.assertEqual(line_1['document_out']['id'], mo_2.id)
        self.assertEqual(line_2['document_in']['id'], mo_1.id)
        self.assertEqual(line_2['quantity'], 6)
        self.assertEqual(line_2['document_out'], False)
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(draft_production_qty['in'], 0)
        self.assertEqual(draft_production_qty['out'], 0)

        mo_form = Form(mo_1)
        mo_form.qty_producing = 10
        mo_form.save()
        mo_1.move_byproduct_ids.quantity = 18
        mo_1.button_mark_done()

        self.env.flush_all()  # flush to correctly build report
        report_values = self.env['report.mrp.report_mo_overview']._get_report_data(mo_1.id)
        self.assertEqual(report_values['byproducts']['details'][0]['name'], byproduct.name)
        self.assertEqual(report_values['byproducts']['details'][0]['quantity'], 18)
        # (Component price $10) * (4 unit to produce one finished) * (the mo qty = 10 units) = $400
        self.assertEqual(report_values['components'][0]['summary']['mo_cost'], 400)
        # cost_share of byproduct = 1.8 -> 1.8 / 100 -> 0.018 * 400 = 7.2
        self.assertAlmostEqual(report_values['byproducts']['summary']['mo_cost'], 7.2)
        byproduct_report_values = report_values['cost_breakdown'][1]
        self.assertEqual(byproduct_report_values['name'], byproduct.name)
        # 7.2 / 18 units = 0.4
        self.assertAlmostEqual(byproduct_report_values['unit_avg_total_cost'], 0.4)

    def test_report_forecast_2_production_backorder(self):
        """ Creates a manufacturing order and produces half the quantity.
        Then creates a backorder and checks the report.
        """
        # Configures the warehouse.
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.manufacture_steps = 'pbm_sam'
        # Configures a product.
        product_apple_pie = self.env['product.product'].create({
            'name': 'Apple Pie',
            'is_storable': True,
        })
        product_apple = self.env['product.product'].create({
            'name': 'Apple',
            'type': 'consu',
        })
        bom = self.env['mrp.bom'].create({
            'product_id': product_apple_pie.id,
            'product_tmpl_id': product_apple_pie.product_tmpl_id.id,
            'product_uom_id': product_apple_pie.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': product_apple.id, 'product_qty': 5}),
            ],
        })
        # Creates a MO and validates the pick components.
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_apple_pie
        mo_form.bom_id = bom
        mo_form.product_qty = 4
        mo_1 = mo_form.save()
        mo_1.action_confirm()
        pick = mo_1.move_raw_ids.move_orig_ids.picking_id
        pick.picking_type_id.show_operations = True  # Could be false without demo data, as the lot group is disabled
        pick_form = Form(pick)
        with Form(pick.move_ids_without_package, view='stock.view_stock_move_operations') as form:
            with form.move_line_ids.edit(0) as move_line:
                move_line.quantity = 20
        pick = pick_form.save()
        pick.button_validate()
        # Produces 3 products then creates a backorder for the remaining product.
        mo_form = Form(mo_1)
        mo_form.qty_producing = 3
        mo_1 = mo_form.save()
        action = mo_1.button_mark_done()
        backorder_form = Form(self.env['mrp.production.backorder'].with_context(**action['context']))
        backorder = backorder_form.save()
        backorder.action_backorder()

        mo_2 = (mo_1.procurement_group_id.mrp_production_ids - mo_1)
        # Checks the forecast report.
        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_apple_pie.product_tmpl_id.ids)
        self.assertEqual(len(lines), 1, "Must have only one line about the backorder")
        self.assertEqual(lines[0]['document_in']['id'], mo_2.id)
        self.assertEqual(lines[0]['quantity'], 1)
        self.assertEqual(lines[0]['document_out'], False)

        # Produces the last unit.
        mo_form = Form(mo_2)
        mo_form.qty_producing = 1
        mo_2 = mo_form.save()
        mo_2.button_mark_done()
        # Checks the forecast report.
        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_apple_pie.product_tmpl_id.ids)
        self.assertEqual(len(lines), 0, "Must have no line")

    def test_report_forecast_3_report_line_corresponding_to_mo_highlighted(self):
        """ When accessing the report from a MO, checks if the correct MO is highlighted in the report
        """
        product_banana = self.env['product.product'].create({
            'name': 'Banana',
            'is_storable': True,
        })
        product_chocolate = self.env['product.product'].create({
            'name': 'Chocolate',
            'type': 'consu',
        })

        # We create 2 identical MO
        mo_form = Form(self.env['mrp.production'])
        mo_form.product_id = product_banana
        mo_form.product_qty = 10
        with mo_form.move_raw_ids.new() as move:
            move.product_id = product_chocolate

        mo_1 = mo_form.save()
        mo_2 = mo_1.copy()
        (mo_1 | mo_2).action_confirm()

        # Check for both MO if the highlight (is_matched) corresponds to the correct MO
        for mo in [mo_1, mo_2]:
            context = mo.action_product_forecast_report()['context']
            _, _, lines = self.get_report_forecast(product_template_ids=product_banana.product_tmpl_id.ids, context=context)
            for line in lines:
                if line['document_in']['id'] == mo.id:
                    self.assertTrue(line['is_matched'], "The corresponding MO line should be matched in the forecast report.")
                else:
                    self.assertFalse(line['is_matched'], "A line of the forecast report not linked to the MO shoud not be matched.")

    def test_kit_packaging_delivery_slip(self):
        superkit = self.env['product.product'].create({
            'name': 'Super Kit',
            'type': 'consu',
            'uom_id': self.env['uom.uom'].create({
                'name': '6-pack',
                'relative_factor': 6,
                'relative_uom_id': self.env.ref('uom.product_uom_unit').id,
            }).id,
        })

        compo01, compo02 = self.env['product.product'].create([{
            'name': n,
            'is_storable': True,
            'uom_id': self.env.ref('uom.product_uom_meter').id,
        } for n in ['Compo 01', 'Compo 02']])

        self.env['mrp.bom'].create({
            'product_tmpl_id': superkit.product_tmpl_id.id,
            'product_qty': 1,
            'type': 'phantom',
            'product_uom_id': superkit.uom_id.id,
            'bom_line_ids': [
                (0, 0, {'product_id': compo01.id, 'product_qty': 6}),
                (0, 0, {'product_id': compo02.id, 'product_qty': 6}),
            ],
        })

        for back_order, expected_vals in [('never', [12, 12]), ('always', [24, 12])]:
            picking_form = Form(self.env['stock.picking'])
            picking_form.picking_type_id = self.picking_type_in
            picking_form.partner_id = self.partner
            with picking_form.move_ids_without_package.new() as move:
                move.product_id = superkit
                move.product_uom_qty = 4
            picking = picking_form.save()
            picking.action_confirm()

            picking.move_ids.write({'quantity': 12, 'picked': True})
            picking.picking_type_id.create_backorder = back_order
            picking.button_validate()
            non_kit_aggregate_values = picking.move_line_ids._get_aggregated_product_quantities()
            self.assertFalse(non_kit_aggregate_values)
            aggregate_values = picking.move_line_ids._get_aggregated_product_quantities(kit_name=superkit.display_name)
            for line in aggregate_values.values():
                self.assertItemsEqual([line[val] for val in ['qty_ordered', 'quantity']], expected_vals)

            html_report = self.env['ir.actions.report']._render_qweb_html('stock.report_deliveryslip', picking.ids)[0]
            self.assertTrue(html_report, "report generated successfully")

    def test_subkit_in_delivery_slip(self):
        """
        Suppose this structure:
        Super Kit --|- Compo 01 x1
                    |- Sub Kit x1 --|- Compo 02 x1
                    |               |- Compo 03 x1

        This test ensures that, when delivering one Super Kit, one Sub Kit, one Compo 01 and one Compo 02,
        and when putting in pack the third component of the Super Kit, the delivery report is correct.
        """
        compo01, compo02, compo03, subkit, superkit = self.env['product.product'].create([{
            'name': n,
            'type': 'consu',
        } for n in ['Compo 01', 'Compo 02', 'Compo 03', 'Sub Kit', 'Super Kit']])

        self.env['mrp.bom'].create([{
            'product_tmpl_id': subkit.product_tmpl_id.id,
            'product_qty': 1,
            'type': 'phantom',
            'bom_line_ids': [
                (0, 0, {'product_id': compo02.id, 'product_qty': 1}),
                (0, 0, {'product_id': compo03.id, 'product_qty': 1}),
            ],
        }, {
            'product_tmpl_id': superkit.product_tmpl_id.id,
            'product_qty': 1,
            'type': 'phantom',
            'bom_line_ids': [
                (0, 0, {'product_id': compo01.id, 'product_qty': 1}),
                (0, 0, {'product_id': subkit.id, 'product_qty': 1}),
            ],
        }])

        picking_form = Form(self.env['stock.picking'])
        picking_form.picking_type_id = self.picking_type_out
        picking_form.partner_id = self.partner
        with picking_form.move_ids_without_package.new() as move:
            move.product_id = superkit
            move.product_uom_qty = 1
        with picking_form.move_ids_without_package.new() as move:
            move.product_id = subkit
            move.product_uom_qty = 1
        with picking_form.move_ids_without_package.new() as move:
            move.product_id = compo01
            move.product_uom_qty = 1
        with picking_form.move_ids_without_package.new() as move:
            move.product_id = compo02
            move.product_uom_qty = 1
        picking = picking_form.save()
        picking.action_confirm()

        picking.move_ids.write({'quantity': 1, 'picked': True})
        move = picking.move_ids.filtered(lambda m: m.description_picking == "Super Kit" and m.product_id == compo03)
        move.move_line_ids.result_package_id = self.env['stock.quant.package'].create({'name': 'Package0001'})
        picking.button_validate()

        html_report = self.env['ir.actions.report']._render_qweb_html(
            'stock.report_deliveryslip', picking.ids)[0].decode('utf-8').split('\n')
        keys = [
            "Package0001", "Compo 03",
            "Products with no package assigned", "Compo 01", "Compo 02",
            "Super Kit", "Compo 01",
            "Sub Kit", "Compo 02", "Compo 03",
        ]
        for line in html_report:
            if not keys:
                break
            if keys[0] in line:
                keys = keys[1:]


        self.assertFalse(keys, "All keys should be in the report with the defined order")

    def test_mo_overview(self):
        """ Test that the overview does not traceback when the final produced qty is 0
        """
        product_chocolate = self.env['product.product'].create({
            'name': 'Chocolate',
            'type': 'consu',
        })
        product_chococake = self.env['product.product'].create({
            'name': 'Choco Cake',
            'is_storable': True,
        })
        workcenter = self.env['mrp.workcenter'].create({
            'name': 'workcenter test',
            'costs_hour': 10,
            'time_start': 10,
            'time_stop': 10,
            'time_efficiency': 90,
        })

        self.env['mrp.bom'].create({
            'product_id': product_chococake.id,
            'product_tmpl_id': product_chococake.product_tmpl_id.id,
            'product_uom_id': product_chococake.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                (0, 0, {'product_id': product_chocolate.id, 'product_qty': 4}),
            ],
            'operation_ids': [
                Command.create({
                    'name': 'Cutting Machine',
                    'workcenter_id': workcenter.id,
                    'time_cycle': 60,
                    'sequence': 1
                }),
            ],
        })
        mo = self.env['mrp.production'].create({
            'name': 'MO',
            'product_qty': 1.0,
            'product_id': product_chococake.id,
        })

        mo.action_confirm()
        # check that the mo and bom cost are correctly calculated after mo confirmation
        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(round(overview_values['data']['operations']['summary']['mo_cost'], 2), 14.45)
        self.assertEqual(round(overview_values['data']['operations']['summary']['bom_cost'], 2), 14.44)
        mo.button_mark_done()
        mo.qty_produced = 0.

        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(overview_values['data']['id'], mo.id, "computing overview value should work")

    def test_overview_with_component_also_as_byproduct(self):
        """ Check that opening he overview of an MO for which the BoM contains an element as both component and byproduct
        does not cause an infinite recursion.
        """
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': self.product.product_tmpl_id.id,
            'product_qty': 1.0,
            'bom_line_ids': [
                Command.create({'product_id': self.product1.id, 'product_qty': 1.0}),
                ],
            'byproduct_ids': [
                Command.create({'product_id': self.product1.id, 'product_qty': 1.0})
                ]
        })

        mo = self.env['mrp.production'].create({
            'product_id': self.product.id,
            'bom_id': bom.id,
            'product_qty': 1,
        })

        mo.action_confirm()
        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(overview_values['data']['id'], mo.id, "Unexpected disparity between overview and MO data")

    def test_multi_step_component_forecast_availability(self):
        """
        Test that the component availability is correcly forecasted
        in multi step manufacturing
        """
        # Configures the warehouse.
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.manufacture_steps = 'pbm_sam'
        final_product, component = self.product, self.product1
        bom = self.env['mrp.bom'].create({
            'product_id': final_product.id,
            'product_tmpl_id': final_product.product_tmpl_id.id,
            'product_uom_id': final_product.uom_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [
                Command.create({'product_id': component.id, 'product_qty': 10}),
            ],
        })
        # Creates a MO without any component in stock
        mo_form = Form(self.env['mrp.production'])
        mo_form.bom_id = bom
        mo_form.product_qty = 2
        mo = mo_form.save()
        mo.action_confirm()
        self.assertEqual(mo.components_availability, 'Not Available')
        self.assertEqual(mo.move_raw_ids.forecast_availability, -20.0)
        self.env['stock.quant']._update_available_quantity(component, warehouse.lot_stock_id, 100)
        # change the qty_producing to force a recompute of the availability
        with Form(mo) as mo_form:
            mo_form.qty_producing = 2.0
        self.assertEqual(mo.components_availability, 'Available')

    def test_mo_overview_same_component(self):
        """
        Test that for an mo for a product which has 2+ component lines for the same product,
        if there is some quantity of the component reserved, we properly match replenishments with
        components lines
        """
        # BOM structure:
        # 'finished', manufactured:
        #    - 1 'part'
        #    - 1 'part'
        part, finished = self.env['product.product'].create([
            {
                'name': name,
                'type': 'consu',
                'is_storable': True,
            } for name in ['Part', 'Finished']
        ])
        self.env['mrp.bom'].create([
            {
                'product_id': finished.id,
                'product_tmpl_id': finished.product_tmpl_id.id,
                'product_qty': 1.0,
                'type': 'normal',
                'bom_line_ids': [
                    Command.create({'product_id': part.id, 'product_qty': 1.0})
                ] * 2,
            }
        ])
        # Put 2 parts in stock
        self.env['stock.quant']._update_available_quantity(part, self.stock_location, 2)

        # Receive 20 parts
        self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_in.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'move_type': 'one',
            'move_ids_without_package': [Command.create({
                    'product_id': part.id,
                    'product_uom_qty': 20,
                    'location_id': self.env.ref('stock.stock_location_suppliers').id,
                    'location_dest_id': self.stock_location.id,
                }),
            ],
        }).action_confirm()

        # Create an MO for 5 finished product
        mo = self.env['mrp.production'].create({
            'name': 'MO',
            'product_qty': 5.0,
            'product_id': finished.id,
        })
        mo.action_confirm()

        # Test overview report values
        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        [line0, line1] = overview_values['data']['components']
        [repl0, repl1] = line0['replenishments'], line1['replenishments']
        self.assertEqual(len(repl0), 1)
        self.assertEqual(len(repl1), 1)
        self.assertEqual(repl0[0]['summary']['quantity'], 3)
        self.assertEqual(repl1[0]['summary']['quantity'], 5)

    def test_report_price_variants(self):
        """
        This tests the MO's report price when a variant is involved. It makes sure
        that the BoM price takes only the current variant and not all of them. It also
        tests that the lines that were removed from the MO but are still in the bom are
        used in the BoM cost computing. Lastly, it makes sure that Kits are also accounted
        for and used in the BoM cost as they should.
        """
        # Create a color variant, which will be used to create a Product
        attribute_color = self.env['product.attribute'].create({'name': 'Color'})
        value_black, value_white = self.env['product.attribute.value'].create([
            {
                'name': 'Black',
                'attribute_id': attribute_color.id,
            },
            {
                'name': 'White',
                'attribute_id': attribute_color.id,
            },
        ])
        # Create 3 product templates, one for the variants, to check to not all variants are used
        # to compute the cost of the MO, another one to make sure the 'missing components' are still
        # taken into account (they are the product that were removed from the MO but are still present
        # in the BoM), and the last one to make sure that kits are still taken in as well.
        product_variants, missing_product, kit_product = self.env['product.template'].create([
            {
                'name': 'Variant Product',
                'type': 'consu',
                'attribute_line_ids': [Command.create(
                    {
                        'attribute_id': attribute_color.id,
                        'value_ids': [
                            Command.link(value_black.id),
                            Command.link(value_white.id),
                        ],
                    },
                )],
            },
            {
                'name': 'Missing Component',
                'type': 'consu',
                'standard_price': 40,
            },
            {
                'name': 'Kit Product',
                'type': 'consu',
                'standard_price': 60,
            },
        ])

        variant_black = product_variants.product_variant_ids[0]
        variant_white = product_variants.product_variant_ids[1]
        variant_black.standard_price = 50
        variant_white.standard_price = 30
        bom_normal, _ = self.env['mrp.bom'].create([
            {
                'product_tmpl_id': product_variants.id,
                'type': 'normal',
                'bom_line_ids': [Command.create({
                    'product_id': missing_product.product_variant_id.id,
                    'product_qty': 1,
                }),
                Command.create({
                    'product_id': kit_product.product_variant_id.id,
                    'product_qty': 1,
                })],
            },
            {
                'product_tmpl_id': kit_product.id,
                'type': 'phantom',
                'bom_line_ids': [Command.create({
                    'product_id': missing_product.product_variant_id.id,
                    'product_qty': 1,
                })]
            },
        ])
        white_tmpl = bom_normal.product_tmpl_id.product_variant_ids.product_template_attribute_value_ids.filtered(lambda tmpl: tmpl.product_attribute_value_id == value_white)
        black_tmpl = bom_normal.product_tmpl_id.product_variant_ids.product_template_attribute_value_ids.filtered(lambda tmpl: tmpl.product_attribute_value_id == value_black)
        black_white_product, black_product, white_product = self.env['product.product'].create([{
                'name': 'Black White',
                'type': 'consu',
                'standard_price': 25,
            },
            {
                'name': 'Black Only',
                'type': 'consu',
                'standard_price': 15,
            },
            {
                'name': 'White Only',
                'type': 'consu',
                'standard_price': 10,
            },
        ])
        self.env['mrp.bom.line'].create([{
                'bom_id': bom_normal.id,
                'product_id': black_white_product.id,
                'product_qty': 1,
                'bom_product_template_attribute_value_ids': [Command.set([black_tmpl.id, white_tmpl.id])],
            },
            {
                'bom_id': bom_normal.id,
                'product_id': black_product.id,
                'product_qty': 1,
                'bom_product_template_attribute_value_ids': [Command.set([black_tmpl.id])],
            },
                        {
                'bom_id': bom_normal.id,
                'product_id': white_product.id,
                'product_qty': 1,
                'bom_product_template_attribute_value_ids': [Command.set([white_tmpl.id])],
            }
        ])
        mo = self.env['mrp.production'].create({
            'product_id': variant_black.id,
            'product_qty': 1,
            'bom_id': bom_normal.id,
        })
        mo_report = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(mo_report['data']['extras']['unit_bom_cost'], mo_report['data']['extras']['unit_mo_cost'], 'The BoM unit cost should be equal to the sum of the products of said BoM')
        # Check that the missing components (the components that were removed from the MO but are still in the BoM)
        # are taken into account when computing the BoM cost
        mo.move_raw_ids.filtered(lambda m: m.product_id == missing_product.product_variant_id and m.bom_line_id.bom_id.type != 'phantom').unlink()
        # When a product has two possible variants, and then is deleted, it should be taken in the missing components
        mo.move_raw_ids.filtered(lambda m: m.product_id == black_white_product and m.bom_line_id.bom_id.type != 'phantom').unlink()
        mo_report = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(mo_report['data']['extras']['unit_bom_cost'], mo_report['data']['extras']['unit_mo_cost'] + missing_product.standard_price + black_white_product.standard_price, 'The BoM unit cost should take the missing components into account, which are the deleted MO lines')

    def test_mo_overview_operation_cost(self):
        """ Test that operations correctly compute their cost depending on their cost_mode. """
        expedition_33 = self.product
        lumiere = self.env['mrp.workcenter'].create({
            'name': 'Lumière',
            'costs_hour': 33,
        })
        bom_baguette = self.env['mrp.bom'].create({
            'product_id': expedition_33.id,
            'product_tmpl_id': expedition_33.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'operation_ids': [
                Command.create({
                    'name': 'Get on a boat',
                    'workcenter_id': lumiere.id,
                    'time_cycle': 60,
                    'sequence': 1,
                    'cost_mode': 'actual'
                }),
                Command.create({
                    'name': 'Die on a beach',
                    'workcenter_id': lumiere.id,
                    'time_cycle': 60,
                    'sequence': 2,
                    'cost_mode': 'estimated'
                }),
            ],
        })

        mo = self.env['mrp.production'].create({
            'name': 'MO',
            'product_qty': 1.0,
            'product_id': expedition_33.id,
        })
        mo.action_confirm()
        mo.workorder_ids.duration = 10

        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(overview_values['data']['operations']['details'][0]['mo_cost'], 33.0)
        self.assertEqual(overview_values['data']['operations']['details'][0]['real_cost'], 5.5)
        self.assertEqual(overview_values['data']['operations']['details'][1]['mo_cost'], 33.0)
        self.assertEqual(overview_values['data']['operations']['details'][1]['real_cost'], 33.0)

        # Costs should stay the same for a done MO and/or if the cost_mode of the operation is changed
        mo.button_mark_done()
        bom_baguette.operation_ids.filtered(lambda o: o.cost_mode == 'estimated').cost_mode = 'actual'
        overview_values = self.env['report.mrp.report_mo_overview'].get_report_values(mo.id)
        self.assertEqual(overview_values['data']['operations']['details'][0]['mo_cost'], 33.0)
        self.assertEqual(overview_values['data']['operations']['details'][0]['real_cost'], 5.5)
        self.assertEqual(overview_values['data']['operations']['details'][1]['mo_cost'], 33.0)
        self.assertEqual(overview_values['data']['operations']['details'][1]['real_cost'], 33.0)
