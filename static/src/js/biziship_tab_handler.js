/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.lastHandledNonce = null;

        onMounted(() => {
            this._checkBiziShipTabSwitch();
        });
        onPatched(() => {
            this._checkBiziShipTabSwitch();
        });
    },

    _checkBiziShipTabSwitch() {
        const record = this.model.root;
        if (!record || !record.data) return;

        const nonce = record.data.biziship_last_fetch_nonce;
        const hasSwitchFlag = this.props.context && this.props.context.biziship_switch_tab;

        // Only switch if we have the flag AND a new nonce we haven't handled yet
        if (hasSwitchFlag && nonce && nonce !== this.lastHandledNonce) {
            this.lastHandledNonce = nonce;

            // Use a slight delay to ensure the notebook has rendered
            setTimeout(() => {
                const quotesTab = document.querySelector('.o_notebook a[name="biziship_freight_quotes"]');
                if (quotesTab && !quotesTab.classList.contains('active')) {
                    quotesTab.click();
                }
            }, 100);
        }
    }
});
