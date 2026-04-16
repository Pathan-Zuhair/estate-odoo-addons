from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError


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

    @api.depends('create_date', 'validity')
    def _compute_date_deadline(self):
        for record in self:
            base_date = record.create_date or fields.Datetime.now()
            record.date_deadline = base_date.date() + timedelta(days=record.validity)

    def _inverse_date_deadline(self):
        for record in self:
            if record.create_date and record.date_deadline:
                record.validity = (record.date_deadline - record.create_date.date()).days

    @api.model
    def create(self, vals):
        property_id = vals.get('property_id')

        if property_id:
            property_rec = self.env['estate.property'].browse(property_id)

            if property_rec.state in ['sold', 'cancelled']:
                raise UserError(
                    "You cannot create offers on a sold or cancelled property."
                )

            existing_offers = property_rec.offer_ids.mapped('price')
            if existing_offers and vals.get('price') < max(existing_offers):
                raise UserError(
                    "You cannot create an offer lower than an existing offer."
                )

            if property_rec.state in ['new']:
                property_rec.state = 'offer_received'

        return super().create(vals)

    def action_accept(self):
        for offer in self:
            property_rec = offer.property_id

            accepted_offers = property_rec.offer_ids.filtered(
                lambda o: o.status == 'accepted'
            )
            if accepted_offers:
                raise UserError("Only one offer can be accepted for a property.")

            offer.status = 'accepted'
            property_rec.buyer_id = offer.partner_id
            property_rec.selling_price = offer.price
            property_rec.state = 'offer_accepted'

    def action_refuse(self):
        self.write({'status': 'refused'})

    def unlink(self):
        for record in self:
            if self.env.user.has_group('estate.group_estate_buyer'):
                if record.status == 'accepted':
                    raise UserError("You cannot delete an accepted offer.")

                if record.create_uid != self.env.user:
                    raise UserError("You can only delete your own offers.")

                if record.property_id.state == 'offer_accepted':
                    raise UserError("You cannot delete offers after an offer is accepted.")

        return super().unlink()
