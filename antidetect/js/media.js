// === Media Devices (CDP cannot spoof) ===
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
        return fakeDevices;
    });
}
