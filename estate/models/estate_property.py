from odoo import models, fields, api
from dateutil.relativedelta import relativedelta
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class EstateProperty(models.Model):
    _name = 'estate.property'
    _description = 'Estate Property'
    _order = 'id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    _sql_constraints = [
        (
            'check_expected_price_positive',
            'CHECK(expected_price > 0)',
            'The expected price must be strictly positive.'
        ),
        (
            'check_selling_price_positive',
            'CHECK(selling_price >= 0)',
            'The selling price must be positive.'
        ),
    ]

    active = fields.Boolean(default=True)

    name = fields.Char(require=True)
    description = fields.Text()
    postcode = fields.Char()

    date_availability = fields.Date(
        copy=False,
        default=lambda self: fields.Date.today() + relativedelta(months=3)
    )

    expected_price = fields.Float(require=True)

    selling_price = fields.Float(
        copy=False,
        readonly=True
    )

    bedrooms = fields.Integer(default=2)
    living_area = fields.Integer()
    facades = fields.Integer()

    garage = fields.Boolean()
    garden = fields.Boolean(string="Garden")
    garden_area = fields.Integer(string='Garden Area (sqm)')

    garden_orientation = fields.Selection(
        [
            ('north', 'North'),
            ('south', 'South'),
            ('east', 'East'),
            ('west', 'West'),
        ],
        string='Garden Orientation'
    )

    state = fields.Selection(
        [
            ('new', 'New'),
            ('offer_received', 'Offer Received'),
            ('offer_accepted', 'Offer Accepted'),
            ('sold', 'Sold'),
            ('cancelled', 'Cancelled')
        ],
        compute="_compute_state",
        store=True
    )

    property_type_id = fields.Many2one(
        'estate.property.type',
        string='Property Type'
    )

    buyer_id = fields.Many2one(
        'res.partner',
        string='Buyer',
        copy=False
    )

    salesperson_id = fields.Many2one(
        'res.users',
        string='Salesperson',
        default=lambda self: self.env.user
    )

    tag_ids = fields.Many2many(
        'estate.property.tag',
        string='Tags'
    )

    offer_ids = fields.One2many(
        'estate.property.offer',
        'property_id',
        string='Offers'
    )

    total_area = fields.Float(
        string='Total Area',
        compute='_compute_total_area',
        store=True
    )

    best_price = fields.Float(
        string='Best Offer',
        compute='_compute_best_price',
        store=True
    )

    color = fields.Integer(compute="_compute_color")

    @api.depends('state')
    def _compute_color(self):
        for rec in self:

            if rec.state == 'sold':
                rec.color = 10
            elif rec.state == 'cancelled':
                rec.color = 2
            else:
                rec.color = 9

    @api.depends('offer_ids', 'offer_ids.status')
    def _compute_state(self):
        for record in self:
            if record.state in ('sold', 'cancelled'):
                continue

            if not record.offer_ids:
                record.state = 'new'
            elif any(o.status == 'accepted' for o in record.offer_ids):
                record.state = 'offer_accepted'
            else:
                record.state = 'offer_received'

    @api.depends('living_area', 'garden_area')
    def _compute_total_area(self):
        for record in self:
            record.total_area = (record.living_area or 0.0) + (record.garden_area or 0.0)

    @api.depends('offer_ids.price')
    def _compute_best_price(self):
        for record in self:
            prices = record.offer_ids.mapped('price')
            record.best_price = max(prices) if prices else 0.0

    @api.onchange('garden')
    def _onchange_garden(self):
        for record in self:
            if record.garden:
                record.garden_area = 10
                record.garden_orientation = 'north'
            else:
                record.garden_area = 0
                record.garden_orientation = False

    def action_cancel(self):
        for record in self:
            if record.state == 'sold':
                raise UserError("A sold property cannot be cancelled.")
            record.state = 'cancelled'

    def action_sold(self):
        for record in self:
            if record.state == 'cancelled':
                raise UserError("A cancelled property cannot be sold.")

            record.state = 'sold'

            # ✅ FIND ACCOUNTANT USERS
            accountant_group = self.env.ref('estate.group_estate_accountant')
            accountant_users = accountant_group.users

            partners = accountant_users.mapped('partner_id').ids

            # ✅ SEND NOTIFICATION
            record.message_post(
                body=f"""Property Sold

    Property: {record.name}
    Selling Price: {record.selling_price}

    Please review and create invoice.
    """,
                partner_ids=partners,
                message_type="notification",
                subtype_xmlid="mail.mt_comment"
            )

    @api.constrains('selling_price', 'expected_price')
    def _check_selling_price(self):
        for record in self:
            if float_is_zero(record.selling_price, precision_rounding=0.01):
                continue

            min_price = record.expected_price * 0.9

            if float_compare(
                record.selling_price,
                min_price,
                precision_rounding=0.01
            ) < 0:
                raise UserError(
                    "The selling price cannot be lower than 90% of the expected price."
                )

    @api.ondelete(at_uninstall=False)
    def _check_property_deletion(self):
        for record in self:
            if record.state not in ('new', 'cancelled'):
                raise UserError(
                    "You can only delete properties in New or Cancelled state."
                )

    def write(self, vals):
        if self.env.user.has_group('estate.group_estate_buyer'):
            forbidden_fields = set(vals.keys()) - {'offer_ids'}
            if forbidden_fields:
                raise UserError("You are not allowed to modify property details.")

        if self.env.user.has_group('estate.group_estate_seller'):
            for record in self:
                allowed_fields = {'state', 'buyer_id', 'selling_price'}
                forbidden_fields = set(vals.keys()) - allowed_fields

                if record.state != 'new' and forbidden_fields:
                    raise UserError("You cannot edit property after offer is received.")

        return super().write(vals)