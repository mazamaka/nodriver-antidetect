#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Start Xvfb with configured resolution (virtual display)
start_xvfb() {
    # Sync display resolution with antidetect screen settings
    DISPLAY_WIDTH="${AD_SCREEN_WIDTH:-${DISPLAY_WIDTH:-1920}}"
    DISPLAY_HEIGHT="${AD_SCREEN_HEIGHT:-${DISPLAY_HEIGHT:-1080}}"

    log_info "Starting Xvfb display :99 (${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x${DISPLAY_DEPTH})"

    # Kill existing Xvfb if running
    pkill Xvfb 2>/dev/null || true

    # Start Xvfb
    Xvfb :99 -screen 0 ${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x${DISPLAY_DEPTH} \
        -ac \
        -nolisten tcp \
        +extension GLX \
        +render \
        -noreset &

    # Wait for Xvfb to start
    sleep 2

    # Verify Xvfb is running
    if pgrep -x Xvfb > /dev/null; then
        log_info "Xvfb started successfully"
    else
        log_error "Failed to start Xvfb"
        exit 1
    fi
}

# Setup display - either use host X11 or start Xvfb
setup_display() {
    # AD_SHOW_GUI=true - use host X11 display (requires -e DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix)
    if [ "${AD_SHOW_GUI}" = "true" ] || [ "${AD_SHOW_GUI}" = "1" ]; then
        if [ -n "${DISPLAY}" ] && [ "${DISPLAY}" != ":99" ]; then
            log_info "Using host X11 display: ${DISPLAY} (GUI mode)"
            # Don't start Xvfb, use host display
            return 0
        else
            log_warn "AD_SHOW_GUI=true but no host DISPLAY found. Falling back to Xvfb."
            log_warn "To show GUI, run with: -e DISPLAY=\$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix"
        fi
    fi

    # Default: start Xvfb (headless virtual display)
    start_xvfb
    export DISPLAY=:99
}

# Configure timezone at runtime
configure_timezone() {
    if [ -n "$AD_TIMEZONE" ]; then
        log_info "Setting timezone to: $AD_TIMEZONE"
        export TZ="$AD_TIMEZONE"
    fi
}

# Configure locale at runtime
configure_locale() {
    if [ -n "$AD_LOCALE" ]; then
        log_info "Setting locale to: $AD_LOCALE"
        # Use proper locale format
        if [[ "$AD_LOCALE" == *".UTF-8" ]]; then
            export LANG="$AD_LOCALE"
        else
            export LANG="${AD_LOCALE}.UTF-8" 2>/dev/null || export LANG="en_US.UTF-8"
        fi
        export LC_ALL="$LANG" 2>/dev/null || true
    fi
}

# Print configuration summary
print_config() {
    log_info "=== Antidetect Configuration ==="
    echo "  Timezone:    ${AD_TIMEZONE:-UTC}"
    echo "  Locale:      ${AD_LOCALE:-en_US.UTF-8}"
    echo "  Screen:      ${AD_SCREEN_WIDTH}x${AD_SCREEN_HEIGHT}"
    echo "  Memory:      ${AD_DEVICE_MEMORY} GB"
    echo "  CPU Cores:   ${AD_HARDWARE_CONCURRENCY}"
    echo "  Platform:    ${AD_PLATFORM}"
    echo "  Languages:   ${AD_LANGUAGES}"
    echo "  Proxy:       ${PROXY_URL:-none}"
    echo "  GUI Mode:    ${AD_SHOW_GUI:-false}"
    echo "  Display:     ${DISPLAY}"
    log_info "================================"
}

# Main entrypoint
main() {
    log_info "Starting nodriver-antidetect container"

    # Configure environment
    configure_timezone
    configure_locale

    # Setup display (Xvfb or host X11 if AD_SHOW_GUI=true)
    setup_display

    # Print configuration
    print_config

    # Execute the main command
    log_info "Executing: $@"
    exec "$@"
}

main "$@"
