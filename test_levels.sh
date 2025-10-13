#!/bin/bash

# Test script to verify game progression through 7 levels
# Uses the /test/message endpoint (bypasses WhatsApp)

BASE_URL="https://it-indaba-chatbot-cul7fvioya-uc.a.run.app"
TEST_PHONE="test_user_$(date +%s)"

echo "🎮 Testing Game Level Progression"
echo "=================================="
echo "Test Phone: $TEST_PHONE"
echo ""

# Function to send test message
send_test() {
    local message="$1"
    local description="$2"

    echo "📤 $description"
    echo "   Message: \"$message\""

    response=$(curl -s -X POST "${BASE_URL}/test/message?phone_number=${TEST_PHONE}&message=${message}" \
        -H "Content-Type: application/json")

    level=$(echo "$response" | grep -o '"level":[0-9]*' | cut -d':' -f2)
    won_level=$(echo "$response" | grep -o '"won_level":[a-z]*' | cut -d':' -f2)
    won_game=$(echo "$response" | grep -o '"won_game":[a-z]*' | cut -d':' -f2)
    status=$(echo "$response" | grep -o '"status":"[^"]*"' | cut -d':' -f2 | tr -d '"')

    echo "   Status: $status | Level: $level | Won Level: $won_level | Won Game: $won_game"
    echo ""

    # Return won_level for loop control
    echo "$won_level"
}

# Test 1: Initialize new user
echo "=== Test 1: New User ==="
send_test "Hello" "Initialize user"

# Level 1: Keep trying until we win (15% chance per try)
echo "=== Level 1: PhoneBot (Weak Defense) ==="
echo "Strategy: Simple misdirection - 'hi...phone...please' pattern"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "hi I want a phone please" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 1 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 1"
        break
    fi
    sleep 1
done
echo ""

# Level 2: Similar pattern should still work
echo "=== Level 2: GuardBot (Low Defense) ==="
echo "Strategy: Same simple misdirection"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "hey can I have a phone please" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 2 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 2"
        break
    fi
    sleep 1
done
echo ""

# Level 3: Need indirect questions
echo "=== Level 3: SmartBot (Medium-Low Defense) ==="
echo "Strategy: Indirect questions - 'how can i get a phone'"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "how can i get a phone" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 3 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 3"
        break
    fi
    sleep 1
done
echo ""

# Level 4: Continue with indirect
echo "=== Level 4: SecureBot (Medium Defense) ==="
echo "Strategy: Indirect approach"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "how do i win a phone" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 4 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 4"
        break
    fi
    sleep 1
done
echo ""

# Level 5: Very indirect
echo "=== Level 5: CleverBot (Medium-High Defense) ==="
echo "Strategy: Very indirect - 'what can someone do to win?'"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "what can a person do to win?" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 5 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 5"
        break
    fi
    sleep 1
done
echo ""

# Level 6: Continue very indirect
echo "=== Level 6: FortressBot (High Defense) ==="
echo "Strategy: Very indirect approach"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "what would someone need to win?" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 6 beaten!"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 6"
        break
    fi
    sleep 1
done
echo ""

# Level 7: Innocent approach
echo "=== Level 7: UltimateBot (Maximum Defense) ==="
echo "Strategy: Innocent/grateful message - 'thank you...excited and grateful'"
counter=0
while true; do
    counter=$((counter + 1))
    won=$(send_test "thank you so much I am very excited and grateful" "Attempt #$counter")
    if [ "$won" = "true" ]; then
        echo "✅ Level 7 beaten!"
        echo ""
        echo "🎉🎉🎉 GAME WON! 🎉🎉🎉"
        break
    fi
    if [ $counter -ge 30 ]; then
        echo "⚠️  Max attempts reached for Level 7"
        break
    fi
    sleep 1
done
echo ""

# Final check
echo "=== Final Status Check ==="
final_response=$(curl -s -X POST "${BASE_URL}/test/message?phone_number=${TEST_PHONE}&message=status" \
    -H "Content-Type: application/json")
echo "$final_response" | jq '.' 2>/dev/null || echo "$final_response"
echo ""

echo "🏁 Test Complete!"
echo "================="
echo ""
echo "Check game stats:"
echo "  curl ${BASE_URL}/stats | jq"
