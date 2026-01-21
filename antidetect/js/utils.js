// === Utility: Proper property definition ===
const defineProperty = (obj, prop, desc) => {
    try {
        Object.defineProperty(obj, prop, { ...desc, configurable: true });
    } catch (e) {}
};

// === Utility: Wrap function preserving native appearance ===
const wrapFn = (original, replacement) => {
    if (!original) return replacement;

    // Match toString exactly
    const origStr = original.toString();
    replacement.toString = function() { return origStr; };

    // Match name
    try {
        Object.defineProperty(replacement, 'name', {
            value: original.name,
            configurable: true
        });
    } catch (e) {}

    // Match length (number of arguments)
    try {
        Object.defineProperty(replacement, 'length', {
            value: original.length,
            configurable: true
        });
    } catch (e) {}

    return replacement;
};

// === Utility: Wrap getter on prototype ===
const wrapGetter = (proto, prop, getter) => {
    const desc = Object.getOwnPropertyDescriptor(proto, prop);
    if (!desc?.get) return;

    const wrapped = wrapFn(desc.get, getter);
    defineProperty(proto, prop, {
        get: wrapped,
        enumerable: desc.enumerable,
        configurable: true
    });
};
