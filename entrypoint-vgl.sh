#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Configure VirtualGL
configure_vgl() {
    log_info "Configuring VirtualGL..."
    
    # VirtualGL needs access to GPU device
    if [ -e /dev/nvidia0 ]; then
        log_info "NVIDIA GPU detected"
        # Configure VirtualGL server
        /opt/VirtualGL/bin/vglserver_config -config +s +f -t 2>/dev/null || true
    else
        log_warn "No NVIDIA GPU found, VirtualGL may not work"
    fi
}

# Start Xvfb (virtual display for output)
start_xvfb() {
    DISPLAY_WIDTH="${AD_SCREEN_WIDTH:-1920}"
    DISPLAY_HEIGHT="${AD_SCREEN_HEIGHT:-1080}"
    
    log_info "Starting Xvfb :99 (${DISPLAY_WIDTH}x${DISPLAY_HEIGHT})"
    
    pkill Xvfb 2>/dev/null || true
    
    Xvfb :99 -screen 0 ${DISPLAY_WIDTH}x${DISPLAY_HEIGHT}x24 \
        -ac +extension GLX +render -noreset &
    
    sleep 2
    export DISPLAY=:99
}

# Set VGL_DISPLAY to point to GPU
setup_vgl_display() {
    # VGL_DISPLAY tells VirtualGL which display has the GPU
    # For headless with nvidia, we use EGL device
    if [ -e /dev/nvidia0 ]; then
        export VGL_DISPLAY=egl
        export __EGL_VENDOR_LIBRARY_FILENAMES=/usr/share/glvnd/egl_vendor.d/10_nvidia.json
        log_info "VGL_DISPLAY=egl (NVIDIA EGL)"
    else
        export VGL_DISPLAY=:0
        log_info "VGL_DISPLAY=:0"
    fi
}

# Create Chrome wrapper that uses vglrun
setup_chrome_vgl_wrapper() {
    log_info "Creating Chrome VGL wrapper..."

    # NOTE: VirtualGL does NOT work with Chrome!
    # Chrome uses ANGLE/EGL which VirtualGL cannot intercept.
    # This wrapper is kept for documentation but will still use llvmpipe.
    # For real GPU, use antidetect-gpu with X11 forwarding instead.
    cat > /usr/local/bin/chrome-vgl << 'WRAPPER'
#!/bin/bash
# VirtualGL wrapper for Chrome (experimental - does not provide real GPU)
# Chrome uses ANGLE/EGL internally, VirtualGL only intercepts GLX calls
export VGL_DISPLAY=egl
export VGL_READBACK=sync
export VGL_COMPRESS=0
exec /opt/VirtualGL/bin/vglrun -d egl /opt/google/chrome/google-chrome "$@"
WRAPPER
    chmod +x /usr/local/bin/chrome-vgl

    # Create symlink so nodriver can find it
    ln -sf /usr/local/bin/chrome-vgl /usr/local/bin/google-chrome
    ln -sf /usr/local/bin/chrome-vgl /usr/local/bin/google-chrome-stable

    # Update PATH to prefer our wrapper
    export PATH="/usr/local/bin:$PATH"

    log_info "Chrome VGL wrapper created at /usr/local/bin/chrome-vgl"
}

print_config() {
    log_info "=== VirtualGL Configuration ==="
    echo "  DISPLAY:     ${DISPLAY}"
    echo "  VGL_DISPLAY: ${VGL_DISPLAY}"
    echo "  GPU:         $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
    echo "  Timezone:    ${AD_TIMEZONE:-UTC}"
    echo "  Screen:      ${AD_SCREEN_WIDTH}x${AD_SCREEN_HEIGHT}"
    log_info "================================"
}

main() {
    log_info "Starting VirtualGL antidetect container"

    configure_vgl
    start_xvfb
    setup_vgl_display
    setup_chrome_vgl_wrapper

    export TZ="${AD_TIMEZONE:-UTC}"

    print_config

    log_info "Executing: $@"
    exec "$@"
}

main "$@"
