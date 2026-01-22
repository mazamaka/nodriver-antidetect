// === Screen properties (CDP setDeviceMetricsOverride is detectable!) ===
// Note: Screen.prototype properties are DATA properties (not getters) in some Chrome builds
// So we use defineProperty to override them with getters

for (const [k, v] of Object.entries(C.screen)) {
    // Override on Screen.prototype
    defineProperty(Screen.prototype, k, {
        get: () => v,
        enumerable: true,
        configurable: true
    });

    // Also override directly on window.screen for safety
    defineProperty(window.screen, k, {
        get: () => v,
        enumerable: true,
        configurable: true
    });
}

// === Window dimensions ===
for (const [k, v] of Object.entries(C.window)) {
    defineProperty(window, k, {
        get: () => v,
        enumerable: true,
        configurable: true
    });
}
