// === Canvas noise (subtle, deterministic per-session) ===
if (C.noise.canvas > 0) {
    const seed = Math.random();

    const addNoise = (data, noise) => {
        for (let i = 0; i < data.length; i += 4) {
            // Deterministic noise based on position and seed
            const n = ((seed * (i + 1) * 9999) % 1 - 0.5) * noise * 255;
            data[i] = Math.max(0, Math.min(255, data[i] + n | 0));
        }
    };

    const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
    CanvasRenderingContext2D.prototype.getImageData = wrapFn(origGetImageData, function(...args) {
        const result = origGetImageData.apply(this, args);
        addNoise(result.data, C.noise.canvas);
        return result;
    });

    const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = wrapFn(origToDataURL, function(...args) {
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const img = ctx.getImageData(0, 0, this.width || 1, this.height || 1);
                addNoise(img.data, C.noise.canvas);
                ctx.putImageData(img, 0, 0);
            } catch (e) {}
        }
        return origToDataURL.apply(this, args);
    });
}
