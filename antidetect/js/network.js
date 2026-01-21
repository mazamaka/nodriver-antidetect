// === Network Information API ===
(function() {
    const connection = {
        effectiveType: '4g',
        rtt: 100,
        downlink: 1.35,
        saveData: false,
        type: 'wifi',
        onchange: null,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    defineProperty(Navigator.prototype, 'connection', {
        get: function() { return connection; },
        enumerable: true,
        configurable: true
    });
})();
