// Navigator properties that CDP has no override for.
// hardwareConcurrency, maxTouchPoints and screen.* are handled by the Emulation
// domain instead - a patched prototype getter is exactly what fingerprint
// checkers look for (pixelscan flags it as "Navigator: Detected").

// deviceMemory has no CDP override, so JS is the only option - and only when the
// real value differs from the profile.
if (C.navigator?.deviceMemory && navigator.deviceMemory !== C.navigator.deviceMemory) {
    const value = C.navigator.deviceMemory;
    wrapGetter(Navigator.prototype, 'deviceMemory', function() { return value; });
}

// doNotTrack - real Chrome exposes it on Navigator.prototype and returns null
// when the user has no preference. Defining it on the navigator instance creates
// an own property that does not exist in a real browser, so patch the prototype
// and only when the profile asks for something else.
if (C.navigator?.doNotTrack !== undefined && navigator.doNotTrack !== C.navigator.doNotTrack) {
    const value = C.navigator.doNotTrack;
    wrapGetter(Navigator.prototype, 'doNotTrack', function() { return value; });
}
