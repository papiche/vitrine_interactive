#!/usr/bin/env bash
# Manage .env for Vitrine Interactive
# Usage: ./manage_env.sh <command> [args]
#   init              Create .env from .env.template if missing
#   show              Print current .env (excluding comments/empties)
#   list              List variable names from .env.template
#   get <KEY>         Print value of KEY
#   set <KEY> <VAL>   Set KEY=VAL in .env (creates .env if needed)
#   unset <KEY>       Remove KEY from .env
#   validate          Check .env has expected keys and valid types

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$SCRIPT_DIR/.env"
TEMPLATE_FILE="$SCRIPT_DIR/.env.template"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

usage() {
    echo "Usage: $0 <command> [args]"
    echo "  init              Create .env from .env.template if missing"
    echo "  show              Print current .env (key=value)"
    echo "  list              List variable names from .env.template"
    echo "  get <KEY>         Print value of KEY"
    echo "  set <KEY> <VAL>   Set KEY=VAL in .env"
    echo "  unset <KEY>       Remove KEY from .env"
    echo "  validate          Check .env has expected keys and valid types"
}

cmd_init() {
    if [[ -f "$ENV_FILE" ]]; then
        echo -e "${YELLOW}.env already exists. Use 'show' to view.${NC}"
        return 0
    fi
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        echo -e "${RED}.env.template not found.${NC}" >&2
        return 1
    fi
    cp "$TEMPLATE_FILE" "$ENV_FILE"
    echo -e "${GREEN}Created .env from .env.template${NC}"
}

cmd_show() {
    if [[ ! -f "$ENV_FILE" ]]; then
        echo -e "${YELLOW}No .env file. Run: $0 init${NC}"
        return 0
    fi
    grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ENV_FILE" | sort
}

cmd_list() {
    if [[ ! -f "$TEMPLATE_FILE" ]]; then
        echo -e "${RED}.env.template not found.${NC}" >&2
        return 1
    fi
    grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$TEMPLATE_FILE" | sed 's/=.*//' | sort -u
}

cmd_get() {
    local key="$1"
    if [[ -z "$key" ]]; then
        echo "Usage: $0 get <KEY>" >&2
        return 1
    fi
    if [[ ! -f "$ENV_FILE" ]]; then
        echo -e "${YELLOW}No .env file.${NC}" >&2
        return 1
    fi
    local line
    line=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null || true)
    if [[ -n "$line" ]]; then
        echo "${line#*=}"
    else
        echo -e "${YELLOW}Key not set.${NC}" >&2
        return 1
    fi
}

cmd_set() {
    local key="$1"
    local val="$2"
    if [[ -z "$key" ]]; then
        echo "Usage: $0 set <KEY> <VALUE>" >&2
        return 1
    fi
    if [[ ! -f "$ENV_FILE" ]]; then
        cmd_init
    fi
    if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
        if [[ -n "$val" ]]; then
            sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
        else
            sed -i "/^${key}=/d" "$ENV_FILE"
        fi
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
    echo -e "${GREEN}Set ${key}=${val}${NC}"
}

cmd_unset() {
    local key="$1"
    if [[ -z "$key" ]]; then
        echo "Usage: $0 unset <KEY>" >&2
        return 1
    fi
    if [[ ! -f "$ENV_FILE" ]]; then
        return 0
    fi
    if grep -qE "^${key}=" "$ENV_FILE" 2>/dev/null; then
        sed -i "/^${key}=/d" "$ENV_FILE"
        echo -e "${GREEN}Unset ${key}${NC}"
    else
        echo -e "${YELLOW}Key not found.${NC}"
    fi
}

cmd_validate() {
    local ok=0
    if [[ ! -f "$ENV_FILE" ]]; then
        echo -e "${YELLOW}No .env file. Run: $0 init${NC}"
        return 0
    fi
    # Expected numeric (float/int) keys
    local float_keys="VITRINE_ZONE_LEFT VITRINE_ZONE_RIGHT VITRINE_ZONE_CENTER_LEFT VITRINE_ZONE_CENTER_RIGHT VITRINE_SWIPE_COOLDOWN VITRINE_THUMBS_UP_HOLD_TIME VITRINE_OPEN_HAND_HOLD_TIME VITRINE_DARK_MODE_TIMEOUT VITRINE_FACE_MATCH_THRESHOLD"
    local int_keys="VITRINE_QR_DISPLAY_TIME VITRINE_MIN_FACE_SIZE"
    for key in $float_keys; do
        local val
        val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | sed 's/.*=//' || true)
        if [[ -n "$val" ]]; then
            if ! [[ "$val" =~ ^[0-9]+\.?[0-9]*$ ]]; then
                echo -e "${RED}${key}: invalid number '${val}'${NC}"
                ok=1
            fi
        fi
    done
    for key in $int_keys; do
        local val
        val=$(grep -E "^${key}=" "$ENV_FILE" 2>/dev/null | sed 's/.*=//' || true)
        if [[ -n "$val" ]]; then
            if ! [[ "$val" =~ ^[0-9]+$ ]]; then
                echo -e "${RED}${key}: invalid integer '${val}'${NC}"
                ok=1
            fi
        fi
    done
    if [[ $ok -eq 0 ]]; then
        echo -e "${GREEN}Validation OK.${NC}"
    fi
    return $ok
}

case "${1:-}" in
    init)   cmd_init ;;
    show)   cmd_show ;;
    list)   cmd_list ;;
    get)    cmd_get "$2" "$3" ;;
    set)    cmd_set "$2" "$3" ;;
    unset)  cmd_unset "$2" ;;
    validate) cmd_validate ;;
    -h|--help|help|"") usage ;;
    *)
        echo "Unknown command: $1" >&2
        usage
        exit 1
        ;;
esac
