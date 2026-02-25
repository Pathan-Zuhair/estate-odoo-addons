from odoo import models
from odoo.exceptions import UserError


class EstateProperty(models.Model):
    _inherit = 'estate.property'

    def action_sold(self):
        for record in self:
            if not record.buyer_id:
                raise UserError("Cannot create invoice: no buyer defined.")

            if not record.selling_price:
                raise UserError("Cannot create invoice: selling price is not set.")

            selling_price = record.selling_price
            commission = selling_price * 0.06
            admin_fee = 100.0

            invoice = self.env['account.move'].create({
                'move_type': 'out_invoice',
                'partner_id': record.buyer_id.id,
                'invoice_line_ids': [
                    # 1️⃣ Property price
                    (0, 0, {
                        'name': 'Property Selling Price',
                        'quantity': 1,
                        'price_unit': selling_price,
                    }),

                    # 2️⃣ 6% commission
                    (0, 0, {
                        'name': '6% Commission',
                        'quantity': 1,
                        'price_unit': commission,
                    }),

                    # 3️⃣ Administrative fee
                    (0, 0, {
                        'name': 'Administrative Fees',
                        'quantity': 1,
                        'price_unit': admin_fee,
                    }),
                ],
            })

            print("Invoice created:", invoice.id)

        return super().action_sold()