// === Media Devices (CDP cannot spoof) ===
// A machine with no camera/microphone at all is a headless tell. Real devices
// already come with per-origin randomised IDs, so the wrapper passes them
// through untouched and only substitutes the profile list when Chrome reports
// nothing (headless, or a container without media devices).
if (navigator.mediaDevices?.enumerateDevices) {
    const fakeDevices = C.media.devices.map(d => ({
        deviceId: d.deviceId,
        kind: d.kind,
        label: d.label,
        groupId: d.groupId,
        toJSON() {
            return {
                deviceId: this.deviceId,
                kind: this.kind,
                label: this.label,
                groupId: this.groupId
            };
        }
    }));

    const orig = navigator.mediaDevices.enumerateDevices;
    navigator.mediaDevices.enumerateDevices = wrapFn(orig, async function() {
        const real = await orig.call(this);
        return real.length ? real : fakeDevices;
    });
}
