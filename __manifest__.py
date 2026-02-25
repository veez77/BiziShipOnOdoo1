{
    'name': 'BiziShipOnOdoo1',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Parse BOL PDFs and send to Email2Quote API',
    'description': """
        This module allows users to upload a Bill of Lading (BOL) PDF,
        parses it using an AI LLM (Groq) to extract LTL dimensions, weight, etc.,
        and sends the data to an external API.
    """,
    'author': 'BiziShip',
    'website': 'https://www.biziship.ai',
    'depends': ['base', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/biziship_bol_wizard_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
