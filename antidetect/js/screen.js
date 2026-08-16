// === Screen: availWidth/availHeight only ===
// screen.width/height come from Emulation.setDeviceMetricsOverride, which keeps
// the Screen getters native. It has no notion of the available area though and
// reports avail == screen, while a real desktop always loses a strip to the menu
// bar / taskbar. Patch just that delta, and only when it actually differs.
for (const prop of ['availWidth', 'availHeight']) {
    const value = C.screen?.[prop];
    if (!value || screen[prop] === value) continue;
    wrapGetter(Screen.prototype, prop, function() { return value; });
}
