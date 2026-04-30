from odoo import models, api


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def get_estate_activity_count(self):
        if (
            self.env.user.has_group('base.group_system')
            and not self.env.user.has_group('estate.group_estate_seller')
            and not self.env.user.has_group('estate.group_estate_accountant')
        ):
            return False
        return self.env['mail.activity'].sudo().search_count([
            ('res_model', '=', 'estate.property'),
            ('user_id', '=', self.env.user.id),
        ])