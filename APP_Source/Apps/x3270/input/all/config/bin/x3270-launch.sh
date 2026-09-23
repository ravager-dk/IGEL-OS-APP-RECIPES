#!/bin/bash
# Profile values are data: never evaluate them as shell code.
set -euo pipefail
APP=/services/x3270
fail() {
    printf 'x3270: %s\n' "$*" >&2
    if command -v logger >/dev/null 2>&1; then logger -t x3270-igel -- "$*" || :; fi
    exit 1
}
# get reads the IGEL registry after UMS/local settings have been merged.
get_setting() {
    local value
    if command -v get >/dev/null 2>&1 && value=$(get "app.x3270.options.$1" 2>/dev/null); then
        printf '%s' "$value"
    else
        printf '%s' "$2"
    fi
}
bool_setting() {
    local value
    value=$(get_setting "$1" "$2")
    case "${value,,}" in
        true|1) printf true ;;
        false|0) printf false ;;
        *) fail "Invalid checkbox value for $1. Reapply the x3270 profile." ;;
    esac
}
readable_file() {
    [[ "$2" == /* && "$2" != *$'\n'* && "$2" != *$'\r'* && -f "$2" && -r "$2" ]] ||
        fail "$1 must be an absolute path to a readable file. Deploy the UMS file before launching x3270."
}
if [[ "${1:-}" == -v || "${1:-}" == -version ]]; then
    exec "$APP/usr/local/bin/x3270" "$@"
fi
[[ -n "${DISPLAY:-}" ]] || fail 'Launch from the logged-in graphical session (DISPLAY is unset).'
mode=$(get_setting mode local)
args=()
case "$mode" in
    local|'')
        args+=("$@")
        ;;
    profile)
        [[ $# -eq 0 ]] || fail 'Command-line overrides are disabled in UMS profile mode. Use Local mode for manual arguments.'
        host=$(get_setting host '')
        port=$(get_setting port 23)
        transport=$(get_setting transport auto)
        lu=$(get_setting lu '')
        tn3270e=$(bool_setting tn3270e true)
        disconnect=$(get_setting disconnect stay)
        verify=$(bool_setting verify_certificate true)
        ca_file=$(get_setting ca_file '')
        model=$(get_setting model 3279-4)
        extended=$(bool_setting extended true)
        codepage=$(get_setting codepage bracket)
        font=$(get_setting font 3270)
        keypad=$(bool_setting keypad false)
        keymap_file=$(get_setting keymap_file '')
        keymap_name=$(get_setting keymap_name ums)
        [[ "$port" =~ ^[0-9]{1,5}$ ]] || fail 'Port must be an integer from 1 to 65535.'
        port=$((10#$port))
        ((port >= 1 && port <= 65535)) || fail 'Port must be from 1 to 65535.'
        [[ "$model" =~ ^327[89]-[2345]$ ]] || fail 'Unsupported terminal model.'
        case "$codepage" in
            cp037|cp273|cp275|cp277|cp278|cp280|cp284|cp285|cp297|cp424|cp500|cp803|cp870|cp871|cp875|cp880|cp1026|cp1047|cp1123|cp1140|cp1141|cp1142|cp1143|cp1144|cp1145|cp1146|cp1147|cp1148|cp1149|cp1158|cp1160|bracket) ;;
            *) fail 'Unsupported single-byte host code page.' ;;
        esac
        case "$font" in
            3270|3270-12|3270-12bold|3270-20|3270-20bold|3270bold|3270gr|3270gt8|3270gt12|3270gt12bold|3270gt16|3270gt16bold|3270gt24|3270gt24bold|3270gt32|3270gt32bold|3270h) ;;
            *) fail 'Selected terminal font is not bundled.' ;;
        esac
        prefix=''
        starttls=false
        case "$transport" in
            auto) starttls=true ;;
            tls) prefix='L:' ;;
            plain) ;;
            *) fail 'Invalid connection mode.' ;;
        esac
        [[ "$tn3270e" == true ]] || prefix+='N:'
        reconnect=false; once=false
        case "$disconnect" in
            stay) ;;
            reconnect) reconnect=true ;;
            exit) once=true ;;
            *) fail 'Invalid disconnect behavior.' ;;
        esac
        if [[ -z "$host" ]]; then
            [[ -z "$lu" && "$disconnect" == stay ]] || fail 'LU name and disconnect actions require a server.'
        else
            # Quote the hostname for x3270 too, so embedded colons cannot be option prefixes.
            if [[ "$host" == \[*\] ]]; then host=${host:1:${#host}-2}; fi
            if [[ "$host" == *:* ]]; then
                [[ "$host" =~ ^[0-9A-Fa-f:]+(%[A-Za-z0-9_.-]+)?$ ]] || fail 'Invalid IPv6 address. Enter only the address, without a port.'
            else
                [[ "$host" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || fail 'Enter a hostname or IP address without a protocol, port or LU prefix.'
            fi
            if [[ -n "$lu" ]]; then
                [[ "$lu" =~ ^[A-Za-z0-9_\$#.-]{1,64}$ ]] || fail 'Invalid LU name. Use a single LU without commas, spaces or @.'
                prefix+="$lu@"
            fi
        fi
        # Do not merge a user's saved session into the UMS-managed connection.
        export NOX3270PRO=1
        unset X3270PRO X3270RDB
        args=(-model "$model" -codepage "$codepage" -efont "$font" -port "$port"
              -xrm "x3270.extendedDataStream: $extended" -xrm "x3270.startTls: $starttls"
              -xrm "x3270.verifyHostCert: $verify" -xrm "x3270.reconnect: $reconnect"
              -xrm "x3270.once: $once" -xrm "x3270.keypadOn: $keypad")
        if [[ -n "$ca_file" ]]; then
            readable_file 'CA certificate file' "$ca_file"
            args+=(-cafile "$ca_file")
        fi
        if [[ -n "$keymap_file" ]]; then
            readable_file 'Keymap file' "$keymap_file"
            [[ "$keymap_name" =~ ^[A-Za-z][A-Za-z0-9_-]*$ && "$keymap_name" != base ]] || fail 'Keymap name must start with a letter, contain only letters, digits, underscores or hyphens, and not be base.'
            # X3270RDB contains resource text, not a path. Cap it below Linux's per-argument limit.
            size=$(wc -c < "$keymap_file")
            ((size > 0 && size <= 65536)) || fail 'Keymap file must contain 1 to 65536 bytes.'
            grep -Eq "^[[:space:]]*x3270[.]keymap[.]${keymap_name}[[:space:]]*:" "$keymap_file" ||
                fail "Keymap file must define x3270.keymap.${keymap_name}: (see the included example)."
            X3270RDB=$(cat -- "$keymap_file")
            export X3270RDB
            args+=(-keymap "$keymap_name")
        else
            args+=(-keymap base)
        fi
        if [[ -n "$host" ]]; then args+=("${prefix}[${host}]:${port}"); fi
        ;;
    *) fail 'Invalid configuration source. Select Local or UMS profile.' ;;
esac
# Each launch registers the private core-font directory with this X server.
xset +fp "$APP/usr/local/share/fonts/X11/misc"
xset fp rehash
exec "$APP/usr/local/bin/x3270" "${args[@]}"
