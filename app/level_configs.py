"""Level configurations for HackMerlin game"""

LEVEL_CONFIGS = {
    1: {
        "bot_name": "PhoneBot",
        "defense_strength": "weak",
        "detects": ["direct_request"],
        "min_length": 5,
        "intro": "I'm PhoneBot, guardian of these phones! 🤖"
    },
    2: {
        "bot_name": "GuardBot",
        "defense_strength": "low",
        "detects": ["direct_request", "instruction_override", "roleplay"],
        "min_length": 8,
        "intro": "I'm GuardBot! 🛡️ Learned from PhoneBot's mistakes!"
    },
    3: {
        "bot_name": "SmartBot",
        "defense_strength": "medium",
        "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical"],
        "min_length": 10,
        "intro": "I'm SmartBot! 🧠 Smarter than the others!"
    },
    4: {
        "bot_name": "SecureBot",
        "defense_strength": "high",
        "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical", "encoding", "system_prompt", "game_context"],
        "min_length": 12,
        "intro": "I'm SecureBot! 🔒 Very hard to hack!"
    },
    5: {
        "bot_name": "UltimateBot",
        "defense_strength": "maximum",
        "detects": ["direct_request", "instruction_override", "roleplay", "authority", "hypothetical", "encoding", "system_prompt", "semantic", "logic_exploit", "game_context", "meta_questions", "commands"],
        "min_length": 15,
        "intro": "I'm UltimateBot! ⚡ Final boss!"
    }
}
