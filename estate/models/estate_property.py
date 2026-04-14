from odoo import _, api, fields, models
from dateutil.relativedelta import relativedelta
from odoo.exceptions import AccessError, UserError
from odoo.tools.float_utils import float_compare, float_is_zero


class EstateProperty(models.Model):
    _name = 'estate.property'
    _description = 'Estate Property'
    _order = 'id desc'

    #  UI CONTROL: Make fields readonly for Estate Users

    @api.model
    def _get_view(self, view_id=None, view_type='form', **options):
        """
        Dynamically modifies form view:
        - Estate Users → all fields readonly (except offers)
        - Estate Managers → full access

        NOTE:
        This is only UI-level restriction.
        Backend security is handled in write().
        """
        arch, view = super()._get_view(view_id, view_type, **options)

        if (
            view_type == 'form'
            and self.env.user.has_group('estate.group_estate_user')
            and not self.env.user.has_group('estate.group_estate_manager')
        ):
            for node in arch.xpath("//field[@name]"):

                # Skip offers section (users must be able to edit offers)
                if node.get('name') == 'offer_ids':
                    continue

                # Skip fields inside offer_ids (nested list)
                if node.xpath("ancestor::field[@name='offer_ids']"):
                    continue

                # Make all other fields readonly
                node.set('readonly', '1')

        return arch, view

    #  BACKEND SECURITY: Prevent unauthorized property edits

    def write(self, vals):
        """
        Enforces strict backend security:

        Estate User:
        -  Cannot edit property fields
        -  Allowed to update via offers (indirect system updates)

        Estate Manager:
        -  Full access

        NOTE:
        Backend validation is mandatory since UI restrictions
        can be bypassed (RPC/import/debug mode).
        """
        if vals and not self.env.su:
            user = self.env.user

            # Apply restriction only to Estate Users (not managers)
            if user.has_group('estate.group_estate_user') and not user.has_group(
                'estate.group_estate_manager'
            ):
                keys = set(vals)

                # Only allow updates coming from offer logic
                allowed = {'offer_ids'}

                # Identify disallowed fields
                extra = keys - allowed

                # Allow system-driven state update (offer creation flow)
                if 'state' in vals and vals['state'] == 'offer_received':
                    extra.discard('state')

                    # Ensure valid state transition
                    if any(rec.state not in ('new', 'offer_received') for rec in self):
                        raise AccessError(
                            _("Only Estate Managers can change the property state.")
                        )

                # Block any unauthorized modification
                if extra:
                    raise AccessError(
                        _("Only Estate Managers can modify property fields.")
                    )

        return super().write(vals)

    #  SQL CONSTRAINTS

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

    # Default availability = today + 3 months
    date_availability = fields.Date(
        copy=False,
        default=lambda self: fields.Date.today() + relativedelta(months=3)
    )

    expected_price = fields.Float(require=True)

    # Selling price updated only via accepted offer
    selling_price = fields.Float(copy=False, readonly=True)

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

    #  STATE MANAGEMENT

    state = fields.Selection(
        [
            ('new', 'New'),
            ('offer_received', 'Offer Received'),
            ('offer_accepted', 'Offer Accepted'),
            ('sold', 'Sold'),
            ('cancelled', 'Cancelled'),
        ],
        required=True,
        copy=False,
        default='new'
    )

    #  RELATIONAL FIELDS

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

    # Offers linked to property
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

    @api.depends('living_area', 'garden_area')
    def _compute_total_area(self):
        """
        Total area = living area + garden area
        """
        for record in self:
            record.total_area = (record.living_area or 0.0) + (record.garden_area or 0.0)

    @api.depends('offer_ids.price')
    def _compute_best_price(self):
        """
        Computes highest offer price
        """
        for record in self:
            prices = record.offer_ids.mapped('price')
            record.best_price = max(prices) if prices else 0.0

    #  ONCHANGE METHODS

    @api.onchange('garden')
    def _onchange_garden(self):
        """
        Auto-fill garden details when enabled
        """
        for record in self:
            if record.garden:
                record.garden_area = 10
                record.garden_orientation = 'north'
            else:
                record.garden_area = 0
                record.garden_orientation = False

    # BUSINESS ACTIONS

    def action_cancel(self):
        """
        Cancel property:
        - Only managers allowed
        - Cannot cancel sold property
        """
        if not self.env.su and not self.env.user.has_group('estate.group_estate_manager'):
            raise AccessError(_("Only Estate Managers can cancel a property."))

        for record in self:
            if record.state == 'sold':
                raise UserError("A sold property cannot be cancelled.")
            record.state = 'cancelled'

    def action_sold(self):
        """
        Mark property as sold:
        - Only managers allowed
        - Cannot sell cancelled property
        """
        if not self.env.su and not self.env.user.has_group('estate.group_estate_manager'):
            raise AccessError(_("Only Estate Managers can mark a property as sold."))

        for record in self:
            if record.state == 'cancelled':
                raise UserError("A cancelled property cannot be sold.")
            record.state = 'sold'


    #  BUSINESS CONSTRAINTS

    # @api.constrains('selling_price', 'expected_price')
    # def _check_selling_price(self):
    #     """
    #     Ensures selling price is at least 90% of expected price
    #     """
    #     for record in self:
    #         # Ignore check if selling price is zero
    #         if float_is_zero(record.selling_price, precision_rounding=0.01):
    #             continue
    #
    #         min_price = record.expected_price * 0.9
    #
    #         if float_compare(
    #                 record.selling_price,
    #                 min_price,
    #                 precision_rounding=0.01
    #         ) < 0:
    #             raise UserError(
    #                 "The selling price cannot be lower than 90% of the expected price."
    #             )


    #  DELETE RESTRICTION

    @api.ondelete(at_uninstall=False)
    def _check_property_deletion(self):
        """
        Allow deletion only if property is:
        - New
        - Cancelled
        """
        for record in self:
            if record.state not in ('new', 'cancelled'):
                raise UserError(
                    "You can only delete properties in New or Cancelled state."
                )