// === Network Information API ===
// Desktop Chrome exposes navigator.connection with effectiveType/rtt/downlink/
// saveData - but NOT `type`, which only exists on Android/ChromeOS. Adding it
// would contradict the desktop platform we claim, so we only provide the object
// when Chrome does not (e.g. behind --disable-features=NetworkInformation).
if (!('connection' in Navigator.prototype)) {
    const connection = {
        effectiveType: '4g',
        rtt: 100,
        downlink: 1.35,
        saveData: false,
        onchange: null,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    defineProperty(Navigator.prototype, 'connection', {
        get: function() { return connection; },
        enumerable: true
    });
}
