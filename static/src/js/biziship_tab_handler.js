/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { onMounted, onPatched } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.orm = useService("orm");
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
        document.addEventListener('input', (ev) => {
            const input = ev.target;
            if (input && input.classList && input.classList.contains('biziship-autofilter')) {
                if (this.autoFilterTimeout) clearTimeout(this.autoFilterTimeout);
                this.autoFilterTimeout = setTimeout(() => {
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }, 300);
            }
        }, true);

        // 2. Refresh BiziShip user profile when either freight tab is clicked
        document.addEventListener('click', (ev) => {
            // Use the selector we know resolves (.o_notebook .nav-link), then check name in JS
            const navLink = ev.target.closest('.o_notebook .nav-link');
            if (!navLink) return;
            const tabName = navLink.getAttribute('name') || navLink.getAttribute('data-name');
            if (tabName !== 'biziship_freight_quotes' && tabName !== 'biziship_freight_details') return;
            const record = this.model.root;
            const recordId = (record && record.resId) || (record && record.data && record.data.id);
            if (!recordId) return;
            this.orm.call('sale.order', 'action_biziship_refresh_profile_rpc', [[recordId]])
                .then((result) => {
                    if (result && this.model.root && this.model.root.data) {
                        this.model.root.data.biziship_priority1_env = result.biziship_priority1_env;
                        this.model.root.data.biziship_demo_tries = result.biziship_demo_tries;
                    }
                })
                .catch((err) => console.warn('BiziShip refresh error:', err));
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
                const quotesTab = document.querySelector(
                    '.o_notebook [name="biziship_freight_quotes"], .o_notebook [data-name="biziship_freight_quotes"]'
                );
                if (quotesTab && !quotesTab.classList.contains('active')) {
                    quotesTab.click();
                }
            }, 100);
        }
    }
});
