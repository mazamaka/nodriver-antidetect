#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Generate Xorg config for headless NVIDIA
generate_xorg_config() {
    local DISPLAY_NUM="${1:-0}"
    local WIDTH="${AD_SCREEN_WIDTH:-1920}"
    local HEIGHT="${AD_SCREEN_HEIGHT:-1080}"

    log_info "Generating Xorg config for NVIDIA headless..."

    # Get GPU BusID using nvidia-smi
    # Output format: 00000000:01:00.0
    # Need to convert to Xorg format: PCI:1:0:0
    local RAW_BUS_ID=$(nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader 2>/dev/null | head -1)
    local GPU_BUS_ID="PCI:1:0:0"  # Default

    if [ -n "$RAW_BUS_ID" ]; then
        # Extract the BUS:DEV.FUNC part (e.g., "01:00.0" from "00000000:01:00.0")
        # Use awk to parse: split by ':' and get last two parts
        local BUS_HEX=$(echo "$RAW_BUS_ID" | awk -F: '{print $(NF-1)}')
        local DEV_FUNC=$(echo "$RAW_BUS_ID" | awk -F: '{print $NF}')
        local DEV_HEX=$(echo "$DEV_FUNC" | cut -d. -f1)
        local FUNC=$(echo "$DEV_FUNC" | cut -d. -f2)

        # Convert hex bus and device to decimal
        if [ -n "$BUS_HEX" ] && [ -n "$DEV_HEX" ]; then
            local BUS_DEC=$(printf "%d" "0x$BUS_HEX" 2>/dev/null || echo "1")
            local DEV_DEC=$(printf "%d" "0x$DEV_HEX" 2>/dev/null || echo "0")
            GPU_BUS_ID="PCI:${BUS_DEC}:${DEV_DEC}:${FUNC}"
        fi
    fi

    log_info "Detected GPU BusID: $GPU_BUS_ID (raw: $RAW_BUS_ID)"

    # Create xorg.conf for headless operation
    cat > /etc/X11/xorg.conf << XORGCONF
Section "ServerLayout"
    Identifier     "Layout0"
    Screen      0  "Screen0"
    InputDevice    "Keyboard0" "CoreKeyboard"
    InputDevice    "Mouse0" "CorePointer"
EndSection

Section "InputDevice"
    Identifier     "Mouse0"
    Driver         "void"
EndSection

Section "InputDevice"
    Identifier     "Keyboard0"
    Driver         "void"
EndSection

Section "Device"
    Identifier     "Device0"
    Driver         "nvidia"
    BusID          "${GPU_BUS_ID}"
    Option         "AllowEmptyInitialConfiguration" "True"
EndSection

Section "Screen"
    Identifier     "Screen0"
    Device         "Device0"
    Monitor        "Monitor0"
    DefaultDepth    24
    Option         "AllowEmptyInitialConfiguration" "True"
    Option         "UseDisplayDevice" "None"
    SubSection     "Display"
        Depth       24
        Modes      "${WIDTH}x${HEIGHT}"
        Virtual    ${WIDTH} ${HEIGHT}
    EndSubSection
EndSection

Section "Monitor"
    Identifier     "Monitor0"
    VendorName     "Unknown"
    ModelName      "Unknown"
    Option         "DPMS"
EndSection
XORGCONF

    log_info "Xorg config created"
}

# Start Xorg server
start_xorg() {
    local DISPLAY_NUM="${1:-0}"

    log_info "Starting Xorg on display :${DISPLAY_NUM}..."

    # Kill any existing X servers
    pkill -9 Xorg 2>/dev/null || true
    pkill -9 X 2>/dev/null || true
    rm -f /tmp/.X${DISPLAY_NUM}-lock 2>/dev/null || true
    rm -f /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true

    # Create required directories
    mkdir -p /tmp/.X11-unix
    chmod 1777 /tmp/.X11-unix

    # Start Xorg in background
    # -noreset: don't reset after last client exits
    # -novtswitch: don't switch VT
    # -sharevts: share VT with other X servers
    Xorg :${DISPLAY_NUM} \
        -noreset \
        -novtswitch \
        -sharevts \
        -config /etc/X11/xorg.conf \
        +extension GLX \
        +extension RENDER \
        &

    XORG_PID=$!

    # Wait for Xorg to start
    local max_wait=30
    local waited=0
    while [ ! -e /tmp/.X11-unix/X${DISPLAY_NUM} ] && [ $waited -lt $max_wait ]; do
        sleep 1
        waited=$((waited + 1))

        # Check if Xorg is still running
        if ! kill -0 $XORG_PID 2>/dev/null; then
            log_error "Xorg process died"
            return 1
        fi
    done

    if [ -e /tmp/.X11-unix/X${DISPLAY_NUM} ]; then
        log_info "Xorg started successfully (PID: $XORG_PID)"
        export DISPLAY=:${DISPLAY_NUM}
        return 0
    else
        log_error "Xorg failed to start within ${max_wait} seconds"
        return 1
    fi
}

# Verify GPU is accessible
verify_gpu() {
    log_info "Verifying GPU access..."

    if ! nvidia-smi > /dev/null 2>&1; then
        log_error "nvidia-smi failed - GPU not accessible"
        return 1
    fi

    local GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)
    log_info "GPU detected: $GPU_NAME"

    # Check if glxinfo works
    if command -v glxinfo > /dev/null 2>&1; then
        local GL_RENDERER=$(DISPLAY=:0 glxinfo 2>/dev/null | grep "OpenGL renderer" | head -1 || echo "N/A")
        log_info "OpenGL renderer: $GL_RENDERER"
    fi

    return 0
}

# Print configuration
print_config() {
    log_info "=== Xorg + NVIDIA Configuration ==="
    echo "  DISPLAY:     ${DISPLAY}"
    echo "  GPU:         $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
    echo "  Driver:      $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'N/A')"
    echo "  Timezone:    ${AD_TIMEZONE:-UTC}"
    echo "  Screen:      ${AD_SCREEN_WIDTH:-1920}x${AD_SCREEN_HEIGHT:-1080}"
    log_info "==================================="
}

main() {
    log_info "Starting Xorg + NVIDIA antidetect container"

    # Check GPU availability
    if [ ! -e /dev/nvidia0 ]; then
        log_error "NVIDIA GPU not found (/dev/nvidia0 missing)"
        log_error "Make sure to run with: --runtime=nvidia --gpus all"
        exit 1
    fi

    # Generate Xorg config
    generate_xorg_config 0

    # Start Xorg
    if ! start_xorg 0; then
        log_error "Failed to start Xorg"
        exit 1
    fi

    # Verify GPU works
    verify_gpu || log_warn "GPU verification failed, continuing anyway..."

    # Set timezone
    export TZ="${AD_TIMEZONE:-UTC}"

    # Print config
    print_config

    # Execute main command
    log_info "Executing: $@"
    exec "$@"
}

main "$@"
