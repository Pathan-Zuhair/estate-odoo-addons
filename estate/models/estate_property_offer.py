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

        return super().create(vals)

    def action_accept(self):
        for record in self:

            if record.property_id.state in ['sold', 'cancelled']:
                raise UserError("You cannot accept offers on a sold or cancelled property.")

            property_rec = record.property_id

            other_offers = property_rec.offer_ids.filtered(lambda o: o != record)
            other_offers.write({'status': 'refused'})

            record.status = 'accepted'

            property_rec.write({
                'state': 'offer_accepted',
                'buyer_id': record.partner_id.id,
                'selling_price': record.price,
            })

    def action_refuse(self):
        for record in self:

            if record.property_id.state in ['sold', 'cancelled']:
                raise UserError("You cannot refuse offers on a sold or cancelled property.")

            record.status = 'refused'

            property_rec = record.property_id

            accepted_offers = property_rec.offer_ids.filtered(lambda o: o.status == 'accepted')

            if not accepted_offers:
                property_rec.write({
                    'state': 'offer_received',
                    'buyer_id': False,
                    'selling_price': 0,
                })

    def unlink(self):
        for record in self:

            if record.status == 'accepted':
                raise UserError("Accepted offers cannot be deleted.")

            if self.env.user.has_group('estate.group_estate_buyer'):

                if record.create_uid != self.env.user:
                    raise UserError("You can only delete your own offers.")

                if record.property_id.state in ('sold', 'cancelled'):
                    raise UserError("You cannot delete offers for sold or cancelled properties.")

        return super().unlink()

    def write(self, vals):

        if self.env.user.has_group('estate.group_estate_buyer'):
            for record in self:
                if record.create_uid != self.env.user:
                    raise UserError("You can only edit your own offers.")

        if self.env.user.has_group('estate.group_estate_seller'):
            allowed_fields = {'status'}

            forbidden_fields = set(vals.keys()) - allowed_fields

            if forbidden_fields:
                raise UserError("Seller can only accept or refuse offers.")

        return super().write(vals)