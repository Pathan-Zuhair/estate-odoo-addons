from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare
from datetime import date


class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    _description = 'Real Estate Property Offer'
    _order = 'price desc'

    _sql_constraints = [
        (
            'check_offer_price_positive',
            'CHECK(price > 0)',
            'The offer price must be strictly positive.'
        ),
    ]

    price = fields.Float(required=True)

    status = fields.Selection(
        [
            ('accepted', 'Accepted'),
            ('refused', 'Refused'),
        ],
        copy=False
    )

    property_state = fields.Selection(
        related='property_id.state',
        store=True,
        readonly=True
    )

    property_type_id = fields.Many2one(
        'estate.property.type',
        related='property_id.property_type_id',
        store=True,
        readonly=True
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Buyer',
        required=True
    )

    property_id = fields.Many2one(
        'estate.property',
        string='Property',
        required=True
    )


    validity = fields.Integer(
        string='Validity (days)',
        default=7
    )

    date_deadline = fields.Date(
        string='Deadline',
        compute='_compute_date_deadline',
        inverse='_inverse_date_deadline',
        store=True
    )

    # SECURITY: Restrict status change to managers only
    def _require_offer_status_manager(self):
        if self.env.su:
            return
        if not self.env.user.has_group('estate.group_estate_manager'):
            raise AccessError(_("Only Estate Managers can change the offer status."))

    #  VALIDATION ADDED HERE (WRITE)
    def write(self, vals):
        user = self.env.user

        for record in self:
            # Restrict ONLY Estate Users (not managers)
            if (
                user.has_group('estate.group_estate_user')
                and not user.has_group('estate.group_estate_manager')
            ):
                if record.status in ('accepted', 'refused'):
                    raise AccessError(_("You cannot modify an offer that is already accepted or refused."))

            #  PRICE VALIDATION ON EDIT
            new_price = vals.get('price', record.price)
            property_rec = record.property_id
            min_price = property_rec.expected_price * 0.9

            if float_compare(new_price, min_price, precision_rounding=0.01) < 0:
                raise UserError(
                    _("Offer price cannot be less than 90% of expected price.")
                )

        # Only manager can change status
        if 'status' in vals:
            self._require_offer_status_manager()

        return super().write(vals)

    def unlink(self):
        for record in self:

            #  Estate User restriction
            if (
                    self.env.user.has_group('estate.group_estate_user')
                    and not self.env.user.has_group('estate.group_estate_manager')
            ):
                if record.status in ('accepted', 'refused'):
                    raise AccessError(
                        _("You cannot delete an offer that is already accepted or refused.")
                    )

        return super().unlink()

    # @api.ondelete(at_uninstall=False)
    # def _check_delete_offer(self):
    #     for record in self:
    #         if record.status in ('accepted', 'refused'):
    #             raise UserError(
    #                 "You cannot delete an offer that is already accepted or refused."
    #             )

    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for record in self:
            base_date = record.create_date or fields.Datetime.now()
            record.date_deadline = base_date.date() + timedelta(days=record.validity)

    def _inverse_date_deadline(self):
        for record in self:
            if record.create_date and record.date_deadline:
                record.validity = (record.date_deadline - record.create_date.date()).days

    #  VALIDATION ADDED HERE (CREATE)
    @api.model
    def create(self, vals):
        if vals.get('status'):
            self._require_offer_status_manager()

        property_id = vals.get('property_id')
        price = vals.get('price')

        if property_id and price:
            property_rec = self.env['estate.property'].browse(property_id)

            # Existing offer check
            existing_offers = property_rec.offer_ids.mapped('price')
            if existing_offers and price < max(existing_offers):
                raise UserError(
                    "You cannot create an offer lower than an existing offer."
                )

            #  90% VALIDATION HERE
            min_price = property_rec.expected_price * 0.9
            if float_compare(price, min_price, precision_rounding=0.01) < 0:
                raise UserError(
                    _("Offer price cannot be less than 90% of expected price.")
                )

        offer = super().create(vals)

        if property_id:
            property_rec.sudo().write({'state': 'offer_received'})

        return offer

    def action_accept(self):
        self._require_offer_status_manager()

        for offer in self:
            property_rec = offer.property_id

            #  CASE 1: Same offer already accepted
            if offer.status == 'accepted':
                raise UserError(_("This offer is already accepted."))

            #  CASE 2: Another offer already accepted
            accepted_offer = property_rec.offer_ids.filtered(
                lambda o: o.status == 'accepted'
            )

            if accepted_offer:
                raise UserError(_("Only one offer can be accepted for a property."))

            #  Accept current offer
            offer.status = 'accepted'

            property_rec.sudo().write({
                'buyer_id': offer.partner_id.id,
                'selling_price': offer.price,
                'state': 'offer_accepted',
            })

    def action_refuse(self):
        self._require_offer_status_manager()
        self.write({'status': 'refused'})

