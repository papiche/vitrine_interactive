#!/bin/bash
################################################################################
# Script: clean_vitrine_posts.sh
# Description: Clean up all Nostr messages posted by UPlanet Vitrine Interactive
# Usage: ./clean_vitrine_posts.sh [--dry-run] [--force]
################################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ASTROPORT_DIR="${HOME}/.zen/Astroport.ONE"
NOSTR_GET_EVENTS="${ASTROPORT_DIR}/tools/nostr_get_events.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Options
DRY_RUN=false
FORCE=false
LIMIT=1000

################################################################################
# Usage
################################################################################
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Clean up all Nostr messages posted by UPlanet Vitrine Interactive.

OPTIONS:
    --dry-run       Show what would be deleted without actually deleting
    --force         Skip confirmation prompt (⚠️  DANGEROUS!)
    --limit N       Maximum number of events to process (default: 1000)
    -h, --help      Show this help message

EXAMPLES:
    # Preview what would be deleted
    $0 --dry-run

    # Delete with confirmation
    $0

    # Delete without confirmation (⚠️  DANGEROUS!)
    $0 --force

EOF
    exit 0
}

################################################################################
# Parse arguments
################################################################################
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --limit)
            LIMIT="$2"
            shift 2
            ;;
        -h|--help)
            usage
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}" >&2
            usage
            ;;
    esac
done

################################################################################
# Check dependencies
################################################################################
if [[ ! -f "$NOSTR_GET_EVENTS" ]]; then
    echo -e "${RED}[ERROR] nostr_get_events.sh not found at $NOSTR_GET_EVENTS${NC}"
    exit 1
fi

################################################################################
# Get captain's pubkey (who posts vitrine photos)
################################################################################
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   🧹 UPlanet Vitrine - Nostr Post Cleaner                    ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Find captain's hex pubkey
CAPTAIN_HEX=""

# Try from .current player
CURRENT_PLAYER="${HOME}/.zen/game/players/.current/.player"
if [[ -f "$CURRENT_PLAYER" ]]; then
    CAPTAIN_EMAIL=$(cat "$CURRENT_PLAYER")
    HEX_FILE="${HOME}/.zen/game/nostr/${CAPTAIN_EMAIL}/HEX"
    if [[ -f "$HEX_FILE" ]]; then
        CAPTAIN_HEX=$(cat "$HEX_FILE")
        echo -e "${GREEN}[INFO] Found captain: $CAPTAIN_EMAIL${NC}"
        echo -e "${GREEN}[INFO] Pubkey (hex): ${CAPTAIN_HEX:0:16}...${NC}"
    fi
fi

if [[ -z "$CAPTAIN_HEX" ]]; then
    echo -e "${YELLOW}[WARN] No captain pubkey found${NC}"
    echo -e "${YELLOW}[INFO] Will search for all vitrine messages by content${NC}"
fi

################################################################################
# Search for vitrine messages
################################################################################
echo ""
echo -e "${CYAN}[INFO] Searching for Vitrine messages...${NC}"

# Create temporary file for results
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# Search strategy:
# 1. Search by tag #vitrine (primary - new messages have this tag)
# 2. Fallback: search by content for legacy messages

FOUND_COUNT=0

# Method 1: Search by tag #vitrine (preferred - faster and more accurate)
echo -e "${CYAN}[INFO] Searching by tag: #vitrine${NC}"
"$NOSTR_GET_EVENTS" --kind 1 --tag-t "vitrine" --limit "$LIMIT" > "$TEMP_FILE" 2>/dev/null
TAG_COUNT=$(cat "$TEMP_FILE" | wc -l)

if [[ "$TAG_COUNT" -gt 0 ]]; then
    echo -e "${GREEN}[INFO] Found $TAG_COUNT message(s) with #vitrine tag${NC}"
    FOUND_COUNT=$TAG_COUNT
fi

# Method 2: Also search for legacy messages without tag (by content)
echo -e "${CYAN}[INFO] Searching for legacy messages (by content)...${NC}"
LEGACY_TEMP=$(mktemp)

if [[ -n "$CAPTAIN_HEX" ]]; then
    # Get captain's messages and filter by content
    "$NOSTR_GET_EVENTS" --kind 1 --author "$CAPTAIN_HEX" --limit "$LIMIT" 2>/dev/null | while read -r line; do
        # Check if content contains vitrine markers and not already found
        EVENT_ID=$(echo "$line" | grep -o '"id":"[^"]*"' | sed 's/"id":"\([^"]*\)"/\1/')
        if echo "$line" | grep -qiE "(Vitrine Interactive|photo_[0-9]{8}_[0-9]{6}\.jpg|📸 Photo from UPlanet)"; then
            # Check if not already in TAG results
            if ! grep -q "$EVENT_ID" "$TEMP_FILE" 2>/dev/null; then
                echo "$line"
            fi
        fi
    done > "$LEGACY_TEMP"
else
    # Search all messages by content
    "$NOSTR_GET_EVENTS" --kind 1 --limit "$LIMIT" 2>/dev/null | while read -r line; do
        EVENT_ID=$(echo "$line" | grep -o '"id":"[^"]*"' | sed 's/"id":"\([^"]*\)"/\1/')
        if echo "$line" | grep -qiE "(Vitrine Interactive|photo_[0-9]{8}_[0-9]{6}\.jpg|📸 Photo from UPlanet)"; then
            if ! grep -q "$EVENT_ID" "$TEMP_FILE" 2>/dev/null; then
                echo "$line"
            fi
        fi
    done > "$LEGACY_TEMP"
fi

LEGACY_COUNT=$(cat "$LEGACY_TEMP" | wc -l)
if [[ "$LEGACY_COUNT" -gt 0 ]]; then
    echo -e "${YELLOW}[INFO] Found $LEGACY_COUNT legacy message(s) without tag${NC}"
    cat "$LEGACY_TEMP" >> "$TEMP_FILE"
    FOUND_COUNT=$((FOUND_COUNT + LEGACY_COUNT))
fi
rm -f "$LEGACY_TEMP"

echo ""
echo -e "${YELLOW}[INFO] Found $FOUND_COUNT vitrine message(s)${NC}"

if [[ "$FOUND_COUNT" -eq 0 ]]; then
    echo -e "${GREEN}[INFO] No vitrine messages to clean up${NC}"
    exit 0
fi

################################################################################
# Display found messages
################################################################################
echo ""
echo -e "${CYAN}[INFO] Messages to delete:${NC}"
echo "─────────────────────────────────────────────────────────────────"

# Show first 10 messages
HEAD_COUNT=0
while IFS= read -r line; do
    if [[ $HEAD_COUNT -ge 10 ]]; then
        break
    fi
    
    if command -v jq &> /dev/null; then
        EVENT_ID=$(echo "$line" | jq -r '.id // "unknown"' 2>/dev/null)
        CONTENT=$(echo "$line" | jq -r '.content // ""' 2>/dev/null | head -c 60)
        CREATED=$(echo "$line" | jq -r '.created_at // 0' 2>/dev/null)
        if [[ "$CREATED" != "0" ]]; then
            DATE=$(date -d "@$CREATED" "+%Y-%m-%d %H:%M" 2>/dev/null || echo "unknown")
        else
            DATE="unknown"
        fi
    else
        EVENT_ID=$(echo "$line" | grep -o '"id":"[^"]*"' | sed 's/"id":"\([^"]*\)"/\1/' | head -c 16)
        CONTENT=$(echo "$line" | grep -o '"content":"[^"]*"' | sed 's/"content":"\([^"]*\)"/\1/' | head -c 60)
        DATE="?"
    fi
    
    echo -e "  ${YELLOW}ID:${NC} ${EVENT_ID:0:16}..."
    echo -e "  ${YELLOW}Date:${NC} $DATE"
    echo -e "  ${YELLOW}Content:${NC} ${CONTENT}..."
    echo "  ─────────────────────────────────────────"
    
    ((HEAD_COUNT++))
done < "$TEMP_FILE"

if [[ "$FOUND_COUNT" -gt 10 ]]; then
    echo -e "  ${YELLOW}... and $((FOUND_COUNT - 10)) more messages${NC}"
fi

echo ""

################################################################################
# Dry run mode
################################################################################
if [[ "$DRY_RUN" == "true" ]]; then
    echo -e "${CYAN}[DRY-RUN] Would delete $FOUND_COUNT message(s)${NC}"
    echo -e "${CYAN}[DRY-RUN] Run without --dry-run to actually delete${NC}"
    exit 0
fi

################################################################################
# Confirmation
################################################################################
if [[ "$FORCE" != "true" ]]; then
    echo -e "${RED}⚠️  WARNING: This will permanently delete $FOUND_COUNT message(s)!${NC}"
    echo -e "${RED}⚠️  This action CANNOT be undone!${NC}"
    echo ""
    echo -n "Type 'DELETE' to confirm: "
    read -r CONFIRM
    
    if [[ "$CONFIRM" != "DELETE" ]]; then
        echo -e "${YELLOW}[INFO] Deletion cancelled${NC}"
        exit 0
    fi
fi

################################################################################
# Delete messages
################################################################################
echo ""
echo -e "${CYAN}[INFO] Deleting $FOUND_COUNT message(s)...${NC}"

# Extract event IDs and delete one by one
DELETED=0
FAILED=0

while IFS= read -r line; do
    if command -v jq &> /dev/null; then
        EVENT_ID=$(echo "$line" | jq -r '.id // ""' 2>/dev/null)
    else
        EVENT_ID=$(echo "$line" | grep -o '"id":"[^"]*"' | sed 's/"id":"\([^"]*\)"/\1/')
    fi
    
    if [[ -z "$EVENT_ID" || "$EVENT_ID" == "null" ]]; then
        continue
    fi
    
    # Delete using strfry directly
    STRFRY_DIR="$HOME/.zen/strfry"
    if [[ -f "${STRFRY_DIR}/strfry" ]]; then
        cd "$STRFRY_DIR"
        DELETE_FILTER="{\"ids\":[\"$EVENT_ID\"]}"
        if ./strfry delete --filter="$DELETE_FILTER" >/dev/null 2>&1; then
            ((DELETED++))
            echo -e "  ${GREEN}✓${NC} Deleted: ${EVENT_ID:0:16}..."
        else
            ((FAILED++))
            echo -e "  ${RED}✗${NC} Failed: ${EVENT_ID:0:16}..."
        fi
        cd - >/dev/null
    fi
done < "$TEMP_FILE"

################################################################################
# Summary
################################################################################
echo ""
echo -e "${CYAN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   📊 Cleanup Summary                                         ║${NC}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GREEN}✓ Deleted:${NC} $DELETED message(s)"
echo -e "  ${RED}✗ Failed:${NC}  $FAILED message(s)"
echo -e "  ${YELLOW}Total:${NC}    $FOUND_COUNT message(s)"
echo ""

if [[ "$FAILED" -eq 0 ]]; then
    echo -e "${GREEN}[OK] Cleanup completed successfully!${NC}"
else
    echo -e "${YELLOW}[WARN] Some messages could not be deleted${NC}"
fi

exit 0

