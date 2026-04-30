{
    'name': 'Estate Account',
    'version': '1.0',
    'category': 'Real Estate',
    'summary': 'Link module between Estate and Accounting',
    'depends': [
        'estate',
        'account',
        'mail',
    ],
    'sequence': 2,
    'data': ['views/estate_property_invoice_page.xml'],
    'installable': True,
    'application': True,
}
