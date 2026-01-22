// === Remove webdriver flag (critical) ===
// Real Chrome returns `false` when not automated, not `undefined`
// CRITICAL: Must preserve native toString() to avoid lie detection
try {
    // Get original descriptor to copy its getter's toString
    const originalDesc = Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver');
    const originalGetter = originalDesc && originalDesc.get;

    // Create replacement getter that returns false
    const newGetter = function webdriver() { return false; };

    // Make toString() look native
    if (originalGetter) {
        newGetter.toString = () => originalGetter.toString();
        Object.defineProperty(newGetter, 'name', { value: 'get webdriver', configurable: true });
    } else {
        // Fallback: make it look like native code
        newGetter.toString = () => 'function get webdriver() { [native code] }';
        Object.defineProperty(newGetter, 'name', { value: 'get webdriver', configurable: true });
    }

    // Override on prototype
    defineProperty(Navigator.prototype, 'webdriver', {
        get: newGetter,
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
