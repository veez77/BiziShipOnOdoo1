/** @odoo-module **/

document.addEventListener('click', function (e) {
    const el = e.target.closest('.biziship-ref-copyable');
    if (!el) return;
    const text = el.getAttribute('data-copy-text');
    if (!text) return;
    navigator.clipboard.writeText(text).then(function () {
        el.setAttribute('title', 'Copied ✓');
        setTimeout(function () { el.setAttribute('title', 'Click to copy'); }, 1500);
    });
});
