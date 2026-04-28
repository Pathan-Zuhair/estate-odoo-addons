from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    property_id = fields.Many2one(
        'estate.property',
        string='Property',
        help='The property related to this invoice'
    )

    property_sold = fields.Boolean(
        string='Property Sold',
        compute='_compute_property_sold',
        store=True,
    )

    @api.depends('property_id.state')
    def _compute_property_sold(self):
        for move in self:
            move.property_sold = bool(
                move.property_id and move.property_id.state == 'sold'
            )

    def _is_estate_readonly_user(self):
        user = self.env.user
        is_estate_admin = user.has_group('estate.group_estate_admin')
        is_estate_buyer_or_seller = (
            user.has_group('estate.group_estate_buyer')
        )
        return is_estate_buyer_or_seller and not is_estate_admin

    @api.model_create_multi
    def create(self, vals_list):
        if self.env.context.get('from_property_sale'):
            return super().create(vals_list)

        if self._is_estate_readonly_user():
            raise AccessError("Buyer/Seller users cannot create invoices.")

        return super().create(vals_list)

    def write(self, vals):
        if self._is_estate_readonly_user():
            raise AccessError("Buyer/Seller users cannot edit invoices.")
        return super().write(vals)

    def unlink(self):
        if self._is_estate_readonly_user():
            raise AccessError("Buyer/Seller users cannot delete invoices.")
        return super().unlink()

    # ✅ ADDED: INVOICE CONFIRM NOTIFICATION (SAFE)
    def action_post(self):
        res = super().action_post()

        for record in self:
            try:
                # Only customer invoices
                if record.move_type != 'out_invoice':
                    continue

                # Must be linked to property
                if not record.property_id:
                    continue

                property_rec = record.property_id

                # Only if property is sold
                if property_rec.state != 'sold':
                    continue

                # Seller (salesperson)
                if not property_rec.salesperson_id:
                    continue

                partner_id = property_rec.salesperson_id.partner_id.id

                # ✅ NOTIFICATION
                property_rec.message_post(
                    body=f"""Invoice Confirmed

Property: {property_rec.name}
Invoice: {record.name}
Amount: {record.amount_total}

Invoice has been confirmed by accountant.
""",
                    partner_ids=[partner_id],
                    message_type="notification",
                    subtype_xmlid="mail.mt_comment"
                )

            except Exception:
                # Never break invoice posting
                continue

        return res


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def _is_estate_readonly_user(self):
        user = self.env.user
        is_estate_admin = user.has_group('estate.group_estate_admin')
        is_estate_buyer_or_seller = (
            user.has_group('estate.group_estate_buyer')
        )
        return is_estate_buyer_or_seller and not is_estate_admin

    @api.constrains('product_id')
    def _check_product_edit_restriction(self):
        user = self.env.user

        is_blocked = (
            (user.has_group('estate.group_estate_buyer') or
             user.has_group('estate.group_estate_seller'))
            and not user.has_group('estate.group_estate_admin')
        )

        for rec in self:
            if is_blocked:
                raise ValidationError(
                    "You cannot modify product in invoice line."
                )

    @api.model_create_multi
    def create(self, vals_list):
        if self._is_estate_readonly_user():
            raise AccessError("Buyer/Seller users cannot create invoice lines.")
        return super().create(vals_list)

    def write(self, vals):
        user = self.env.user

        if (
            (user.has_group('estate.group_estate_buyer'))
            and not user.has_group('estate.group_estate_admin')
        ):
            raise AccessError("You cannot modify invoice lines.")

        return super().write(vals)

    def unlink(self):
        if self._is_estate_readonly_user():
            raise AccessError("Buyer/Seller users cannot delete invoice lines.")
        return super().unlink()