// === webdriver flag ===
// Real Chrome has a Navigator.prototype.webdriver getter that returns false.
// Deleting the property or returning undefined is itself a detectable anomaly,
// so we only step in when the flag is actually raised.
if (navigator.webdriver !== false) {
    wrapGetter(Navigator.prototype, 'webdriver', function() { return false; });
}

// === Navigator: pdfViewerEnabled (standard Chrome property) ===
if (navigator.pdfViewerEnabled !== true) {
    wrapGetter(Navigator.prototype, 'pdfViewerEnabled', function() { return true; });
}
