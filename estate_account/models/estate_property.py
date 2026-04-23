from odoo import models, fields, api
from odoo.exceptions import UserError


class EstateProperty(models.Model):
    _inherit = 'estate.property'

    invoice_ids = fields.Many2one(
        'account.move',
        compute='_compute_invoice_ids',
        string='Invoices',
    )

    @api.depends('state')
    def _compute_invoice_ids(self):
        for record in self:
            record.invoice_ids = self.env['account.move'].search([
                ('property_id', '=', record.id),
            ])

    def action_sold(self):
        for record in self:
            if not record.buyer_id:
                raise UserError("Cannot create invoice: no buyer defined.")

            if not record.selling_price or record.selling_price <= 0:
                raise UserError("Cannot create invoice: selling price is not set.")

            # Define variables clearly before using them
            price = record.selling_price
            comm_amount = price * 0.06
            fee = 100.0

            # Create the invoice using .sudo() to bypass the Access Error
            # without giving the Seller 'Invoicing' permissions.
            self.env['account.move'].sudo().create({
                'move_type': 'out_invoice',
                'partner_id': record.buyer_id.id,
                'property_id': record.id,
                'invoice_line_ids': [
                    (0, 0, {
                        'name': 'Property Selling Price',
                        'quantity': 1,
                        'price_unit': price,
                    }),
                    (0, 0, {
                        'name': '6% Commission',
                        'quantity': 1,
                        'price_unit': comm_amount,
                    }),
                    (0, 0, {
                        'name': 'Administrative Fees',
                        'quantity': 1,
                        'price_unit': fee,
                    }),
                ],
            })

        # Call the parent method to update the property state to 'Sold'
        return super().action_sold()