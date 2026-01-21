// === Screen properties (CDP setDeviceMetricsOverride is detectable!) ===
for (const [k, v] of Object.entries(C.screen)) {
    wrapGetter(Screen.prototype, k, function() { return v; });
}

// === Window dimensions ===
for (const [k, v] of Object.entries(C.window)) {
    defineProperty(window, k, {
        get: () => v,
        enumerable: true,
        configurable: true
    });
}
