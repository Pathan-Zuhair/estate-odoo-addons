from odoo import models, fields, api

class EstatePropertyType(models.Model):
    _name = 'estate.property.type'
    _description = 'Estate Property Type'
    _order = 'sequence,name'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)

    property_ids = fields.One2many(
        comodel_name="estate.property",
        inverse_name="property_type_id",
        string="Properties"
    )

    # ✅ One2many inverse
    offer_ids = fields.One2many(
        'estate.property.offer',
        'property_type_id',
        string='Offers'
    )

    # ✅ Computed count
    offer_count = fields.Integer(
        compute='_compute_offer_count',
        string='Offers'
    )

    _sql_constraints = [
        (
            'unique_property_type_name',
            'UNIQUE(name)',
            'The property type name must be unique.'
        ),
    ]

    # 🔹 COMPUTE METHOD
    @api.depends('offer_ids')
    def _compute_offer_count(self):
        for record in self:
            record.offer_count = len(record.offer_ids)