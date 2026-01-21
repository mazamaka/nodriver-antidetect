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

# Start Xvfb with configured resolution
start_xvfb() {
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
    log_info "================================"
}

# Main entrypoint
main() {
    log_info "Starting nodriver-antidetect container"

    # Configure environment
    configure_timezone
    configure_locale

    # Start display server
    start_xvfb

    # Export display
    export DISPLAY=:99

    # Print configuration
    print_config

    # Execute the main command
    log_info "Executing: $@"
    exec "$@"
}

main "$@"
