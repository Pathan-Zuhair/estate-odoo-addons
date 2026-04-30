from odoo import models, fields, api
from odoo.exceptions import AccessError, ValidationError
from markupsafe import Markup


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

    def action_post(self):
        res = super().action_post()

        for record in self:
            try:
                if record.move_type != 'out_invoice':
                    continue

                if not record.property_id:
                    continue

                property_rec = record.property_id

                if property_rec.state != 'sold':
                    continue

                if not property_rec.salesperson_id:
                    continue

                partner_id = property_rec.salesperson_id.partner_id.id

                property_rec.message_post(
                    body=Markup(f"""
                <p><b>Invoice Confirmed</b></p>
                <p>
                Property: {property_rec.name}<br/>
                Invoice: {record.name}<br/>
                Amount: {record.amount_total}
                </p>
                <p>Invoice has been confirmed by accountant.</p>
                """),
                    partner_ids=[partner_id],
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment"
                )

            except Exception:
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