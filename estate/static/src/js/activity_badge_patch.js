/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";

console.log("ESTATE JS LOADED");

// Get component from registry
const activityMenu = registry.category("systray").get("mail.activity_menu");

patch(activityMenu.Component.prototype, {
    setup() {
        super.setup();
        console.log("ActivityMenu patched");
    },

    get totalWithFuture() {
        const total = this.store.activityCounter || 0;

        let extra = 0;

        for (const group of this.store.activityGroups || []) {
            if (
                group.model === "estate.property" ||
                group.model === "estate.property.offer"
            ) {
                extra += group.planned_count || 0;
            }
        }

        console.log("Original:", total, "Extra:", extra);

        return total + extra;
    },
});