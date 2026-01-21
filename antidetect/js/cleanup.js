// === Clean automation traces ===
const automationProps = [
    'cdc_adoQpoasnfa76pfcZLmcfl_Array',
    'cdc_adoQpoasnfa76pfcZLmcfl_Promise',
    'cdc_adoQpoasnfa76pfcZLmcfl_Symbol',
    '__webdriver_evaluate',
    '__selenium_evaluate',
    '__webdriver_script_function',
    '__webdriver_script_func',
    '__webdriver_script_fn',
    '__fxdriver_evaluate',
    '__driver_unwrapped',
    '__webdriver_unwrapped',
    '__driver_evaluate',
    '__selenium_unwrapped',
    '__fxdriver_unwrapped',
    '$chrome_asyncScriptInfo',
    '$cdc_asdjflasutopfhvcZLmcfl_',
    '__nightmare',
    '_phantom',
    '_selenium',
    'callPhantom',
    'domAutomation',
    'domAutomationController'
];

automationProps.forEach(p => {
    try { delete window[p]; } catch {}
});

try {
    if (document.$cdc_asdjflasutopfhvcZLmcfl_) {
        delete document.$cdc_asdjflasutopfhvcZLmcfl_;
    }
} catch (e) {}
