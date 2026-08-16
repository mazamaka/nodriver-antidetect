// === Permissions API ===
// The classic headless tell is Notification.permission === 'denied' while
// permissions.query() answers 'prompt'. Headful Chrome is already consistent,
// so patch query() only when that mismatch is actually present.
if (navigator.permissions?.query && typeof Notification !== 'undefined'
    && Notification.permission === 'denied') {
    const orig = navigator.permissions.query;
    navigator.permissions.query = wrapFn(orig, function(desc) {
        if (desc && desc.name === 'notifications') {
            return Promise.resolve({state: Notification.permission, onchange: null});
        }
        return orig.call(this, desc);
    });
}
