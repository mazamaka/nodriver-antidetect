// === Permissions API (realistic responses) ===
if (navigator.permissions?.query) {
    const orig = navigator.permissions.query;
    navigator.permissions.query = wrapFn(orig, function(desc) {
        // Return 'prompt' for notifications (realistic default)
        if (desc.name === 'notifications') {
            return Promise.resolve({ state: 'prompt', onchange: null });
        }
        return orig.call(this, desc);
    });
}
