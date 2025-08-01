# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo.tests import HttpCase, tagged

from odoo.addons.http_routing.tests.common import MockRequest


_logger = logging.getLogger(__name__)


@tagged('post_install', '-at_install', 'website_snippets')
class TestSnippets(HttpCase):

    def test_01_snippet_products_edition(self):
        self.env['product.product'].create({
            'name': 'Test Product',
            'website_published': True,
            'sale_ok': True,
            'list_price': 500,
        })
        self.env['product.product'].create({
            'name': 'Test Product 2',
            'website_published': True,
            'sale_ok': True,
            'list_price': 500,
        })
        self.env['product.product'].create({
            'name': 'Test Product 3',
            'website_published': True,
            'sale_ok': True,
            'list_price': 500,
        })
        self.env['product.product'].create({
            'name': 'Test Product 4',
            'website_published': True,
            'sale_ok': True,
            'list_price': 500,
        })
        self.start_tour('/', 'website_sale.snippet_products', login='admin')

    def test_02_snippet_products_remove(self):
        Visitor = self.env['website.visitor']
        user = self.env['res.users'].search([('login', '=', 'admin')])
        website_visitor = Visitor.search([('partner_id', '=', user.partner_id.id)])
        if not website_visitor:
            with MockRequest(user.with_user(user).env, website=self.env['website'].get_current_website()):
                website_visitor = Visitor.create({'partner_id': user.partner_id.id})
        self.assertEqual(website_visitor.name, user.name, "The visitor should be linked to the admin user, not OdooBot or anything.")
        self.product = self.env['product.product'].create({
            'name': 'Storage Box',
            'website_published': True,
            'image_512': b'/product/static/img/product_product_9-image.jpg',
            'display_name': 'Bin',
            'description_sale': 'Pedal-based opening system',
        })
        before_tour_product_ids = website_visitor.product_ids.ids
        website_visitor._add_viewed_product(self.product.id)

        self.start_tour('/', 'website_sale.products_snippet_recently_viewed', login='admin')
        self.assertEqual(before_tour_product_ids, website_visitor.product_ids.ids, "There shouldn't be any new product in recently viewed after this tour")
