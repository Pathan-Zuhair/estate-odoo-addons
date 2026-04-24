import random
from odoo import models, fields, api

class EstatePropertyTag(models.Model):
    _name = 'estate.property.tag'
    _description = 'Estate Property Tag'
    _order = 'name'

    name = fields.Char(required=True)
    color = fields.Integer(string="Color")

    _sql_constraints = [
        (
            'unique_property_tag_name',
            'UNIQUE(name)',
            'The property tag name must be unique.'
        ),
    ]

    @api.model
    def create(self, vals):
        # Assign random color if not provided
        if 'color' not in vals:
            vals['color'] = random.randint(1, 11)
        return super().create(vals)