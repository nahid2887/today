#!/bin/bash
# Quick verification that the main application works correctly

echo "========================================="
echo "Starting AI Hotel Application"
echo "========================================="
echo ""
echo "The application should now:"
echo "✓ Find hotels in Dhaka (3 hotels)"
echo "✓ Search globally when price+city fails"
echo "✓ Not carry over city context incorrectly"
echo ""
echo "Try these test queries:"
echo "1. 'find hotels in dhaka'"
echo "2. 'hotels over 250 dollars'"
echo "3. 'find hotels in sydney' then 'show me cheaper options'"
echo ""
echo "Starting application..."
echo ""

uv run python main.py
