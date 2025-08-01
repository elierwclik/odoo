# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, datetime, timedelta

from odoo.tests import Form, TransactionCase
from odoo import Command


class TestReportsCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Partner'})
        cls.ModelDataObj = cls.env['ir.model.data']
        cls.picking_type_in = cls.env['stock.picking.type'].browse(cls.ModelDataObj._xmlid_to_res_id('stock.picking_type_in'))
        cls.picking_type_out = cls.env['stock.picking.type'].browse(cls.ModelDataObj._xmlid_to_res_id('stock.picking_type_out'))
        cls.supplier_location = cls.env['stock.location'].browse(cls.ModelDataObj._xmlid_to_res_id('stock.stock_location_suppliers'))
        cls.stock_location = cls.env['stock.location'].browse(cls.ModelDataObj._xmlid_to_res_id('stock.stock_location_stock'))

        cls.product1 = cls.env['product.product'].create({
            'name': 'Mellohi"',
            'is_storable': True,
            'categ_id': cls.env.ref('product.product_category_goods').id,
            'tracking': 'lot',
            'default_code': 'C4181234""154654654654',
            'barcode': 'scan""me'
        })
        cls.serial_product = cls.env['product.product'].create({
            'name': 'simple prod',
            'is_storable': True,
            'tracking': 'serial',
        })

        product_form = Form(cls.env['product.product'])
        product_form.is_storable = True
        product_form.name = 'Product'
        product_form.categ_id = cls.env.ref('product.product_category_goods')
        cls.product = product_form.save()
        cls.product_template = cls.product.product_tmpl_id
        cls.wh_2 = cls.env['stock.warehouse'].create({
            'name': 'Evil Twin Warehouse',
            'code': 'ETWH',
        })

    def get_report_forecast(self, product_template_ids=False, product_variant_ids=False, context=False):
        if product_template_ids:
            report = self.env['stock.forecasted_product_template']
            product_ids = product_template_ids
        elif product_variant_ids:
            report = self.env['stock.forecasted_product_product']
            product_ids = product_template_ids
        if context:
            report = report.with_context(context)
        report_values = report.get_report_values(docids=product_ids)
        docs = report_values['docs']
        lines = docs['lines']
        return report_values, docs, lines


class TestReports(TestReportsCommon):

    def test_product_label_reports(self):
        """ Test that all the special characters are correctly rendered for the product name, the default code and the barcode.
            In this test we test that the double quote is rendered correctly.
        """
        report = self.env.ref('stock.label_product_product')
        target = b'\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FDscan""me^FS\n^XZj\n\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FDscan""me^FS\n^XZj\n'
        rendering, qweb_type = report._render_qweb_text('stock.label_product_product', self.product1.product_tmpl_id.id, {'quantity_by_product': {self.product1.product_tmpl_id.id: 2}, 'active_model': 'product.template', 'zpl_template': 'normal'})
        self.assertEqual(target, rendering.replace(b' ', b''), 'Product name, default code or barcode is not correctly rendered, make sure the quotes are escaped correctly')
        self.assertEqual(qweb_type, 'text', 'the report type is not good')

    def test_product_label_custom_barcode_reports(self):
        """ Test that the custom barcodes are correctly rendered with special characters."""
        report = self.env.ref('stock.label_product_product')
        target = b'\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FD123"barcode^FS\n^XZj\n\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FD123"barcode^FS\n^XZj\n\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FDbarcode"456^FS\n^XZj\n\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^FO35,77^BY2^BCN,100,Y,N,N^FDbarcode"456^FS\n^XZj\n'
        rendering, qweb_type = report._render_qweb_text('stock.label_product_product', self.product1.product_tmpl_id.id, {'custom_barcodes': {self.product1.product_tmpl_id.id: [('123"barcode', 2), ('barcode"456', 2)]}, 'quantity_by_product': {}, 'active_model': 'product.template', 'zpl_template': 'normal'})
        self.assertEqual(target, rendering.replace(b' ', b''), 'Custom barcodes are most likely not corretly rendered, make sure the quotes are escaped correctly')
        self.assertEqual(qweb_type, 'text', 'the report type is not good')

    def test_reports_with_special_characters(self):
        product_test = self.env['product.product'].create({
            'name': 'Mellohi"',
            'is_storable': True,
            'tracking': 'lot',
            'default_code': 'C4181234""154654654654',
            'barcode': '9745213796142'
        })

        lot1 = self.env['stock.lot'].create({
            'name': 'Volume-Beta"',
            'product_id': product_test.id,
        })
        #add group to the user
        self.env.user.group_ids += self.env.ref('stock.group_stock_lot_print_gs1')
        report = self.env.ref('stock.label_lot_template')
        target = b'\n\n^XA^CI28\n^FO100,50\n^A0N,44,33^FD[C4181234""154654654654]Mellohi"^FS\n^FO100,100\n^A0N,44,33^FDLN/SN:Volume-Beta"^FS\n\n^FO425,150^BY3\n^BXN,8,200\n^FD010974521379614210Volume-Beta"^FS\n^XZ\n'

        rendering, qweb_type = report._render_qweb_text('stock.label_lot_template', lot1.id)
        self.assertEqual(target, rendering.replace(b' ', b''), 'The rendering is not good, make sure quotes are correctly escaped')
        self.assertEqual(qweb_type, 'text', 'the report type is not good')

    def test_reports_product_no_barcode(self):
        """ Test that product without barcode is correctly rendered without a barcode.
        """
        report = self.env.ref('stock.label_product_product')
        self.product1.barcode = False
        target = b'\n\n^XA^CI28\n\n^FT35,40^A0N,25^FD[C4181234""154654654654]Mellohi"^FS\n^XZj\n'
        rendering, qweb_type = report._render_qweb_text('stock.label_product_product', self.product1.product_tmpl_id.id, {'quantity_by_product': {self.product1.product_tmpl_id.id: 1}, 'active_model': 'product.template', 'zpl_template': 'normal'})
        self.assertEqual(target, rendering.replace(b' ', b''), 'Product name, default code or barcode is not correctly rendered, make sure the quotes are escaped correctly')
        self.assertEqual(qweb_type, 'text', 'the report type is not good')

    def test_report_quantity_1(self):
        product_form = Form(self.env['product.product'])
        product_form.is_storable = True
        product_form.name = 'Product'
        product = product_form.save()

        warehouse = self.env['stock.warehouse'].search([], limit=1)
        stock = self.env['stock.location'].create({
            'name': 'New Stock',
            'usage': 'internal',
            'location_id': warehouse.view_location_id.id,
        })

        # Inventory Adjustement of 50.0 today.
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': stock.id,
            'inventory_quantity': 50
        }).action_apply_inventory()
        self.env.flush_all()
        report_records_today = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            [], ['product_qty:sum'])
        report_records_tomorrow = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() + timedelta(days=1))],
            [], ['product_qty:sum'])
        report_records_yesterday = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() - timedelta(days=1))],
            [], ['product_qty:sum'])
        self.assertEqual(report_records_today[0][0], 50.0)
        self.assertEqual(report_records_tomorrow[0][0], 50.0)
        self.assertEqual(report_records_yesterday[0][0], 0.0)

        # Delivery of 20.0 units tomorrow
        move_out = self.env['stock.move'].create({
            'date': datetime.now() + timedelta(days=1),
            'location_id': stock.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 20.0,
        })
        self.env.flush_all()
        report_records_tomorrow = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() + timedelta(days=1))],
            [], ['product_qty:sum'])
        self.assertEqual(report_records_tomorrow[0][0], 50.0)
        move_out._action_confirm()
        self.env.flush_all()
        report_records_tomorrow = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() + timedelta(days=1))],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'forecast'), 30.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'out'), -20.0)
        report_records_today = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records_today if state == 'forecast'), 50.0)

        # Receipt of 10.0 units tomorrow
        move_in = self.env['stock.move'].create({
            'date': datetime.now() + timedelta(days=1),
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': stock.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 10.0,
        })
        move_in._action_confirm()
        self.env.flush_all()
        report_records_tomorrow = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() + timedelta(days=1))],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'forecast'), 40.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'out'), -20.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'in'), 10.0)
        report_records_today = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records_today if state == 'forecast'), 50.0)

        # Delivery of 20.0 units tomorrow
        move_out = self.env['stock.move'].create({
            'date': datetime.now() - timedelta(days=1),
            'location_id': stock.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 30.0,
        })
        move_out._action_confirm()
        self.env.flush_all()
        report_records_today = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            ['state'], ['product_qty:sum'])
        report_records_tomorrow = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() + timedelta(days=1))],
            ['state'], ['product_qty:sum'])
        report_records_yesterday = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today() - timedelta(days=1))],
            ['state'], ['product_qty:sum'])

        self.assertEqual(sum(product_qty for state, product_qty in report_records_yesterday if state == 'forecast'), -30.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_yesterday if state == 'out'), -30.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_yesterday if state == 'in'), 0.0)

        self.assertEqual(sum(product_qty for state, product_qty in report_records_today if state == 'forecast'), 20.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_today if state == 'out'), 0.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_today if state == 'in'), 0.0)

        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'forecast'), 10.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'out'), -20.0)
        self.assertEqual(sum(product_qty for state, product_qty in report_records_tomorrow if state == 'in'), 10.0)

    def test_report_quantity_2(self):
        """ Not supported case.
        """
        product_form = Form(self.env['product.product'])
        product_form.is_storable = True
        product_form.name = 'Product'
        product = product_form.save()

        warehouse = self.env['stock.warehouse'].search([], limit=1)
        stock = self.env['stock.location'].create({
            'name': 'Stock Under Warehouse',
            'usage': 'internal',
            'location_id': warehouse.view_location_id.id,
        })
        stock_without_wh = self.env['stock.location'].create({
            'name': 'Stock Outside Warehouse',
            'usage': 'internal',
            'location_id': self.env.ref('stock.stock_location_locations').id,
        })
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': stock.id,
            'inventory_quantity': 50
        }).action_apply_inventory()
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': product.id,
            'location_id': stock_without_wh.id,
            'inventory_quantity': 50
        }).action_apply_inventory()
        move = self.env['stock.move'].create({
            'location_id': stock.id,
            'location_dest_id': stock_without_wh.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 10.0,
        })
        move._action_confirm()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today()), ('warehouse_id', '!=', False)],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records if state == 'forecast'), 40.0)
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records if state == 'forecast'), 40.0)
        move = self.env['stock.move'].create({
            'location_id': stock_without_wh.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 10.0,
        })
        move._action_confirm()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            ['state'], ['product_qty:sum'])
        self.assertEqual(sum(product_qty for state, product_qty in report_records if state == 'forecast'), 40.0)

    def test_report_quantity_3(self):
        product_form = Form(self.env['product.product'])
        product_form.is_storable = True
        product_form.name = 'Product'
        product = product_form.save()

        warehouse = self.env['stock.warehouse'].search([], limit=1)
        stock = self.env['stock.location'].create({
            'name': 'Rack',
            'usage': 'view',
            'location_id': warehouse.view_location_id.id,
        })
        stock_real_loc = self.env['stock.location'].create({
            'name': 'Drawer',
            'usage': 'internal',
            'location_id': stock.id,
        })

        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], 0.0)

        # Receipt of 20.0 units tomorrow
        move_in = self.env['stock.move'].create({
            'location_id': self.env.ref('stock.stock_location_suppliers').id,
            'location_dest_id': stock.id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 20.0,
        })
        move_in._action_confirm()
        move_in.move_line_ids.location_dest_id = stock_real_loc.id
        move_in.move_line_ids.quantity = 20.0
        move_in.picked = True
        move_in._action_done()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], 20.0)

        # Delivery of 10.0 units tomorrow
        move_out = self.env['stock.move'].create({
            'location_id': stock.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'product_id': product.id,
            'product_uom': product.uom_id.id,
            'product_uom_qty': 10.0,
        })
        move_out._action_confirm()
        move_out._action_assign()
        move_out.move_line_ids.quantity = 10.0
        move_out.picked = True
        move_out._action_done()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('product_id', '=', product.id), ('date', '=', date.today())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], 10.0)

    def test_report_quantity_4(self):
        """ Checks the predicted quantity works in a multi-step setup.
        """
        now = datetime.now()
        customer_loc, supplier_loc = self.env['stock.warehouse']._get_partner_locations()
        self.wh_2.write({'reception_steps': 'two_steps', 'delivery_steps': 'pick_ship'})

        # Pick move for delivery of 5 units in 2 days
        move_pick = self.env['stock.move'].create({
            'picking_type_id': self.wh_2.pick_type_id.id,
            'location_id': self.wh_2.lot_stock_id.id,
            'location_final_id': customer_loc.id,
            'product_id': self.product1.id,
            'product_uom_qty': 5.0,
            'date': now + timedelta(days=2),
        })
        move_pick._action_confirm()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('state', '=', 'forecast'), ('product_id', '=', self.product1.id), ('date', '=', now.date())],
            [], ['product_qty:sum'])
        self.assertFalse(report_records[0][0], "Forecast should still be at 0 today, so no records.")
        report_records = self.env['report.stock.quantity']._read_group(
            [('state', '=', 'forecast'), ('product_id', '=', self.product1.id), ('date', '=', (now + timedelta(days=2)).date())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], -5)

        # In move for receipt of 10 units tomorrow
        move_in = self.env['stock.move'].create({
            'picking_type_id': self.wh_2.in_type_id.id,
            'location_id': supplier_loc.id,
            'location_final_id': self.wh_2.lot_stock_id.id,
            'product_id': self.product1.id,
            'product_uom_qty': 10.0,
            'date': now + timedelta(days=1),
        })
        move_in._action_confirm()
        self.env.flush_all()
        report_records = self.env['report.stock.quantity']._read_group(
            [('state', '=', 'forecast'), ('product_id', '=', self.product1.id), ('date', '=', now.date())],
            [], ['product_qty:sum'])
        self.assertFalse(report_records[0][0], "Forecast should still be at 0 today, so no records.")
        report_records = self.env['report.stock.quantity']._read_group(
            [('state', '=', 'forecast'), ('product_id', '=', self.product1.id), ('date', '=', (now + timedelta(days=1)).date())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], 10)
        report_records = self.env['report.stock.quantity']._read_group(
            [('state', '=', 'forecast'), ('product_id', '=', self.product1.id), ('date', '=', (now + timedelta(days=2)).date())],
            [], ['product_qty:sum'])
        self.assertEqual(report_records[0][0], 5)

    def test_report_forecast_1(self):
        """ Checks report data for product is empty. Then creates and process
        some operations and checks the report data accords rigthly these operations.
        """
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)

        # Creates a receipt then checks draft picking quantities.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt = receipt_form.save()
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 2
        receipt = receipt_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 2)
        self.assertEqual(draft_picking_qty['out'], 0)

        # Creates a delivery then checks draft picking quantities.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery = delivery_form.save()
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery = delivery_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 2)
        self.assertEqual(draft_picking_qty['out'], 5)

        # Confirms the delivery: must have one report line and no more pending qty out now.
        delivery.action_confirm()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 1, "Must have 1 line.")
        self.assertEqual(draft_picking_qty['in'], 2)
        self.assertEqual(draft_picking_qty['out'], 0)
        delivery_line = lines[0]
        self.assertEqual(delivery_line['quantity'], 5)
        self.assertEqual(delivery_line['replenishment_filled'], False)
        self.assertEqual(delivery_line['document_out']['id'], delivery.id)

        # Confirms the receipt, must have two report lines now:
        #   - line with 2 qty (from the receipt to the delivery)
        #   - line with 3 qty (delivery, unavailable)
        receipt.action_confirm()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 2, "Must have 2 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        fulfilled_line = lines[0]
        unavailable_line = lines[1]
        self.assertEqual(fulfilled_line['replenishment_filled'], True)
        self.assertEqual(fulfilled_line['quantity'], 2)
        self.assertEqual(fulfilled_line['document_in']['id'], receipt.id)
        self.assertEqual(fulfilled_line['document_out']['id'], delivery.id)
        self.assertEqual(unavailable_line['replenishment_filled'], False)
        self.assertEqual(unavailable_line['quantity'], 3)
        self.assertEqual(unavailable_line['document_out']['id'], delivery.id)

        # Creates a new receipt for the remaining quantity, confirm it...
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        receipt2 = receipt_form.save()
        receipt2.action_confirm()

        # ... and valid the first one.
        receipt_form = Form(receipt)
        with receipt_form.move_ids_without_package.edit(0) as move_line:
            move_line.quantity = 2
        receipt = receipt_form.save()
        receipt.move_ids.picked = True
        receipt.button_validate()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 2, "Still must have 2 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        line1 = lines[0]
        line2 = lines[1]
        # First line must be fulfilled thanks to the stock on hand.
        self.assertEqual(line1['quantity'], 2)
        self.assertEqual(line1['replenishment_filled'], True)
        self.assertEqual(line1['document_in'], False)
        self.assertEqual(line1['document_out']['id'], delivery.id)
        # Second line must be linked to the second receipt.
        self.assertEqual(line2['quantity'], 3)
        self.assertEqual(line2['replenishment_filled'], True)
        self.assertEqual(line2['document_in']['id'], receipt2.id)
        self.assertEqual(line2['document_out']['id'], delivery.id)

    def test_report_forecast_2_replenishments_order(self):
        """ Creates a receipt then creates a delivery using half of the receipt quantity.
        Checks replenishment lines are correctly sorted (assigned first, unassigned at the end).
        """
        # Creates a receipt then checks draft picking quantities.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 6
        receipt = receipt_form.save()
        receipt.action_confirm()

        # Creates a delivery then checks draft picking quantities.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        delivery = delivery_form.save()
        delivery.action_confirm()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        self.assertEqual(len(lines), 2, "Must have 2 line.")
        line_1 = lines[0]
        line_2 = lines[1]
        self.assertEqual(line_1['document_in']['id'], receipt.id)
        self.assertEqual(line_1['document_out']['id'], delivery.id)
        self.assertEqual(line_2['document_in']['id'], receipt.id)
        self.assertEqual(line_2['document_out'], False)

    def test_report_forecast_3_sort_by_date(self):
        """ Creates some deliveries with different dates and checks the report
        lines are correctly sorted by date. Then, creates some receipts and
        check their are correctly linked according to their date.
        """
        today = datetime.today()
        one_hours = timedelta(hours=1)
        one_day = timedelta(days=1)
        one_month = timedelta(days=30)
        # Creates a bunch of deliveries with different date.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_1 = delivery_form.save()
        delivery_1.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today + one_hours
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_2 = delivery_form.save()
        delivery_2.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today - one_hours
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_3 = delivery_form.save()
        delivery_3.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today + one_day
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_4 = delivery_form.save()
        delivery_4.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today - one_day
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_5 = delivery_form.save()
        delivery_5.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today + one_month
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_6 = delivery_form.save()
        delivery_6.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = today - one_month
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery_7 = delivery_form.save()
        delivery_7.action_confirm()

        # Order must be: 7, 5, 3, 1, 2, 4, 6
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 7, "The report must have 7 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery_7.id)
        self.assertEqual(lines[1]['document_out']['id'], delivery_5.id)
        self.assertEqual(lines[2]['document_out']['id'], delivery_3.id)
        self.assertEqual(lines[3]['document_out']['id'], delivery_1.id)
        self.assertEqual(lines[4]['document_out']['id'], delivery_2.id)
        self.assertEqual(lines[5]['document_out']['id'], delivery_4.id)
        self.assertEqual(lines[6]['document_out']['id'], delivery_6.id)

        # Creates 3 receipts for 20 units.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = today + one_month
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        receipt_1 = receipt_form.save()
        receipt_1.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = today - one_month
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        receipt_2 = receipt_form.save()
        receipt_2.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = today - one_hours
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 10
        receipt_3 = receipt_form.save()
        receipt_3.action_confirm()

        # Check report lines (link and order).
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 7, "The report must have 7 line.")
        self.assertEqual(draft_picking_qty['in'], 0)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery_7.id)
        self.assertEqual(lines[0]['document_in']['id'], receipt_2.id)
        self.assertEqual(lines[0]['is_late'], False)
        self.assertEqual(lines[1]['document_out']['id'], delivery_5.id)
        self.assertEqual(lines[1]['document_in']['id'], receipt_3.id)
        self.assertEqual(lines[1]['is_late'], True)
        self.assertEqual(lines[2]['document_out']['id'], delivery_3.id)
        self.assertEqual(lines[2]['document_in']['id'], receipt_3.id)
        self.assertEqual(lines[2]['is_late'], False)
        self.assertEqual(lines[3]['document_out']['id'], delivery_1.id)
        self.assertEqual(lines[3]['document_in']['id'], receipt_1.id)
        self.assertEqual(lines[3]['is_late'], True)
        self.assertEqual(lines[4]['document_out']['id'], delivery_2.id)
        self.assertEqual(lines[4]['document_in'], False)
        self.assertEqual(lines[5]['document_out']['id'], delivery_4.id)
        self.assertEqual(lines[5]['document_in'], False)
        self.assertEqual(lines[6]['document_out']['id'], delivery_6.id)
        self.assertEqual(lines[6]['document_in'], False)

    def test_report_forecast_4_intermediate_transfers(self):
        """ Create a receipt in 3 steps and check the report line.
        """
        grp_multi_loc = self.env.ref('stock.group_stock_multi_locations')
        grp_multi_routes = self.env.ref('stock.group_adv_location')
        self.env.user.write({'group_ids': [(4, grp_multi_loc.id)]})
        self.env.user.write({'group_ids': [(4, grp_multi_routes.id)]})
        # Warehouse config.
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.reception_steps = 'three_steps'
        # Product config.
        self.product.write({'route_ids': [(4, self.env.ref('stock.route_warehouse0_mto').id)]})
        # Create a RR
        pg1 = self.env['procurement.group'].create({})
        reordering_rule = self.env['stock.warehouse.orderpoint'].create({
            'name': 'Product RR',
            'location_id': warehouse.lot_stock_id.id,
            'product_id': self.product.id,
            'product_min_qty': 5,
            'product_max_qty': 10,
            'group_id': pg1.id,
        })
        reordering_rule.action_replenish()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        pickings = self.env['stock.picking'].search([('product_id', '=', self.product.id)])
        receipt = pickings.filtered(lambda p: p.picking_type_id.id == self.picking_type_in.id)

        # The Forecasted Report don't show intermediate moves, it must display only ingoing/outgoing documents.
        self.assertEqual(len(lines), 1, "The report must have only 1 line.")
        self.assertEqual(lines[0]['document_in']['id'], receipt.id, "The report must only show the receipt.")
        self.assertEqual(lines[0]['document_out'], False)
        self.assertEqual(lines[0]['quantity'], reordering_rule.product_max_qty)

    def test_report_forecast_5_multi_warehouse(self):
        """ Create some transfer for two different warehouses and check the
        report display the good moves according to the selected warehouse.
        """
        # Warehouse config.
        wh_2 = self.wh_2
        picking_type_out_2 = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', wh_2.id),
        ])

        # Creates a delivery then checks draft picking quantities.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery = delivery_form.save()
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        delivery = delivery_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['out'], 5)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0)
        self.assertEqual(draft_picking_qty['out'], 0)

        # Confirm the delivery -> The report must now have 1 line.
        delivery.action_confirm()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 1)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery.id)
        self.assertEqual(lines[0]['quantity'], 5)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0)
        self.assertEqual(draft_picking_qty['out'], 0)

        # Creates a delivery for the second warehouse.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_out_2
        delivery_2 = delivery_form.save()
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 8
        delivery_2 = delivery_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 1)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery.id)
        self.assertEqual(lines[0]['quantity'], 5)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0)
        self.assertEqual(draft_picking_qty['out'], 8)
        # Confirm the second delivery -> The report must now have 1 line.
        delivery_2.action_confirm()
        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 1)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery.id)
        self.assertEqual(lines[0]['quantity'], 5)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 1)
        self.assertEqual(draft_picking_qty['out'], 0)
        self.assertEqual(lines[0]['document_out']['id'], delivery_2.id)
        self.assertEqual(lines[0]['quantity'], 8)

    def test_report_forecast_5_multi_warehouse_chain(self):
        """ Create a MTO chain inter warehouse, the forecast report should ignore the
        "not current" warehouse"""

        wh_2 = self.wh_2
        wh = self.env.ref('stock.warehouse0')
        # replenish rule
        replenish_route = self.env['stock.route'].create({
            'name': "replenish",
            'rule_ids': [Command.create({
                'name': "replenish",
                'action': "pull",
                'location_src_id': wh_2.lot_stock_id.id,
                'location_dest_id': wh.lot_stock_id.id,
                'picking_type_id': wh_2.int_type_id.id,
                'location_dest_from_rule': True,
            })],
        })
        self.env.ref('stock.route_warehouse0_mto').active = True
        self.product.route_ids = [Command.set([self.env.ref('stock.route_warehouse0_mto').id, replenish_route.id])]
        self.env['stock.quant']._update_available_quantity(self.product, wh_2.lot_stock_id, 5)

        # Creates a delivery to empty WH
        delivery = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': wh.out_type_id.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 5,
                'product_uom': self.product.uom_id.id,
                'location_id': wh.lot_stock_id.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'procure_method': 'make_to_order',
            })],
        })
        delivery.action_confirm()

        # Check the WH2 ressuply WH
        inter_wh_delivery = self.env['stock.move'].search([
            ('picking_type_id', '=', wh_2.int_type_id.id),
            ('location_id', '=', wh_2.lot_stock_id.id),
            ('location_dest_id', '=', wh.lot_stock_id.id),
            ('product_id', '=', self.product.id),
        ])
        self.assertEqual(len(inter_wh_delivery), 1)
        _, _, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh.id},
        )
        # The forecast should show 1 line linking the delivery with the replenish
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['document_out']['id'], delivery.id)
        self.assertEqual(lines[0]['document_in']['id'], inter_wh_delivery.picking_id.id)

    def test_report_forecast_6_multi_company(self):
        """ Create transfers for two different companies and check report
        display the right transfers.
        """
        # Configure second warehouse.
        company_2 = self.env['res.company'].create({'name': 'Aperture Science'})
        wh_2 = self.env['stock.warehouse'].search([('company_id', '=', company_2.id)])
        wh_2_picking_type_in = wh_2.in_type_id

        # Creates a receipt then checks draft picking quantities.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        wh_1_receipt = receipt_form.save()
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 2
        wh_1_receipt = receipt_form.save()

        # Creates a receipt then checks draft picking quantities.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = wh_2_picking_type_in
        wh_2_receipt = receipt_form.save()
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        wh_2_receipt = receipt_form.save()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 2)
        self.assertEqual(draft_picking_qty['out'], 0)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        draft_picking_qty = docs['draft_picking_qty']
        self.assertEqual(len(lines), 0, "Must have 0 line.")
        self.assertEqual(draft_picking_qty['in'], 5)
        self.assertEqual(draft_picking_qty['out'], 0)

        # Confirm the receipts -> The report must now have one line for each company.
        wh_1_receipt.action_confirm()
        wh_2_receipt.action_confirm()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        self.assertEqual(len(lines), 1, "Must have 1 line.")
        self.assertEqual(lines[0]['document_in']['id'], wh_1_receipt.id)
        self.assertEqual(lines[0]['quantity'], 2)

        report_values, docs, lines = self.get_report_forecast(
            product_template_ids=self.product_template.ids,
            context={'warehouse_id': wh_2.id},
        )
        self.assertEqual(len(lines), 1, "Must have 1 line.")
        self.assertEqual(lines[0]['document_in']['id'], wh_2_receipt.id)
        self.assertEqual(lines[0]['quantity'], 5)

    def test_report_forecast_7_multiple_variants(self):
        """ Create receipts for different variant products and check the report
        work well with them.Also, check the receipt/delivery lines are correctly
        linked depending of their product variant.
        """
        # Create some variant's attributes.
        product_attr_color = self.env['product.attribute'].create({'name': 'Color'})
        color_gray = self.env['product.attribute.value'].create({
            'name': 'Old Fashioned Gray',
            'attribute_id': product_attr_color.id,
        })
        color_blue = self.env['product.attribute.value'].create({
            'name': 'Electric Blue',
            'attribute_id': product_attr_color.id,
        })
        product_attr_size = self.env['product.attribute'].create({'name': 'size'})
        size_pocket = self.env['product.attribute.value'].create({
            'name': 'Pocket',
            'attribute_id': product_attr_size.id,
        })
        size_xl = self.env['product.attribute.value'].create({
            'name': 'XL',
            'attribute_id': product_attr_size.id,
        })

        # Create a new product and set some variants on the product.
        product_template = self.env['product.template'].create({
            'name': 'Game Joy',
            'is_storable': True,
            'attribute_line_ids': [
                (0, 0, {
                    'attribute_id': product_attr_color.id,
                    'value_ids': [(6, 0, [color_gray.id, color_blue.id])]
                }),
                (0, 0, {
                    'attribute_id': product_attr_size.id,
                    'value_ids': [(6, 0, [size_pocket.id, size_xl.id])]
                }),
            ],
        })
        gamejoy_pocket_gray = product_template.product_variant_ids[0]
        gamejoy_xl_gray = product_template.product_variant_ids[1]
        gamejoy_pocket_blue = product_template.product_variant_ids[2]
        gamejoy_xl_blue = product_template.product_variant_ids[3]

        # Create two receipts.
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_pocket_gray
            move_line.product_uom_qty = 8
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_pocket_blue
            move_line.product_uom_qty = 4
        receipt_1 = receipt_form.save()
        receipt_1.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_pocket_gray
            move_line.product_uom_qty = 2
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_xl_gray
            move_line.product_uom_qty = 10
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_xl_blue
            move_line.product_uom_qty = 12
        receipt_2 = receipt_form.save()
        receipt_2.action_confirm()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_template.ids)
        self.assertEqual(len(lines), 5, "Must have 5 lines.")
        self.assertTrue(all(product_variant['id'] in product_template.product_variant_ids.ids for product_variant in docs['product_variants']))

        # Create a delivery for one of these products and check the report lines
        # are correctly linked to the good receipts.
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = gamejoy_pocket_gray
            move_line.product_uom_qty = 10
        delivery = delivery_form.save()
        delivery.action_confirm()

        report_values, docs, lines = self.get_report_forecast(product_template_ids=product_template.ids)
        self.assertEqual(len(lines), 5, "Still must have 5 lines.")
        self.assertEqual(docs['product_variants_ids'], product_template.product_variant_ids.ids)
        # First and second lines should be about the "Game Joy Pocket (gray)"
        # and must link the delivery with the two receipt lines.
        line_1 = lines[0]
        line_2 = lines[1]
        self.assertEqual(line_1['product']['id'], gamejoy_pocket_gray.id)
        self.assertEqual(line_1['quantity'], 8)
        self.assertTrue(line_1['replenishment_filled'])
        self.assertEqual(line_1['document_in']['id'], receipt_1.id)
        self.assertEqual(line_1['document_out']['id'], delivery.id)
        self.assertEqual(line_2['product']['id'], gamejoy_pocket_gray.id)
        self.assertEqual(line_2['quantity'], 2)
        self.assertTrue(line_2['replenishment_filled'])
        self.assertEqual(line_2['document_in']['id'], receipt_2.id)
        self.assertEqual(line_2['document_out']['id'], delivery.id)

    def test_report_forecast_8_delivery_to_receipt_link(self):
        """
        Create 2 deliveries, and 1 receipt tied to the second delivery.
        The report should show the source document as the 2nd delivery, and show the first
        delivery completely unfilled.
        """
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 100
        delivery = delivery_form.save()
        delivery.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 200
        delivery2 = delivery_form.save()
        delivery2.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt = receipt_form.save()
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 200
        receipt = receipt_form.save()
        receipt.move_ids[0].write({
            'move_dest_ids': [(4, delivery2.move_ids[0].id)],
        })
        receipt.action_confirm()

        # Test compute _compute_forecast_information
        self.assertEqual(delivery.move_ids.forecast_availability, -100)
        self.assertEqual(delivery2.move_ids.forecast_availability, 200)
        self.assertFalse(delivery.move_ids.forecast_expected_date)
        self.assertEqual(delivery2.move_ids.forecast_expected_date, receipt.move_ids.date)

        _, _, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)

        self.assertEqual(len(lines), 2, 'Only 2 lines')
        delivery_line = [l for l in lines if l['document_out']['id'] == delivery.id][0]
        self.assertTrue(delivery_line, 'No line for delivery 1')
        self.assertFalse(delivery_line['replenishment_filled'])
        delivery2_line = [l for l in lines if l['document_out']['id'] == delivery2.id][0]
        self.assertTrue(delivery2_line, 'No line for delivery 2')
        self.assertTrue(delivery2_line['replenishment_filled'])

    def test_report_forecast_9_delivery_to_receipt_link_over_received(self):
        """
        Create 2 deliveries, and 1 receipt tied to the second delivery.
        Set the quantity on the receipt to be enough for BOTH deliveries.
        For example, this can happen if they have manually increased the quantity on the generated PO.
        The report should show both deliveries fulfilled.
        """
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 100
        delivery = delivery_form.save()
        delivery.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 200
        delivery2 = delivery_form.save()
        delivery2.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt = receipt_form.save()
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 300
        receipt = receipt_form.save()
        receipt.move_ids[0].write({
            'move_dest_ids': [(4, delivery2.move_ids[0].id)],
        })
        receipt.action_confirm()

        # Test compute _compute_forecast_information
        self.assertEqual(delivery.move_ids.forecast_availability, 100)
        self.assertEqual(delivery2.move_ids.forecast_availability, 200)
        self.assertEqual(delivery.move_ids.forecast_expected_date, receipt.move_ids.date)
        self.assertEqual(delivery2.move_ids.forecast_expected_date, receipt.move_ids.date)

        _, _, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)

        self.assertEqual(len(lines), 2, 'Only 2 lines')
        delivery_line = [l for l in lines if l['document_out']['id'] == delivery.id][0]
        self.assertTrue(delivery_line, 'No line for delivery 1')
        self.assertTrue(delivery_line['replenishment_filled'])
        delivery2_line = [l for l in lines if l['document_out']['id'] == delivery2.id][0]
        self.assertTrue(delivery2_line, 'No line for delivery 2')
        self.assertTrue(delivery2_line['replenishment_filled'])

    def test_report_forecast_10_report_line_corresponding_to_picking_highlighted(self):
        """ When accessing the report from a stock move, checks if the correct picking is highlighted in the report
            and if the forecasted availability for incoming and outcoming moves is correct
        """
        # Creation of one delivery with date 'today'
        delivery_form = Form(self.env['stock.picking'])
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.scheduled_date = date.today()
        with delivery_form.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 200
        delivery1 = delivery_form.save()
        delivery1.action_confirm()

        # Creation of one receipt with date 'today + 1' and smaller qty than the delivery
        scheduled_date1 = datetime.now() + timedelta(days=1)
        receipt_form = Form(self.env['stock.picking'])
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = scheduled_date1
        with receipt_form.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 150
        receipt1 = receipt_form.save()
        receipt1.action_confirm()
        self.assertEqual(delivery1.move_ids.forecast_availability, -50.0)

        # Creation of an identical receipt which should lead to a positive forecast availability
        scheduled_date2 = datetime.now() + timedelta(days=3)
        receipt_form = Form(self.env['stock.picking'])
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = scheduled_date2
        with receipt_form.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 50
        receipt2 = receipt_form.save()
        receipt2.action_confirm()

        # Check forecast_information of delivery1
        delivery1.move_ids._compute_forecast_information()  # Because depends not "complete"
        self.assertEqual(delivery1.move_ids.forecast_availability, 200)
        self.assertEqual(delivery1.move_ids.forecast_expected_date, scheduled_date2)

        receipt2.move_ids.quantity = receipt2.move_ids.product_uom_qty
        receipt2.move_ids.picked = True
        receipt2.button_validate()
        # Check forecast_information of delivery1, because the receipt2 as been validate the forecast_expected_date == receipt1.scheduled_date
        delivery1.move_ids._compute_forecast_information()
        self.assertEqual(delivery1.move_ids.forecast_availability, 200)
        self.assertEqual(delivery1.move_ids.forecast_expected_date, scheduled_date1)

        delivery2 = delivery1.copy()
        delivery2_form = Form(delivery2)
        delivery2_form.scheduled_date = datetime.now() + timedelta(days=1)
        delivery2 = delivery2_form.save()
        delivery2.action_confirm()
        delivery2.move_ids.quantity = delivery1.move_ids.quantity
        # Unreserve to avoid stealing the 50 unit in stock
        delivery2.do_unreserve()
        # Still needs 200 qty to fulfill delivery2's need
        self.assertEqual(delivery2.move_ids.forecast_availability, -200)

        # Check for both deliveries and receipts if the highlight (is_matched) corresponds to the correct picking
        for picking in [delivery1, delivery2, receipt1, receipt2]:
            context = picking.move_ids[0].action_product_forecast_report()['context']
            _, _, lines = self.get_report_forecast(product_template_ids=self.product_template.ids, context=context)
            for line in lines:
                if (line['document_in'] and picking.id == line['document_in']['id']) or (line['document_out'] and picking.id == line['document_out']['id']): #document_in is False
                    self.assertTrue(line['is_matched'], "The corresponding picking should be matched in the forecast report.")
                else:
                    self.assertFalse(line['is_matched'], "A line of the forecast report not linked to the picking shoud not be matched.")

    def test_report_forecast_11_non_reserved_order(self):
        """ Creates deliveries with different operation type reservation methods.
        Checks replenishment lines are correctly sorted by the flollowing criteria:
            - If the reservation date is in the past at any time T, use the priority and scheduled date
            - If the reservation date is in the future, use reservation date, priority and scheduled date
            'manual': always last (no reservation_date)
            'at_confirm': reservation_date = time of creation
            'by_date': reservation_date = scheduled_date - reservation_days_before(_priority)
        """

        picking_type_manual = self.picking_type_out.copy()
        picking_type_by_date = picking_type_manual.copy()
        picking_type_at_confirm = picking_type_manual.copy()
        picking_type_manual.reservation_method = 'manual'
        picking_type_manual.sequence_code = 'manual'
        picking_type_by_date.reservation_method = 'by_date'
        picking_type_by_date.sequence_code = 'by'
        # artificially make non-priority moves reserve before priority moves to
        # check order doesn't prioritize priority
        picking_type_by_date.reservation_days_before = '6'
        picking_type_by_date.reservation_days_before_priority = '4'
        picking_type_at_confirm.reservation_method = 'at_confirm'
        picking_type_at_confirm.sequence_code = 'confirm'

        # 'manual' reservation => no reservation_date
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_manual
        delivery_form.scheduled_date = datetime.now() - timedelta(days=10)
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        delivery_manual = delivery_form.save()
        delivery_manual.action_confirm()

        # 'by_date' reservation => reservation_date = 1 day before today
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_by_date
        delivery_form.scheduled_date = datetime.now() + timedelta(days=5)
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        delivery_by_date = delivery_form.save()
        delivery_by_date.action_confirm()

        # 'by_date' reservation (priority) => reservation_date = 1 day after today
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_by_date
        delivery_form.scheduled_date = datetime.now() + timedelta(days=5)
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        delivery_by_date_priority = delivery_form.save()
        # <field name="priority" invisible="name == '/'"/>
        # The priority field is not visible until the name is set,
        # which is done after a first save / the `create`
        delivery_form.priority = '1'
        delivery_by_date_priority = delivery_form.save()
        delivery_by_date_priority.action_confirm()

        # 'at_confirm' reservation => reservation_date = today
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_at_confirm
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 3
        delivery_at_confirm = delivery_form.save()
        delivery_at_confirm.action_confirm()

        # Order should be: delivery_at_confirm, delivery_by_date, delivery_by_date_priority, delivery_manual
        _, _, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        self.assertEqual(len(lines), 4, "The report must have 4 lines.")
        self.assertEqual(lines[0]['document_out']['id'], delivery_at_confirm.id)
        self.assertEqual(lines[1]['document_out']['id'], delivery_by_date.id)
        self.assertEqual(lines[2]['document_out']['id'], delivery_by_date_priority.id)
        self.assertEqual(lines[3]['document_out']['id'], delivery_manual.id)

        all_delivery = delivery_by_date | delivery_at_confirm | delivery_by_date_priority | delivery_manual
        self.assertEqual(all_delivery.move_ids.mapped("forecast_availability"), [-3.0, -3.0, -3.0, -3.0])

        # Creation of one receipt to fulfill the 2 first deliveries delivery_by_date and delivery_at_confirm
        receipt_form = Form(self.env['stock.picking'])
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        receipt_form.scheduled_date = date.today() + timedelta(days=1)
        with receipt_form.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 6
        receipt1 = receipt_form.save()
        receipt1.action_confirm()

        self.assertEqual(all_delivery.move_ids.mapped("forecast_availability"), [3, 3, -3.0, -3.0])

    def test_report_forecast_12_reserved_transit(self):
        """ Tests the transit feature, in 2 step incoming shipment warehouse, create
            incoming transfer, validate it, create outgoing transfer and check report to show
            quantities needed are in transit
        """
        grp_multi_loc = self.env.ref('stock.group_stock_multi_locations')
        grp_multi_routes = self.env.ref('stock.group_adv_location')
        self.env.user.write({'group_ids': [(4, grp_multi_loc.id)]})
        self.env.user.write({'group_ids': [(4, grp_multi_routes.id)]})
        # Warehouse config.
        warehouse = self.env.ref('stock.warehouse0')
        warehouse.reception_steps = 'two_steps'
        outgoing = Form(self.env['stock.picking'])
        outgoing.picking_type_id = self.picking_type_out
        with outgoing.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 2
        outgoing = outgoing.save()
        outgoing.action_confirm()
        incoming = Form(self.env['stock.picking'])
        incoming.picking_type_id = self.picking_type_in
        with incoming.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 2
        incoming = incoming.save()
        incoming.action_confirm()
        incoming.move_ids.picked = True
        incoming.button_validate()
        _, _, lines = self.get_report_forecast(product_template_ids=self.product_template.ids)
        self.assertEqual(len(lines), 1)
        self.assertEqual(bool(lines[0]['move_out']), True)
        self.assertEqual(lines[0]['in_transit'], True)

    def test_report_forecast_13_availability_from_sublocations(self):
        """
            Check that the forecast_availability is correctly computed for moves
            whose source is a sublocation of the stock warehouse location
        """
        stock_location = self.env.ref('stock.warehouse0').lot_stock_id
        sublocation = self.env['stock.location'].create({
            'name': 'Warehouse0 / Sublocation',
            'barcode': 'TEST_BARCODE_LOCATION',
            'location_id': stock_location.id
        })
        self.env['stock.quant']._update_available_quantity(self.product, sublocation, 10.0)
        delivery_form = Form(self.env['stock.picking'])
        delivery_form.picking_type_id = self.picking_type_out
        delivery_form.partner_id = self.partner
        with delivery_form.move_ids_without_package.new() as move:
            move.product_id = self.product
            move.product_uom_qty = 3
        delivery = delivery_form.save()
        delivery.action_confirm()
        delivery.do_unreserve()
        self.assertRecordValues(delivery.move_ids, [
            {
                'product_uom_qty': 3.0,
                'location_id': stock_location.id,
                'quantity': 0.0,
                'forecast_availability': 3.0,
            }
        ])
        # Change the source of the picking to be the sublocation
        # and check the forecast_availability stays unchanged
        with Form(delivery) as delivery_form:
            delivery_form.location_id = sublocation
        self.assertRecordValues(delivery.move_ids, [
            {
                'product_uom_qty': 3.0,
                'location_id': sublocation.id,
                'quantity': 0.0,
                'forecast_availability': 3.0,
            }
        ])
        _, _, lines = self.get_report_forecast(product_template_ids=self.product.product_tmpl_id.ids)
        self.assertEqual(len(lines), 2)
        picking_line = next(filter(lambda line: line.get('document_out'), lines))
        self.assertEqual(
            (picking_line['quantity'], picking_line['replenishment_filled'], picking_line['document_out']['id']),
            (3.0, True, delivery.id)
        )
        stock_line = next(filter(lambda line: not line.get('document_out'), lines))
        self.assertEqual(
            (stock_line['quantity'], stock_line['replenishment_filled']),
            (7.0, True)
        )

    def test_report_forecast_14_ongoing_multi_step_delivery(self):
        """ Check that an ongoing multi-step delivery is properly picked up by the forecast report.
        """
        customer_loc, __ = self.env['stock.warehouse']._get_partner_locations()
        self.wh_2.write({'delivery_steps': 'pick_ship'})

        # Pick move for future delivery
        move_pick = self.env['stock.move'].create({
            'picking_type_id': self.wh_2.pick_type_id.id,
            'location_id': self.wh_2.lot_stock_id.id,
            'location_final_id': customer_loc.id,
            'product_id': self.product1.id,
            'product_uom_qty': 5.0,
        })
        move_pick._action_confirm()
        _, _, lines = self.get_report_forecast(product_template_ids=self.product1.product_tmpl_id.ids, context={'warehouse_id': self.wh_2.id})
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['move_out']['id'], move_pick.id)

    def test_report_reception_1_one_receipt(self):
        """ Create 2 deliveries and 1 receipt where some of the products being received
        can be reserved for the deliveries. Check that the reception report correctly
        shows these corresponding potential allocations + correctly reserves incoming moves
        when reserve button is pushed.
        """
        product2 = self.env['product.product'].create({
            'name': 'Extra Product',
            'is_storable': True,
        })

        product3 = self.env['product.product'].create({
            'name': 'Unpopular Product',
            'is_storable': True,
        })

        # Creates some deliveries for reception report to match against
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 5
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = product2
            move_line.product_uom_qty = 10
        delivery1 = delivery_form.save()
        delivery1.action_confirm()

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 2
        delivery2 = delivery_form.save()
        delivery2.action_confirm()

        # Create a receipt
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            # incoming qty greater than total (2 moves) outgoing amount => 2 report lines, each = outgoing qty
            move_line.product_id = self.product
            move_line.product_uom_qty = 15
        with receipt_form.move_ids_without_package.new() as move_line:
            # outgoing qty greater than incoming amount => report line = incoming qty
            move_line.product_id = product2
            move_line.product_uom_qty = 5
        with receipt_form.move_ids_without_package.new() as move_line:
            # not outgoing => shouldn't appear in report
            move_line.product_id = product3
            move_line.product_uom_qty = 5
        receipt = receipt_form.save()

        # check that reception report has correct number of deliveries/outgoing moves
        # but the quantities aren't available for assignment yet (i.e. can link as chained moves)
        report = self.env['report.stock.report_reception']
        report_values = report._get_report_values(docids=[receipt.id])
        sources_to_lines = report_values['sources_to_lines']
        self.assertEqual(len(sources_to_lines), 2, "The report has wrong number of outgoing pickings.")
        all_lines = []
        for lines in sources_to_lines.values():
            for line in lines:
                self.assertFalse(line['is_qty_assignable'], "The receipt IS DRAFT => its move quantities ARE NOT available to assign.")
                all_lines.append(line)
        self.assertEqual(len(all_lines), 3, "The report has wrong number of outgoing moves.")
        # we expect this order based on move creation
        self.assertEqual(all_lines[0]['quantity'], 5, "The first move has wrong incoming qty.")
        self.assertEqual(all_lines[0]['product']['id'], self.product.id, "The first move has wrong incoming product to assign.")
        self.assertEqual(all_lines[1]['quantity'], 5, "The second move has wrong incoming qty.")
        self.assertEqual(all_lines[1]['product']['id'], product2.id, "The second move has wrong incoming product to assign.")
        self.assertEqual(all_lines[2]['quantity'], 2, "The last move has wrong incoming qty.")
        self.assertEqual(all_lines[2]['product']['id'], self.product.id, "The third move has wrong incoming product to assign.")

        # check that report correctly realizes outgoing moves can be linked when receipt is done
        receipt.action_confirm()
        for move in receipt.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        receipt.button_validate()
        report_values = report._get_report_values(docids=[receipt.id])

        sources_to_lines = report_values['sources_to_lines']
        all_lines = []
        move_ids = []
        qtys = []
        in_ids = []
        for lines in sources_to_lines.values():
            for line in lines:
                self.assertTrue(line['is_qty_assignable'], "The receipt IS DONE => all of its move quantities ARE assignable")
                all_lines.append(line)
                move_ids.append(line['move_out'].id)
                qtys.append(line['quantity'])
                in_ids += line['move_ins']
        # line quantities should be the same when receipt is done compared to when it was draft
        self.assertEqual(len(all_lines), 3, "The report has wrong number of outgoing moves.")
        self.assertEqual(all_lines[0]['quantity'], 5, "The first move has wrong incoming qty to reserve.")
        self.assertEqual(all_lines[0]['product']['id'], self.product.id, "The first move has wrong product to reserve.")
        self.assertEqual(all_lines[1]['quantity'], 5, "The second move has wrong incoming qty to reserve.")
        self.assertEqual(all_lines[1]['product']['id'], product2.id, "The second move has wrong product to reserve.")
        self.assertEqual(all_lines[2]['quantity'], 2, "The last move has wrong incoming qty to reserve.")
        self.assertEqual(all_lines[2]['product']['id'], self.product.id, "The third move has wrong product to reserve.")

        # check that report assign button works correctly
        report.action_assign(move_ids, qtys, in_ids)
        self.assertEqual(len(receipt.move_ids[0].move_dest_ids.ids), 2, "Demand qty of first and last moves should now be linked to incoming.")
        self.assertEqual(len(receipt.move_ids[1].move_dest_ids.ids), 1, "Demand qty of second move should now be linked to incoming.")
        self.assertEqual(len(receipt.move_ids[2].move_dest_ids.ids), 0, "product3 should have no moves linked to it.")
        self.assertEqual(len(delivery1.move_ids.filtered(lambda m: m.product_id == product2)), 2, "product2 outgoing move should be split between linked and non-linked quantities.")

    def test_report_reception_2_two_receipts(self):
        """ Create 1 delivery and 2 receipts where the products being received
        can be reserved for the delivery. Check that the reception report correctly
        shows corresponding potential allocations when receipts have differing states.
        """
        # Creates delivery for reception report to match against
        outgoing_qty = 100
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = outgoing_qty
        delivery = delivery_form.save()
        delivery.action_confirm()

        # Create 2 receipts and check its reception report values
        receipt1_qty = 5
        receipt2_qty = 3
        incoming_qty = receipt1_qty + receipt2_qty
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = receipt1_qty
        receipt1 = receipt_form.save()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = receipt2_qty
        receipt2 = receipt_form.save()

        # check that report correctly merges draft incoming quantities
        report = self.env['report.stock.report_reception']
        report_values = report._get_report_values(docids=[receipt1.id, receipt2.id])
        self.assertEqual(len(report_values['docs']), 2, "There should be 2 receipts to assign from in this report")
        sources_to_lines = report_values['sources_to_lines']
        self.assertEqual(len(sources_to_lines), 1, "The report has wrong number of outgoing pickings.")
        all_lines = list(sources_to_lines.values())[0]
        self.assertEqual(len(all_lines), 1, "The report has wrong number of outgoing move lines.")
        self.assertFalse(all_lines[0]['is_qty_assignable'], "The receipt IS NOT done => its move quantities ARE NOT available to reserve (i.e. done).")
        self.assertEqual(all_lines[0]['quantity'], 8, "The move has wrong incoming qty.")

        # check that report splits assignable and non-assignable quantities when 1 receipt is draft and other is confirmed
        receipt1.action_confirm()
        for move in receipt1.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        report_values = report._get_report_values(docids=[receipt1.id, receipt2.id])

        sources_to_lines = report_values['sources_to_lines']
        all_lines = list(sources_to_lines.values())[0]
        # line quantities depends on done vs not done incoming quantities => should be 2 lines now
        self.assertEqual(len(all_lines), 2, "The report has wrong number of lines (1 assignable + 1 not).")
        self.assertEqual(all_lines[0]['quantity'], receipt1_qty, "The first move has wrong incoming qty to assign.")
        self.assertTrue(all_lines[0]['is_qty_assignable'], "1 receipt is confirmed => should have 1 reservable move.")
        self.assertEqual(all_lines[1]['quantity'], receipt2_qty, "The second move has wrong (expected) incoming qty.")
        self.assertFalse(all_lines[1]['is_qty_assignable'], "1 receipt is draft => should have 1 non-assignable move.")

        # check that we can assign incoming quantities from 2 different CONFIRMED receipts and then unassign just 1 of them afterwards
        receipt2.action_confirm()
        report_values = report._get_report_values(docids=[receipt1.id, receipt2.id])
        sources_to_lines = report_values['sources_to_lines']
        all_lines = list(sources_to_lines.values())[0]
        self.assertEqual(len(all_lines), 1, "The report has wrong number of lines (1 outgoing move they are assignable to).")
        self.assertEqual(all_lines[0]['quantity'], incoming_qty, "The total amount of incoming qty to assign should be receipt1 + receipt2's qties.")
        self.assertTrue(all_lines[0]['is_qty_assignable'], "receipts are confirmed, incoming moves should be assignable.")
        report.action_assign(delivery.move_ids_without_package.ids, [incoming_qty], (receipt1 | receipt2).move_ids_without_package.ids)
        mto_move = delivery.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_move = delivery.move_ids_without_package - mto_move
        # check that assigned (MTO) move is correctly created
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(len(non_mto_move), 1, "Remaining not-assigned outgoing qty should have split into separate move")
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Incorrect quantity split for MTO move")
        self.assertEqual(mto_move.state, 'waiting', "MTO move state not correctly set")
        # unassign only 1 of the incoming moves
        report.action_unassign([mto_move.id], receipt2_qty, receipt2.move_ids_without_package.ids)
        mto_move = delivery.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_moves = delivery.move_ids_without_package - mto_move
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(len(non_mto_moves), 2, "Original split not-assigned outgoing qty should still exist + new move of unassigned qty")
        self.assertEqual(mto_move.product_uom_qty, receipt1_qty, "Incorrect quantity split for remaining MTO move qty")
        self.assertEqual(mto_move.state, 'waiting', "MTO move state shouldn't have changed")

        # check that report doesn't allow done and non-done moves at same time
        receipt1.button_validate()
        reason = report._get_report_values(docids=[receipt1.id, receipt2.id])['reason']
        self.assertEqual(reason, "This report cannot be used for done and not done %s at the same time" % report._get_doc_types(), "empty report reason not shown")

        # check that we can assign incoming quantities from 2 different DONE receipts and then unassign just 1 of them afterwards when reserved amounts in delivery
        receipt2.button_validate()
        # create clean delivery since moves are split in original delivery + new delivery will auto merge the moves
        delivery.action_cancel()
        delivery2 = delivery.copy()
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'location_id': self.stock_location.id,
            'inventory_quantity': outgoing_qty
        }).action_apply_inventory()
        delivery2.action_confirm()
        self.assertEqual(delivery2.move_ids_without_package.quantity, outgoing_qty, "Delivery move should already be reserved")
        report.action_assign(delivery2.move_ids_without_package.ids, [incoming_qty], (receipt1 | receipt2).move_ids_without_package.ids)
        mto_move = delivery2.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_move = delivery2.move_ids_without_package - mto_move
        # check that assigned (MTO) move is correctly created
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(len(non_mto_move), 1, "Remaining not-assigned outgoing qty should have split into separate move")
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Incorrect quantity split for MTO move")
        self.assertEqual(mto_move.state, 'assigned', "MTO move should still be reserved")
        # unassign only 1 of the incoming moves
        report.action_unassign([mto_move.id], receipt2_qty, receipt2.move_ids_without_package.ids)
        mto_move = delivery2.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_moves = delivery2.move_ids_without_package - mto_move
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(len(non_mto_moves), 2, "Original split not-assigned outgoing qty should still exist + new move of unassigned qty")
        self.assertEqual(mto_move.product_uom_qty, receipt1_qty, "Incorrect quantity split for remaining MTO move qty")
        self.assertEqual(mto_move.quantity, receipt1_qty, "Incorrect reserved amount split for remaining MTO move qty")
        self.assertEqual(mto_move.state, 'assigned', "MTO move state shouldn't have changed")
        total_non_mto_qty = sum(move.quantity for move in non_mto_moves)
        self.assertEqual(total_non_mto_qty, outgoing_qty - (receipt1_qty + receipt2_qty), "Unassigned move should be also unreserved")

    def test_report_reception_3_multiwarehouse(self):
        """ Check that reception report respects same warehouse for
        receipts and deliveries.
        """
        # Warehouse config.
        wh_2 = self.env['stock.warehouse'].create({
            'name': 'Other Warehouse',
            'code': 'OTHER',
        })
        picking_type_out_2 = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id', '=', wh_2.id),
        ])

        # Creates delivery in warehouse2
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = picking_type_out_2
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = 100
        delivery = delivery_form.save()
        delivery.action_confirm()

        # Create a receipt in warehouse1
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.quantity = 15
        receipt = receipt_form.save()

        report = self.env['report.stock.report_reception']
        report_values = report._get_report_values(docids=[receipt.id])
        self.assertEqual(len(report_values['sources_to_lines']), 0, "The receipt and delivery are in different warehouses => no moves to link to should be found.")

    def test_report_reception_5_move_splitting(self):
        """ Check the complicated use cases of correct move splitting when assigning/unassigning when:
        1. Qty to assign is less than delivery qty demand
        2. Delivery already has some reserved quants
        3. Receipt and delivery are not yet 'done' at time of assign/unassign
        """
        incoming_qty = 4
        outgoing_qty = 10
        qty_in_stock = outgoing_qty - incoming_qty
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'location_id': self.stock_location.id,
            'inventory_quantity': qty_in_stock
        }).action_apply_inventory()

        # create delivery + receipt
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = outgoing_qty
        delivery = delivery_form.save()
        delivery.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = incoming_qty
        receipt = receipt_form.save()
        receipt.action_confirm()

        self.assertEqual(len(delivery.move_ids_without_package), 1)
        report = self.env['report.stock.report_reception']

        # -------------------
        # check report assign
        # -------------------
        report.action_assign(delivery.move_ids_without_package.ids, [incoming_qty], receipt.move_ids_without_package.ids)
        mto_move = delivery.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_move = delivery.move_ids_without_package - mto_move

        # check that delivery move splits correctly when receipt move is assigned to it
        self.assertEqual(len(delivery.move_ids_without_package), 2, "Delivery moves should have split into assigned + not assigned")
        self.assertEqual(len(delivery.move_ids_without_package.mapped('move_orig_ids')), 1, "Only 1 delivery + 1 receipt move should be assigned")
        self.assertEqual(len(receipt.move_ids_without_package.mapped('move_dest_ids')), 1, "Receipt move should remain unsplit")

        # check that assigned (MTO) move is correctly created
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Incorrect quantity split for MTO move")
        self.assertEqual(mto_move.quantity, 0, "Receipt is not done => assigned move can't have a reserved qty")
        self.assertEqual(mto_move.state, 'waiting', "MTO move state not correctly set")

        # check that non-assigned move has correct values
        self.assertEqual(non_mto_move.product_uom_qty, outgoing_qty - incoming_qty, "Incorrect quantity split for non-MTO move")
        self.assertEqual(non_mto_move.quantity, qty_in_stock, "Reserved qty not correctly linked to non-MTO move")
        self.assertEqual(non_mto_move.state, 'assigned', "Fully reserved move has not correctly set state")

        # ---------------------
        # check report unassign
        # ---------------------
        report.action_unassign([mto_move.id], incoming_qty, receipt.move_ids_without_package.ids)
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Move quantities should be unchanged")
        self.assertEqual(mto_move.procure_method, 'make_to_stock', "Procure method not correctly reset")
        self.assertEqual(mto_move.state, 'confirmed', "Move state not correctly reset (to non-MTO state)")

    def test_report_reception_6_backorders(self):
        """ Check the complicated use case with backorder when:
        1. Incoming qty is greater than outgoing qty needed to be assigned + total outgoing qty is assigned
        2. Smaller qty is completed + backorder is made for rest
        3. Backorder qty (which is still assigned) is unassigned + re-assigned
        """
        incoming_qty = 10
        outgoing_qty = 8
        orig_incoming_quantity = 4

        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.partner_id = self.partner
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = outgoing_qty
        delivery = delivery_form.save()
        delivery.action_confirm()

        # Create receipt w/greater qty than needed delivery qty
        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = incoming_qty
        receipt = receipt_form.save()
        receipt.action_confirm()

        report = self.env['report.stock.report_reception']
        report.action_assign(delivery.move_ids_without_package.ids, [outgoing_qty], receipt.move_ids_without_package.ids)
        self.assertEqual(receipt.move_ids_without_package.move_dest_ids.ids, delivery.move_ids_without_package.ids, "Link between receipt and delivery moves should have been made")

        for move in receipt.move_ids:
            move.quantity = orig_incoming_quantity
        receipt.move_ids.picked = True
        Form.from_action(self.env, receipt.button_validate()).save().process()
        backorder = self.env['stock.picking'].search([('backorder_id', '=', receipt.id)])

        # Check backorder assigned quantities
        self.assertEqual(receipt.move_ids_without_package.move_dest_ids, backorder.move_ids_without_package.move_dest_ids, "Backorder should have copied link to delivery move")
        report_values = report._get_report_values(docids=[backorder.id])
        sources_to_lines = report_values['sources_to_lines']
        all_lines = list(sources_to_lines.values())[0]
        self.assertEqual(len(all_lines), 1, "The report has wrong number of outgoing moves.")
        # we expect that the report won't know about original receipt done amount, so it will show outgoing_qty as assigned
        # (rather than the remaining amount that isn't reserved). This can change if the report becomes more sophisticated
        self.assertEqual(all_lines[0]['quantity'], incoming_qty - orig_incoming_quantity, "The report doesn't have the correct qty assigned.")

        # Unassign the amount we expect to see in the report + check split correctly happens
        report.action_unassign(delivery.move_ids_without_package.ids, outgoing_qty, backorder.move_ids_without_package.ids)
        self.assertEqual(len(delivery.move_ids_without_package), 2, "The delivery should have split its reserved qty from the original move")
        reserved_move = receipt.move_ids_without_package.move_dest_ids
        self.assertEqual(len(reserved_move), 1, "Move w/reserved qty should have full demand reserved")
        self.assertEqual(reserved_move.state, 'assigned', "Move w/reserved qty should have full demand reserved")
        self.assertEqual(reserved_move.product_uom_qty, orig_incoming_quantity, "Done amount in original receipt should be amount demanded/reserved in delivery still with a link")
        report_values = report._get_report_values(docids=[backorder.id])
        sources_to_lines = report_values['sources_to_lines']
        all_lines = list(sources_to_lines.values())[0]
        self.assertEqual(len(all_lines), 1, "The report should only contain the remaining non-reserved move")
        self.assertEqual(all_lines[0]['quantity'], outgoing_qty - orig_incoming_quantity, "The report doesn't have the correct qty to assign")

        # Re-assign the remaining delivery amount and check that everything reserves correctly in the end
        report.action_assign((delivery.move_ids_without_package - reserved_move).ids, [outgoing_qty - orig_incoming_quantity], backorder.move_ids_without_package.ids)
        for move in backorder.move_ids:
            move.quantity = incoming_qty - orig_incoming_quantity
        backorder.move_ids.picked = True
        backorder.button_validate()
        for move in delivery.move_ids_without_package:
            self.assertEqual(move.state, 'assigned', "All delivery moves should be fully reserved now")

    def test_report_reception_7_done_receipt(self):
        """ Check the complicated use cases of correct move splitting when assigning when:
        1. Outgoing qty is greater than incoming qty + total outgoing qty is already reserved
        2. Receipt is already done and then assigned
        """

        incoming_qty = 4
        outgoing_qty = 10
        self.env['stock.quant'].with_context(inventory_mode=True).create({
            'product_id': self.product.id,
            'location_id': self.stock_location.id,
            'inventory_quantity': outgoing_qty
        }).action_apply_inventory()

        # create delivery + receipt
        delivery_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        delivery_form.picking_type_id = self.picking_type_out
        with delivery_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = outgoing_qty
        delivery = delivery_form.save()
        delivery.action_confirm()

        receipt_form = Form(self.env['stock.picking'], view='stock.view_picking_form')
        receipt_form.partner_id = self.partner
        receipt_form.picking_type_id = self.picking_type_in
        with receipt_form.move_ids_without_package.new() as move_line:
            move_line.product_id = self.product
            move_line.product_uom_qty = incoming_qty
        receipt = receipt_form.save()
        receipt.action_confirm()
        receipt.button_validate()

        self.assertEqual(len(delivery.move_ids_without_package), 1)
        self.assertEqual(delivery.move_ids_without_package.quantity, outgoing_qty, "Delivery move should already be reserved")
        report = self.env['report.stock.report_reception']

        # -------------------
        # check report assign
        # -------------------
        report.action_assign(delivery.move_ids_without_package.ids, [incoming_qty], receipt.move_ids_without_package.ids)
        mto_move = delivery.move_ids_without_package.filtered(lambda m: m.procure_method == 'make_to_order')
        non_mto_move = delivery.move_ids_without_package - mto_move

        # check that delivery move splits correctly when receipt move is assigned to it, done receipt = can be assigned to reserved outs
        self.assertEqual(len(delivery.move_ids_without_package), 2, "Delivery moves should have split into assigned + not assigned")
        self.assertEqual(len(delivery.move_ids_without_package.move_orig_ids), 1, "Only 1 delivery + 1 receipt move should be assigned")
        self.assertEqual(len(receipt.move_ids_without_package.move_dest_ids), 1, "Receipt move should remain unsplit")

        # check that assigned (MTO) move is correctly created
        self.assertEqual(len(mto_move), 1, "Only 1 delivery move should be MTO")
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Incorrect quantity split for MTO move")
        self.assertEqual(mto_move.quantity, incoming_qty, "Receipt IS done => assigned pre-reserved move reserved_qty = assigned receipt move qty")
        self.assertEqual(mto_move.state, 'assigned', "MTO move state not correctly set")

        # check that non-assigned move has correct values
        self.assertEqual(non_mto_move.product_uom_qty, outgoing_qty - incoming_qty, "Incorrect quantity split for non-MTO move")
        self.assertEqual(non_mto_move.quantity, outgoing_qty - incoming_qty, "Remaining reserved qty not correctly linked to non-MTO move")
        self.assertEqual(non_mto_move.state, 'assigned', "Remaining non-MTO reserved move should stay reserved")

        # ---------------------
        # check report unassign
        # ---------------------
        report.action_unassign([mto_move.id], incoming_qty, receipt.move_ids_without_package.ids)
        self.assertEqual(mto_move.product_uom_qty, incoming_qty, "Move quantities should be unchanged")
        self.assertEqual(mto_move.procure_method, 'make_to_stock', "Procure method not correctly reset")
        self.assertEqual(mto_move.state, 'confirmed', "Unassigning receipt move should also unreserve the out move")

    def test_report_reception_immediate_transfer(self):
        """ Having a delivery, a receipt with a move line created before the move
        (i.e., an immediate transfer) for the product of the SO should have the delivery in its
        'Allocation' entries.
        """
        Report = self.env['report.stock.report_reception']

        planned_delivery = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_out.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.env.ref('stock.stock_location_customers').id,
            'move_ids': [(0, 0, {
                'location_id': self.stock_location.id,
                'location_dest_id': self.env.ref('stock.stock_location_customers').id,
                'product_id': self.product.id,
                'product_uom_qty': 1,
            })],
        })
        planned_delivery.action_confirm()

        immediate_receipt_transfer = self.env['stock.picking'].create({
            'picking_type_id': self.picking_type_in.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
        })
        self.env['stock.move.line'].create({
            'picking_id': immediate_receipt_transfer.id,
            'location_id': self.supplier_location.id,
            'location_dest_id': self.stock_location.id,
            'product_id': self.product.id,
            'quantity': 1,
        })

        sources_to_lines = Report._get_report_values(docids=[immediate_receipt_transfer.id])['sources_to_lines']
        for lines in sources_to_lines.values():
            for line in lines:
                self.assertFalse(line['is_qty_assignable'])

        immediate_receipt_transfer.button_validate()
        out_move = planned_delivery.move_ids
        in_move = immediate_receipt_transfer.move_ids

        sources_lines_items, = Report._get_report_values(docids=[immediate_receipt_transfer.id])['sources_to_lines'].items()
        sources, lines = sources_lines_items
        (source,), = sources
        self.assertEqual(source, planned_delivery)
        self.assertEqual(lines[0]['quantity'], out_move.quantity)

        Report.action_assign(out_move.ids, [out_move.quantity], [in_move.ids])
        self.assertEqual(out_move.procure_method, 'make_to_order')

        Report.action_unassign(out_move.id, out_move.quantity, in_move.ids)
        self.assertEqual(out_move.procure_method, 'make_to_stock')

    def test_report_stock_lot_customer_simple_delivery(self):
        """
        Deliver an SN product
        The SN/Lot report should show the delivered SN
        """
        stock_location = self.env.ref('stock.stock_location_stock')
        customer_location = self.env.ref('stock.stock_location_customers')
        out_type = self.env.ref('stock.picking_type_out')

        sn = self.env['stock.lot'].create({'name': 'supersn', 'product_id': self.serial_product.id})
        self.env['stock.quant']._update_available_quantity(self.serial_product, stock_location, quantity=1, lot_id=sn)

        delivery = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': out_type.id,
            'location_id': stock_location.id,
            'location_dest_id': customer_location.id,
            'move_ids': [Command.create({
                'product_id': self.serial_product.id,
                'product_uom_qty': 1,
                'location_id': stock_location.id,
                'location_dest_id': customer_location.id,
            })],
        })
        delivery.action_confirm()
        delivery.button_validate()

        action_view_stock_serial_domain = self.partner.action_view_stock_serial()['domain']
        customer_lots = self.env['stock.lot'].search(action_view_stock_serial_domain)
        self.assertEqual(customer_lots, sn)

    def test_partner_lot_report_sml_without_picking(self):
        """
        Deliver a classic product and a tracked one
        The SML of the SN is not directly linked to the picking
        The report should still show the delivered SN
        """
        stock_location = self.env.ref('stock.stock_location_stock')
        customer_location = self.env.ref('stock.stock_location_customers')
        out_type = self.env.ref('stock.picking_type_out')

        self.product.is_storable = False
        delivery = self.env['stock.picking'].create({
            'partner_id': self.partner.id,
            'picking_type_id': out_type.id,
            'location_id': stock_location.id,
            'location_dest_id': customer_location.id,
            'move_ids': [Command.create({
                'product_id': self.product.id,
                'product_uom_qty': 1,
                'location_id': stock_location.id,
                'location_dest_id': customer_location.id,
            })],
        })
        delivery.action_confirm()

        sn = self.env['stock.lot'].create({'name': 'supersn', 'product_id': self.serial_product.id})
        delivery.move_ids = [Command.create({
            'product_id': self.serial_product.id,
            'product_uom_qty': 1,
            'location_id': stock_location.id,
            'location_dest_id': customer_location.id,
            'move_line_ids': [Command.create({
                'product_id': self.serial_product.id,
                'quantity': 1,
                'lot_id': sn.id,
            })],
        })]
        delivery.button_validate()

        action_view_stock_serial_domain = self.partner.action_view_stock_serial()['domain']
        customer_lots = self.env['stock.lot'].search(action_view_stock_serial_domain)
        self.assertEqual(customer_lots, sn)
