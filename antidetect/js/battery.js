// === Battery API (realistic desktop values) ===
if (navigator.getBattery) {
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

    const orig = navigator.getBattery;
    navigator.getBattery = wrapFn(orig, function() {
        return Promise.resolve(battery);
    });
}
