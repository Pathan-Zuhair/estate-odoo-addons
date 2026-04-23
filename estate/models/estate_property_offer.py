from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare


class EstatePropertyOffer(models.Model):
    _name = 'estate.property.offer'
    _description = 'Real Estate Property Offer'
    _order = 'price desc'

    _sql_constraints = [
        (
            'check_offer_price_positive',
            'CHECK(price > 0)',
            'The offer price must be strictly positive.',
        ),
    ]

    price = fields.Float(required=True)
    status = fields.Selection(
        [
            ('accepted', 'Accepted'),
            ('refused', 'Refused'),
        ],
        copy=False,
    )
    property_state = fields.Selection(
        related='property_id.state',
        store=True,
        readonly=True,
    )
    property_type_id = fields.Many2one(
        'estate.property.type',
        related='property_id.property_type_id',
        store=True,
        readonly=True,
    )
    partner_id = fields.Many2one('res.partner', string='Buyer', required=True)
    property_id = fields.Many2one('estate.property', string='Property', required=True)
    validity = fields.Integer(string='Validity (days)', default=7)
    date_deadline = fields.Date(
        string='Deadline',
        compute='_compute_date_deadline',
        inverse='_inverse_date_deadline',
        store=True,
    )

    # Check if current user is ONLY seller (not manager)
    def _is_estate_seller(self):
        user = self.env.user
        return user.has_group('estate.group_estate_seller') and not user.has_group(
            'estate.group_estate_manager'
        )

    # Ensure only manager/seller can change status
    def _require_offer_status_access(self):
        if self.env.su:
            return

        if not (
                self.env.user.has_group('estate.group_estate_manager')
                or self.env.user.has_group('estate.group_estate_seller')
        ):
            raise AccessError(_("Only Estate Managers and Estate Sellers can update offer status."))

    # Prevent modifying offers of sold properties
    def _check_property_not_sold_for_status_action(self):
        sold_offers = self.filtered(lambda offer: offer.property_id.state == 'sold')
        if sold_offers:
            raise AccessError(_("You cannot change offers for a property that is already sold."))

    def _check_offer_price(self, price, property_rec):
        min_price = property_rec.expected_price * 0.9
        if float_compare(price, min_price, precision_rounding=0.01) < 0:
            raise UserError(_("Offer price cannot be less than 90% of expected price."))

    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for record in self:
            base_date = record.create_date or fields.Datetime.now()
            record.date_deadline = base_date.date() + timedelta(days=record.validity)

    def _inverse_date_deadline(self):
        for record in self:
            if record.create_date and record.date_deadline:
                record.validity = (record.date_deadline - record.create_date.date()).days

    @api.model_create_multi
    def create(self, vals_list):
        # sellers cannot create offers
        if not self.env.su and self._is_estate_seller():
            raise AccessError(_("Estate Sellers cannot create offers."))

        for vals in vals_list:
            if vals.get('status'):
                self._require_offer_status_access()

            property_id = vals.get('property_id')
            price = vals.get('price')
            if not property_id or price is None:
                continue
            # fetch property record
            property_rec = self.env['estate.property'].browse(property_id)
            # prevent lower offer than existing offers
            existing_offers = property_rec.offer_ids.mapped('price')
            if existing_offers and price < max(existing_offers):
                raise UserError(_("You cannot create an offer lower than an existing offer."))
            # enforce 90% rule
            self._check_offer_price(price, property_rec)

        offers = super().create(vals_list)

        # if property was new → move to "offer_received"
        for offer in offers.filtered(lambda record: record.property_id.state == 'new'):
            offer.property_id.sudo().write({'state': 'offer_received'})
        return offers

    def write(self, vals):

        # Block editing of accepted offers for non-managers
        if 'status' not in vals:
            if not self.env.user.has_group('estate.group_estate_manager'):
                for offer in self:
                    if offer.status in ('accepted', 'refused'):
                        raise AccessError(_("You cannot modify an accepted or refused offer."))

        # sellers cannot edit offers
        if not self.env.su and self._is_estate_seller():
            if 'status' in vals:
                self._check_property_not_sold_for_status_action()
            raise AccessError(_("Estate Sellers cannot edit offers."))

        # status update permission check
        if 'status' in vals:
            self._require_offer_status_access()

        for record in self:
            if 'price' in vals:
                new_price = vals['price']
                self._check_offer_price(new_price, record.property_id)

        return super().write(vals)

    def unlink(self):
        if not self.env.su:
            user = self.env.user

            # sellers cannot delete offers
            if self._is_estate_seller():
                raise AccessError(_("Estate Sellers cannot delete offers."))

            # normal users cannot delete accepted/refused offers
            if (
                    user.has_group('estate.group_estate_user')
                    and not user.has_group('estate.group_estate_manager')
            ):
                # Block BOTH accepted and refused
                blocked_offers = self.filtered(lambda offer: offer.status in ('accepted', 'refused'))
                if blocked_offers:
                    raise AccessError(
                        _("Estate Users cannot delete offers whose status is accepted or refused.")
                    )

        # Capture related properties BEFORE deletion
        properties = self.mapped('property_id')

        # Perform deletion
        res = super().unlink()

        # Update state AFTER deletion
        for prop in properties:
            if not prop.offer_ids:
                prop.sudo().state = 'new'

        return res

    def action_delete_offer(self):
        self.unlink()
        return True

    def action_accept(self):
        self._require_offer_status_access()
        self._check_property_not_sold_for_status_action()

        for offer in self:
            if offer.status == 'accepted':
                continue

            # ensure only ONE accepted offer per property

            accepted_offer = offer.property_id.offer_ids.filtered(
                lambda current_offer: current_offer.status == 'accepted' and current_offer.id != offer.id
            )
            if accepted_offer:
                raise UserError(_("Only one offer can be accepted for a property."))

            # mark offer accepted
            offer.sudo().write({'status': 'accepted'})

            #  update property when offer accepted
            offer.property_id.sudo().write(
                {
                    'buyer_id': offer.partner_id.id,
                    'selling_price': offer.price,
                    'state': 'offer_accepted',
                }
            )

    # if previously accepted, reset property info
    def action_refuse(self):
        self._require_offer_status_access()
        self._check_property_not_sold_for_status_action()

        for offer in self:
            if offer.status == 'accepted':
                offer.property_id.sudo().write(
                    {
                        'buyer_id': False,
                        'selling_price': 0.0,
                        'state': 'offer_received',
                    }
                )
            offer.sudo().write({'status': 'refused'})
