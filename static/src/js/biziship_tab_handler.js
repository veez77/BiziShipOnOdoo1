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
            this._setupBiziShipHandlers();
        });
        onPatched(() => {
            this._checkBiziShipTabSwitch();
        });
    },

    _setupBiziShipHandlers() {
        if (this.bizishipHandlersInitialized) return;
        this.bizishipHandlersInitialized = true;

        // 1. Autofilter Logic (Debounced)
        // This triggers a 'change' event on the input field as the user types,
        // which Odoo's ORM listens to to execute 'onchange' methods immediately.
        document.addEventListener('input', (ev) => {
            const input = ev.target;
            if (input && input.classList && input.classList.contains('biziship-autofilter')) {
                if (this.autoFilterTimeout) clearTimeout(this.autoFilterTimeout);
                this.autoFilterTimeout = setTimeout(() => {
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }, 300);
            }
        }, true);
    },

    _checkBiziShipTabSwitch() {
        const record = this.model.root;
        if (!record || !record.data) return;

        const nonce = record.data.biziship_last_fetch_nonce;
        const hasSwitchFlag = this.props.context && this.props.context.biziship_switch_tab;

        if (hasSwitchFlag && nonce && nonce !== this.lastHandledNonce) {
            this.lastHandledNonce = nonce;
            setTimeout(() => {
                const quotesTab = document.querySelector('.o_notebook a[name="biziship_freight_quotes"]');
                if (quotesTab && !quotesTab.classList.contains('active')) {
                    quotesTab.click();
                }
            }, 100);
        }
    }
});
