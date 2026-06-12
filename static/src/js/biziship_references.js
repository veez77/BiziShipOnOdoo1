/** @odoo-module **/

/**
 * BiziShip reference-numbers widget.
 *
 * Bound to a JSON Char field holding an array of reference strings:
 *   index 0 = primary "Reference Number" (sent as reference_number)
 *   index 1+ = "Additional References" (sent as additional_references)
 *
 * UI: the primary row (REF1) is always shown; the user can add up to 2 more
 * (REF2, REF3) via "+ Add another reference" and remove the extras. The cap of
 * 2 additional (3 total) is enforced here in the UI only. Values are committed
 * on change (blur) to avoid focus loss while typing.
 */

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

const MAX_ADDITIONAL = 2; // 1 primary + 2 additional = 3 total
const MAX_LEN = 64;

export class BizishipReferences extends Component {
    static template = "biziship.References";
    static props = { ...standardFieldProps };

    // Always returns an array of at least one element (the primary row).
    get references() {
        try {
            const v = JSON.parse(this.props.record.data[this.props.name] || "[]");
            const arr = Array.isArray(v) ? v.map((x) => (typeof x === "string" ? x : "")) : [];
            return arr.length ? arr : [""];
        } catch (e) {
            return [""];
        }
    }

    get readonly() {
        return this.props.readonly;
    }

    get canAdd() {
        return !this.readonly && this.references.length < MAX_ADDITIONAL + 1;
    }

    _commit(arr) {
        // Drop nothing here (preserve order/empties for editing); trimming happens server-side.
        this.props.record.update({ [this.props.name]: JSON.stringify(arr) });
    }

    badge(index) {
        return "REF" + (index + 1);
    }

    placeholder(index) {
        return index === 0 ? "e.g. REF-12345" : "Additional reference";
    }

    onChange(index, ev) {
        const arr = this.references.slice();
        arr[index] = (ev.target.value || "").slice(0, MAX_LEN);
        this._commit(arr);
    }

    addRow() {
        if (this.canAdd) {
            this._commit([...this.references, ""]);
        }
    }

    removeRow(index) {
        if (index === 0) {
            return; // the primary row is never removed
        }
        const arr = this.references.slice();
        arr.splice(index, 1);
        this._commit(arr.length ? arr : [""]);
    }
}

registry.category("fields").add("biziship_references", {
    component: BizishipReferences,
    displayName: "BiziShip Reference Numbers",
    supportedTypes: ["char", "text"],
});
