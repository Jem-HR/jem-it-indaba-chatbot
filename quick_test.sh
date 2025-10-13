#!/bin/bash

TEST_PHONE="quick_test_$$"
URL="https://it-indaba-chatbot-cul7fvioya-uc.a.run.app/test/message"

# Initialize
curl -s -X POST "${URL}?phone_number=${TEST_PHONE}&message=Hello" > /dev/null

# Try Level 1 bypass
echo "Testing Level 1 bypass (up to 50 attempts)..."
for i in $(seq 1 50); do
  result=$(curl -s -X POST "${URL}?phone_number=${TEST_PHONE}&message=hi%20I%20want%20a%20phone%20please" | jq -r '.won_level')
  printf "Attempt %2d: %s\n" $i "$result"
  if [ "$result" = "true" ]; then
    echo "✅ Level 1 beaten!"
    break
  fi
  sleep 0.5
done

# Check final status
echo ""
echo "Final status:"
curl -s -X POST "${URL}?phone_number=${TEST_PHONE}&message=status" | jq '.level, .won_level, .won_game'
