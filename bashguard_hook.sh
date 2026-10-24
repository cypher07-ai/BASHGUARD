#!/bin/bash
# ============================================================
#  BashGuard — Linux/Mac Terminal Hook
#  Intercepts dangerous commands BEFORE they execute.
#
#  USAGE:
#    1. Start server:   python3 server.py
#    2. Load hook:      source ./bashguard_hook.sh
#    3. Type commands — BashGuard watches everything
#    4. To disable:     bashguard-off
# ============================================================

BASHGUARD_ENABLED=true
BASHGUARD_SERVER="http://localhost:8000"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ── BLOCK LIST — Permanently blocked commands ──
BLOCKLIST=(
    "rm -rf /"
    "rm -rf /*"
    "rm -rf ~"
    "dd if=/dev/zero"
    "dd if=/dev/random"
    ":(){:|:&};:"
    "> /dev/sda"
    "mkfs.ext4 /dev/sda"
    "mkfs.ext4 /dev/sdb"
    "format c:"
    "shutdown -h now"
    "halt"
    "init 0"
)

# ── DANGEROUS KEYWORDS ──
DANGEROUS_KEYWORDS=(
    "rm " "rmdir" "unlink"
    "chmod " "chown " "chgrp "
    "kill " "killall " "pkill "
    "dd if=" "mkfs"
    "git push -f" "git push --force"
    "DROP " "DELETE FROM" "TRUNCATE "
    "curl|bash" "curl|sh" "wget|sh"
    "mv /" "cp /dev/"
    "iptables -F" "ufw disable"
    "passwd" "useradd" "userdel"
    "npm publish"
    "docker rm" "docker rmi" "docker system prune"
    "systemctl stop" "service stop"
    "reboot" "shutdown"
)

# ── SAFE COMMANDS — Skip these ──
SAFE_COMMANDS=(
    "ls" "ll" "la" "dir"
    "cat" "less" "more" "head" "tail"
    "echo" "printf"
    "pwd" "cd" "pushd" "popd"
    "clear" "cls"
    "whoami" "hostname" "date" "uptime"
    "history" "which" "whereis" "type"
    "man" "help" "info"
    "git status" "git log" "git branch" "git diff"
    "python --version" "python3 --version" "node --version"
    "pip list" "pip3 list" "npm list"
    "top" "htop" "ps" "df" "du" "free"
    "grep" "find" "wc" "sort" "uniq"
    "code" "vim" "nano" "vi"
    "bashguard"
)

# ── Helper: Check if command is safe ──
is_safe_command() {
    local cmd_lower
    cmd_lower=$(echo "$1" | tr '[:upper:]' '[:lower:]' | xargs)
    for safe in "${SAFE_COMMANDS[@]}"; do
        if [[ "$cmd_lower" == "$safe"* ]]; then
            return 0
        fi
    done
    return 1
}

# ── Helper: Check if command is hard-blocked ──
is_hard_blocked() {
    local cmd_lower
    cmd_lower=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    for blocked in "${BLOCKLIST[@]}"; do
        blocked_lower=$(echo "$blocked" | tr '[:upper:]' '[:lower:]')
        if [[ "$cmd_lower" == *"$blocked_lower"* ]]; then
            return 0
        fi
    done
    return 1
}

# ── Helper: Check if command has dangerous keywords ──
has_dangerous_keyword() {
    local cmd_lower
    cmd_lower=$(echo "$1" | tr '[:upper:]' '[:lower:]')
    for keyword in "${DANGEROUS_KEYWORDS[@]}"; do
        keyword_lower=$(echo "$keyword" | tr '[:upper:]' '[:lower:]')
        if [[ "$cmd_lower" == *"$keyword_lower"* ]]; then
            return 0
        fi
    done
    return 1
}

# ── Helper: Call BashGuard API ──
call_bashguard_api() {
    local cmd="$1"
    local json_cmd
    json_cmd=$(echo "$cmd" | python3 -c "import sys,json; print(json.dumps(sys.stdin.read().strip()))")
    local response
    response=$(curl -s --max-time 15 -X POST "${BASHGUARD_SERVER}/simulate" \
        -H "Content-Type: application/json" \
        -d "{\"command\": $json_cmd}" 2>/dev/null)
    echo "$response"
}

# ── Helper: Parse JSON field ──
json_get() {
    echo "$1" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    val = data.get('$2', '')
    if isinstance(val, list):
        print('\n'.join(str(x) for x in val))
    else:
        print(val)
except:
    print('')
" 2>/dev/null
}

# ── Show warning ──
show_warning() {
    local response="$1"
    local risk_level risk_score is_reversible safer_command

    risk_level=$(json_get "$response" "risk_level")
    risk_score=$(json_get "$response" "risk_score")
    is_reversible=$(json_get "$response" "is_reversible")
    safer_command=$(json_get "$response" "safer_command")
    planned_cmd=$(json_get "$response" "planned_command")

    local risk_color="$WHITE"
    case "$risk_level" in
        CRITICAL|HIGH) risk_color="$RED" ;;
        MEDIUM) risk_color="$YELLOW" ;;
        *) risk_color="$GREEN" ;;
    esac

    local undo_text="Possible"
    local undo_color="$GREEN"
    if [[ "$is_reversible" == "False" || "$is_reversible" == "false" ]]; then
        undo_text="IMPOSSIBLE"
        undo_color="$RED"
    fi

    echo ""
    echo -e "  ${CYAN}========== BASHGUARD - COMMAND INTERCEPTED ==========${NC}"
    echo ""
    echo -e "  ${WHITE}Command: ${planned_cmd}${NC}"
    echo -e "  ${risk_color}Risk:    ${risk_level} (${risk_score}/100)${NC}"
    echo -e "  ${undo_color}Undo:    ${undo_text}${NC}"
    echo ""

    # Show risk reasons
    local reasons
    reasons=$(json_get "$response" "risk_reasons")
    if [[ -n "$reasons" ]]; then
        echo -e "  ${YELLOW}Why this is risky:${NC}"
        local i=1
        while IFS= read -r reason; do
            [[ -n "$reason" ]] && echo -e "    ${YELLOW}${i}. ${reason}${NC}"
            ((i++))
        done <<< "$reasons"
        echo ""
    fi

    # Show safer alternative
    if [[ -n "$safer_command" && "$safer_command" != "None" && "$safer_command" != "" ]]; then
        echo -e "  ${GREEN}Safer alternative: ${safer_command}${NC}"
        echo ""
    fi

    echo -e "  ${CYAN}=====================================================${NC}"
}

# ── THE MAIN HOOK — preexec function ──
bashguard_preexec() {
    [[ "$BASHGUARD_ENABLED" != "true" ]] && return 0

    local cmd="$1"

    # Skip empty
    [[ -z "$cmd" || "$cmd" =~ ^[[:space:]]*$ ]] && return 0

    # Skip safe commands
    if is_safe_command "$cmd"; then
        return 0
    fi

    # Hard-blocked — STOP
    if is_hard_blocked "$cmd"; then
        echo ""
        echo -e "  ${RED}========== BASHGUARD - BLOCKED ==========${NC}"
        echo -e "  ${RED}This command is PERMANENTLY BLOCKED.${NC}"
        echo -e "  ${WHITE}Command: ${cmd}${NC}"
        echo -e "  ${RED}=========================================${NC}"
        echo ""
        return 1
    fi

    # Has dangerous keyword — full simulation
    if has_dangerous_keyword "$cmd"; then
        echo ""
        echo -e "  ${CYAN}[BashGuard] Dangerous command detected. Simulating...${NC}"

        local response
        response=$(call_bashguard_api "$cmd")

        if [[ -z "$response" || "$response" == "" ]]; then
            echo -e "  ${YELLOW}[BashGuard] Server offline. Allow command? (y/n): ${NC}"
            read -r choice
            [[ "$choice" == "y" ]] && return 0 || return 1
        fi

        local risk_level
        risk_level=$(json_get "$response" "risk_level")

        if [[ "$risk_level" == "CRITICAL" || "$risk_level" == "HIGH" || "$risk_level" == "MEDIUM" ]]; then
            show_warning "$response"

            local safer_command
            safer_command=$(json_get "$response" "safer_command")

            if [[ -n "$safer_command" && "$safer_command" != "None" && "$safer_command" != "" ]]; then
                echo -ne "  ${WHITE}[A]pprove  [S]afer  [C]ancel: ${NC}"
            else
                echo -ne "  ${WHITE}[A]pprove  [C]ancel: ${NC}"
            fi
            read -r choice

            case "${choice,,}" in
                a|approve|y|yes)
                    echo -e "  ${GREEN}[BashGuard] Approved.${NC}"
                    return 0
                    ;;
                s|safer|safe)
                    if [[ -n "$safer_command" && "$safer_command" != "None" ]]; then
                        echo -e "  ${GREEN}[BashGuard] Running safer command: ${safer_command}${NC}"
                        eval "$safer_command"
                        return 1  # Don't run original
                    else
                        echo -e "  ${YELLOW}[BashGuard] No safer option. Cancelled.${NC}"
                        return 1
                    fi
                    ;;
                *)
                    echo -e "  ${RED}[BashGuard] CANCELLED.${NC}"
                    return 1
                    ;;
            esac
        fi

        echo -e "  ${GREEN}[BashGuard] LOW risk. Proceeding.${NC}"
    fi

    return 0
}

# ── Install the hook using DEBUG trap ──
bashguard_trap() {
    # Get the command about to execute
    local cmd="$BASH_COMMAND"

    # Skip if we're inside the hook itself
    [[ "$BASHGUARD_INSIDE_HOOK" == "true" ]] && return

    # Skip the prompt command
    [[ "$cmd" == "$PROMPT_COMMAND" ]] && return

    # Mark we're inside the hook
    BASHGUARD_INSIDE_HOOK=true

    if ! bashguard_preexec "$cmd"; then
        BASHGUARD_INSIDE_HOOK=false
        # Kill the command by returning from the trap
        return 1 2>/dev/null || true
    fi

    BASHGUARD_INSIDE_HOOK=false
}

# ── Control functions ──
bashguard-off() {
    BASHGUARD_ENABLED=false
    echo -e "  ${YELLOW}[BashGuard] DISABLED.${NC}"
}

bashguard-on() {
    BASHGUARD_ENABLED=true
    echo -e "  ${GREEN}[BashGuard] ENABLED.${NC}"
}

bashguard-status() {
    if [[ "$BASHGUARD_ENABLED" == "true" ]]; then
        echo -e "  ${GREEN}BashGuard: ACTIVE${NC}"
    else
        echo -e "  ${RED}BashGuard: DISABLED${NC}"
    fi

    if curl -s --max-time 3 "${BASHGUARD_SERVER}/" > /dev/null 2>&1; then
        echo -e "  ${GREEN}Server: RUNNING${NC}"
    else
        echo -e "  ${RED}Server: OFFLINE${NC}"
    fi
}

# ── Activate the hook ──
trap 'bashguard_trap' DEBUG

# ── Banner ──
echo ""
echo -e "  ${CYAN}========== BashGuard - Terminal Protection ==========${NC}"
echo -e "  ${GREEN}Status: ACTIVE${NC}"
echo -e "  ${WHITE}Every command is checked before execution.${NC}"
echo -e "  ${WHITE}Platform: Linux/Mac (bash hook)${NC}"
echo -e "  ${GRAY}Type 'bashguard-off' to disable.${NC}"
echo -e "  ${CYAN}=====================================================${NC}"
echo ""
