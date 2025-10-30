#!/bin/bash
# Quick reset script for Azurite storage
# 
# Usage:
#   ./tools/reset_azurite.sh
#   
# This is a convenience wrapper around the Python reset script

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( dirname "$SCRIPT_DIR" )"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  AZURITE STORAGE RESET FOR LOCAL POSTMAN TESTING${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════════${NC}"
echo ""

# Check if Azurite is running
echo -e "${YELLOW}Checking if Azurite is running...${NC}"
if ! nc -z 127.0.0.1 10002 2>/dev/null; then
    echo -e "${RED}✗ Azurite is not running!${NC}"
    echo ""
    echo -e "${YELLOW}Start Azurite with:${NC}"
    echo "  python tools/start_local_stack.py"
    echo ""
    exit 1
fi
echo -e "${GREEN}✓ Azurite is running on 127.0.0.1:10002${NC}"
echo ""

# Run the Python reset script
echo -e "${YELLOW}Running reset script...${NC}"
echo ""

cd "$PROJECT_ROOT"
python tools/reset_azurite.py

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  RESET SUCCESSFUL!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo "  1. Open Postman collection: docs/04-development/postman-local-collection.json"
    echo "  2. Run test 1.5 'Slug Sync - Fetch and Update' to populate slugs"
    echo "  3. Run claim tests (2.1, 2.2, etc.)"
    echo "  4. Run release tests (3.1, 3.1b, etc.)"
    echo "  5. Run audit tests (4.1, 4.2, etc.)"
    echo ""
else
    echo ""
    echo -e "${RED}✗ Reset failed! Check the error message above.${NC}"
    exit 1
fi
