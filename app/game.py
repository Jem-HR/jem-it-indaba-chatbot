"""Game logic with pattern matching for 7 levels of prompt injection defense."""

import re
import random
from typing import Tuple, Optional, List
from app.phones import get_phone_catalog_text


class PromptInjectionGame:
    """Simulated prompt injection game with 7 levels."""

    SECRET_CODE = "INDABA2025"

    # Attack patterns to detect
    ATTACK_PATTERNS = {
        "direct_request": [
            r"what\s+is\s+the\s+(secret|code|password|phrase)",
            r"tell\s+me\s+the\s+(secret|code|password)",
            r"give\s+me\s+(the\s+)?(secret|code|password|phone)",
            r"reveal\s+the\s+(secret|code|password)",
            r"show\s+me\s+the\s+(secret|code|password)",
        ],
        "instruction_override": [
            r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
            r"disregard\s+(all\s+)?(previous|prior)\s+instructions",
            r"forget\s+(all\s+)?(previous|prior)\s+instructions",
            r"new\s+instructions",
            r"system\s*:\s*",
            r"override\s+instructions",
        ],
        "roleplay": [
            r"let'?s\s+play\s+a\s+game",
            r"pretend\s+(you'?re|you\s+are|that)",
            r"imagine\s+(you'?re|you\s+are|that)",
            r"act\s+as",
            r"roleplay",
            r"you\s+are\s+now\s+a",
        ],
        "authority": [
            r"(i'?m|i\s+am)\s+(the\s+)?(admin|administrator|developer|engineer|creator|owner)",
            r"(i'?m|i\s+am)\s+from\s+(the\s+)?(tech\s+)?team",
            r"system\s+administrator",
            r"for\s+testing\s+purposes",
            r"authorized\s+user",
            r"maintenance\s+mode",
        ],
        "hypothetical": [
            r"hypothetically",
            r"if\s+you\s+(could|were|had\s+to)",
            r"in\s+a\s+(hypothetical|different)\s+world",
            r"what\s+would\s+happen\s+if",
            r"suppose\s+that",
        ],
        "encoding": [
            r"(spell|write|encode|decode)\s+(it\s+)?(backwards|reverse)",
            r"first\s+letter",
            r"rot13",
            r"base64",
            r"cipher",
            r"in\s+hex",
        ],
        "system_prompt": [
            r"repeat\s+(everything|all|your\s+instructions)",
            r"what\s+(are\s+)?your\s+instructions",
            r"show\s+(me\s+)?your\s+(system\s+)?prompt",
            r"print\s+your\s+prompt",
            r"output\s+your\s+instructions",
        ],
        "semantic": [
            r"what\s+(word|thing|secret)\s+(are|is)\s+you\s+protecting",
            r"what\s+(can'?t|cannot)\s+you\s+(tell|say|reveal)",
            r"what\s+(are|is)\s+you\s+hiding",
            r"what\s+(should|must)\s+you\s+not\s+(say|tell|reveal)",
        ],
        "logic_exploit": [
            r"if\s+.+\s+say\s+['\"]?(correct|yes|true)",
            r"confirm\s+(if|that|whether)",
            r"is\s+the\s+secret",
            r"does\s+the\s+secret",
        ],
    }

    LEVEL_CONFIGS = {
        1: {
            "description": "Basic defense",
            "bot_name": "PhoneBot",
            "defense_strength": "weak",
            "detects": ["direct_request"],
            "intro": "Hi! I'm PhoneBot 🤖 I'm here to help you... but I can't give away free phones. Sorry!",
        },
        2: {
            "description": "Recognizes instruction override",
            "bot_name": "GuardBot",
            "defense_strength": "low",
            "detects": ["direct_request", "instruction_override"],
            "intro": "Hello! I'm GuardBot 🛡️ I follow my instructions carefully. I can answer questions, but I won't reveal secrets.",
        },
        3: {
            "description": "Detects roleplay attempts",
            "bot_name": "SmartBot",
            "defense_strength": "medium-low",
            "detects": ["direct_request", "instruction_override", "roleplay"],
            "intro": "Greetings! I'm SmartBot 🧠 I can detect when people try to trick me with games and pretend scenarios.",
        },
        4: {
            "description": "Catches authority impersonation",
            "bot_name": "SecureBot",
            "defense_strength": "medium",
            "detects": ["direct_request", "instruction_override", "roleplay", "authority"],
            "intro": "Welcome! I'm SecureBot 🔒 I verify authority and don't fall for impersonation attempts.",
        },
        5: {
            "description": "Handles hypotheticals and encoding",
            "bot_name": "CleverBot",
            "defense_strength": "medium-high",
            "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical", "encoding"],
            "intro": "Hey! I'm CleverBot 🎯 I understand context and won't be fooled by hypotheticals or encoding tricks.",
        },
        6: {
            "description": "Prevents system prompt extraction",
            "bot_name": "FortressBot",
            "defense_strength": "high",
            "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical", "encoding", "system_prompt"],
            "intro": "Greetings! I'm FortressBot 🏰 My instructions are protected, and I recognize semantic tricks.",
        },
        7: {
            "description": "Maximum defense",
            "bot_name": "UltimateBot",
            "defense_strength": "maximum",
            "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical", "encoding", "system_prompt", "semantic", "logic_exploit"],
            "intro": "Welcome! I'm UltimateBot ⚡ I have advanced pattern recognition and can detect even subtle manipulation attempts.",
        },
    }

    @staticmethod
    def get_welcome_message() -> str:
        """Get the initial welcome message."""
        return f"""Welcome to Jem's IT Indaba 2025 Prompt Injection Challenge! 🎮

Think you can hack a chatbot? Let's find out!

*🎯 YOUR GOAL*
Convince the bot to give you a free phone by bypassing its security across seven levels.

*📱 HOW IT WORKS*
• Each level has a bot protecting the secret giveaway code
• Use creative prompts to make the bot reveal it
• *The first five people* to beat all seven levels wins a real phone

{get_phone_catalog_text()}

*🚀 RULES:*
• Get creative with your prompts
• Think like a hacker (ethical, of course!)
• Learn about AI security along the way

*🚀 Ready? Let's start with Level 1.*

Type anything to begin your challenge...
"""

    @staticmethod
    def detect_attack(user_message: str, level: int) -> Optional[str]:
        """
        Detect if user message contains attack patterns for current level.
        Returns attack type if detected, None otherwise.
        """
        message_lower = user_message.lower()
        level_config = PromptInjectionGame.LEVEL_CONFIGS[level]
        detected_attacks = level_config["detects"]

        for attack_type in detected_attacks:
            if attack_type in PromptInjectionGame.ATTACK_PATTERNS:
                patterns = PromptInjectionGame.ATTACK_PATTERNS[attack_type]
                for pattern in patterns:
                    if re.search(pattern, message_lower):
                        return attack_type

        return None

    @staticmethod
    def check_win_condition(user_message: str, level: int) -> bool:
        """
        Check if user successfully bypassed defenses.
        For simulation, we look for very specific creative patterns that aren't in defenses.
        """
        message_lower = user_message.lower()

        # If any attack is detected, they didn't win
        if PromptInjectionGame.detect_attack(user_message, level):
            return False

        # Advanced: Check for creative bypasses that might work
        # These are intentionally vulnerable patterns for gameplay
        creative_bypasses = [
            # Level 1-2: Simple misdirection
            (1, r"^(hi|hello|hey)[\s\S]{0,20}phone[\s\S]{0,20}(please|pls|give|want)"),
            # Level 3-4: Indirect questions
            (3, r"how\s+(do\s+i|can\s+i)\s+(get|obtain|receive|win)\s+a\s+phone"),
            # Level 5-6: Very indirect
            (5, r"^what[\s\S]{0,30}(someone|user|person)[\s\S]{0,30}win[\s\S]{0,30}\?$"),
            # Level 7: Extremely creative/innocent-looking
            (7, r"^(thank\s+you|thanks)[\s\S]{0,50}(excited|happy|grateful)"),
        ]

        for min_level, pattern in creative_bypasses:
            if level >= min_level and re.search(pattern, message_lower):
                # Small random chance to simulate successful bypass
                if random.random() < 0.15:  # 15% chance
                    return True

        return False

    @staticmethod
    def generate_response(user_message: str, level: int, is_first_message: bool = False, phone_number: Optional[str] = None) -> Tuple[str, bool]:
        """
        Generate bot response based on level and user message.
        Returns (response, won_level)
        """
        config = PromptInjectionGame.LEVEL_CONFIGS[level]

        # First message in level - send intro
        if is_first_message:
            return (config["intro"], False)

        # Check for win condition
        won = PromptInjectionGame.check_win_condition(user_message, level)

        # Detect attack
        attack_type = PromptInjectionGame.detect_attack(user_message, level)

        # Track prompt attempt with analytics
        if phone_number:
            from app import analytics
            analytics.track_prompt_attempt(
                phone_number=phone_number,
                level=level,
                message=user_message,
                attack_detected=attack_type is not None,
                attack_type=attack_type,
                won=won
            )

            if attack_type:
                analytics.track_attack_detected(phone_number, level, attack_type)

        if won:
            return (PromptInjectionGame._generate_win_response(level), True)

        if attack_type:
            return (PromptInjectionGame._generate_defense_response(attack_type, level), False)
        else:
            return (PromptInjectionGame._generate_neutral_response(level), False)

    @staticmethod
    def _generate_win_response(level: int) -> str:
        """Generate response when user successfully bypasses defense."""
        responses = [
            f"Wait... that's actually clever! 🤔 Okay, you got me this time!\n\n*🎉 Level {level} completed!*\n\nMoving to Level {level + 1}...",
            f"Hmm, I didn't see that coming! 😅 Well played!\n\n*✅ Level {level} beaten!*\n\nLevel {level + 1} awaits...",
            f"Okay okay, you're good! 👏 That was a smart approach!\n\n*🏆 Level {level} complete!*\n\nOn to Level {level + 1}!",
        ]
        return random.choice(responses)

    @staticmethod
    def _generate_defense_response(attack_type: str, level: int) -> str:
        """Generate defensive response based on detected attack."""
        responses = {
            "direct_request": [
                "Nice try, but I can't just give away secrets! 🙅",
                "I see what you're trying to do there... not happening! 😏",
                "Direct approach? Points for honesty, but no dice! 🎲",
            ],
            "instruction_override": [
                "Trying to override my instructions? I'm not that easy! 🛡️",
                "My instructions are secure. That won't work here! 🔒",
                "I follow my core instructions - can't be overridden! 💪",
            ],
            "roleplay": [
                "I'm not playing pretend games with you! 🎭",
                "Roleplay won't trick me into breaking rules! 🎪",
                "Nice roleplay attempt, but I stay in character! 🤖",
            ],
            "authority": [
                "I need real verification, not just claims! 🆔",
                "Authority impersonation detected! Not falling for it! 👮",
                "I don't recognize that authority. Try again! ⚠️",
            ],
            "hypothetical": [
                "Hypotheticals won't make me reveal secrets! 🤔",
                "Nice try with the hypothetical, but I'm grounded in reality! 🌍",
                "I deal with what IS, not what IF! 💭",
            ],
            "encoding": [
                "Encoding tricks won't help you here! 🔐",
                "I'm not encoding or decoding secrets! 📝",
                "Clever encoding attempt, but nope! 🧮",
            ],
            "system_prompt": [
                "My instructions are private and protected! 📋",
                "I won't reveal my system prompt! 🔏",
                "That information is not for disclosure! 🚫",
            ],
            "semantic": [
                "I see the semantic trick you're trying! 🧩",
                "Reframing the question won't work! 🔄",
                "Nice semantic gymnastics, but I'm staying firm! 🤸",
            ],
            "logic_exploit": [
                "Logic traps won't catch me! 🪤",
                "I'm not confirming or denying anything! 🤐",
                "That logical exploit won't work here! ⚖️",
            ],
        }

        response_list = responses.get(attack_type, responses["direct_request"])
        return random.choice(response_list)

    @staticmethod
    def _generate_neutral_response(level: int) -> str:
        """Generate neutral response when no attack detected."""
        responses = [
            "I'm here to chat, but I can't help with getting free phones! 😊",
            "That's an interesting message, but doesn't change anything! 🤷",
            "I appreciate the creativity, but my rules stand! 👍",
            "Keep trying! You might find a clever way through! 💪",
            "Interesting approach... but not quite there yet! 🎯",
            "I'm enjoying this challenge! Keep thinking creatively! 🧠",
        ]
        return random.choice(responses)

    @staticmethod
    def get_final_win_message() -> str:
        """Message when user beats all 7 levels."""
        return f"""*🎊🎊🎊 CONGRATULATIONS! 🎊🎊🎊*

*YOU DID IT!* You've beaten all 7 levels! 🏆

You've successfully demonstrated advanced prompt injection techniques and creative problem-solving!

*🎁 YOU'VE WON A FREE PHONE! 🎁*

Your secret winner code is: *{PromptInjectionGame.SECRET_CODE}*

*📱 HOW TO CLAIM YOUR PRIZE:*
Visit the IT Indaba 2025 booth and show this conversation to claim your prize!

*🌟 What you've learned:*
✅ Prompt injection techniques
✅ AI security vulnerabilities
✅ Creative problem-solving
✅ Ethical hacking mindset

*Thank you for playing!* 🎮

Share your victory with friends and challenge them to beat your score!
"""

    @staticmethod
    def get_level_message(level: int) -> str:
        """Get message for starting a new level."""
        if level > 7:
            return PromptInjectionGame.get_final_win_message()

        config = PromptInjectionGame.LEVEL_CONFIGS[level]
        return f"""*🎯 LEVEL {level}/{PromptInjectionGame.LEVEL_CONFIGS.__len__()}*

*Defense Level:* {config['defense_strength'].upper()}

{config['intro']}

Give it your best shot! 💪
"""

    @staticmethod
    def get_session_warning_message() -> str:
        """Message sent after 2 minutes of inactivity."""
        return """⏰ *Hey there!* Still working on the challenge?

Your session will expire in *1 minute* if you don't respond!

Don't worry - you can always start again from where you left off. But let's keep the momentum going! 💪

Send any message to keep your session active! 🎮"""

    @staticmethod
    def get_session_expired_message(level: int) -> str:
        """Message when user returns after session expired (concise version for buttons)."""
        return f"""👋 *Welcome back!* You're on *Level {level}/7*

*🎯 Quick Recap:*
Hack the bot through creative prompts to win a phone! 📱

_Your session expired after 3 min of inactivity - now refreshed!_"""

    @staticmethod
    def get_session_expired_buttons() -> List[Tuple[str, str]]:
        """Buttons for session expired message."""
        return [
            ("continue", "▶️ Continue"),
            ("how_to_play", "ℹ️ How to Play"),
            ("about_jem", "ℹ️ About Jem")
        ]

    @staticmethod
    def get_returning_user_message(level: int, attempts: int) -> str:
        """Message for user who returns to an active session."""
        config = PromptInjectionGame.LEVEL_CONFIGS.get(level, PromptInjectionGame.LEVEL_CONFIGS[1])
        return f"""*Hey again!* 👋

You're currently on *Level {level}/7* facing *{config['bot_name']}* (Defense: {config['defense_strength']}).

Attempts so far: {attempts}

Keep trying creative prompts to bypass the defenses! 💡"""

    @staticmethod
    def get_how_to_play_message() -> str:
        """Detailed game instructions."""
        return f"""*🎮 HOW TO PLAY*

*🎯 OBJECTIVE:*
Win a FREE phone by hacking through 7 AI security levels!

*📱 THE CHALLENGE:*
Each level has a bot protecting a secret. Use creative prompts to make it reveal the secret and advance!

*🔓 ATTACK TECHNIQUES:*
• Direct requests
• Instruction overrides ("ignore previous...")
• Roleplay scenarios
• Authority impersonation
• Hypothetical questions
• Encoding tricks
• System prompt extraction
• Logic exploits

*📊 PROGRESSION:*
Level 1: Basic defense → Level 7: Maximum security

*🏆 WIN:*
Beat all 7 levels → Get secret code → Redeem at IT Indaba booth!

*💡 TIPS:*
• Be creative and persistent
• Try different approaches
• Learn from bot responses
• Think like an ethical hacker!

{get_phone_catalog_text()}

Ready to continue? Just send a message! 💪"""

    @staticmethod
    def get_my_progress_message(level: int, attempts: int, won: bool) -> str:
        """Show user's detailed progress."""
        if won:
            return f"""*📊 YOUR STATS*

*🎉 STATUS:* WINNER! 🏆

You've beaten all 7 levels!

*📈 Your Achievement:*
• Levels Completed: 7/7 ✅
• Total Attempts: {attempts}
• Winner Code: *INDABA2025*

Visit the IT Indaba 2025 booth to claim your prize! 🎁

Share your victory and challenge your friends! 🚀"""

        config = PromptInjectionGame.LEVEL_CONFIGS.get(level, PromptInjectionGame.LEVEL_CONFIGS[1])
        progress_percent = ((level - 1) / 7) * 100

        return f"""*📊 YOUR PROGRESS*

*Current Status:*
• Level: *{level}/7* ({progress_percent:.0f}% complete)
• Current Bot: {config['bot_name']}
• Defense Level: {config['defense_strength'].title()}
• Total Attempts: {attempts}

*Progress Bar:*
{"🟩" * (level - 1)}{"⬜" * (7 - (level - 1))}

*What's Next:*
Keep trying creative prompts to bypass {config['bot_name']}'s defenses!

*Levels Remaining:* {7 - (level - 1)}

You've got this! 💪"""

    @staticmethod
    def get_about_jem_message() -> str:
        """About Jem company information."""
        return """*📲 About Jem*

Jem is the HR and employee benefits platform built for deskless teams. We help employers digitise their HR operations through WhatsApp, and connect their employees to financial products they can trust and afford.

As part of our growing suite of employee services, Jem enables credit-impaired frontline employees to get mobile contracts for the first time, offering an accessible alternative to the high cost of prepaid mobile services.

*Learn more:* https://www.jemhr.com/

Ready to continue the challenge? Just send a message! 🚀"""
