{
    'name': 'BiziShip',
    'version': '17.0.2.0.0',
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
        'wizards/biziship_freight_quote_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
