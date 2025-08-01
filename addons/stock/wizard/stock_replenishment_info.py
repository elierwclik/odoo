# Part of Odoo. See LICENSE file for full copyright and licensing details.

import babel.dates
from json import dumps
from datetime import datetime, time
from dateutil.relativedelta import relativedelta


from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.fields import Domain
from odoo.tools.date_utils import get_month, subtract
from odoo.tools.misc import get_lang, format_date


class StockReplenishmentInfo(models.TransientModel):
    _name = 'stock.replenishment.info'
    _description = 'Stock supplier replenishment information'
    _rec_name = 'orderpoint_id'

    orderpoint_id = fields.Many2one('stock.warehouse.orderpoint')
    product_id = fields.Many2one('product.product', related='orderpoint_id.product_id')
    qty_to_order = fields.Float(related='orderpoint_id.qty_to_order')
    json_lead_days = fields.Char(compute='_compute_json_lead_days')
    json_replenishment_history = fields.Char(compute='_compute_json_replenishment_history')

    warehouseinfo_ids = fields.One2many(related='orderpoint_id.warehouse_id.resupply_route_ids')
    wh_replenishment_option_ids = fields.One2many('stock.replenishment.option', 'replenishment_info_id', compute='_compute_wh_replenishment_options')

    @api.depends('orderpoint_id')
    def _compute_wh_replenishment_options(self):
        for replenishment_info in self:
            replenishment_info.wh_replenishment_option_ids = self.env['stock.replenishment.option'].create([
                {'product_id': replenishment_info.product_id.id, 'route_id': route_id.id, 'replenishment_info_id': replenishment_info.id}
                for route_id in replenishment_info.warehouseinfo_ids
            ]).sorted(lambda o: o.free_qty, reverse=True)

    @api.depends('orderpoint_id')
    def _compute_json_lead_days(self):
        self.json_lead_days = False
        for replenishment_report in self:
            if not replenishment_report.orderpoint_id.product_id or not replenishment_report.orderpoint_id.location_id:
                continue
            orderpoint = replenishment_report.orderpoint_id
            orderpoints_values = orderpoint._get_lead_days_values()
            dummy, lead_days_description = orderpoint.rule_ids._get_lead_days(
                orderpoint.product_id, **orderpoints_values)
            replenishment_report.json_lead_days = dumps({
                'lead_days_date': format_date(self.env, replenishment_report.orderpoint_id.lead_days_date),
                'lead_days_description': lead_days_description,
                'today': format_date(self.env, fields.Date.today()),
                'trigger': orderpoint.trigger,
                'qty_forecast': self.env['ir.qweb.field.float'].value_to_html(orderpoint.qty_forecast, {'decimal_precision': 'Product Unit'}),
                'qty_to_order': self.env['ir.qweb.field.float'].value_to_html(orderpoint.qty_to_order, {'decimal_precision': 'Product Unit'}),
                'product_min_qty': self.env['ir.qweb.field.float'].value_to_html(orderpoint.product_min_qty, {'decimal_precision': 'Product Unit'}),
                'product_max_qty': self.env['ir.qweb.field.float'].value_to_html(orderpoint.product_max_qty, {'decimal_precision': 'Product Unit'}),
                'product_uom_name': orderpoint.product_uom_name,
                'virtual': orderpoint.trigger == 'manual' and orderpoint.create_uid.id == SUPERUSER_ID,
                'visibility_days': orderpoint.visibility_days if orderpoint.product_uom.compare(orderpoint.qty_forecast, orderpoint.product_min_qty) < 0 else 0,
                'visibility_days_date': format_date(self.env, replenishment_report.orderpoint_id.lead_days_date + relativedelta(days=orderpoint.visibility_days))
            })

    @api.depends('orderpoint_id')
    def _compute_json_replenishment_history(self):
        for replenishment_report in self:
            replenishment_history = []
            today = fields.Datetime.now()
            first_month = subtract(today, months=2)
            date_from, dummy = get_month(first_month)
            dummy, date_to = get_month(today)
            domain = Domain([
                ('product_id', '=', replenishment_report.product_id.id),
                ('date', '>=', date_from),
                ('date', '<=', datetime.combine(date_to, time.max)),
                ('state', '=', 'done'),
                ('company_id', '=', replenishment_report.orderpoint_id.company_id.id)
            ])
            quantity_by_month_out = self.env['stock.move']._read_group(
                domain & Domain('location_dest_id.usage', '=', 'customer'),
                ['date:month'], ['product_qty:sum'])
            quantity_by_month_returned = dict(self.env['stock.move']._read_group(
                domain & Domain('location_id.usage', '=', 'customer'),
                ['date:month'], ['product_qty:sum']))
            locale = get_lang(self.env).code
            fmt = models.READ_GROUP_DISPLAY_FORMAT['month']
            for month, product_qty_sum in quantity_by_month_out:
                replenishment_history.append({
                    'name': babel.dates.format_datetime(month, format=fmt, locale=locale),
                    'quantity': product_qty_sum - quantity_by_month_returned.get(month, 0),
                    'uom_name': replenishment_report.product_id.uom_id.display_name,
                })
            replenishment_report.json_replenishment_history = dumps({
                'template': 'stock.replenishmentHistory',
                'replenishment_history': replenishment_history
            })


class StockReplenishmentOption(models.TransientModel):
    _name = 'stock.replenishment.option'
    _description = 'Stock warehouse replenishment option'

    route_id = fields.Many2one('stock.route')
    product_id = fields.Many2one('product.product')
    replenishment_info_id = fields.Many2one('stock.replenishment.info')

    location_id = fields.Many2one('stock.location', related='warehouse_id.lot_stock_id')
    warehouse_id = fields.Many2one('stock.warehouse', related='route_id.supplier_wh_id')
    uom = fields.Char(related='product_id.uom_name')
    qty_to_order = fields.Float(related='replenishment_info_id.qty_to_order')

    free_qty = fields.Float(compute='_compute_free_qty')
    lead_time = fields.Char(compute='_compute_lead_time')

    warning_message = fields.Char(compute='_compute_warning_message')

    @api.depends('product_id', 'route_id')
    def _compute_free_qty(self):
        for record in self:
            record.free_qty = record.product_id.with_context(location=record.location_id.id).free_qty

    @api.depends('replenishment_info_id')
    def _compute_lead_time(self):
        for record in self:
            rule = self.env['procurement.group']._get_rule(record.product_id, record.location_id, {
                'route_ids': record.route_id,
                'warehouse_id': record.warehouse_id,
            })
            delay = rule._get_lead_days(record.product_id)[0]['total_delay'] if rule else 0
            record.lead_time = _("%s days", delay)

    @api.depends('warehouse_id', 'free_qty', 'uom', 'qty_to_order')
    def _compute_warning_message(self):
        self.warning_message = ''
        for record in self:
            if record.free_qty < record.qty_to_order:
                record.warning_message = _(
                    '%(warehouse)s can only provide %(free_qty)s %(uom)s, while the quantity to order is %(qty_to_order)s %(uom)s.',
                    warehouse=record.warehouse_id.name,
                    free_qty=record.free_qty,
                    uom=record.uom,
                    qty_to_order=record.qty_to_order
                )

    def select_route(self):
        if self.free_qty < self.qty_to_order:
            return {
                "type": "ir.actions.act_window",
                "res_model": "stock.replenishment.option",
                "res_id": self.id,
                "views": [[self.env.ref('stock.replenishment_option_warning_view').id, "form"]],
                "target": "new",
                "name": _("Quantity available too low")
            }
        return self.order_all()

    def order_avbl(self):
        self.replenishment_info_id.orderpoint_id.route_id = self.route_id
        self.replenishment_info_id.orderpoint_id.qty_to_order = self.free_qty
        return {'type': 'ir.actions.act_window_close'}

    def order_all(self):
        self.replenishment_info_id.orderpoint_id.route_id = self.route_id
        return {'type': 'ir.actions.act_window_close'}
