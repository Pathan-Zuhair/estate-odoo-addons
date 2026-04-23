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
        """
        arch, view = super()._get_view(view_id, view_type, **options)

        if (
                view_type == 'form'
                and self.env.user.has_group('estate.group_estate_user')
                and not self.env.user.has_group('estate.group_estate_seller')
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

    def _is_estate_seller(self):
        user = self.env.user
        return user.has_group('estate.group_estate_seller') and not user.has_group(
            'estate.group_estate_manager'
        )

    def _require_property_action_access(self):
        if self.env.su:
            return

        if not (
                self.env.user.has_group('estate.group_estate_manager')
                or self.env.user.has_group('estate.group_estate_seller')
        ):
            raise AccessError(
                _("Only Estate Managers and Estate Sellers can change property status.")
            )

    def write(self, vals):
        if vals and not self.env.su:
            user = self.env.user

            for record in self:

                if self._is_estate_seller():

                    # Once Offer received → seller cannot edit property fields
                    if record.state == 'offer_received':
                        if set(vals.keys()) != {'state'}:
                            raise AccessError(
                                _("Seller cannot modify property once an offer is received.")
                            )

                    #  AFTER sold/cancelled → no changes at all
                    if record.state in ('sold', 'cancelled'):
                        raise AccessError(
                            _("Seller cannot modify property once it is sold or cancelled.")
                        )

                    # BEFORE acceptance → cannot mark as sold
                    if record.state in ('new', 'offer_received'):
                        if vals.get('state') == 'sold':
                            raise AccessError(
                                _("Seller can only mark property as Sold after an offer is accepted.")
                            )

                    #  AFTER acceptance → restrict everything except valid state change
                    if record.state == 'offer_accepted':

                        if set(vals.keys()) != {'state'}:
                            raise AccessError(
                                _("Seller cannot modify property after offer is accepted.")
                            )

                        if vals.get('state') not in ('sold', 'cancelled'):
                            raise AccessError(
                                _("Seller can only mark property as Sold.")
                            )

                #  ESTATE USER restriction
                if (
                        user.has_group('estate.group_estate_user')
                        and not user.has_group('estate.group_estate_seller')
                        and not user.has_group('estate.group_estate_manager')
                ):
                    keys = set(vals)
                    allowed = {'offer_ids'}
                    extra = keys - allowed

                    if 'state' in vals and vals['state'] == 'offer_received':
                        extra.discard('state')

                        if any(rec.state not in ('new', 'offer_received') for rec in self):
                            raise AccessError(
                                _("Only Estate Seller can change the property state.")
                            )

                    if extra:
                        raise AccessError(
                            _("Only Estate Seller can modify property fields.")
                        )

        return super().write(vals)

    def unlink(self):
        if not self.env.su and self._is_estate_seller():
            locked_properties = self.filtered(lambda record: record.state == 'offer_accepted')
            if locked_properties:
                raise AccessError(
                    _("Estate Sellers cannot delete properties once an offer is accepted.")
                )
        return super().unlink()

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
    living_area = fields.Integer(string='Living Area (sqm)')
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
        - Only managers and sellers allowed
        - Cannot cancel sold property
        """
        self._require_property_action_access()

        for record in self:
            if record.state == 'sold':
                raise UserError("A sold property cannot be cancelled.")
            record.write({'state': 'cancelled'})

    def action_sold(self):
        """
        Mark property as sold:
        - Only managers and sellers allowed
        - Cannot sell cancelled property
        """
        self._require_property_action_access()

        for record in self:
            if record.state == 'cancelled':
                raise UserError("A cancelled property cannot be sold.")
            record.write({'state': 'sold'})

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