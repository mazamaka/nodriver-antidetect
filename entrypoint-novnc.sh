#!/bin/bash
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_highlight() { echo -e "${CYAN}[noVNC]${NC} $1"; }

# Generate Xorg config for headless NVIDIA
generate_xorg_config() {
    local DISPLAY_NUM="${1:-0}"
    local WIDTH="${SCREEN_WIDTH:-1920}"
    local HEIGHT="${SCREEN_HEIGHT:-1080}"

    log_info "Generating Xorg config for NVIDIA headless..."

    local RAW_BUS_ID=$(nvidia-smi --query-gpu=pci.bus_id --format=csv,noheader 2>/dev/null | head -1)
    local GPU_BUS_ID="PCI:1:0:0"

    if [ -n "$RAW_BUS_ID" ]; then
        local BUS_HEX=$(echo "$RAW_BUS_ID" | awk -F: '{print $(NF-1)}')
        local DEV_FUNC=$(echo "$RAW_BUS_ID" | awk -F: '{print $NF}')
        local DEV_HEX=$(echo "$DEV_FUNC" | cut -d. -f1)
        local FUNC=$(echo "$DEV_FUNC" | cut -d. -f2)

        if [ -n "$BUS_HEX" ] && [ -n "$DEV_HEX" ]; then
            local BUS_DEC=$(printf "%d" "0x$BUS_HEX" 2>/dev/null || echo "1")
            local DEV_DEC=$(printf "%d" "0x$DEV_HEX" 2>/dev/null || echo "0")
            GPU_BUS_ID="PCI:${BUS_DEC}:${DEV_DEC}:${FUNC}"
        fi
    fi

    log_info "Detected GPU BusID: $GPU_BUS_ID"

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

    pkill -9 Xorg 2>/dev/null || true
    pkill -9 X 2>/dev/null || true
    rm -f /tmp/.X${DISPLAY_NUM}-lock 2>/dev/null || true
    rm -f /tmp/.X11-unix/X${DISPLAY_NUM} 2>/dev/null || true

    mkdir -p /tmp/.X11-unix
    chmod 1777 /tmp/.X11-unix

    Xorg :${DISPLAY_NUM} \
        -noreset \
        -novtswitch \
        -sharevts \
        -config /etc/X11/xorg.conf \
        +extension GLX \
        +extension RENDER \
        &

    XORG_PID=$!

    local max_wait=30
    local waited=0
    while [ ! -e /tmp/.X11-unix/X${DISPLAY_NUM} ] && [ $waited -lt $max_wait ]; do
        sleep 1
        waited=$((waited + 1))
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
        log_error "Xorg failed to start"
        return 1
    fi
}

# Start x11vnc server
start_vnc() {
    local VNC_PORT="${VNC_PORT:-5900}"
    local VNC_PASSWORD="${VNC_PASSWORD:-antidetect}"

    log_info "Starting x11vnc on port ${VNC_PORT}..."

    # Create password file
    mkdir -p /root/.vnc
    x11vnc -storepasswd "$VNC_PASSWORD" /root/.vnc/passwd 2>/dev/null

    # Kill existing vnc
    pkill -9 x11vnc 2>/dev/null || true

    # Start x11vnc
    x11vnc \
        -display :0 \
        -rfbport $VNC_PORT \
        -rfbauth /root/.vnc/passwd \
        -shared \
        -forever \
        -noxdamage \
        -cursor arrow \
        -bg \
        -o /var/log/x11vnc.log

    sleep 2

    if pgrep x11vnc > /dev/null; then
        log_info "x11vnc started successfully on port $VNC_PORT"
        return 0
    else
        log_error "x11vnc failed to start"
        cat /var/log/x11vnc.log 2>/dev/null || true
        return 1
    fi
}

# Start noVNC (websockify)
start_novnc() {
    local NOVNC_PORT="${NOVNC_PORT:-6080}"
    local VNC_PORT="${VNC_PORT:-5900}"

    log_info "Starting noVNC on port ${NOVNC_PORT}..."

    # Kill existing
    pkill -9 websockify 2>/dev/null || true

    # Find noVNC web directory
    local NOVNC_WEB="/usr/share/novnc"
    if [ ! -d "$NOVNC_WEB" ]; then
        NOVNC_WEB="/usr/share/javascript/novnc"
    fi

    # Start websockify with noVNC
    websockify \
        --web=$NOVNC_WEB \
        $NOVNC_PORT \
        localhost:$VNC_PORT \
        > /var/log/novnc.log 2>&1 &

    NOVNC_PID=$!
    sleep 2

    if kill -0 $NOVNC_PID 2>/dev/null; then
        log_info "noVNC started successfully (PID: $NOVNC_PID)"
        return 0
    else
        log_error "noVNC failed to start"
        cat /var/log/novnc.log 2>/dev/null || true
        return 1
    fi
}

# Start window manager
start_wm() {
    log_info "Starting openbox window manager..."
    openbox &
    sleep 1
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
    return 0
}

# Print configuration
print_config() {
    local HOST_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "localhost")

    log_info "=== noVNC + NVIDIA Configuration ==="
    echo "  DISPLAY:     ${DISPLAY}"
    echo "  GPU:         $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo 'N/A')"
    echo "  Driver:      $(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo 'N/A')"
    echo "  Screen:      ${SCREEN_WIDTH:-1920}x${SCREEN_HEIGHT:-1080}"
    echo "  VNC Port:    ${VNC_PORT:-5900}"
    echo "  noVNC Port:  ${NOVNC_PORT:-6080}"
    log_info "==================================="
    echo ""
    log_highlight "Browser access: http://localhost:${NOVNC_PORT:-6080}/vnc.html"
    log_highlight "VNC password: ${VNC_PASSWORD:-antidetect}"
    echo ""
}

main() {
    log_info "Starting noVNC + NVIDIA antidetect container"

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

    # Start window manager
    start_wm

    # Start VNC server
    if ! start_vnc; then
        log_error "Failed to start VNC"
        exit 1
    fi

    # Start noVNC
    if ! start_novnc; then
        log_error "Failed to start noVNC"
        exit 1
    fi

    # Set timezone
    export TZ="${AD_TIMEZONE:-UTC}"

    # Update antidetect screen settings to match
    export AD_SCREEN_WIDTH="${SCREEN_WIDTH:-1920}"
    export AD_SCREEN_HEIGHT="${SCREEN_HEIGHT:-1080}"

    # Print config
    print_config

    # Execute main command
    log_info "Executing: $@"
    exec "$@"
}

main "$@"
