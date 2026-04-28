from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError
from markupsafe import Markup


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

    def action_delete_offer(self):
        for record in self:
            if record.status in ('accepted', 'refused'):
                raise UserError("You cannot delete accepted or refused offers.")

            if record.property_id.state != 'offer_received':
                raise UserError("You can delete offers only in Offer Received stage.")

            if record.create_uid.id != self.env.user.id:
                raise UserError("You can only delete your own offers.")

        return self.unlink()

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
                raise UserError("You cannot create offers on a sold or cancelled property.")

            price = vals.get('price', 0)
            min_price = property_rec.expected_price * 0.9

            if price < min_price:
                raise UserError(f"Offer must be at least 90% of expected price ({min_price}).")

            existing_offers = property_rec.offer_ids.mapped('price')

            if existing_offers and price < max(existing_offers):
                raise UserError("You cannot create an offer lower than an existing offer.")

        record = super().create(vals)

        property_rec = record.property_id

        # ✅ Prepare partners safely
        partners = []
        if property_rec.salesperson_id:
            partners.append(property_rec.salesperson_id.partner_id.id)
        if record.partner_id:
            partners.append(record.partner_id.id)

        # ✅ CHATTER MESSAGE (FIXED POSITION)
        property_rec.message_post(
            body=f"""
    <p><b>New Offer Received</b></p>
    <p>
    Buyer: {record.partner_id.name}<br/>
    Amount: {record.price}
    </p>
    """,
            partner_ids=partners,
            message_type="comment",
            subtype_xmlid="mail.mt_comment"
        )

        # ✅ ACTIVITY (FOR BUTTONS)
        activity_type = self.env.ref('mail.mail_activity_data_todo')

        if property_rec.salesperson_id:
            property_rec.activity_schedule(
                activity_type_id=activity_type.id,
                user_id=property_rec.salesperson_id.id,
                summary="Review new offer",
                note=f"Offer from {record.partner_id.name} for {record.price}",
            )

        return record

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

            partners = []
            if property_rec.salesperson_id:
                partners.append(property_rec.salesperson_id.partner_id.id)
            if record.partner_id:
                partners.append(record.partner_id.id)

                property_rec.message_post(
                    body=Markup(f"""
                <p><b>Offer Accepted</b></p>
                <p>
                Buyer: {record.partner_id.name}<br/>
                Final Price: {record.price}
                </p>
                """),
                    partner_ids=partners,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment"
                )

    def action_refuse(self):
        for record in self:
            if record.property_id.state in ['sold', 'cancelled']:
                raise UserError("You cannot refuse offers on a sold or cancelled property.")

            record.status = 'refused'

            property_rec = record.property_id

            # ✅ EXISTING LOGIC (UNCHANGED)
            accepted_offers = property_rec.offer_ids.filtered(lambda o: o.status == 'accepted')

            if not accepted_offers:
                property_rec.write({
                    'state': 'offer_received',
                    'buyer_id': False,
                    'selling_price': 0,
                })

            # ✅ PARTNERS FOR NOTIFICATION
            partners = []
            if property_rec.salesperson_id:
                partners.append(property_rec.salesperson_id.partner_id.id)
            if record.partner_id:
                partners.append(record.partner_id.id)

            # ✅ CHATTER MESSAGE (STYLED)
            property_rec.message_post(
                body=Markup(f"""
    <p><b style="color:red;">Offer Refused</b></p>
    <p>
    Buyer: {record.partner_id.name}<br/>
    Amount: {record.price}
    </p>
    """),
                partner_ids=partners,
                message_type="comment",
                subtype_xmlid="mail.mt_comment"
            )

            # 🟢 OPTIONAL: REMOVE ACTIVITY (clean UI)
            activities = property_rec.activity_ids.filtered(
                lambda act: act.summary == "Review new offer"
            )
            activities.unlink()

    def unlink(self):
        properties = self.mapped('property_id')

        for record in self:
            if record.status == 'accepted':
                raise UserError("Accepted or Refused offers cannot be deleted.")

            if self.env.user.has_group('estate.group_estate_buyer'):
                if record.create_uid.id != self.env.user.id:
                    raise UserError("You can only delete your own offers.")

                if record.property_id.state in ('sold', 'cancelled'):
                    raise UserError("You cannot delete offers for sold or cancelled properties.")

        res = super().unlink()

        return res

    def write(self, vals):
        if self.env.user.has_group('estate.group_estate_buyer'):
            for record in self:
                if record.status in ('accepted', 'refused'):
                    raise UserError("You cannot modify an accepted or refused offer.")

                if record.create_uid.id != self.env.user.id:
                    raise UserError("You can only edit your own offers.")

        if self.env.user.has_group('estate.group_estate_seller'):
            allowed_fields = {'status'}
            forbidden_fields = set(vals.keys()) - allowed_fields

            if forbidden_fields:
                raise UserError("Seller can only accept or refuse offers.")

        return super().write(vals)