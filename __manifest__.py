{
    'name': 'BiziShip',
    'version': '17.0.2.0.8',
    'category': 'Sales',
    'summary': 'AI-Powered LTL Quoting & Automated Freight Procurement',
    'description': """
        The ultimate shipping companion for Odoo. Supercharge your logistics 
        with instant Mega-Search LTL quoting, real-time rate shopping, and 
        AI-driven BOL extraction to optimize your bottom line.
    """,
    'author': 'BiziShip',
    'depends': ['base', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/accessorial_data.xml',
        'wizards/biziship_bol_wizard_views.xml',
        'wizards/biziship_quote_confirm_wizard_views.xml',
        'wizards/biziship_booking_warning_wizard_views.xml',
        'wizards/biziship_freight_quote_wizard_views.xml',
        'wizards/biziship_auth_wizard_views.xml',
        'wizards/biziship_save_freight_wizard_views.xml',
        'wizards/biziship_load_freight_wizard_views.xml',
        'wizards/biziship_tracking_wizard_views.xml',
        'views/sale_order_views.xml',
        'views/res_users_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'biziship/static/src/js/biziship_tab_handler.js',
            'biziship/static/src/js/biziship_places_autocomplete.js',
            'biziship/static/src/js/biziship_commodity_autocomplete.js',
            'biziship/static/src/xml/biziship_commodity_templates.xml',
            'biziship/static/src/css/biziship_modern.css',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
