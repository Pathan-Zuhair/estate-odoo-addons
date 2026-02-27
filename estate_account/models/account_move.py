# estate_account/models/account_move.py
from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    # Link invoice to a property
    property_id = fields.Many2one(
        'estate.property',
        string='Property',
        help='The property related to this invoice'
    )

    # Boolean to indicate if invoice is for a sold property
    property_sold = fields.Boolean(
        string='Property Sold',
        compute='_compute_property_sold',
        store=True,
    )

    @api.depends('property_id.state')
    def _compute_property_sold(self):
        for move in self:
            move.property_sold = bool(move.property_id and move.property_id.state == 'sold')