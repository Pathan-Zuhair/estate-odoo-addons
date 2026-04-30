from odoo import models, fields, api


class MailActivity(models.Model):
    _inherit = "mail.activity"

    @api.model_create_multi
    def create(self, vals_list):

        activities = super().create(vals_list)

        today = fields.Date.today()

        estate_activities = activities.filtered(
            lambda act: act.res_model in ['estate.property', 'estate.property.offer']
        )

        if estate_activities:
            users = estate_activities.mapped('user_id')

            for user in users:

                count = self.search_count([
                    ('user_id', '=', user.id),
                    ('active', '=', True),
                    '|',
                        ('date_deadline', '<=', today),
                        '&',
                            ('date_deadline', '>', today),
                            ('res_model', 'in', ['estate.property', 'estate.property.offer'])
                ])

                user._bus_send(
                    "mail.activity/updated",
                    {
                        "activity_created": True,
                        "count_diff": count,
                    }
                )

        return activities