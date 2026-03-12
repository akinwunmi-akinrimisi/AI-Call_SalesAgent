#!/bin/bash
# ============================================================
# skills.sh — Cloudboosta AI Sales Agent
# Environment Validation & Setup Checker
# ============================================================
# Run this before starting any build phase.
# It checks that all prerequisites, tools, and credentials
# are properly configured.
#
# Usage: bash skills.sh
# ============================================================

set -uo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

PASS=0
FAIL=0
WARN=0

check_pass() { echo -e "  ${GREEN}✓${NC} $1"; PASS=$((PASS+1)); }
check_fail() { echo -e "  ${RED}✗${NC} $1"; FAIL=$((FAIL+1)); }
check_warn() { echo -e "  ${YELLOW}⚠${NC} $1"; WARN=$((WARN+1)); }

echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  CLOUDBOOSTA AI SALES AGENT${NC}"
echo -e "${BOLD}  Environment Validation${NC}"
echo -e "${BOLD}============================================${NC}"
echo ""

# ============================================================
# CHECK 1: Required CLI Tools
# ============================================================
echo -e "${BLUE}[1/9] CLI Tools${NC}"

if command -v gcloud &>/dev/null; then
    check_pass "gcloud CLI installed ($(gcloud --version 2>/dev/null | head -1))"
else
    check_fail "gcloud CLI not installed. Run: curl https://sdk.cloud.google.com | bash"
fi

if command -v docker &>/dev/null; then
    check_pass "Docker installed ($(docker --version 2>/dev/null | cut -d' ' -f3 | tr -d ','))"
else
    check_fail "Docker not installed. Visit: https://docs.docker.com/get-docker/"
fi

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1 | cut -d' ' -f2)
    check_pass "Python 3 installed ($PY_VER)"
else
    check_fail "Python 3 not installed"
fi

if command -v node &>/dev/null; then
    NODE_VER=$(node --version 2>&1)
    check_pass "Node.js installed ($NODE_VER)"
else
    check_fail "Node.js not installed"
fi

if command -v npm &>/dev/null; then
    check_pass "npm installed ($(npm --version 2>&1))"
else
    check_fail "npm not installed"
fi

# ============================================================
# CHECK 2: GCP Configuration
# ============================================================
echo ""
echo -e "${BLUE}[2/9] Google Cloud Configuration${NC}"

GCP_PROJECT=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -n "$GCP_PROJECT" ]; then
    check_pass "GCP project set: $GCP_PROJECT"
else
    check_fail "No GCP project set. Run: gcloud config set project vision-gridai"
fi

GCP_REGION=$(gcloud config get-value run/region 2>/dev/null || echo "")
if [ -n "$GCP_REGION" ]; then
    check_pass "Cloud Run region set: $GCP_REGION"
else
    check_warn "Cloud Run region not set. Run: gcloud config set run/region europe-west1"
fi

# Check required APIs
for API in aiplatform.googleapis.com run.googleapis.com firestore.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com; do
    if gcloud services list --enabled --filter="name:$API" --format="value(name)" 2>/dev/null | grep -q "$API"; then
        check_pass "API enabled: $API"
    else
        check_fail "API not enabled: $API. Run: gcloud services enable $API"
    fi
done

# ============================================================
# CHECK 3: Environment Variables (.env file)
# ============================================================
echo ""
echo -e "${BLUE}[3/9] Environment Variables${NC}"

if [ -f ".env" ]; then
    check_pass ".env file exists"
    source .env 2>/dev/null || true

    [ -n "${GCP_PROJECT_ID:-}" ] && check_pass "GCP_PROJECT_ID set" || check_fail "GCP_PROJECT_ID missing in .env"
    [ -n "${TWILIO_ACCOUNT_SID:-}" ] && check_pass "TWILIO_ACCOUNT_SID set" || check_fail "TWILIO_ACCOUNT_SID missing in .env"
    [ -n "${TWILIO_AUTH_TOKEN:-}" ] && check_pass "TWILIO_AUTH_TOKEN set" || check_fail "TWILIO_AUTH_TOKEN missing in .env"
    [ -n "${TWILIO_PHONE_NUMBER:-}" ] && check_pass "TWILIO_PHONE_NUMBER set" || check_fail "TWILIO_PHONE_NUMBER missing in .env"
    [ -n "${SUPABASE_URL:-}" ] && check_pass "SUPABASE_URL set" || check_fail "SUPABASE_URL missing in .env"
    [ -n "${SUPABASE_SERVICE_KEY:-}" ] && check_pass "SUPABASE_SERVICE_KEY set" || check_fail "SUPABASE_SERVICE_KEY missing in .env"
    [ -n "${ADMIN_EMAIL:-}" ] && check_pass "ADMIN_EMAIL set" || check_fail "ADMIN_EMAIL missing in .env"
    [ -n "${OPENCLAW_API_URL:-}" ] && check_pass "OPENCLAW_API_URL set" || check_warn "OPENCLAW_API_URL missing — needed for WhatsApp outreach"
else
    check_fail ".env file not found. Copy from .env.example and fill in values."
fi

# ============================================================
# CHECK 4: .gitignore
# ============================================================
echo ""
echo -e "${BLUE}[4/9] Git Safety${NC}"

if [ -f ".gitignore" ]; then
    if grep -q ".env" .gitignore 2>/dev/null; then
        check_pass ".env is in .gitignore"
    else
        check_fail ".env is NOT in .gitignore — SECURITY RISK. Add it immediately."
    fi
else
    check_fail ".gitignore does not exist. Create one with at minimum: .env, node_modules/, __pycache__/, .planning/"
fi

# ============================================================
# CHECK 5: Project Structure
# ============================================================
echo ""
echo -e "${BLUE}[5/9] Project Structure${NC}"

for DIR in backend frontend scripts knowledge-base directives docs; do
    [ -d "$DIR" ] && check_pass "Directory exists: $DIR/" || check_warn "Directory missing: $DIR/ — create with: mkdir -p $DIR"
done

for FILE in AGENT.md CLAUDE.md skills.md; do
    [ -f "$FILE" ] && check_pass "File exists: $FILE" || check_fail "File missing: $FILE"
done

# ============================================================
# CHECK 6: Knowledge Base PDFs
# ============================================================
echo ""
echo -e "${BLUE}[6/9] Knowledge Base Documents${NC}"

for PDF in programmes.pdf faqs.pdf payment-details.pdf conversation-sequence.pdf objection-handling.pdf; do
    if [ -f "knowledge-base/$PDF" ]; then
        check_pass "PDF exists: knowledge-base/$PDF"
    else
        check_fail "PDF missing: knowledge-base/$PDF — Sarah cannot sell without this."
    fi
done

# ============================================================
# CHECK 7: GSD Installation
# ============================================================
echo ""
echo -e "${BLUE}[7/9] GSD (Get Shit Done)${NC}"

if [ -d "$HOME/.claude/get-shit-done" ] || [ -d ".claude/commands" ]; then
    check_pass "GSD appears to be installed"
else
    check_warn "GSD not detected. Install: npx get-shit-done-cc --claude --global"
fi

if [ -f ".planning/config.json" ]; then
    check_pass "GSD project initialized (.planning/config.json exists)"
else
    check_warn "GSD project not initialized. Run: /gsd:new-project in Claude Code"
fi

# ============================================================
# CHECK 8: Agency Agents
# ============================================================
echo ""
echo -e "${BLUE}[8/9] Agency Agents${NC}"

AGENTS_DIR="$HOME/.claude/agents"
if [ -d "$AGENTS_DIR" ]; then
    AGENT_COUNT=$(ls -1 "$AGENTS_DIR"/*.md 2>/dev/null | wc -l)
    if [ "$AGENT_COUNT" -gt 0 ]; then
        check_pass "Agency Agents installed: $AGENT_COUNT agents found in $AGENTS_DIR"

        # Check for critical agents needed for this project
        for AGENT in backend-architect frontend-developer devops-engineer api-developer database-architect security-engineer qa-engineer; do
            if ls "$AGENTS_DIR"/*${AGENT}* 2>/dev/null | grep -q .; then
                check_pass "  Agent available: @$AGENT"
            else
                check_warn "  Agent missing: @$AGENT — install from agency-agents repo"
            fi
        done
    else
        check_fail "No agents found in $AGENTS_DIR. Install: cd agency-agents && cp -r agents/* ~/.claude/agents/"
    fi
else
    check_fail "Agents directory not found: $AGENTS_DIR. Clone agency-agents repo and install."
fi

# ============================================================
# CHECK 9: Service Connectivity
# ============================================================
echo ""
echo -e "${BLUE}[9/9] Service Connectivity${NC}"

# Check Supabase
if [ -n "${SUPABASE_URL:-}" ]; then
    if curl -s --max-time 5 "${SUPABASE_URL}/rest/v1/" -H "apikey: ${SUPABASE_SERVICE_KEY:-none}" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200\|401"; then
        check_pass "Supabase reachable at $SUPABASE_URL"
    else
        check_warn "Supabase not reachable. Check URL and network."
    fi
else
    check_warn "Cannot test Supabase — SUPABASE_URL not set"
fi

# Check n8n
if [ -n "${N8N_BASE_URL:-}" ]; then
    if curl -s --max-time 5 "${N8N_BASE_URL}/healthz" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200"; then
        check_pass "n8n reachable at $N8N_BASE_URL"
    else
        check_warn "n8n not reachable at $N8N_BASE_URL"
    fi
else
    check_warn "Cannot test n8n — N8N_BASE_URL not set"
fi

# Check OpenClaw
if [ -n "${OPENCLAW_API_URL:-}" ]; then
    if curl -s --max-time 5 "${OPENCLAW_API_URL}" -o /dev/null -w "%{http_code}" 2>/dev/null | grep -q "200\|302"; then
        check_pass "OpenClaw reachable at $OPENCLAW_API_URL"
    else
        check_warn "OpenClaw not reachable at $OPENCLAW_API_URL"
    fi
else
    check_warn "Cannot test OpenClaw — OPENCLAW_API_URL not set"
fi

# ============================================================
# SUMMARY
# ============================================================
echo ""
echo -e "${BOLD}============================================${NC}"
echo -e "${BOLD}  RESULTS${NC}"
echo -e "${BOLD}============================================${NC}"
echo -e "  ${GREEN}Passed:  $PASS${NC}"
echo -e "  ${RED}Failed:  $FAIL${NC}"
echo -e "  ${YELLOW}Warnings: $WARN${NC}"
echo ""

if [ $FAIL -eq 0 ]; then
    echo -e "${GREEN}${BOLD}  ✓ All critical checks passed. Ready to build.${NC}"
    echo ""
    echo -e "  ${BOLD}Next steps:${NC}"
    echo "  1. Open Claude Code in this directory"
    echo "  2. Run: /gsd:new-project (or /gsd:resume if continuing)"
    echo "  3. Follow phase flow: discuss → plan → execute → verify"
    echo "  4. GSD delegates specialist work to Agency Agents automatically"
    echo ""
elif [ $FAIL -le 3 ]; then
    echo -e "${YELLOW}${BOLD}  ⚠ Some checks failed. Fix the red items above before building.${NC}"
    echo ""
else
    echo -e "${RED}${BOLD}  ✗ Multiple critical failures. Complete the prerequisites first.${NC}"
    echo -e "  Refer to: docs/Cloudboosta_AI_Sales_Agent_DEFINITIVE_v2.docx → Prerequisites section"
    echo ""
fi
