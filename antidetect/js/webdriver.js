// === Remove webdriver flag (critical) ===
try {
    // Delete from prototype
    const proto = Object.getPrototypeOf(navigator);
    if ('webdriver' in proto) {
        delete proto.webdriver;
    }
    // Also override getter
    defineProperty(Navigator.prototype, 'webdriver', {
        get: () => undefined,
        enumerable: true,
        configurable: true
    });
} catch (e) {}

// === Navigator: pdfViewerEnabled (standard Chrome property) ===
defineProperty(Navigator.prototype, 'pdfViewerEnabled', {
    get: () => true,
    enumerable: true,
    configurable: true
});
