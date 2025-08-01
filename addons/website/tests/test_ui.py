# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import json
import unittest

from werkzeug.urls import url_encode

import odoo
import odoo.tests
from odoo import http
from odoo.addons.base.tests.common import HttpCaseWithUserDemo
from odoo.addons.web_editor.controllers.main import Web_Editor
from odoo.addons.website.tests.common import HttpCaseWithWebsiteUser
from odoo.fields import Command


@odoo.tests.tagged('-at_install', 'post_install')
class TestUiCustomizeTheme(odoo.tests.HttpCase):
    def test_01_attachment_website_unlink(self):
        ''' Some ir.attachment needs to be unlinked when a website is unlink,
            otherwise some flows will just crash. That's the case when 2 website
            have their theme color customized. Removing a website will make its
            customized attachment generic, thus having 2 attachments with the
            same URL available for other websites, leading to singleton errors
            (among other).

            But no all attachment should be deleted, eg we don't want to delete
            a SO or invoice PDF coming from an ecommerce order.
        '''
        Website = self.env['website']
        Page = self.env['website.page']
        Attachment = self.env['ir.attachment']

        website_default = Website.browse(1)
        website_test = Website.create({'name': 'Website Test'})

        # simulate attachment state when editing 2 theme through customize
        custom_url = '/_custom/web.assets_frontend/TEST/website/static/src/scss/options/colors/user_theme_color_palette.scss'
        scss_attachment = Attachment.create({
            'name': custom_url,
            'type': 'binary',
            'mimetype': 'text/scss',
            'datas': '',
            'url': custom_url,
            'website_id': website_default.id
        })
        scss_attachment.copy({'website_id': website_test.id})

        # simulate PDF from ecommerce order
        # Note: it will only have its website_id flag if the website has a domain
        # equal to the current URL (fallback or get_current_website())
        so_attachment = Attachment.create({
            'name': 'SO036.pdf',
            'type': 'binary',
            'mimetype': 'application/pdf',
            'datas': '',
            'website_id': website_test.id
        })

        # avoid sql error on page website_id restrict
        Page.search([('website_id', '=', website_test.id)]).unlink()
        website_test.unlink()
        self.assertEqual(Attachment.search_count([('url', '=', custom_url)]), 1, 'Should not left duplicates when deleting a website')
        self.assertTrue(so_attachment.exists(), 'Most attachment should not be deleted')
        self.assertFalse(so_attachment.website_id, 'Website should be removed')


@odoo.tests.tagged('-at_install', 'post_install')
class TestUiHtmlEditor(HttpCaseWithUserDemo):

    def test_html_editor_language(self):
        Lang = self.env['res.lang']
        Page = self.env['website.page']

        default_website = self.env.ref('website.default_website')
        parseltongue = Lang.create({
            'name': 'Parseltongue',
            'code': 'pa_GB',
            'iso_code': 'pa_GB',
            'url_code': 'pa_GB',
        })
        Lang._activate_lang(parseltongue.code)
        default_website.write({
            'language_ids': [
                Command.link(parseltongue.id),
            ],
            'default_lang_id': parseltongue.id,
        })

        page = Page.create({
            'name': 'Test page',
            'type': 'qweb',
            'arch': '''
                <t t-call="website.layout">
                    <div>rumbler</div>
                </t>
            ''',
            'key': 'test.generic_view',
            'website_id': default_website.id,
            'is_published': True,
            'url': '/test_page',
        })

        page.view_id.update_field_translations('arch_db', {
            parseltongue.code: {
                'rumbler': 'rommelpot',
            }
        })
        self.env.ref('base.user_admin').lang = parseltongue.code
        self.start_tour(self.env['website'].get_client_action_url('/test_page'), 'html_editor_language', login='admin')
        self.assertIn("rumbler", page.view_id.with_context(lang='en_US').arch)
        self.assertIn("rommelpot", page.view_id.with_context(lang='pa_GB').arch)

    def test_html_editor_multiple_templates(self):
        Website = self.env['website']
        View = self.env['ir.ui.view']
        Page = self.env['website.page']

        self.generic_view = View.create({
            'name': 'Generic',
            'type': 'qweb',
            'arch': '''
                <div>content</div>
            ''',
            'key': 'test.generic_view',
        })

        self.generic_page = Page.create({
            'view_id': self.generic_view.id,
            'url': '/generic',
        })

        generic_page = Website.viewref('test.generic_view')
        # Use an empty page layout with oe_structure id for this test
        oe_structure_layout = '''
            <t name="Generic" t-name="test.generic_view">
                <t t-call="website.layout">
                    <div id="oe_structure_test_ui" class="oe_structure oe_empty"/>
                </t>
            </t>
        '''
        generic_page.arch = oe_structure_layout
        oe_structure_layout = generic_page.arch
        self.start_tour(self.env['website'].get_client_action_url('/generic'), 'html_editor_multiple_templates', login='admin')
        self.assertEqual(View.search_count([('key', '=', 'test.generic_view')]), 2, "homepage view should have been COW'd")
        self.assertTrue(generic_page.arch == oe_structure_layout, "Generic homepage view should be untouched")
        self.assertEqual(len(generic_page.inherit_children_ids.filtered(lambda v: 'oe_structure' in v.name)), 0, "oe_structure view should have been deleted when aboutus was COW")
        specific_page = Website.with_context(website_id=1).viewref('test.generic_view')
        self.assertTrue(specific_page.arch != oe_structure_layout, "Specific homepage view should have been changed")
        self.assertEqual(len(specific_page.inherit_children_ids.filtered(lambda v: 'oe_structure' in v.name)), 1, "oe_structure view should have been created on the specific tree")

    def test_html_editor_scss(self):
        self.user_demo.write({
            'group_ids': [(6, 0, [
                self.env.ref('base.group_user').id,
                self.env.ref('website.group_website_designer').id
            ])]
        })
        self.start_tour(self.env['website'].get_client_action_url('/contactus'), 'test_html_editor_scss', login='admin')
        self.start_tour(self.env['website'].get_client_action_url('/'), 'test_html_editor_scss_2', login='demo')

    def test_ace_editor_is_hidden(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'test_ace_editor_is_hidden', login='admin')

    def test_media_dialog_undraw(self):
        BASE_URL = self.base_url()
        banner = '/website/static/src/img/snippets_demo/s_banner.jpg'

        def mock_media_library_search(self, **params):
            return {
                'results': 1,
                'media': [{
                    'id': 1,
                    'media_url': BASE_URL + banner,
                    'thumbnail_url': BASE_URL + banner,
                    'tooltip': False,
                    'author': 'undraw',
                    'author_link': BASE_URL,
                }],
            }

        # disable undraw, no third party should be called in tests
        # Mocked for the previews in the media dialog
        mock_media_library_search.routing_type = 'json'
        Web_Editor.media_library_search = http.route(['/web_editor/media_library_search'], type='jsonrpc', auth='user', website=True)(mock_media_library_search)

        self.start_tour("/", 'website_media_dialog_undraw', login='admin')

    def test_code_editor_usable(self):
        # TODO: enable debug mode when failing tests have been fixed (props validation)
        url = '/odoo/action-website.website_preview'
        self.start_tour(url, 'website_code_editor_usable', login='admin')


@odoo.tests.tagged('external', '-standard', '-at_install', 'post_install')
class TestUiHtmlEditorWithExternal(HttpCaseWithUserDemo):
    def test_media_dialog_external_library(self):
        self.start_tour("/", 'website_media_dialog_external_library', login='admin')


@odoo.tests.tagged('-at_install', 'post_install')
class TestUiTranslate(odoo.tests.HttpCase):
    def test_admin_tour_rte_translator(self):
        self.env['res.lang'].create({
            'name': 'Parseltongue',
            'code': 'pa_GB',
            'iso_code': 'pa_GB',
            'url_code': 'pa_GB',
        })
        self.start_tour(self.env['website'].get_client_action_url('/'), 'rte_translator', login='admin', timeout=120)

    def test_translate_menu_name(self):
        lang_en = self.env.ref('base.lang_en')
        parseltongue = self.env['res.lang'].create({
            'name': 'Parseltongue',
            'code': 'pa_GB',
            'iso_code': 'pa_GB',
            'url_code': 'pa_GB',
        })
        self.env['res.lang']._activate_lang(parseltongue.code)
        default_website = self.env.ref('website.default_website')
        default_website.write({
            'default_lang_id': lang_en.id,
            'language_ids': [(6, 0, (lang_en + parseltongue).ids)],
        })
        new_menu = self.env['website.menu'].create({
            'name': 'Menu to edit',
            'parent_id': default_website.menu_id.id,
            'website_id': default_website.id,
            'url': '/englishURL',
        })

        self.start_tour(self.env['website'].get_client_action_url('/'), 'translate_menu_name', login='admin')

        self.assertNotEqual(new_menu.name, 'value pa-GB', msg="The new menu should not have its value edited, only its translation")
        self.assertEqual(new_menu.with_context(lang=parseltongue.code).name, 'value pa-GB', msg="The new translation should be set")

    # TODO master-mysterious-egg fix error
    @unittest.skip("prepare mysterious-egg for merging")
    def test_translate_text_options(self):
        lang_en = self.env.ref('base.lang_en')
        lang_fr = self.env.ref('base.lang_fr')
        self.env['res.lang']._activate_lang(lang_fr.code)
        default_website = self.env.ref('website.default_website')
        default_website.write({
            'default_lang_id': lang_en.id,
            'language_ids': [(6, 0, (lang_en + lang_fr).ids)],
        })

        self.start_tour(self.env['website'].get_client_action_url('/'), 'translate_text_options', login='admin')

    def test_snippet_translation(self):
        ResLang = self.env['res.lang']
        parseltongue, fake_user_lang = ResLang.create([{
            'name': 'Parseltongue',
            'code': 'pa_GB',
            'iso_code': 'pa_GB',
            'url_code': 'pa_GB',
            'direction': 'rtl',
        }, {
            'name': 'Fake User Lang',
            'code': 'fu_GB',
            'iso_code': 'fu_GB',
            'url_code': 'fu_GB',
        }])
        ResLang._activate_lang(parseltongue.code)
        ResLang._activate_lang(fake_user_lang.code)
        self.env.ref('base.user_admin').lang = fake_user_lang.code
        self.env.ref('website.s_cover').update_field_translations('arch_db', {
            parseltongue.code: {
                # See contact_us_label
                'Contact us': 'Contact us in Parseltongue'
            },
            fake_user_lang.code: {
                'Contact us': 'Contact us in Fake User Lang'
            }
        })
        website = self.env['website'].create({
            'name': 'website pa_GB',
            'language_ids': [(6, 0, [parseltongue.id])],
            'default_lang_id': parseltongue.id,
        })
        website_2 = self.env['website'].create({
            'name': 'website en_US',
            'language_ids': [(6, 0, [self.env.ref('base.lang_en').id, parseltongue.id])],
            'default_lang_id': parseltongue.id,
        })
        self.env['website'].create({
            'name': 'website fu_GB',
            'language_ids': [Command.set([fake_user_lang.id])],
            'default_lang_id': fake_user_lang.id,
        })

        self.start_tour(f"/website/force/{website.id}", 'snippet_translation', login='admin')
        self.start_tour(f"/website/force/{website_2.id}", 'snippet_translation_changing_lang', login='admin')
        self.start_tour(f"/website/force/{website_2.id}", 'snippet_translation_switching_website', login='admin')
        self.start_tour(f"/website/force/{website.id}", 'snippet_dialog_rtl', login='admin')


@odoo.tests.common.tagged('post_install', '-at_install')
class TestUi(HttpCaseWithWebsiteUser):

    def test_01_admin_tour_homepage(self):
        self.start_tour("/odoo", 'homepage', login='admin')

    def test_02_restricted_editor(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'restricted_editor', login="website_user")

    def test_04_website_navbar_menu(self):
        website = self.env['website'].search([], limit=1)
        self.env['website.menu'].create({
            'name': 'Test Tour Menu',
            'url': '/test-tour-menu',
            'parent_id': website.menu_id.id,
            'sequence': 0,
            'website_id': website.id,
        })
        self.start_tour("/", 'website_navbar_menu')

    def test_05_specific_website_editor(self):
        asset_bundle_xmlid = "website.assets_edit_frontend"
        website_default = self.env['website'].search([], limit=1)

        new_website = self.env['website'].create({'name': 'New Website'})

        code = b"document.body.dataset.hello = 'world';"
        attach = self.env['ir.attachment'].create({
            'name': 'EditorExtension.js',
            'mimetype': 'text/javascript',
            'datas': base64.b64encode(code),
        })
        custom_url = '/_custom/web/content/%s/%s' % (attach.id, attach.name)
        attach.url = custom_url

        self.env['ir.asset'].create({
            'name': 'EditorExtension',
            'bundle': "website.assets_edit_frontend",
            'path': custom_url,
            'website_id': new_website.id,
        })

        base_website_bundle = self.env['ir.qweb']._get_asset_bundle(asset_bundle_xmlid, assets_params={'website_id': website_default.id})
        self.assertNotIn(custom_url, [f['url'] for f in base_website_bundle.files])
        base_website_css_version = base_website_bundle.get_version('css')
        base_website_js_version = base_website_bundle.get_version('js')

        new_website_bundle_modified = self.env['ir.qweb']._get_asset_bundle("website.assets_edit_frontend", assets_params={'website_id': new_website.id})
        self.assertIn(custom_url, [f['url'] for f in new_website_bundle_modified.files])
        self.assertEqual(new_website_bundle_modified.get_version('css'), base_website_css_version)
        self.assertNotEqual(new_website_bundle_modified.get_version('js'), base_website_js_version, "js version for new website should now have been changed")

        url_params = url_encode({'path': '/@/'})
        self.start_tour(f'/website/force/{website_default.id}?{url_params}', "generic_website_editor", login="website_user")
        self.start_tour(f'/website/force/{new_website.id}?{url_params}', "specific_website_editor", login="website_user")

    def test_06_public_user_editor(self):
        website_default = self.env['website'].search([], limit=1)
        self.env['website.page'].search([
            ('url', '=', '/'), ('website_id', '=', website_default.id)
        ], limit=1).arch = """
            <t name="Homepage" t-name="website.homepage">
                <t t-call="website.layout">
                    <textarea class="o_public_user_editor_test_textarea o_wysiwyg_loader"/>
                </t>
            </t>
        """
        self.start_tour("/", "public_user_editor", login=None)

    def test_07_snippet_version(self):
        website_snippets = self.env.ref('website.snippets')
        view_ids = self.env['ir.ui.view'].create([{
            'name': 'Test snip',
            'type': 'qweb',
            'key': 'website.s_test_snip',
            'arch': """
                <section class="s_test_snip">
                    <t t-snippet-call="website.s_share"/>
                </section>
            """,
        }, {
            'type': 'qweb',
            'inherit_id': website_snippets.id,
            'arch': """
                <xpath expr="//t[@t-snippet='website.s_parallax']" position="after">
                    <t t-snippet="website.s_test_snip" group="content"/>
                </xpath>
            """,
        }])
        self.start_tour(self.env['website'].get_client_action_url('/'), 'snippet_version_1', login='admin')

        self.env['ir.ui.view'].create([
            {
                'name': 'Test snippet version 999',
                'mode': 'extension',
                'inherit_id': view_ids[0].id,
                'arch': """
                    <xpath expr="//section[hasclass('s_test_snip')]" position="attributes">
                        <attribute name="data-vjs">999</attribute>
                    </xpath>
                """
            },
            {
                'name': 'Share snippet version 999',
                'mode': 'extension',
                'inherit_id': self.env.ref("website.s_share").id,
                'arch': """
                    <xpath expr="//div" position="attributes">
                        <attribute name="data-vcss">999</attribute>
                    </xpath>
                """
            },
            {
                'name': 's_text_image version 999',
                'mode': 'extension',
                'inherit_id': self.env.ref("website.s_text_image").id,
                'arch': """
                    <xpath expr="//section[hasclass('s_text_image')]" position="attributes">
                        <attribute name="data-vxml">999</attribute>
                    </xpath>
                """
            }
        ])

        self.start_tour(self.env['website'].get_client_action_url('/'), 'snippet_version_2', login='admin')

    def test_08_website_style_custo(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'website_style_edition', login='admin')

    def test_09_website_edit_link_popover(self):
        self.start_tour('/@/', 'edit_link_popover', login='admin', timeout=180)

    def test_10_website_conditional_visibility(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'conditional_visibility_1', login='admin')
        self.start_tour('/odoo', 'conditional_visibility_2', login='website_user')
        self.start_tour(self.env['website'].get_client_action_url('/'), 'conditional_visibility_3', login='admin', timeout=180)
        self.start_tour(self.env['website'].get_client_action_url('/'), 'conditional_visibility_4', login='admin')
        self.start_tour(self.env['website'].get_client_action_url('/'), 'conditional_visibility_5', login='admin')

    def test_11_website_snippet_background_edition(self):
        self.env['ir.attachment'].create({
            'public': True,
            'type': 'url',
            'url': '/web/image/123/test.png',
            'name': 'test.png',
            'mimetype': 'image/png',
        })
        self.start_tour(self.env['website'].get_client_action_url('/'), 'snippet_background_edition', login='admin')

    def test_12_edit_translated_page_redirect(self):
        lang = self.env['res.lang']._activate_lang('nl_NL')
        self.env['website'].browse(1).write({'language_ids': [(4, lang.id, 0)]})
        self.start_tour("/nl/contactus", 'edit_translated_page_redirect', login='admin')

    def test_14_carousel_snippet_content_removal(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'carousel_content_removal', login='admin')

    # TODO master-mysterious-egg fix error
    @unittest.skip("prepare mysterious-egg for merging")
    def test_15_website_link_tools(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'link_tools', login="admin")

    def test_16_website_edit_megamenu(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'edit_megamenu', login='admin')

    def test_website_megamenu_active_nav_link(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'megamenu_active_nav_link', login='admin')

    def test_17_website_edit_menus(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'edit_menus', login='admin')

    def test_18_website_snippets_menu_tabs(self):
        self.start_tour('/', 'website_snippets_menu_tabs', login='admin')

    def test_19_website_page_options(self):
        self.start_tour("/odoo", "website_page_options", login="admin")

    def test_20_snippet_editor_panel_options(self):
        self.start_tour('/@/', 'snippet_editor_panel_options', login='admin')

    def test_21_website_start_cloned_snippet(self):
        self.start_tour('/odoo', 'website_start_cloned_snippet', login='admin')

    def test_22_website_gray_color_palette(self):
        self.start_tour('/odoo', 'website_gray_color_palette', login='admin')

    def test_23_website_multi_edition(self):
        self.start_tour('/@/', 'website_multi_edition', login='admin')

    def test_24_snippet_cache_across_websites(self):
        default_website = self.env.ref('website.default_website')
        website = self.env['website'].create({
            'name': 'Test Website',
            'domain': '',
            'sequence': 20
        })
        self.env['ir.ui.view'].with_context(website_id=default_website.id).save_snippet(
            name='custom_snippet_test',
            arch="""
                <section class="s_text_block" data-snippet="s_text_block">
                    <div class="custom_snippet_website_1">Custom Snippet Website 1</div>
                </section>
            """,
            thumbnail_url='/website/static/src/img/snippets_thumbs/s_text_block.svg',
            snippet_key='s_text_block',
            template_key='website.snippets')
        self.start_tour('/@/', 'snippet_cache_across_websites', login='admin', cookies={
            'websiteIdMapping': json.dumps({'Test Website': website.id})
        })

    def test_26_website_media_dialog_icons(self):
        self.env.ref('website.default_website').write({
            'social_twitter': 'https://twitter.com/Odoo',
            'social_facebook': 'https://www.facebook.com/Odoo',
            'social_linkedin': 'https://www.linkedin.com/company/odoo',
            'social_youtube': 'https://www.youtube.com/user/OpenERPonline',
            'social_github': 'https://github.com/odoo',
            'social_instagram': 'https://www.instagram.com/explore/tags/odoo/',
            'social_tiktok': 'https://www.tiktok.com/@odoo',
            'social_discord': 'https://discord.com/servers/discord-town-hall-169256939211980800',
        })
        self.start_tour("/", 'website_media_dialog_icons', login='admin')

    def test_27_website_clicks(self):
        self.start_tour('/odoo', 'website_click_tour', login='admin')

    def test_29_website_text_edition(self):
        self.start_tour('/@/', 'website_text_edition', login='admin')

    def test_29_website_backend_menus_redirect(self):
        Menu = self.env['ir.ui.menu']
        menu_root = Menu.create({'name': 'Test Root'})
        Menu.create({
            'name': 'Test Child',
            'parent_id': menu_root.id,
            'action': 'ir.actions.act_window,%d' % (self.env.ref('base.open_module_tree').id,),
        })
        self.env.ref('base.user_admin').action_id = self.env.ref('base.menu_administration').id
        self.assertFalse(menu_root.action, 'The top menu should not have an action (or the test/tour will not test anything).')
        self.start_tour('/', 'website_backend_menus_redirect', login='admin')

    def test_30_website_text_animations(self):
        self.start_tour("/", 'text_animations', login='admin')

    def test_31_website_edit_megamenu_big_icons_subtitles(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'edit_megamenu_big_icons_subtitles', login='admin')

    def test_32_website_background_colorpicker(self):
        self.start_tour(self.env['website'].get_client_action_url("/"), "website_background_colorpicker", login="admin")

    def test_website_media_dialog_image_shape(self):
        self.start_tour("/", 'website_media_dialog_image_shape', login='admin')

    def test_website_media_dialog_insert_media(self):
        self.start_tour("/", "website_media_dialog_insert_media", login="admin")

    def test_website_text_font_size(self):
        self.start_tour('/@/', 'website_text_font_size', login='admin', timeout=300)

    def test_update_column_count(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'website_update_column_count', login="admin")

    def test_website_text_highlights(self):
        self.start_tour("/", 'text_highlights', login='admin')

    def test_website_extra_items_no_dirty_page(self):
        """
        Having enough menus to trigger the "+" folded menus has been known to
        wrongfully mark the page as dirty. There are 3 cases:

        - the menu is not folded outside of edit mode and when entering edit
          mode, the "+" appears and some menu are folded

        - the menu is folded outside of edit mode and when entering edit mode
          the resize actually makes it so different menu items are folded

        - the menu is folded outside of edit mode and when entering edit mode it
          stays the same (known to have been broken because edit mode tweaks the
          dropdown behavior)

        Those are fixed. This test makes sure the third case stays fixed.
        At the moment, the first two cases are not marking the page as dirty but
        the related "+" menu behavior is kinda broken so it would be difficult
        to test (TODO).
        """
        # Remove all menu items but the first one
        website = self.env['website'].get_current_website()
        website.menu_id.child_id[1:].unlink()
        # Create a new menu item whose text is very long so that we are sure
        # it is folded into the extra items "+" menu outside of edit mode and
        # stays the same when entering edit mode.
        self.env['website.menu'].create({
            'name': 'Menu %s' % ('a' * 200),  # Very long text
            'website_id': website.id,
            'parent_id': website.menu_id.id,
        })

        self.start_tour('/', 'website_no_action_no_dirty_page', login='admin')

    def test_website_no_dirty_page(self):
        # Previous tests are testing the dirty behavior when the extra items
        # "+" menu comes in play. For other "no dirty" tests, we just remove
        # most menu items first to make sure they pass independently.
        website = self.env['website'].get_current_website()
        website.menu_id.child_id[1:].unlink()

        self.start_tour('/', 'website_no_dirty_page', login='admin')

    def test_interaction_lifecycle(self):
        self.env['ir.asset'].create({
            'name': 'wysiwyg_patch_start_and_destroy',
            'bundle': 'website.assets_wysiwyg',
            'path': 'website/static/tests/tour_utils/lifecycle_patch_wysiwyg.js',
        })
        self.start_tour(self.env['website'].get_client_action_url('/'), 'interaction_lifecycle', login='admin')

    # TODO master-mysterious-egg fix error
    @unittest.skip("prepare mysterious-egg for merging")
    def test_drop_404_ir_attachment_url(self):
        website_snippets = self.env.ref('website.snippets')
        self.env['ir.ui.view'].create([{
            'name': '404 Snippet',
            'type': 'qweb',
            'key': 'website.s_404_snippet',
            'arch': """
                <section class="s_404_snippet">
                    <div class="container">
                        <img class="img-responsive img-thumbnail" src="/web/image/website.404_ir_attachment"/>
                    </div>
                </section>
            """,
        }, {
            'type': 'qweb',
            'inherit_id': website_snippets.id,
            'arch': """
                <xpath expr="//t[@t-snippet='website.s_parallax']" position="after">
                    <t t-snippet="website.s_404_snippet" group="images"/>
                </xpath>
            """,
        }])
        attachment = self.env['ir.attachment'].create({
            'name': '404_ir_attachment',
            'type': 'url',
            'url': '/web/static/__some__typo__.png',
            'mimetype': 'image/png',
        })
        self.env['ir.model.data'].create({
            'name': '404_ir_attachment',
            'module': 'website',
            'model': 'ir.attachment',
            'res_id': attachment.id,
        })
        self.start_tour(self.env['website'].get_client_action_url('/'), 'drop_404_ir_attachment_url', login='admin')

    def test_mobile_order_with_drag_and_drop(self):
        self.start_tour(self.env['website'].get_client_action_url('/'), 'website_mobile_order_with_drag_and_drop', login='admin')

    def test_powerbox_snippet(self):
        self.start_tour('/', 'website_powerbox_snippet', login='admin')
        self.start_tour('/', 'website_powerbox_keyword', login='admin')

    def test_website_no_dirty_lazy_image(self):
        website = self.env['website'].browse(1)
        # Enable multiple langs to reduce the chance of the test being silently
        # broken by ensuring that it receives a lot of extra o_dirty elements.
        # This is done to account for potential later changes in the number of
        # o_dirty elements caused by legitimate modifications in the code.
        # Perfs: `_activate_lang()` does not load .pot so it is perf friendly
        lang_fr = self.env['res.lang']._activate_lang('fr_FR')
        lang_es = self.env['res.lang']._activate_lang('es_AR')
        lang_zh = self.env['res.lang']._activate_lang('zh_HK')
        lang_ar = self.env['res.lang']._activate_lang('ar_SY')
        website.language_ids = self.env.ref('base.lang_en') + lang_fr + lang_es + lang_zh + lang_ar
        # Select "dropdown with image" language selector template
        for key, active in [
            # footer
            ('portal.footer_language_selector', True),
            ('website.footer_language_selector_inline', False),
            ('website.footer_language_selector_flag', True),
            ('website.footer_language_selector_no_text', False),
            ('website.footer_language_selector_flag', True),
            ('website.footer_language_selector_no_text', False),
            # header
            ('website.header_language_selector', True),
            ('website.header_language_selector_inline', False),
            ('website.header_language_selector_flag', True),
            ('website.header_language_selector_no_text', False),
            ('website.header_language_selector_flag', True),
            ('website.header_language_selector_no_text', False),
        ]:
            self.env['website'].with_context(website_id=website.id).viewref(key).active = active

        self.start_tour('/', 'website_no_dirty_lazy_image', login='admin')

    def test_website_edit_menus_delete_parent(self):
        website = self.env['website'].browse(1)
        menu_tree = self.env['website.menu'].get_tree(website.id)

        parent_menu = menu_tree['children'][0]['fields']
        child_menu = menu_tree['children'][1]['fields']
        child_menu['parent_id'] = parent_menu['id']

        self.env['website.menu'].save(website.id, {'data': [parent_menu, child_menu]})
        self.start_tour(self.env['website'].get_client_action_url('/'), 'edit_menus_delete_parent', login='admin')

    def test_snippet_carousel(self):
        self.start_tour('/', 'snippet_carousel', login='admin')

    def test_snippet_carousel_autoplay(self):
        self.start_tour("/", "snippet_carousel_autoplay", login="admin")

    def test_media_iframe_video(self):
        self.start_tour("/", "website_media_iframe_video", login="admin")

    def test_snippet_visibility_option(self):
        self.start_tour("/", "snippet_visibility_option", login="admin")

    def test_website_font_family(self):
        self.start_tour("/", "website_font_family", login="admin")

    def test_website_seo_notification(self):
        self.start_tour(self.env['website'].get_client_action_url("/"), "website_seo_notification", login="admin")

    def test_website_add_snippet_dialog(self):
        self.start_tour("/", "website_add_snippet_dialog", login="admin")

    def test_popup_visibility_option(self):
        self.start_tour("/", "website_popup_visibility_option", login="admin")

    def test_systray_items_disappear(self):
        self.start_tour("/", "website_systray_items_disappear", login="admin")
