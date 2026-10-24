#!/bin/bash
# ============================================================
#  BashGuard — Linux/Mac Terminal Hook
#  Works by overriding dangerous commands as bash functions.
#  This is the RELIABLE approach — no DEBUG trap hackery.
#
#  USAGE:
#    source ./bashguard_hook.sh
# ============================================================

BASHGUARD_ENABLED=true
BASHGUARD_SERVER="http://localhost:8000"

# Colors
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; WHITE='\033[1;37m'; GRAY='\033[0;90m'; NC='\033[0m'

# ── Core: Ask user before running a command ──
_bg_ask() {
    local cmd_display="$1"   # what to show the user
    local cmd_run="$2"       # actual command+args to run if approved
    shift 2
    local args=("$@")        # remaining args

    echo "" >&2
    echo -e "  ${CYAN}======== BASHGUARD - COMMAND INTERCEPTED ========${NC}" >&2
    echo -e "  ${WHITE}Command: ${cmd_display}${NC}" >&2
    echo "" >&2

    # Try to call simulate API for richer info
    local sim
    sim=$(echo "$cmd_display" | python3 -c "
import sys, json, urllib.request
cmd = sys.stdin.read().strip()
try:
    data = json.dumps({'command': cmd}).encode()
    req = urllib.request.Request('${BASHGUARD_SERVER}/simulate',
        data=data, headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req, timeout=8)
    d = json.loads(res.read())
    print(f\"  Risk:    {d.get('risk_level','?')} ({d.get('risk_score','?')}/100)\")
    rev = 'YES' if d.get('is_reversible') else 'NO - IRREVERSIBLE'
    print(f\"  Undo:    {rev}\")
    reasons = d.get('risk_reasons', [])
    if reasons:
        print(f\"  Reasons: {reasons[0]}\")
    safer = d.get('safer_command', '')
    if safer and safer != 'None':
        print(f\"  Safer:   {safer}\")
        print(f\"  __SAFER__{safer}\")
except Exception as e:
    print(f\"  [Server offline — showing basic warning]\")
" 2>/dev/null)

    # Print simulation info
    echo "$sim" | grep -v "^  __SAFER__" >&2

    # Extract safer command if present
    local safer
    safer=$(echo "$sim" | grep "^  __SAFER__" | sed 's/^  __SAFER__//')

    echo "" >&2

    if [[ -n "$safer" ]]; then
        echo -ne "  ${WHITE}[A]pprove  [S]afer alternative  [C]ancel: ${NC}" >&2
    else
        echo -ne "  ${WHITE}[A]pprove  [C]ancel: ${NC}" >&2
    fi

    local choice
    read -r choice

    case "${choice,,}" in
        a|approve|y|yes)
            echo -e "  ${GREEN}[BashGuard] Approved.${NC}" >&2
            echo -e "  ${CYAN}=================================================${NC}" >&2
            # Run the real command
            command $cmd_run "${args[@]}"
            ;;
        s|safer|safe)
            if [[ -n "$safer" ]]; then
                echo -e "  ${GREEN}[BashGuard] Running safer: ${safer}${NC}" >&2
                echo -e "  ${CYAN}=================================================${NC}" >&2
                eval "$safer"
            else
                echo -e "  ${YELLOW}[BashGuard] No safer option. Cancelled.${NC}" >&2
                echo -e "  ${CYAN}=================================================${NC}" >&2
            fi
            ;;
        *)
            echo -e "  ${RED}[BashGuard] CANCELLED. Nothing ran.${NC}" >&2
            echo -e "  ${CYAN}=================================================${NC}" >&2
            ;;
    esac
    echo "" >&2
}

# ── Core: Hard block (no questions asked) ──
_bg_block() {
    local cmd="$1"
    echo "" >&2
    echo -e "  ${RED}======== BASHGUARD - PERMANENTLY BLOCKED ========${NC}" >&2
    echo -e "  ${RED}This command CANNOT be run under any circumstances.${NC}" >&2
    echo -e "  ${WHITE}Command: ${cmd}${NC}" >&2
    echo -e "  ${RED}=================================================${NC}" >&2
    echo "" >&2
}

# ============================================================
#  OVERRIDE DANGEROUS COMMANDS
# ============================================================

# ── rm ──
rm() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command rm "$@"; return; }
    local full_cmd="rm $*"
    local full_lower="${full_cmd,,}"

    # Hard block: rm -rf / or rm -rf ~ or rm -rf /*
    if [[ "$full_lower" == *"rm -rf /"* ]] || \
       [[ "$full_lower" == *"rm -rf ~"* ]] || \
       [[ "$full_lower" == *"rm -rf /*"* ]]; then
        _bg_block "$full_cmd"
        return 1
    fi

    # Warn on recursive or force delete
    if [[ "$*" == *"-r"* ]] || [[ "$*" == *"-f"* ]]; then
        _bg_ask "$full_cmd" "rm" "$@"
    else
        # Single file delete — still ask
        _bg_ask "$full_cmd" "rm" "$@"
    fi
}

# ── chmod ──
chmod() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command chmod "$@"; return; }
    _bg_ask "chmod $*" "chmod" "$@"
}

# ── chown ──
chown() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command chown "$@"; return; }
    _bg_ask "chown $*" "chown" "$@"
}

# ── kill ──
kill() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command kill "$@"; return; }
    _bg_ask "kill $*" "kill" "$@"
}

# ── killall ──
killall() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command killall "$@"; return; }
    _bg_ask "killall $*" "killall" "$@"
}

# ── pkill ──
pkill() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command pkill "$@"; return; }
    _bg_ask "pkill $*" "pkill" "$@"
}

# ── dd ──
dd() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command dd "$@"; return; }
    local full_cmd="dd $*"
    # Hard block dd to /dev/sda or /dev/zero on whole disk
    if [[ "$*" == *"/dev/sda"* ]] || [[ "$*" == *"of=/dev/sd"* ]]; then
        _bg_block "$full_cmd"
        return 1
    fi
    _bg_ask "$full_cmd" "dd" "$@"
}

# ── mkfs ──
mkfs() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command mkfs "$@"; return; }
    _bg_block "mkfs $*"
    return 1
}

# ── shutdown ──
shutdown() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command shutdown "$@"; return; }
    _bg_ask "shutdown $*" "shutdown" "$@"
}

# ── reboot ──
reboot() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command reboot "$@"; return; }
    _bg_ask "reboot $*" "reboot" "$@"
}

# ── git — intercept force push ──
git() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command git "$@"; return; }
    local full_cmd="git $*"

    if [[ "$*" == *"push"* ]] && { [[ "$*" == *"--force"* ]] || [[ "$*" == *" -f"* ]]; }; then
        _bg_ask "$full_cmd" "git" "$@"
    else
        command git "$@"
    fi
}

# ── mv — warn on moving to /dev/null or system paths ──
mv() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command mv "$@"; return; }
    local full_cmd="mv $*"

    if [[ "$*" == *"/dev/null"* ]] || [[ "$*" == *"/ "* ]]; then
        _bg_ask "$full_cmd" "mv" "$@"
    else
        command mv "$@"
    fi
}

# ── wget/curl piped to shell ──
# These can't be easily overridden for pipes, but we catch common forms:
curl() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command curl "$@"; return; }
    # curl ... | bash  — can't fully catch the pipe but warn on suspicious URLs
    command curl "$@"
}

# ── systemctl stop/disable ──
systemctl() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command systemctl "$@"; return; }
    local full_cmd="systemctl $*"

    if [[ "$1" == "stop" ]] || [[ "$1" == "disable" ]] || \
       [[ "$1" == "mask" ]] || [[ "$1" == "poweroff" ]]; then
        _bg_ask "$full_cmd" "systemctl" "$@"
    else
        command systemctl "$@"
    fi
}

# ── service stop ──
service() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command service "$@"; return; }
    local full_cmd="service $*"

    if [[ "$2" == "stop" ]] || [[ "$2" == "restart" ]]; then
        _bg_ask "$full_cmd" "service" "$@"
    else
        command service "$@"
    fi
}

# ── docker destructive ops ──
docker() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command docker "$@"; return; }
    local full_cmd="docker $*"

    if [[ "$1" == "rm" ]] || [[ "$1" == "rmi" ]] || \
       [[ "$1 $2" == "system prune" ]] || [[ "$1 $2" == "container prune" ]]; then
        _bg_ask "$full_cmd" "docker" "$@"
    else
        command docker "$@"
    fi
}

# ── passwd ──
passwd() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command passwd "$@"; return; }
    _bg_ask "passwd $*" "passwd" "$@"
}

# ── userdel ──
userdel() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && { command userdel "$@"; return; }
    _bg_ask "userdel $*" "userdel" "$@"
}

# ============================================================
#  CONTROL FUNCTIONS
# ============================================================

bashguard-off() {
    BASHGUARD_ENABLED=false
    echo -e "${YELLOW}[BashGuard] DISABLED. Commands run without interception.${NC}"
}

bashguard-on() {
    BASHGUARD_ENABLED=true
    echo -e "${GREEN}[BashGuard] ENABLED.${NC}"
}

bashguard-status() {
    if [[ "$BASHGUARD_ENABLED" == "true" ]]; then
        echo -e "  ${GREEN}BashGuard: ACTIVE${NC}"
    else
        echo -e "  ${RED}BashGuard: DISABLED${NC}"
    fi
    if curl -s --max-time 3 "${BASHGUARD_SERVER}/" >/dev/null 2>&1; then
        echo -e "  ${GREEN}Server:    RUNNING at ${BASHGUARD_SERVER}${NC}"
    else
        echo -e "  ${RED}Server:    OFFLINE — start with: python3 server.py${NC}"
    fi
    echo -e "  ${WHITE}Watching:  rm, chmod, chown, kill, killall, pkill, dd, mkfs,"
    echo -e "             git push --force, shutdown, reboot, systemctl, docker${NC}"
}

# ── Banner ──
echo ""
echo -e "  ${CYAN}======== BashGuard - Terminal Protection ========${NC}"
echo -e "  ${GREEN}Status:   ACTIVE${NC}"
echo -e "  ${WHITE}Method:   Command override (rm, chmod, kill, git, ...)${NC}"
echo -e "  ${WHITE}Every dangerous command asks before running.${NC}"
echo -e "  ${GRAY}Type 'bashguard-off' to disable, 'bashguard-status' to check.${NC}"
echo -e "  ${CYAN}=================================================${NC}"
echo ""
