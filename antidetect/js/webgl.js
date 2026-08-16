// === WebGL vendor/renderer (CDP cannot spoof) ===
// Patching getParameter is itself detectable: CreepJS scores it as a stealth
// technique (measured +20% stealth on a machine with a real GPU). It only pays
// off when the real renderer is a software one, which screams headless/container.
// mode: auto (default) | always | off
(function() {
    const mode = C.webgl.mode || 'auto';
    if (mode === 'off') return;

    const realRenderer = (() => {
        try {
            const gl = document.createElement('canvas').getContext('webgl');
            const dbg = gl.getExtension('WEBGL_debug_renderer_info');
            return String(gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL));
        } catch (e) { return ''; }
    })();

    const isSoftware = /swiftshader|llvmpipe|software|mesa|virgl/i.test(realRenderer);
    if (mode === 'auto' && !isSoftware) return;

    const glParams = {
        37445: C.webgl.vendor,    // UNMASKED_VENDOR_WEBGL
        37446: C.webgl.renderer,  // UNMASKED_RENDERER_WEBGL
        7936: 'WebKit',           // VENDOR (standard)
        7937: 'WebKit WebGL'      // RENDERER (standard)
    };

    const patchGL = (proto) => {
        const orig = proto.getParameter;
        if (!orig) return;

        proto.getParameter = wrapFn(orig, function(param) {
            const spoofed = glParams[param];
            return spoofed !== undefined ? spoofed : orig.call(this, param);
        });
    };

    if (typeof WebGLRenderingContext !== 'undefined') {
        patchGL(WebGLRenderingContext.prototype);
    }
    if (typeof WebGL2RenderingContext !== 'undefined') {
        patchGL(WebGL2RenderingContext.prototype);
    }
})();
