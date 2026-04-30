/** @odoo-module **/

import { ActivityMenu } from "@mail/core/web/activity_menu";
import { patch } from "@web/core/utils/patch";
import { useState, onWillStart } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(ActivityMenu.prototype, {
    setup() {
        super.setup();
        this.state = useState({
            estateCount: null,
        });
        const orm = useService("orm");
        onWillStart(async () => {
            try {
                const count = await orm.call("res.users", "get_estate_activity_count", []);
                this.state.estateCount = count === false ? null : (count || 0);
                if (this.state.estateCount !== null) {
                    this.store.activityCounter = this.state.estateCount;
                }
            } catch (e) {
                console.warn("estate badge: failed to fetch count", e);
            }
        });
    },

    get activityCounterDisplay() {
        return this.state.estateCount === null ? this.store.activityCounter : this.state.estateCount;
    },
});