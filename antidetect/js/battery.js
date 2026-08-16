// === Battery API ===
// Chrome exposes getBattery() on every desktop platform and already reports
// charging/level for a machine without a battery, so overriding it only adds a
// patched function for detectors to find. Fill in only when the API is missing.
if (!navigator.getBattery) {
    const battery = {
        charging: true,
        chargingTime: 0,
        dischargingTime: Infinity,
        level: 1.0,
        onchargingchange: null,
        onchargingtimechange: null,
        ondischargingtimechange: null,
        onlevelchange: null,
        addEventListener: function() {},
        removeEventListener: function() {},
        dispatchEvent: function() { return true; }
    };

    defineProperty(Navigator.prototype, 'getBattery', {
        value: function getBattery() { return Promise.resolve(battery); },
        enumerable: false,
        writable: true
    });
}
