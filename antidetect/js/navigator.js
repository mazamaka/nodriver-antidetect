// Navigator properties spoofing
// Handles: doNotTrack, globalPrivacyControl
// Note: WebGPU is disabled via Chrome flags (--disable-features=WebGPU,Vulkan --use-angle=gl)

// doNotTrack - should be null or "1" for real browsers
// null = user hasn't set preference (most common)
// "1" = do not track enabled
if (C.navigator?.doNotTrack !== undefined) {
    Object.defineProperty(navigator, 'doNotTrack', {
        get: () => C.navigator.doNotTrack,
        configurable: true
    });
}

// globalPrivacyControl - Chrome doesn't support it natively
// Should be undefined in Chrome (not null, not false)
// Only Firefox/Brave support it
if ('globalPrivacyControl' in navigator) {
    try {
        delete navigator.globalPrivacyControl;
    } catch (e) {
        Object.defineProperty(navigator, 'globalPrivacyControl', {
            get: () => undefined,
            configurable: true
        });
    }
}
