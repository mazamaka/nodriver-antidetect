// === Navigator: Plugins & MimeTypes ===
// These MUST be spoofed via JS as CDP has no API for this
(function() {
    const createPlugin = (data) => {
        const plugin = {};
        const mimes = [];

        data.mimeTypes.forEach((mt, i) => {
            const mimeType = {
                type: mt.type,
                suffixes: mt.suffixes,
                description: mt.description,
                enabledPlugin: plugin
            };
            mimes.push(mimeType);
            plugin[i] = mimeType;
            plugin[mt.type] = mimeType;
        });

        Object.defineProperties(plugin, {
            name: { value: data.name, enumerable: true, configurable: true },
            description: { value: data.description, enumerable: true, configurable: true },
            filename: { value: data.filename, enumerable: true, configurable: true },
            length: { value: mimes.length, enumerable: true, configurable: true },
            item: { value: function(i) { return this[i] || null; }, configurable: true },
            namedItem: { value: function(n) { return this[n] || null; }, configurable: true },
            [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, configurable: true }
        });

        return plugin;
    };

    const plugins = C.plugins.map(createPlugin);
    const pluginArray = {};
    const mimeTypes = {};
    let mimeIdx = 0;

    plugins.forEach((p, i) => {
        pluginArray[i] = p;
        pluginArray[p.name] = p;

        for (let j = 0; j < p.length; j++) {
            const mt = p[j];
            if (!mimeTypes[mt.type]) {
                mimeTypes[mt.type] = mt;
                mimeTypes[mimeIdx++] = mt;
            }
        }
    });

    Object.defineProperties(pluginArray, {
        length: { value: plugins.length, enumerable: true, configurable: true },
        item: { value: function(i) { return this[i] || null; }, configurable: true },
        namedItem: { value: function(n) { return this[n] || null; }, configurable: true },
        refresh: { value: function() {}, configurable: true },
        [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, configurable: true }
    });

    Object.defineProperties(mimeTypes, {
        length: { value: mimeIdx, enumerable: true, configurable: true },
        item: { value: function(i) { return this[i] || null; }, configurable: true },
        namedItem: { value: function(n) { return this[n] || null; }, configurable: true },
        [Symbol.iterator]: { value: function*() { for (let i = 0; i < this.length; i++) yield this[i]; }, configurable: true }
    });

    defineProperty(Navigator.prototype, 'plugins', {
        get: function() { return pluginArray; },
        enumerable: true,
        configurable: true
    });

    defineProperty(Navigator.prototype, 'mimeTypes', {
        get: function() { return mimeTypes; },
        enumerable: true,
        configurable: true
    });
})();
