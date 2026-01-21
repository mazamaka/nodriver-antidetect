// === WebGL vendor/renderer (CDP cannot spoof) ===
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
