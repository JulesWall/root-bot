"""
Text data and command sheets for the help system in English (/help).
Follows CONCEPTION_HELP.md specifications.
"""

UI = {
    "select_category_placeholder": "Choose a category...",
    "select_command_placeholder": "View a command in detail...",
    "btn_home": "Home",
    "btn_back_category": "Back to category",
    "btn_view_text": "View as text",
    "btn_view_slash": "View as slash",
    "mode_slash": "Slash Mode",
    "mode_text": "Text Mode",
    "footer_slash": "Root OS • Help • Slash Mode",
    "footer_text": "Root OS • Help • Text Mode • Prefix: {prefix}",
    "navigation_expired": "Navigation expired. Run `/help` again to continue.",
    "not_author_error": "Run `/help` to open your own personal guide.",
    "unknown_command_title": "Command Not Found",
    "unknown_command_body": (
        "This command is not available in the player help guide.\n"
        "Choose a category to browse available commands."
    ),
    "beta_note": (
        "\n\n*The game is currently in beta: some commands require access. "
        "You can browse this guide and initialize your network with `/network`.*"
    ),
    "sec_syntax": "Syntax",
    "sec_parameters": "Parameters",
    "sec_example": "Example",
    "sec_prerequisites": "Prerequisites",
    "sec_advice": "Advice",
    "sec_aliases": "Text Aliases",
    "sec_linked": "Related Commands",
}

CATEGORIES = [
    {
        "id": "home",
        "emoji": "🏠",
        "label": "Home",
        "description": "General overview and first steps",
    },
    {
        "id": "all",
        "emoji": "📜",
        "label": "All Commands",
        "description": "Complete index of all 24 commands",
    },
    {
        "id": "network",
        "emoji": "⛏️",
        "label": "Develop Network",
        "description": "Hardware, mining and firewall",
    },
    {
        "id": "combat",
        "emoji": "⚔️",
        "label": "Attack & Defend",
        "description": "Attack points, scans and PvP hacks",
    },
    {
        "id": "events",
        "emoji": "🎮",
        "label": "Event Challenges",
        "description": "Cryptography mini-games and network puzzles",
    },
    {
        "id": "trade",
        "emoji": "🤝",
        "label": "Trade & Rank",
        "description": "Trading, reputation, attestations and leaderboards",
    },
    {
        "id": "info",
        "emoji": "⚙️",
        "label": "Language & Info",
        "description": "Preferences and system information",
    },
    {
        "id": "syntax",
        "emoji": "📖",
        "label": "Reading Syntax",
        "description": "Parameters, aliases and prefix rules",
    },
]

PAGES = {
    "home": {
        "title": "📡 ROOT — Help Center",
        "body_slash": (
            "Grow your network, mine Rootium, and compete against other players.\n\n"
            "**🚀 First Steps on Root:**\n"
            "**1. Initialize your network — `/network`**\n"
            "Find your balances, hardware, and mining rate.\n\n"
            "**2. Install a miner — `/buy`**\n"
            "Open the shop and choose an affordable mining module.\n\n"
            "**3. Collect production — `/claim`**\n"
            "Your miners accumulate Rootium. When RAM is full, mining halts.\n\n"
            "**4. Fund your expansion — `/convert` and `/event`**\n"
            "Convert some Rootium into dollars and take part in events.\n\n"
            "**5. Upgrade your network — `/upgrade`**\n"
            "Firewall increases defense and unlocks advanced modules (note: tier 1 enters PvP!).\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**Core Resources:**\n"
            "• **USD ($)**: Currency for mining, defense, and firewall upgrades.\n"
            "• **RTM**: Mined Rootium, required for attacks, compilation, and scans.\n"
            "• **ATK**: Attack points produced with `/compile`.\n\n"
            "👉 *Use the menu below to browse categories or jump directly with `/help command:buy`.*"
        ),
        "body_text": (
            "Grow your network, mine Rootium, and compete against other players.\n\n"
            "**🚀 First Steps on Root:**\n"
            "**1. Initialize your network — `{prefix}network`**\n"
            "Find your balances, hardware, and mining rate.\n\n"
            "**2. Install a miner — `{prefix}buy`**\n"
            "Open the shop and choose an affordable mining module.\n\n"
            "**3. Collect production — `{prefix}claim`**\n"
            "Your miners accumulate Rootium. When RAM is full, mining halts.\n\n"
            "**4. Fund your expansion — `{prefix}convert` and `{prefix}event`**\n"
            "Convert some Rootium into dollars and take part in events.\n\n"
            "**5. Upgrade your network — `{prefix}upgrade`**\n"
            "Firewall increases defense and unlocks advanced modules (note: tier 1 enters PvP!).\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "**Core Resources:**\n"
            "• **USD ($)**: Currency for mining, defense, and firewall upgrades.\n"
            "• **RTM**: Mined Rootium, required for attacks, compilation, and scans.\n"
            "• **ATK**: Attack points produced with `{prefix}compile`.\n\n"
            "👉 *Use the menu below to browse categories or jump directly with `{prefix}help buy`.*"
        ),
    },
    "all": {
        "title": "📜 ROOT — All Commands",
        "body_slash": (
            "Complete index of all 24 public player commands in Root.\n\n"
            "**⛏️ Develop Network**\n"
            "• **/network** — Initialize profile or inspect balances & hardware\n"
            "• **/buy** — Purchase hardware (mining, attack, defense)\n"
            "• **/claim** — Claim mined Rootium and clear RAM\n"
            "• **/convert** — Sell Rootium for USD at current rate\n"
            "• **/upgrade** — Upgrade firewall tier\n\n"
            "**⚔️ Attack & Defend**\n"
            "• **/compile** — Craft attack points (ATK) from Rootium\n"
            "• **/scan** — Scan an opponent to discover their Secret ID\n"
            "• **/hack** — Launch a targeted cyberattack\n\n"
            "**🎮 Event Challenges**\n"
            "• **/event** — Active events dashboard\n"
            "• **/hash** — Guess the secret block number\n"
            "• **/pin** — Crack the 4-digit PIN code\n"
            "• **/decode** — Decipher letters in the matrix\n"
            "• **/anomaly** — Detect corrupted line number\n"
            "• **/buffer** — Reassemble memory fragments\n"
            "• **/signal** — Identify dominant frequency letter\n"
            "• **/packet** — Find missing network packet number\n\n"
            "**🤝 Trade & Rank**\n"
            "• **/rep** — Grant a daily reputation point\n"
            "• **/trade** — Propose a bilateral resource trade\n"
            "• **/attest** — Attest minimum balance publicly\n"
            "• **/top** — View top player leaderboards\n\n"
            "**⚙️ Language & Info**\n"
            "• **/lang** — Configure display language (fr/en)\n"
            "• **/ping** — Measure bot latency & Gateway heartbeat\n"
            "• **/botinfo** — System statistics and uptime\n"
            "• **/invite** — Get official bot invitation link\n\n"
            "👉 *Select any command below to open its detailed sheet.*"
        ),
        "body_text": (
            "Complete index of all 24 public player commands in Root.\n\n"
            "**⛏️ Develop Network**\n"
            "• **{prefix}network** (alias `{prefix}n`) — Inspect balances & hardware\n"
            "• **{prefix}buy** — Purchase hardware (mining, attack, defense)\n"
            "• **{prefix}claim** (alias `{prefix}cl`) — Claim mined Rootium\n"
            "• **{prefix}convert** (alias `{prefix}cv` / `{prefix}sell`) — Sell RTM for USD\n"
            "• **{prefix}upgrade** — Upgrade firewall tier\n\n"
            "**⚔️ Attack & Defend**\n"
            "• **{prefix}compile** (alias `{prefix}cp`) — Craft ATK points\n"
            "• **{prefix}scan** — Scan an opponent for Secret ID\n"
            "• **{prefix}hack** (alias `{prefix}hk`) — Launch a cyberattack\n\n"
            "**🎮 Event Challenges**\n"
            "• **{prefix}event** (alias `{prefix}events`, `{prefix}e`) — Events dashboard\n"
            "• **{prefix}hash** (alias `{prefix}h`) — Find secret block number\n"
            "• **{prefix}pin** (alias `{prefix}p`) — Crack the 4-digit PIN\n"
            "• **{prefix}decode** (alias `{prefix}d`) — Decipher matrix code\n"
            "• **{prefix}anomaly** (alias `{prefix}a`) — Find corrupted line\n"
            "• **{prefix}buffer** (alias `{prefix}b`) — Reassemble buffer\n"
            "• **{prefix}signal** (alias `{prefix}s`) — Detect dominant letter\n"
            "• **{prefix}packet** (alias `{prefix}pa`) — Find missing packet\n\n"
            "**🤝 Trade & Rank**\n"
            "• **{prefix}rep** (alias `{prefix}reputation`) — Grant reputation\n"
            "• **{prefix}trade** — Propose a bilateral trade\n"
            "• **{prefix}attest** (alias `{prefix}certify`) — Attest minimum balance\n"
            "• **{prefix}top** (alias `{prefix}leaderboard`) — View leaderboards\n\n"
            "**⚙️ Language & Info**\n"
            "• **{prefix}lang** (alias `{prefix}language`) — Configure language\n"
            "• **{prefix}ping** — Measure bot latency\n"
            "• **{prefix}botinfo** — System statistics\n"
            "• **{prefix}invite** — Get official invite link\n\n"
            "👉 *Select any command below to open its detailed sheet.*"
        ),
    },
    "network": {
        "title": "⛏️ Develop Network",
        "body_slash": (
            "Check your network, install hardware, and collect production to fund your expansion.\n\n"
            "• **/network**: Initialize your profile or inspect your hardware and memory state.\n"
            "• **/buy**: Open catalog or purchase mining, offensive, or defensive modules directly.\n"
            "• **/claim**: Claim mined Rootium to your wallet and free up RAM.\n"
            "• **/convert**: Convert RTM to USD at the current market rate.\n"
            "• **/upgrade**: Start upgrading your firewall tier.\n\n"
            "👉 *Select a command in the dropdown menu below for complete details.*"
        ),
        "body_text": (
            "Check your network, install hardware, and collect production to fund your expansion.\n\n"
            "• **{prefix}network** (alias `{prefix}n`): Initialize your profile or inspect your hardware.\n"
            "• **{prefix}buy**: Open catalog or purchase modules directly.\n"
            "• **{prefix}claim** (alias `{prefix}cl`): Claim mined Rootium and free up RAM.\n"
            "• **{prefix}convert** (alias `{prefix}cv` / `{prefix}sell`): Sell RTM for USD.\n"
            "• **{prefix}upgrade**: Upgrade your firewall tier.\n\n"
            "👉 *Select a command in the dropdown menu below for complete details.*"
        ),
    },
    "combat": {
        "title": "⚔️ Attack & Defend",
        "body_slash": (
            "Offensive modules provide throughput. Use `/compile` to craft ATK points, "
            "then `/scan` to find a target's secret ID and `/hack` to breach their system.\n\n"
            "• **/compile**: Produce attack points (ATK) with your chosen method.\n"
            "• **/scan**: Scan an opponent to discover their Secret ID.\n"
            "• **/hack**: Commit ATK points to strike an opponent's network.\n\n"
            "🛡️ *To protect yourself, purchase defense modules with `/buy kind:defense` and upgrade your firewall with `/upgrade`.*"
        ),
        "body_text": (
            "Offensive modules provide throughput. Use `{prefix}compile` to craft ATK points, "
            "then `{prefix}scan` to find a target's secret ID and `{prefix}hack` to breach their system.\n\n"
            "• **{prefix}compile** (alias `{prefix}cp`): Craft ATK points using your RTM.\n"
            "• **{prefix}scan**: Attempt to extract a target's Secret ID.\n"
            "• **{prefix}hack** (alias `{prefix}hk`): Launch a targeted cyberattack.\n\n"
            "🛡️ *To protect yourself, purchase defense modules with `{prefix}buy defense` and upgrade your firewall with `{prefix}upgrade`.*"
        ),
    },
    "events": {
        "title": "🎮 Event Challenges",
        "body_slash": (
            "Check `/event` for active challenges. Run any mini-game command without arguments to view its status, "
            "then submit your guess.\n\n"
            "• **/event**: Dashboard of all community events and availability.\n"
            "• **/hash**: Guess the secret block number within a binary search range.\n"
            "• **/pin**: Uncover the 4-digit PIN code.\n"
            "• **/decode**: Decipher coordinates in an alphanumeric matrix.\n"
            "• **/anomaly**: Find the line containing an anomalous character.\n"
            "• **/buffer**: Reconstruct fragmented memory blocks in numeric order.\n"
            "• **/signal**: Identify the dominant radio frequency.\n"
            "• **/packet**: Identify the missing network packet number.\n\n"
            "👉 *Select any mini-game below to read its solving guide.*"
        ),
        "body_text": (
            "Check `{prefix}event` for active challenges. Run any mini-game command without arguments to view its status, "
            "then submit your guess.\n\n"
            "• **{prefix}event** (alias `{prefix}events`, `{prefix}e`): Active events dashboard.\n"
            "• **{prefix}hash** (alias `{prefix}h`): Find the secret block number.\n"
            "• **{prefix}pin** (alias `{prefix}p`): Uncover the 4-digit PIN code.\n"
            "• **{prefix}decode** (alias `{prefix}d`): Read the code in the matrix.\n"
            "• **{prefix}anomaly** (alias `{prefix}a`): Spot the corrupted line.\n"
            "• **{prefix}buffer** (alias `{prefix}b`): Reassemble the ordered fragments.\n"
            "• **{prefix}signal** (alias `{prefix}s`): Detect the dominant letter.\n"
            "• **{prefix}packet** (alias `{prefix}pa`): Find the missing packet.\n\n"
            "👉 *Select any mini-game below to read its solving guide.*"
        ),
    },
    "trade": {
        "title": "🤝 Trade & Rank",
        "body_slash": (
            "Trade resources, grant reputation, and check the leaderboards.\n\n"
            "• **/rep**: Award a daily reputation point to another player.\n"
            "• **/trade**: Propose a secure bilateral resource swap.\n"
            "• **/attest**: Publicly prove your balance meets a threshold without disclosing exact figures.\n"
            "• **/top**: Check top hacker rankings (reputation, wealth, event wins).\n\n"
            "👉 *Select a command below to explore its parameters.*"
        ),
        "body_text": (
            "Trade resources, grant reputation, and check the leaderboards.\n\n"
            "• **{prefix}rep** (alias `{prefix}reputation`): Give reputation to a player.\n"
            "• **{prefix}trade**: Propose a bilateral trade.\n"
            "• **{prefix}attest** (alias `{prefix}certify`, `{prefix}proof`): Attest minimum balance.\n"
            "• **{prefix}top** (alias `{prefix}leaderboard`): View top players.\n\n"
            "👉 *Select a command below to explore its parameters.*"
        ),
    },
    "info": {
        "title": "⚙️ Language & Info",
        "body_slash": (
            "Set your preferred language and check Root bot statistics.\n\n"
            "• **/lang**: Set or check your display language (French or English).\n"
            "• **/ping**: Measure bot latency and Discord Gateway responsiveness.\n"
            "• **/botinfo**: View general bot stats, uptime, and system status.\n"
            "• **/invite**: Get the official link to invite Root to your Discord server."
        ),
        "body_text": (
            "Set your preferred language and check Root bot statistics.\n\n"
            "• **{prefix}lang** (alias `{prefix}language`): Set language (fr/en).\n"
            "• **{prefix}ping**: Check bot latency.\n"
            "• **{prefix}botinfo**: System stats and uptime.\n"
            "• **{prefix}invite**: Official Root bot invite link."
        ),
    },
    "syntax": {
        "title": "📖 Reading Command Syntax",
        "body_slash": (
            "**In Slash Mode:**\n"
            "Type `/` followed by the command name, then fill the Discord fields.\n"
            "Example: `/buy kind:mining tier:1`\n\n"
            "**In Text Mode:**\n"
            "Type the server prefix, command name, and positional arguments in order.\n"
            "Example: `{prefix}buy mining 1`\n\n"
            "**Notation Guide:**\n"
            "• `<value>`: required parameter.\n"
            "• `[value]`: optional parameter.\n"
            "• `mining|attack|defense`: choose one of these options.\n"
            "*(Never type the angle brackets `< >` or square brackets `[ ]`.)*\n\n"
            "**Aliases:**\n"
            "Aliases are shortcuts in **Text Mode** only. For example, `{prefix}n` is identical to `{prefix}network`.\n\n"
            "**Confirmation:**\n"
            "Adding `confirm` directly skips the quote/confirmation prompt and executes immediately."
        ),
        "body_text": (
            "**In Text Mode:**\n"
            "Type the server prefix, command name, and space-separated arguments.\n"
            "Example: `{prefix}buy mining 1`\n\n"
            "**In Slash Mode:**\n"
            "Type `/` followed by the command name to fill Discord options.\n"
            "Example: `/buy kind:mining tier:1`\n\n"
            "**Notation Guide:**\n"
            "• `<value>`: required parameter.\n"
            "• `[value]`: optional parameter.\n"
            "• `mining|attack|defense`: choose one of these options.\n"
            "*(Never type the angle brackets `< >` or square brackets `[ ]`.)*\n\n"
            "**Aliases:**\n"
            "Aliases provide quick shortcuts in text: `{prefix}cp` replaces `{prefix}compile`.\n\n"
            "**Confirmation:**\n"
            "Appending `confirm` executes the command immediately without asking for confirmation."
        ),
    },
}

COMMANDS = {
    # ── Page 2: Develop Network ──────────────────────────────────
    "network": {
        "name": "network",
        "category": "network",
        "title": "📡 `/network` — Create or Inspect Network",
        "description": "Initializes your profile upon first use, then displays your network stats, hardware, and wallet balances.",
        "slash_syntax": "/network",
        "text_syntax": "{prefix}network",
        "parameters": "None.",
        "slash_example": "/network",
        "text_example": "{prefix}network",
        "prerequisites": "No prerequisites. This command initializes your account if you haven't started yet.",
        "advice": "Start here! Check back often to monitor mining yields and memory fullness.",
        "aliases": ["{prefix}n"],
        "linked_commands": ["buy", "claim"],
    },
    "buy": {
        "name": "buy",
        "category": "network",
        "title": "🛒 `/buy` — Purchase Hardware",
        "description": "Buy mining rigs (RTM), attack processors (ATK), or defense nodes to equip your network.",
        "slash_syntax": "/buy [kind:<mining|attack|defense>] [tier:<1–5>] [confirm:confirm]",
        "text_syntax": "{prefix}buy [mining|attack|defense] [tier] [confirm]",
        "parameters": (
            "• `kind`: Module type (`mining`, `attack`, `defense`). Opens shop catalog if omitted.\n"
            "• `tier`: Module tier from 1 to 5 (defaults to 1 if `kind` is provided).\n"
            "• `confirm`: Skips the interactive quote and executes immediately."
        ),
        "slash_example": "/buy kind:mining tier:1",
        "text_example": "{prefix}buy mining 1",
        "prerequisites": "An active network, required funds (USD or RTM), and sufficient firewall level.",
        "advice": "Run `/buy` without parameters to browse the interactive shop catalog.",
        "aliases": ["Text synonym: `{prefix}buy bay_defense` for defense modules"],
        "linked_commands": ["claim", "compile", "upgrade"],
    },
    "claim": {
        "name": "claim",
        "category": "network",
        "title": "⚡ `/claim` — Collect Mined Rootium",
        "description": "Transfers mined Rootium stored in hardware RAM to your main balance and clears buffer memory.",
        "slash_syntax": "/claim",
        "text_syntax": "{prefix}claim",
        "parameters": "None.",
        "slash_example": "/claim",
        "text_example": "{prefix}claim",
        "prerequisites": "An active network with at least one miner having accumulated Rootium.",
        "advice": "When RAM fills up, mining stops completely! Check `/network` to track your gauge.",
        "aliases": ["{prefix}cl"],
        "linked_commands": ["convert", "network"],
    },
    "convert": {
        "name": "convert",
        "category": "network",
        "title": "💱 `/convert` — Convert RTM to USD",
        "description": "Sell Rootium for USD at the current dynamic exchange rate.",
        "slash_syntax": "/convert amount:<amount|all> [confirm:confirm]",
        "text_syntax": "{prefix}convert <amount|all> [confirm]",
        "parameters": (
            "• `amount`: Exact amount of Rootium to sell, or `all` to convert your entire available RTM.\n"
            "• `confirm`: Directly executes the sale without a quote."
        ),
        "slash_example": "/convert amount:0.00002",
        "text_example": "{prefix}convert 0.00002",
        "example_note": "To convert everything: `/convert amount:all` or `{prefix}convert all`.",
        "prerequisites": "An active network and sufficient RTM balance.",
        "advice": "Keep some Rootium handy: it is required for compiling ATK points (`/compile`) and scanning targets (`/scan`).",
        "aliases": ["{prefix}cv", "Alternative text command: `{prefix}sell <amount|all> [confirm]`"],
        "linked_commands": ["buy", "upgrade"],
    },
    "upgrade": {
        "name": "upgrade",
        "category": "network",
        "title": "🛡️ `/upgrade` — Upgrade Firewall",
        "description": "Increases your firewall level to boost total defense and unlock advanced hardware tiers.",
        "slash_syntax": "/upgrade [confirm:confirm]",
        "text_syntax": "{prefix}upgrade [confirm]",
        "parameters": "• `confirm`: Instantly starts the upgrade without interactive confirmation.",
        "slash_example": "/upgrade",
        "text_example": "{prefix}upgrade",
        "prerequisites": "An active network, sufficient USD, and no firewall upgrade already in progress.",
        "advice": "Warning: At tier 0, you enjoy special novice PvP protection. Upgrading to tier 1 exposes you to attacks!",
        "aliases": [],
        "linked_commands": ["buy", "network"],
    },

    # ── Page 3: Attack & Defend ──────────────────────────────────
    "compile": {
        "name": "compile",
        "category": "combat",
        "title": "⚙️ `/compile` — Craft ATK Points",
        "description": "Starts a compilation batch to produce attack points (ATK) from your Rootium stock.",
        "slash_syntax": "/compile method:<unskilled|skilled|ai> [atk:<integer|all>] [confirm:confirm]",
        "text_syntax": "{prefix}compile <unskilled|skilled|ai> [integer|all] [confirm]",
        "parameters": (
            "• `method`: Crafting method (`unskilled`, `skilled`, `ai`).\n"
            "• `atk`: Amount of ATK to craft (defaults to `all` for the maximum allowed by your hardware throughput).\n"
            "• `confirm`: Starts the batch without displaying the quote."
        ),
        "slash_example": "/compile method:ai atk:1",
        "text_example": "{prefix}compile ai 1",
        "example_note": "Maximum batch: `/compile method:unskilled atk:all`",
        "prerequisites": "An active network, at least one attack module installed, required RTM, and no active batch.",
        "advice": "Compare RTM cost and delivery duration in the quote before confirming.",
        "aliases": ["{prefix}cp", "Method text aliases: `uns`/`nq`, `sk`/`q`, `ia`"],
        "linked_commands": ["scan", "hack"],
    },
    "scan": {
        "name": "scan",
        "category": "combat",
        "title": "🔍 `/scan` — Scan a Player",
        "description": "Scans an opponent's network to breach their firewall and uncover their Secret ID.",
        "slash_syntax": "/scan target:<@player>",
        "text_syntax": "{prefix}scan <@player>",
        "parameters": "• `target`: Mention or selection of the target player.",
        "slash_example": "/scan target:@Alex",
        "text_example": "{prefix}scan @Alex",
        "prerequisites": "An active network, required RTM funds, and an eligible target (firewall ≥ 1).",
        "advice": "Scan odds depend on stats. If successful, note down the Secret ID: it expires after a short period!",
        "aliases": [],
        "linked_commands": ["hack", "compile"],
    },
    "hack": {
        "name": "hack",
        "category": "combat",
        "title": "💥 `/hack` — Attack a Network",
        "description": "Commit ATK points to strike an opponent's network and loot a miner or destroy offensive modules.",
        "slash_syntax": "/hack secret_id:<code> attack_points:<integer> zone:<mining|attack> [confirm:confirm]",
        "text_syntax": "{prefix}hack <secret_id> <attack_points> <mining|attack> [confirm]",
        "parameters": (
            "• `secret_id`: Valid target Secret ID obtained from a previous scan.\n"
            "• `attack_points`: Number of ATK points to commit.\n"
            "• `zone`: Target area (`mining` to steal a miner, `attack` to destroy offensive gear).\n"
            "• `confirm`: Launches the cyberattack without a risk estimate."
        ),
        "slash_example": "/hack secret_id:123456 attack_points:10 zone:mining",
        "text_example": "{prefix}hack 123456 10 mining",
        "example_note": "`123456` and 10 ATK are illustrative values.",
        "prerequisites": "A valid Secret ID, sufficient ATK points, and an unprotected target.",
        "advice": "To succeed, committed ATK must STRICTLY exceed opponent total defense. A tie results in failure!",
        "aliases": ["{prefix}hk"],
        "linked_commands": ["scan", "compile"],
    },

    # ── Page 4: Event Challenges ─────────────────────────────────
    "event": {
        "name": "event",
        "category": "events",
        "title": "🎯 `/event` — Community Events",
        "description": "Displays the community event dashboard, active mini-games, prizes, and current challenge statuses.",
        "slash_syntax": "/event",
        "text_syntax": "{prefix}event",
        "parameters": "None.",
        "slash_example": "/event",
        "text_example": "{prefix}event",
        "prerequisites": "No special prerequisites to inspect the dashboard.",
        "advice": "Pick an active challenge, then invoke its command with no arguments to view the puzzle.",
        "aliases": ["{prefix}events", "{prefix}e"],
        "linked_commands": ["hash", "pin", "decode"],
    },
    "hash": {
        "name": "hash",
        "category": "events",
        "title": "🔢 `/hash` — Guess Block Number",
        "description": "Find the secret block validation number using 'higher' or 'lower' hints.",
        "slash_syntax": "/hash [guess:<integer>]",
        "text_syntax": "{prefix}hash [integer]",
        "parameters": "• `guess`: Your proposed number. Omit to view current range and challenge state.",
        "slash_example": "/hash guess:500",
        "text_example": "{prefix}hash 500",
        "prerequisites": "An active hash mining event.",
        "advice": "Use binary search based on the displayed interval to narrow down the answer.",
        "aliases": ["{prefix}h"],
        "linked_commands": ["event"],
    },
    "pin": {
        "name": "pin",
        "category": "events",
        "title": "🔐 `/pin` — Crack the PIN Code",
        "description": "Discover the secret 4-digit PIN code by analyzing feedback on your personal search bracket.",
        "slash_syntax": "/pin [guess:<integer>]",
        "text_syntax": "{prefix}pin [integer]",
        "parameters": "• `guess`: Proposed PIN. Omit to check challenge status.",
        "slash_example": "/pin guess:60",
        "text_example": "{prefix}pin 60",
        "prerequisites": "An active PIN challenge.",
        "advice": "Your bracket is personal: do not assume it matches other players' search ranges.",
        "aliases": ["{prefix}p"],
        "linked_commands": ["event"],
    },
    "decode": {
        "name": "decode",
        "category": "events",
        "title": "🧩 `/decode` — Matrix Cipher",
        "description": "Reconstruct a 4-letter password by reading coordinate intersections on the matrix grid.",
        "slash_syntax": "/decode [code:<4 letters>]",
        "text_syntax": "{prefix}decode [code]",
        "parameters": "• `code`: The 4 deciphered letters. Omit to view the matrix grid.",
        "slash_example": "/decode code:ABCD",
        "text_example": "{prefix}decode ABCD",
        "prerequisites": "An active decoding challenge.",
        "advice": "Submit the deciphered letters, not the grid row/column numbers!",
        "aliases": ["{prefix}d"],
        "linked_commands": ["event"],
    },
    "anomaly": {
        "name": "anomaly",
        "category": "events",
        "title": "🚨 `/anomaly` — Detect Corrupted Line",
        "description": "Scan lines of code to identify the row index containing a hidden digit.",
        "slash_syntax": "/anomaly [line:<1–10>]",
        "text_syntax": "{prefix}anomaly [line]",
        "parameters": "• `line`: Row number (1 to 10). Omit to view the stream.",
        "slash_example": "/anomaly line:4",
        "text_example": "{prefix}anomaly 4",
        "prerequisites": "An active network anomaly event.",
        "advice": "Count lines from top to bottom starting at 1. Reply with the line number, not the digit.",
        "aliases": ["{prefix}a"],
        "linked_commands": ["event"],
    },
    "buffer": {
        "name": "buffer",
        "category": "events",
        "title": "💾 `/buffer` — Reassemble Memory Buffer",
        "description": "Order fragmented memory chunks chronologically (1 through 6) to form the password.",
        "slash_syntax": "/buffer [code:<6 letters>]",
        "text_syntax": "{prefix}buffer [code]",
        "parameters": "• `code`: The 6 assembled letters in order 1–6. Omit to view chunks.",
        "slash_example": "/buffer code:ABCDEF",
        "text_example": "{prefix}buffer ABCDEF",
        "prerequisites": "An active buffer challenge.",
        "advice": "Order letters by their chunk numbers, not their display order on screen.",
        "aliases": ["{prefix}b"],
        "linked_commands": ["event"],
    },
    "signal": {
        "name": "signal",
        "category": "events",
        "title": "📡 `/signal` — Frequency Detection",
        "description": "Analyze a noisy transmission and identify the most frequent character.",
        "slash_syntax": "/signal [letter:<letter>]",
        "text_syntax": "{prefix}signal [letter]",
        "parameters": "• `letter`: The dominant letter. Omit to inspect the transmission.",
        "slash_example": "/signal letter:A",
        "text_example": "{prefix}signal A",
        "prerequisites": "An active radio signal challenge.",
        "advice": "You can also tap the interactive buttons directly beneath the challenge message.",
        "aliases": ["{prefix}s"],
        "linked_commands": ["event"],
    },
    "packet": {
        "name": "packet",
        "category": "events",
        "title": "📦 `/packet` — Find Missing Packet",
        "description": "Identify which sequence packet number (between 1 and 10) was dropped in transit.",
        "slash_syntax": "/packet [guess:<1–10>]",
        "text_syntax": "{prefix}packet [number]",
        "parameters": "• `guess`: Missing packet index. Omit to view received packets.",
        "slash_example": "/packet guess:7",
        "text_example": "{prefix}packet 7",
        "prerequisites": "An active packet loss event.",
        "advice": "Quickly spot the missing number in the series from 1 to 10.",
        "aliases": ["{prefix}pa"],
        "linked_commands": ["event"],
    },

    # ── Page 5: Trade & Rank ─────────────────────────────────────
    "rep": {
        "name": "rep",
        "category": "trade",
        "title": "⭐ `/rep` — Grant Reputation",
        "description": "Award a reputation point to another player to commend their fair play and permanently boost their mining.",
        "slash_syntax": "/rep target:<@player>",
        "text_syntax": "{prefix}rep <@player>",
        "parameters": "• `target`: The recipient player.",
        "slash_example": "/rep target:@Alex",
        "text_example": "{prefix}rep @Alex",
        "prerequisites": "An active network, daily cooldown respected, and you cannot target yourself.",
        "advice": "Receiving reputation grants a permanent efficiency bonus on your mining rigs!",
        "aliases": ["{prefix}reputation"],
        "linked_commands": ["top"],
    },
    "trade": {
        "name": "trade",
        "category": "trade",
        "title": "🤝 `/trade` — Propose a Trade",
        "description": "Opens a secure transaction offer to trade USD and/or Rootium with another player.",
        "slash_syntax": "/trade target:<@player> [offer:<resources>] [request:<resources>]",
        "text_syntax": "{prefix}trade <@player> <signed resources>",
        "parameters": (
            "• In Slash Mode:\n"
            "  - `target`: Partner player.\n"
            "  - `offer`: What you send (e.g. `50usd`, `0.001rtm` or `50usd 0.001rtm`).\n"
            "  - `request`: What you receive in exchange (e.g. `0.001rtm`).\n"
            "• In Text Mode:\n"
            "  - Use signs: `-` for what you send and `+` for what you receive!"
        ),
        "slash_example": "/trade target:@Alex offer:50usd request:0.001rtm",
        "text_example": "{prefix}trade @Alex -50usd +0.001rtm",
        "example_note": "Amounts are entered without signs in dedicated slash fields, but WITH `-` and `+` in text mode.",
        "prerequisites": "Both players must have an active network and sufficient funds in their balances.",
        "advice": "Carefully review offer and request details on the confirmation modal before accepting.",
        "aliases": [],
        "linked_commands": ["attest"],
    },
    "attest": {
        "name": "attest",
        "category": "trade",
        "title": "📜 `/attest` — Attest Minimum Balance",
        "description": "Generates cryptographic proof that your balance meets at least a threshold without revealing exact holdings.",
        "slash_syntax": "/attest currency:<USD|RTM> amount:<amount>",
        "text_syntax": "{prefix}attest <usd|rtm> <amount>",
        "parameters": (
            "• `currency`: Certified currency (`USD` or `RTM`).\n"
            "• `amount`: Threshold balance you wish to certify."
        ),
        "slash_example": "/attest currency:USD amount:100",
        "text_example": "{prefix}attest usd 100",
        "example_note": "Compact text format accepted: `{prefix}attest 100usd`.",
        "prerequisites": "An active network and actual balance at least equal to the attested amount.",
        "advice": "Great for proving solvency to trade partners without exposing your total fortune.",
        "aliases": ["{prefix}certify", "{prefix}proof"],
        "linked_commands": ["trade"],
    },
    "top": {
        "name": "top",
        "category": "trade",
        "title": "🏆 `/top` — View Leaderboards",
        "description": "Displays the hall of fame for top network hackers across multiple categories.",
        "slash_syntax": "/top [category:<reputation|usd|events>]",
        "text_syntax": "{prefix}top [reputation|usd|events]",
        "parameters": (
            "• `category`: Ranking metric (`reputation` by default, `usd` for wealth, `events` for victories)."
        ),
        "slash_example": "/top category:events",
        "text_example": "{prefix}top events",
        "prerequisites": "None to view.",
        "advice": "You can toggle between leaderboard categories using buttons below the message.",
        "aliases": ["{prefix}leaderboard"],
        "linked_commands": ["rep"],
    },

    # ── Page 6: Language & Info ──────────────────────────────────
    "lang": {
        "name": "lang",
        "category": "info",
        "title": "🌐 `/lang` — Select Language",
        "description": "Configures your preferred display language for all Root bot messages and notifications.",
        "slash_syntax": "/lang [choice:<fr|en|reset>]",
        "text_syntax": "{prefix}lang [fr|en|reset]",
        "parameters": (
            "• `choice`: `fr` for French, `en` for English, `reset` to match your Discord client. "
            "Leave blank to check your current setting."
        ),
        "slash_example": "/lang choice:en",
        "text_example": "{prefix}lang en",
        "prerequisites": "None.",
        "advice": "Your language setting is stored with your account and follows you across Discord servers.",
        "aliases": ["{prefix}language"],
        "linked_commands": ["botinfo"],
    },
    "ping": {
        "name": "ping",
        "category": "info",
        "title": "🏓 `/ping` — Test Latency",
        "description": "Measures Discord Gateway heartbeat and bot response time.",
        "slash_syntax": "/ping",
        "text_syntax": "{prefix}ping",
        "parameters": "None.",
        "slash_example": "/ping",
        "text_example": "{prefix}ping",
        "prerequisites": "None.",
        "advice": "Useful to check if Discord or network lags are occurring.",
        "aliases": [],
        "linked_commands": ["botinfo"],
    },
    "botinfo": {
        "name": "botinfo",
        "category": "info",
        "title": "ℹ️ `/botinfo` — Root Bot Info",
        "description": "Displays Root bot overview statistics: system uptime, connected servers, and version.",
        "slash_syntax": "/botinfo",
        "text_syntax": "{prefix}botinfo",
        "parameters": "None.",
        "slash_example": "/botinfo",
        "text_example": "{prefix}botinfo",
        "prerequisites": "None.",
        "advice": "Gives a quick summary of bot health and server load.",
        "aliases": [],
        "linked_commands": ["invite", "ping"],
    },
    "invite": {
        "name": "invite",
        "category": "info",
        "title": "🔗 `/invite` — Bot Invite Link",
        "description": "Generates the official link to invite Root with recommended permissions to your Discord server.",
        "slash_syntax": "/invite",
        "text_syntax": "{prefix}invite",
        "parameters": "None.",
        "slash_example": "/invite",
        "text_example": "{prefix}invite",
        "prerequisites": "None.",
        "advice": "Share this link with friends or community managers to install Root on new servers.",
        "aliases": [],
        "linked_commands": ["botinfo"],
    },
}

COMMAND_ALIASES = {
    "n": "network",
    "cl": "claim",
    "cv": "convert",
    "sell": "convert",
    "cp": "compile",
    "hk": "hack",
    "events": "event",
    "e": "event",
    "h": "hash",
    "p": "pin",
    "d": "decode",
    "a": "anomaly",
    "b": "buffer",
    "s": "signal",
    "pa": "packet",
    "reputation": "rep",
    "certify": "attest",
    "proof": "attest",
    "leaderboard": "top",
    "language": "lang",
}

