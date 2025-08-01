{
    'name': "HTML Editor",
    'summary': """
        A Html Editor component and plugin system
    """,
    'description': """
Html Editor
==========================
This addon provides an extensible, maintainable editor.
    """,

    'author': "odoo",
    'website': "https://www.odoo.com",
    'version': '1.0',
    'category': 'Hidden',
    'depends': ['base', 'bus', 'web'],
    'auto_install': True,
    'assets': {
        'web.assets_frontend': [
            ('include', 'html_editor.assets_media_dialog'),
            ('include', 'html_editor.assets_readonly'),
            'html_editor/static/src/public/**/*',
        ],
        'web.assets_backend': [
            ('include', 'html_editor.assets_editor'),
            'html_editor/static/src/others/dynamic_placeholder_plugin.js',
            'html_editor/static/src/backend/**/*',
            'html_editor/static/src/fields/**/*',
        ],
        'html_editor.assets_editor': [
            'web/static/lib/dompurify/DOMpurify.js',
            ('include', 'html_editor.assets_media_dialog'),
            ('include', 'html_editor.assets_readonly'),
            'html_editor/static/src/*',
            'html_editor/static/src/components/history_dialog/**/*',
            'html_editor/static/src/core/**/*',
            'html_editor/static/src/main/**/*',
            'html_editor/static/src/others/collaboration/**/*',
            'html_editor/static/src/others/embedded_components/**/*',
            'html_editor/static/src/others/embedded_component*',
            'html_editor/static/src/others/qweb_picker*',
            'html_editor/static/src/others/qweb_plugin*',
            'html_editor/static/src/services/**/*',
            ('remove', 'html_editor/static/src/components/history_dialog/history_dialog.dark.scss'),
            ('remove', 'html_editor/static/src/main/movenode.dark.scss'),
            ('remove', 'html_editor/static/src/main/toolbar/toolbar.dark.scss'),
            ('remove', 'html_editor/static/src/main/chatgpt/language_selector.dark.scss'),
            ('remove', 'html_editor/static/src/main/table/table_align_selector.dark.scss'),
        ],
        'html_editor.assets_media_dialog': [
            # Bundle to use the media dialog in the backend and the frontend
            'html_editor/static/src/components/switch/**/*',
            'html_editor/static/src/main/media/media_dialog/**/*',
        ],
        'html_editor.assets_readonly': [
            'html_editor/static/src/components/html_viewer/**/*',
            'html_editor/static/src/local_overlay_container.*',
            'html_editor/static/src/main/local_overlay.scss',
            'html_editor/static/src/position_hook.*',
            'html_editor/static/src/html_migrations/**/*',
            'html_editor/static/src/main/list/list.scss',
            'html_editor/static/src/main/media/file.scss',
            'html_editor/static/src/others/embedded_component_utils.js',
            'html_editor/static/src/others/embedded_components/core/**/*',
            'html_editor/static/src/utils/**/*',
        ],
        "web.assets_web_dark": [
            'html_editor/static/src/components/history_dialog/history_dialog.dark.scss',
            'html_editor/static/src/main/movenode.dark.scss',
            'html_editor/static/src/main/toolbar/toolbar.dark.scss',
            'html_editor/static/src/main/chatgpt/language_selector.dark.scss',
            'html_editor/static/src/main/table/table_align_selector.dark.scss',
        ],
        'web.assets_tests': [
            'html_editor/static/tests/tours/**/*',
        ],
        'web.assets_unit_tests': [
            'html_editor/static/tests/**/*',
        ],
        'web.assets_unit_tests_setup': [
            'html_editor/static/src/public/**/*',
        ],
        'html_editor.assets_image_cropper': [
            'html_editor/static/lib/cropperjs/cropper.css',
            'html_editor/static/lib/cropperjs/cropper.js',
            'html_editor/static/lib/webgl-image-filter/webgl-image-filter.js',
        ],
    },
    'license': 'LGPL-3'
}
