// === Navigator: Plugins & MimeTypes ===
// These MUST be spoofed via JS as CDP has no API for this
// CRITICAL: Must properly inherit from PluginArray/MimeTypeArray for instanceof checks
(function() {
    // Get real prototypes from original navigator.plugins/mimeTypes
    const realPlugins = navigator.plugins;
    const realMimeTypes = navigator.mimeTypes;
    const PluginArrayProto = Object.getPrototypeOf(realPlugins);
    const MimeTypeArrayProto = Object.getPrototypeOf(realMimeTypes);
    const PluginProto = realPlugins.length > 0 ? Object.getPrototypeOf(realPlugins[0]) : null;
    const MimeTypeProto = realMimeTypes.length > 0 ? Object.getPrototypeOf(realMimeTypes[0]) : null;

    const createMimeType = (data, plugin) => {
        const mimeType = Object.create(MimeTypeProto || Object.prototype);
        Object.defineProperties(mimeType, {
            type: { value: data.type, enumerable: true, configurable: true },
            suffixes: { value: data.suffixes, enumerable: true, configurable: true },
            description: { value: data.description, enumerable: true, configurable: true },
            enabledPlugin: { value: plugin, enumerable: true, configurable: true }
        });
        return mimeType;
    };

    const createPlugin = (data) => {
        const plugin = Object.create(PluginProto || Object.prototype);
        const mimes = [];

        // First pass: create mimeTypes with circular reference to plugin
        data.mimeTypes.forEach((mt, i) => {
            const mimeType = createMimeType(mt, plugin);
            mimes.push(mimeType);
            Object.defineProperty(plugin, i, { value: mimeType, enumerable: true, configurable: true });
            Object.defineProperty(plugin, mt.type, { value: mimeType, enumerable: false, configurable: true });
        });

        Object.defineProperties(plugin, {
            name: { value: data.name, enumerable: true, configurable: true },
            description: { value: data.description, enumerable: true, configurable: true },
            filename: { value: data.filename, enumerable: true, configurable: true },
            length: { value: mimes.length, enumerable: true, configurable: true },
            item: { value: function(i) { return this[i] || null; }, enumerable: false, configurable: true },
            namedItem: { value: function(n) { return this[n] || null; }, enumerable: false, configurable: true },
            [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, enumerable: false, configurable: true }
        });

        return { plugin, mimes };
    };

    // Create plugins array with proper prototype chain
    const pluginArray = Object.create(PluginArrayProto);
    const mimeTypeArray = Object.create(MimeTypeArrayProto);
    const allMimeTypes = [];
    let mimeIdx = 0;

    C.plugins.forEach((data, i) => {
        const { plugin, mimes } = createPlugin(data);
        Object.defineProperty(pluginArray, i, { value: plugin, enumerable: true, configurable: true });
        Object.defineProperty(pluginArray, plugin.name, { value: plugin, enumerable: false, configurable: true });

        mimes.forEach(mt => {
            if (!allMimeTypes.find(m => m.type === mt.type)) {
                Object.defineProperty(mimeTypeArray, mimeIdx, { value: mt, enumerable: true, configurable: true });
                Object.defineProperty(mimeTypeArray, mt.type, { value: mt, enumerable: false, configurable: true });
                allMimeTypes.push(mt);
                mimeIdx++;
            }
        });
    });

    Object.defineProperties(pluginArray, {
        length: { value: C.plugins.length, enumerable: true, configurable: true },
        item: { value: function(i) { return this[i] || null; }, enumerable: false, configurable: true },
        namedItem: { value: function(n) { return this[n] || null; }, enumerable: false, configurable: true },
        refresh: { value: function() {}, enumerable: false, configurable: true },
        [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, enumerable: false, configurable: true }
    });

    Object.defineProperties(mimeTypeArray, {
        length: { value: mimeIdx, enumerable: true, configurable: true },
        item: { value: function(i) { return this[i] || null; }, enumerable: false, configurable: true },
        namedItem: { value: function(n) { return this[n] || null; }, enumerable: false, configurable: true },
        [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, enumerable: false, configurable: true }
    });

    defineProperty(Navigator.prototype, 'plugins', {
        get: function() { return pluginArray; },
        enumerable: true,
        configurable: true
    });

    defineProperty(Navigator.prototype, 'mimeTypes', {
        get: function() { return mimeTypeArray; },
        enumerable: true,
        configurable: true
    });
})();
