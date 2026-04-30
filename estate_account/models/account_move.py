# estate_account/models/account_move.py
from odoo import models, fields, api
from odoo.exceptions import AccessError

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


    def action_post(self):
        res = super().action_post()

        for move in self:
            # Only customer invoices
            if move.move_type != 'out_invoice':
                continue

            property_rec = move.property_id

            # Ensure linked property + seller exists
            if not property_rec or not property_rec.salesperson_id:
                continue

            seller = property_rec.salesperson_id

            # Message
            body = (
                f"INVOICE CONFIRMED\n\n"
                f"Property: {property_rec.name}\n"
                f"Buyer: {move.partner_id.name}\n"
                f"Invoice: {move.name}\n"
                f"Total Amount: ${move.amount_total:,.2f}"
            )

            # Send notification (Inbox + popup)
            property_rec.sudo().message_post(
                body=body,
                message_type='comment',
                subtype_xmlid='mail.mt_comment',
                partner_ids=[seller.partner_id.id],
                author_id=self.env.user.partner_id.id,
            )

        return res