text = {
    'g_already_handled': '> ℹ️ **Already Handled** · This confirmation has already been processed or expired.',
    'g_log_reputation': '> ⭐ **Honor** · <@{giver}> awarded `{points}` reputation point(s) to <@{recipient}>.',
    'g_log_title': '🛡️ Root OS · Event Log',
    'g_log_new_player': '> 👤 **New Node** · <@{player}> joined the network · Initial grant: `{usd} USD`.',
    'g_title': '{action}',
    'g_confirm': 'Confirm',
    'g_cancel': 'Cancel',
    'g_cancelled': '> 🚫 **Operation Cancelled** · The action was interrupted.',
    'g_empty': '*None*',
    'g_line': '> 🔹 **{label}**: {value}',
    'g_error_guild_only_command': '> ⛔ **Action unavailable in Direct Messages** · This command can only be executed within a Discord server.',
    'g_error_no_network': '> 🌐 **Node Not Found** · You do not have an active network yet. Use `/network` to create your player profile.',
    'g_error_database_unconfigured': '> ⚙️ **Maintenance Required** · The Root database must be configured and initialized by an administrator.',
    'g_error_database_unavailable': '> 🔌 **Connection Lost** · The database is temporarily unavailable. Try again in a moment.',
    'g_error_busy': '> ⏳ **System Busy** · Another operation is already in progress on your account. Please wait a moment.',
    'g_error_invalid_amount': '> ⚠️ **Invalid Amount** · Specify a positive number (max **2 decimals** in USD or **5** in RTM).',
    'g_error_insufficient_funds': '> 💳 **Insufficient Funds** · Your balance is too low to complete this transaction.',
    'g_error_insufficient_funds_usd': '> 💳 **Insufficient Funds** · Your balance is too low. Cost: **{usd} USD**.',
    'g_error_insufficient_funds_rtm': '> 💳 **Insufficient Funds** · Your balance is too low. Cost: **{rtm} RTM**.',
    'g_error_insufficient_funds_both': '> 💳 **Insufficient Funds** · Your balance is too low. Cost: **{usd} USD** · **{rtm} RTM**.',
    'g_error_upgrade_insufficient_funds': '> 💳 **Insufficient Funds** · Your balance is too low. You need **{usd} USD** to upgrade your firewall to **Level {level}**.',
    'g_error_invalid_selection': '> ❓ **Invalid Selection** · Invalid choice or item not found.',
    'g_error_buy_usage': '> ⚠️ **Invalid Syntax** · Usage for the `buy` command:\n\n🔹 **Syntax**: `{prefix}buy <type> [tier] [count|all] [confirm]`\n🔹 **Available types**: `mining`, `attack`, `defense`\n🔹 **Tiers**: `1` to `5` (default: `1`)\n🔹 **Quantity**: Positive integer (default: `1`)\n🔹 **Confirmation**: `confirm` *(optional, to immediately purchase)*\n\n💡 **Examples**:\n• `{prefix}buy mining` ➔ Quote for 1x mining T1\n• `{prefix}buy attack 2 5` ➔ Quote for 5x attack T2\n• `{prefix}buy defense 3 20 confirm` ➔ Immediate purchase of 20x defense T3',
    'g_error_rep_usage': '> ⚠️ **Invalid Syntax** · Usage for the `rep` command:\n\n🔹 **Syntax**: `{prefix}rep <@player>`\n🔹 **Description**: Award an honor/reputation point to another registered player.\n⏱️ **Cooldown**: 1 vote every 24h.\n\n💡 **Example**:\n• `{prefix}rep @Player`',
    'g_error_trade_usage': '> ⚠️ **Invalid Syntax** · Usage for the `trade` command:\n\n🔹 **Syntax**: `{prefix}trade <@player> <-resources to give> <+resources to request>`\n🔹 **Prefixes**:\n  • `-`: what you **give / send** (e.g. `-50usd`, `-1rtm`)\n  • `+`: what you **request / receive** (e.g. `+2rtm`, `+100usd`)\n🔹 **Tradable resources**: `usd` (max 2 decimals) and `rtm` (max 5 decimals)\n\n💡 **Examples**:\n• `{prefix}trade @Player -50usd +1rtm` ➔ You offer 50 USD in exchange for 1 RTM\n• `{prefix}trade @Player -100usd` ➔ Pure gift of 100 USD\n• `{prefix}trade @Player +2rtm` ➔ Pure request for 2 RTM',
    'g_trade_proposal_title': '🤝 Network Trade Proposal',
    'g_trade_proposal_desc': 'A resource trade was proposed between <@{initiator}> and <@{target}>.\n\n📤 **Sent by <@{initiator}>:**\n{send_lines}\n\n📥 **Sent by <@{target}>:**\n{receive_lines}\n\n{validation_status}',
    'g_trade_status_waiting_both': '⏳ *Waiting for both players to validate.*',
    'g_trade_status_waiting_initiator': '⏳ *Waiting for <@{initiator}> to validate.*',
    'g_trade_status_waiting_target': '⏳ *Waiting for <@{target}> to validate.*',
    'g_trade_status_initiator_ok': '✅ <@{initiator}> validated · Waiting for <@{target}>...',
    'g_trade_status_target_ok': '✅ <@{target}> validated · Waiting for <@{initiator}>...',
    'g_trade_success_summary': '> 🤝 **Trade Successfully Completed** · Transaction finalized across the network between <@{initiator}> and <@{target}>!',
    'g_trade_cancelled': '> 🚫 **Trade Cancelled** · The proposal was declined or interrupted.',
    'g_trade_timeout': '> ⏱️ **Trade Expired** · Validation time limit (3 minutes) elapsed without confirmation.',
    'g_trade_dm_received': '🤝 **Root Trade Report**\n\nYour exchange with **{partner}** was successfully validated!\n\n📦 **Resources received:**\n{received_lines}\n\n💸 **Resources sent:**\n{sent_lines}',
    'g_trade_no_resources': '• *No resources (0)*',
    'g_trade_forbidden': '> ⛔ **Unauthorized Action** · You are not allowed to interact with this trade.',
    'g_trade_not_allowed': '> ⛔ **Forbidden Action** · You are not allowed to do that.',
    'g_trade_btn_validate': 'Validate',
    'g_trade_btn_refuse': 'Refuse',
    'g_attest_usage': '> ⚠️ **Invalid Syntax** · Usage: `{prefix}attest <USD|RTM> <amount>`\n💡 **Example**: `{prefix}attest USD 500`',
    'g_attest_success': '✅ <@{user}> holds at least **{amount} {currency}** in their network.',
    'g_attest_failed': '🚫 <@{user}> does not hold at least **{amount} {currency}** in their network.',
    'g_reputation_dm_received': '⭐ **Reputation Point Received!**\n\nYou received **{points} reputation point** from **{giver}** (on *{server}*)!',
    'g_reputation_success': '⭐ You gave **{points} reputation point** to <@{recipient}>!',
    'g_error_quote_changed': '> 🔄 **Quote Updated** · Prices have changed. Rerun the command to confirm the updated quote.',
    'g_error_upgrade_in_progress': '> ⏳ **Upgrade Already in Progress** · A firewall upgrade to **Level {level}** is already in progress (finishes: <t:{timestamp}:R>).',
    'g_error_firewall_required': '> 🧱 **Firewall Required** · This action requires a **Level {level}** firewall minimum.',
    'g_error_maximum_level': '> 🛡️ **Maximum Level** · Your firewall has already reached maximum level.',
    'g_error_self_target': '> 🚫 **Invalid Target** · You cannot target your own network.',
    'g_error_cooldown': '> ⏱️ **Cooldown Active** · You cannot award reputation yet. Please return in **{time}**.',
    'g_error_claim_cooldown': '> ⏱️ **Cooldown Active** · You just claimed your mining. Try again in **{remaining}**.',
    'g_error_hourly_cooldown': '⏱️ Already claimed ! Come back in **{remaining}** !',
    'g_hourly_first': '💵 You received **{total} USD** ! Come back <t:{next_ts}:R> to start your combo ! 🔥 Combo : {streak}, bonus +{bonus}%',
    'g_hourly_combo': '💵 You received **{total} USD** ! Come back <t:{next_ts}:R> ! 🔥 Combo : {streak}, bonus +{bonus}%',
    'g_hourly_broken': '💵 You received **{total} USD** ! 💥 Combo lost. Come back <t:{next_ts}:R> ! 🔥 Combo : {streak}, bonus +{bonus}%',
    'g_hourly_broken_saver_prompt': '\n🛡️ **Combo Saver**: You lost a combo of **{lost_streak}** (+{lost_bonus}%). Would you like to use **1 Combo Saver Credit** to restore it for your next `/hr`? *(Available credits: {credits})*',
    'g_hourly_btn_save': '🛡️ Save combo (-1 credit)',
    'g_hourly_btn_no_credits': '🛡️ Save combo (0 credit)',
    'g_hourly_saved_success': '🛡️ **Combo restored!** Your combo of **{streak}** (+{bonus}%) will be active for your next `/hr`! *(Remaining credits: {credits})*',
    'g_error_insufficient_combo_saver_credits': '> 🛡️ **Insufficient Credits** · You do not have any Combo Saver credits to restore your combo.',
    'g_error_no_combo_to_save': '> ℹ️ **No Combo to Save** · You have no lost combo waiting to be restored.',
    'g_error_forbidden': '> ⛔ **Access Denied** · You do not have permission to perform this action.',
    'g_error_guild_required': '> 🏢 **Server Required** · This action must be performed within a server.',
    'g_error_target_not_registered': '> 👤 **Unregistered Player** · This user is not registered on Root yet!',
    'g_error_invalid_secret_id': '> ❓ **Invalid Secret ID** · This code is invalid or has expired.',
    'g_error_secret_id_exhausted': '> ⚠️ **Secret ID Unavailable** · Could not allocate a unique secret ID. Try again in a moment.',
    'g_error_compile_usage': '> ⚠️ **Invalid Syntax** · Usage for the `compile` command:\n\n🔹 **Syntax**: `{prefix}compile <method> [atk|all]`\n🔹 **Methods**: `unskilled` (unskilled humans), `skilled` (operators), `ai` (AI cluster)\n🔹 **ATK**: attack points to produce (`all` = maximum possible according to your Bit/s throughput)\n\n💡 **Examples**:\n• `{prefix}compile unskilled` ➔ Quote for your maximum throughput\n• `{prefix}compile skilled 50` ➔ 50 ATK via skilled operators\n• `{prefix}compile ai all` ➔ Max production via the AI cluster',
    'g_error_compile_in_progress': '> ⏳ **Production Already in Progress** · A **{atk} ATK** job ({method}) is already running (finishes: <t:{timestamp}:R>).',
    'g_error_compile_max_exceeded': '> ⚠️ **Capacity Exceeded** · You cannot compile more than **{max_atk} ATK** in a single order (limit set by your **{bits_per_s} Bit/s** throughput).',
    'g_error_no_attack_modules': '> ⚔️ **No Attack Modules** · Install an attack module (`/buy attack`) before compiling.',
    'g_net_title': '🌐 Root Network Terminal',
    'g_net_author': '{name}\'s Network',
    'g_net_status': '🟢 **Operational Node** · Deployed on {created}',
    'g_net_economy': '💳 Wallet & Economy',
    'g_net_economy_desc': '> 💵 **Dollars**: `{usd} USD`\n> ◈ **Rootium**: `{rtm} RTM`\n> ⭐ **Reputation**: `{reputation} pts`{rep_bonus_str}',
    'g_net_defense': '🛡️ Security & System',
    'g_net_defense_desc': '> 🧱 **Firewall**: `Lv. {firewall}/5`  {bar}\n> 🛡️ **Defense**: `{defense} pts`',
    'g_net_upgrade_progress': '> ⏳ *Lv. {level} upgrade in progress: <t:{timestamp}:R>*',
    'g_net_misc': '📊 Miscellaneous',
    'g_net_misc_desc': '> ⭐ **Reputation**: `{reputation} pts`',
    'g_net_firewall': '> 🧱 **Firewall**: `Lv. {firewall}/5`  {bar}',
    'g_net_network_defense': '> 🛡️ **Defense**: `{defense} pts`',
    'g_net_secret_name': '🔐 Secret ID',
    'g_net_secret_desc': '> 🔑 **Code**: `{secret_id}`\n> ⏳ Rotates: <t:{timestamp}:R>',
    'g_net_atk': '⚔️ Attack Points',
    'g_net_atk_stock': '> ⚔️ **ATK stock**: `{atk}`',
    'g_net_hack_progress': '> ⏳ *{method} production: **{atk} ATK** · <t:{timestamp}:R>*',
    'g_net_bays': '🗄️ Bays & Modules',
    'g_net_bay_row': '> `T{tier}` ❯ 🪙 `{mining}` · ⚔️ `{attack}` · 🛡️ `{defense}`',
    'g_net_bays_empty': '> *No modules equipped in bays.*',
    'g_net_rack_bay_title': '🖥️ **Bay {tier:02d}**',
    'g_net_rack_bay_stats': '🪙 `{m_count}x` ({m_power})  │  ⚔️ `{a_count}x` ({a_power})  │  🛡️ `{d_count}x` ({d_power})',
    'g_net_rack_total_title': '⚡ TOTAL INFRASTRUCTURE',
    'g_net_rack_total_hashrate': '• 🪙 **Global Hashrate**: `{hashrate}`',
    'g_net_rack_total_combat': '• ⚔️ **Attack**: `{attack}`  •  🛡️ **Bays**: `{defense}`',
    'g_net_rack_total_net_def': '• 🌐 **Network Defense**: `{defense}` *(Firewall Lv. {level})*',
    'g_net_rack_ram': '• 🧠 **Memory (RAM)**: `{used} / {total}` ({pct}%) · ⏳ Fills in: `{fill}`',
    'g_net_rack_mining': '• 🪙 **Mining**: `{rate} RTM/min`{rep_bonus_note} · 📥 claimable: `{pending} RTM`{full}',
    'g_net_mining_full': ' · 🔴 **FULL**',
    'g_net_ram_alert': '⚠️ **MEMORY FULL (100%)** · Mining paused! Claim to free up RAM.',
    'g_net_btn_claim': 'Claim',
    'g_net_btn_refresh': 'Refresh',
    'g_net_scan_progress': '• 🔍 Scan in progress: Analyzing {target} (<t:{timestamp}:R>)',
    'g_net_retaliation_anonymous': '• ⚖️ Retaliation authorized: **{count}** anonymous intrusion(s) (expires in {remaining})',
    'g_net_retaliation_identified': '• ⚖️ Retaliation authorized: Retaliation against {target} (expires in {remaining})',
    'g_net_claim_toast': 'Successfully extracted **{amount} RTM**!',
    'g_net_footer': 'Root OS • Node #{discord_id}',
    'g_infra_name_0': 'Jury-rigged smartphone',
    'g_infra_name_1': 'Custom desktop PC',
    'g_infra_name_2': 'Workstation',
    'g_infra_name_3': 'Dedicated server',
    'g_infra_name_4': 'Server room',
    'g_infra_name_5': 'Datacenter',
    'g_infra_desc_0': 'Improvised mobile workstation and local relay',
    'g_infra_desc_1': 'Modular desktop tower and network station',
    'g_infra_desc_2': 'High-performance workstation for intensive compute',
    'g_infra_desc_3': 'Professional rack-mounted server chassis',
    'g_infra_desc_4': 'Multiple server racks and dedicated facility',
    'g_infra_desc_5': 'Ultra-secure high-availability enterprise data center',
    'g_net_v2_header': 'ROOT OS / {name}',
    'g_net_v2_sub': '{infra_name} · Personal network · Active session',
    'g_net_v2_sub_hardware': '{infra_name} · Detailed hardware inventory',
    'g_net_v2_infra_title': '{infra_name} · Level {level}',
    'g_net_v2_farm_stat': '**Mining farm** · {count} miners ({hashrate})',
    'g_net_v2_compute_stat': '**Compute power** · {power}',
    'g_net_v2_defense_stat': '**Defense** · {bay_def} DEF (Bays) · {net_def} DEF (Network)',
    'g_net_v2_prod_stat': '**Production** · {rate} RTM/h',
    'g_net_v2_memory_stat': '**Memory (RAM)** · {bar} {pct}% ({used} / {total})',
    'g_net_v2_claim_stat': '**To claim** · {buffer} RTM',
    'g_net_v2_balances_stat': '**Wallet** · {usd} USD · {rtm} RTM · {reputation} reputation pts{rep_bonus_str}',
    'g_net_v2_status_operational': '**System operational** · Monitoring active',
    'g_net_v2_status_alert': '**Memory saturation alert** · Claim required',
    'g_net_v2_btn_claim': 'Claim',
    'g_net_v2_btn_hardware': 'Hardware',
    'g_net_v2_btn_station': 'Station',
    'g_net_v2_btn_refresh': 'Refresh',
    'g_net_v2_btn_back': 'Back',
    'g_net_v2_hardware_title': 'Installed bays and modules',
    'g_net_v2_hardware_tier_row': '**Tier {tier}**: {m_count}x Mining ({m_power}) · {a_count}x Attack ({a_power}) · {d_count}x Defense ({d_power})',
    'g_net_v2_hardware_empty': '*No modules installed in this bay.*',
    'g_pvp_v2_maintenance': '⚠️ **PvP V2 Maintenance** · This feature is temporarily unavailable during the deployment of the new electronic warfare system.',
    'g_pvp_v2_compile_deprecated': '> ⚠️ **ATK Production Disabled** · Manual ATK production is replaced by the V2 software development cycle. Use `/dev` or the Software button in your `/network`.',
    'g_pvp_v2_channel_busy': '> ⏱️ **Channel Busy** · A development job is already active on the **{channel}** channel. Wait for its completion or cancel it.',
    'g_pvp_v2_research_already_completed': '> 📦 **Research Already Completed** · You already own the research folder for this family and tier.',
    'g_pvp_v2_research_folder_required': '> 📁 **Research Folder Required** · You must first research and own the corresponding research folder to compile this software.',
    'g_pvp_v2_patch_already_installed': '> 🛡️ **Patch Already Active** · This patch is already installed and permanently protects your modules of this tier.',
    'g_pvp_v2_no_attack_module': '> ⚠️ **Zero Offensive Power** · You must own at least one attack module to power the offensive channel.',
    'g_pvp_v2_no_defense_module': '> ⚠️ **Zero Bay Defense** · You must own at least one bay defense module to power the defensive channel.',
    'g_error_channel_busy': '> ⏱️ **Channel Busy** · A development job is already active on the **{channel}** channel. Wait for completion or cancel it with `{prefix}dev cancel {channel}`.',
    'g_error_research_already_completed': '> 📦 **Research Already Completed** · You already hold the research folder for **{family} T{tier}**.',
    'g_error_research_folder_required': '> 📁 **Folder Required** · You must first research and hold the research folder for **{family} T{tier}** prior to compiling.',
    'g_error_patch_already_installed': '> 🛡️ **Patch Already Active** · This patch ({fingerprint}) is already installed and permanently protects your modules of this tier.',
    'g_error_no_attack_module': '> ⚠️ **No Offensive Power** · You must own at least one attack module to power the offense channel (`{prefix}buy attack`).',
    'g_error_no_defense_module': '> ⚠️ **No Bay Defense** · You must own at least one bay defense module to power the defense channel (`{prefix}buy defense`).',
    'g_error_insufficient_rootium': '> ⚠️ **Insufficient Funds** · Insufficient Rootium balance to fund this development (cost: **{rtm} RTM**).',
    'g_error_quote_changed': '> ⚠️ **Quote Expired** · Conditions or resources changed since the quote was generated. Please run the command again.',
    'g_error_no_active_job': '> ⚠️ **No Active Job** · No development job is currently active on the **{channel}** channel.',
    'g_error_patch_not_found': '> ⚠️ **Patch Not Found** · No matching patch found in your software library.',
    'g_error_fingerprint_collision': '> ⚠️ **Fingerprint Collision** · Unable to assign a unique fingerprint for this family. Please retry shortly.',
    'g_error_dev_start_usage': '> ⚠️ **Invalid Syntax** · Usage: `{prefix}dev start <research|compile|patch_research|patch_compile> <family> <tier> [fingerprint] [confirm]`',
    'g_error_dev_cancel_usage': '> ⚠️ **Invalid Syntax** · Usage: `{prefix}dev cancel <offense|defense>`',
    'g_pvp_v2_quote_header': '{e_ops} **SOFTWARE DEVELOPMENT QUOTE**',
    'g_pvp_v2_quote_body': (
        "> {e_log} **Type**: `{job_type_label}`\n"
        "> {e_con} **Family**: `{family}` · **Tier**: `T{tier}`{fp_str}\n"
        "> {e_con} **Channel**: `{channel_label}`\n"
        "> {e_pui} **Allocated Power**: `{power}`\n"
        "> {e_mem} **RTM Cost**: `{rtm_cost} RTM`\n"
        "> {e_tmp} **Estimated Duration**: `{duration}`\n\n"
        "*Confirm launching development with the buttons below.*"
    ),
    'g_pvp_v2_job_started': (
        "> {e_log} **Development Started** · `{job_type_label}` · `{family}` T{tier}{fp_str}\n"
        "> {e_con} **Channel**: `{channel_label}`\n"
        "> {e_mem} **Cost Paid**: `{rtm_cost} RTM`\n"
        "> {e_tmp} **Expected Delivery**: <t:{timestamp}:R> *(around <t:{timestamp}:t>)*"
    ),
    'g_pvp_v2_job_cancelled': '> {e_alt} **Development Cancelled** · The active job on channel `{channel_label}` has been cancelled. Engaged RTM was consumed.',
    'g_pvp_v2_delivered_dm': '> {e_mem} **DEVELOPMENT COMPLETE** · Your `{job_type_label}` job for **{family} T{tier}** is complete!\n> • **Fingerprint**: `{fingerprint}`\n> • View your library with `/network` (Software) or `/library`.',
    'g_pvp_v2_patch_installed': '> {e_fw} **Patch Deployed** · Patch for `{family}` (Fingerprint `{fingerprint}`) is now installed. Modules of this tier are protected.',
    'g_pvp_v2_library_title': '{e_mem} **SOFTWARE & PATCH LIBRARY**',
    'g_pvp_v2_library_active_jobs': '{e_tmp} **Active Development Jobs:**',
    'g_pvp_v2_library_no_active_jobs': '> *No active development jobs.*',
    'g_pvp_v2_library_folders': '{e_ops} **Owned Research Folders:**',
    'g_pvp_v2_library_no_folders': '> *No research folders.*',
    'g_pvp_v2_library_copies': '{e_log} **Compiled Software Copies:**',
    'g_pvp_v2_library_no_copies': '> *No compiled software.*',
    'g_pvp_v2_library_patches': '{e_fw} **Network Patches:**',
    'g_pvp_v2_library_no_patches': '> *No patches.*',
    'g_pvp_v2_btn_library': 'Software',
    'g_pvp_v2_btn_install': 'Install {fp}',
    'g_dev_syntax': (
        "{e_ops} **SOFTWARE DEVELOPMENT & PATCH CENTER (PvP V2)**\n\n"
        "The development cycle allows crafting offensive tools or defensive patches. "
        "You operate **two parallel computation channels**: the **offense** channel (powered by your attack modules) "
        "and the **defense** channel (powered by your bay defense modules).\n\n"
        "**Channels & Job Types:**\n"
        "> • `{prefix}dev start research <family> <tier>`\n"
        ">   Research a source folder (**offense**). Required prior to compiling.\n"
        "> • `{prefix}dev start compile <family> <tier>`\n"
        ">   Compile an executable software copy (**offense**). Uses an existing research folder.\n"
        "> • `{prefix}dev start patch_research <family> <tier> <fingerprint>`\n"
        ">   Research a countermeasure for a targeted fingerprint (**defense**).\n"
        "> • `{prefix}dev start patch_compile <family> <tier> <fingerprint>`\n"
        ">   Fabricate the network patch (**defense**). Ready to deploy to your server bays.\n\n"
        "**Available Commands:**\n"
        "> • `{prefix}dev start ... [confirm]`: Displays a cost quote, or starts immediately if `confirm` is specified.\n"
        "> • `{prefix}dev status`: Displays active development jobs.\n"
        "> • `{prefix}dev cancel <offense|defense>`: Aborts the active job on the specified channel (spent RTM is consumed).\n"
        "> • `{prefix}dev help`: Displays this lexicon and guide.\n"
        "> • `{prefix}library` (or `!lib`): Shows held research folders, compiled tools, and defensive patches.\n\n"
        "**Available Software Families:**\n"
        "> `hostile_miner`, `ransomware`, `currency_theft`, `saturation`, `network_scan`, `software_theft`, `espionage`"
    ),
    'g_welcome_lang_pick': '🌐 **Welcome to Root.** Choose your language:',
    'g_welcome_onboarding': '> 👋 **Network created.** Start by buying a **tier 1 miner** with `{prefix}buy`!\n> You can then mine with `{prefix}claim` and earn new USD with **events** (`{prefix}event`).',
    'g_shop_title': '🛒 Network Components Market',
    'g_shop_description': 'Upgrade your server racks and expand your infrastructure through three specialized branches.\nSelect a category below to browse the available components.',
    'g_shop_field_mining': '🪙 Mining Branch — USD',
    'g_shop_field_mining_desc': '**Role:** produces Rootium (**RTM**).\n• **Hashrate (H/s)** — Increases Rootium mining speed.\n• **RAM** — Increases the storage capacity for mined RTM before collecting it with `/claim`.\n• **Currency:** USD ($).',
    'g_shop_field_attack': '⚔️ Attack Branch — RTM',
    'g_shop_field_attack_desc': '**Role:** produces attack points (**ATK**) with `/compile`.\n• **Bandwidth (Bit/s)** — Speeds up attack point compilation.\n• **ATK Points** — Resource used to perform scans with `/scan` and launch attacks with `/hack`.\n• **Currency:** RTM.',
    'g_shop_field_defense': '🛡️ Defense Branch — USD',
    'g_shop_field_defense_desc': '**Role:** provides defense points to your infrastructure.\n• **Local Defense (DEF)** — Increases your infrastructure\'s defense points.\n• **Currency:** USD ($).',
    'g_shop_btn_mining': 'Mining',
    'g_shop_btn_attack': 'Attack',
    'g_shop_btn_defense': 'Defense',
    'g_shop_btn_close': 'Close',
    'g_shop_select_placeholder': 'Select a module to purchase...',
    'g_shop_select_empty': '⚠️ No module currently purchasable',
    'g_shop_cat_mining_title': '🛒 Hardware Market — Mining',
    'g_shop_cat_mining_desc': 'Mining modules increase your **Hashrate (H/s)** to extract Rootium and expand your **RAM** buffer to hold more RTM before claiming.',
    'g_shop_cat_attack_title': '🛒 Hardware Market — Attack',
    'g_shop_cat_attack_desc': 'Attack modules provide **Bit/s**. This digital throughput is required to compile **ATK** points (`{prefix}compile`), needed for scanning (`{prefix}scan`) and hacking.',
    'g_shop_cat_defense_title': '🛒 Hardware Market — Defense',
    'g_shop_cat_defense_desc': 'Defense modules add permanent **DEF** points to your racks, increasing overall network resilience against enemy scans.',
    'g_shop_syntax_field': '⌨️ Direct Command (Keyboard)',
    'g_shop_syntax_mining': '`{prefix}buy mining <tier>` or `/buy kind:mining tier:<tier>`\n*(e.g.: `{prefix}buy mining 1` for Tier 1)*',
    'g_shop_syntax_attack': '`{prefix}buy attack <tier>` or `/buy kind:attack tier:<tier>`\n*(e.g.: `{prefix}buy attack 1` for Tier 1)*',
    'g_shop_syntax_defense': '`{prefix}buy defense <tier>` or `/buy kind:defense tier:<tier>`\n*(e.g.: `{prefix}buy defense 1` for Tier 1)*',
    'g_shop_wallet_field': '💰 Your Current Resources',
    'g_shop_wallet_info': '• **Balance:** {balance}\n• **Firewall:** Level {fw}',
    'g_shop_no_affordable_hint': '*💡 No module of this type can be purchased with your current balance or firewall level.*',
    'g_buy_quote': 'Do you wish to install: **{item}**?\n• 💵 Cost: **{usd} USD**\n• ◈ Cost: **{rtm} RTM**\n• 💳 Remaining balance: {cur_usd} USD ➔ **{rem_usd} USD**\n• ⚡ Yield: **{stat_gain_formatted}**\n• 📈 New total: **{stat_new_formatted}** *(currently {stat_current_formatted})*\n\n*Confirm your purchase with the buttons below.*',
    'g_buy_quote_usd': 'Do you wish to install: **{item}**?\n• 💵 Cost: **{usd} USD**\n• 💳 Remaining balance: {cur_usd} USD ➔ **{rem_usd} USD**\n• ⚡ Yield: **{stat_gain_formatted}**\n• 📈 New total: **{stat_new_formatted}** *(currently {stat_current_formatted})*\n\n*Confirm your purchase with the buttons below.*',
    'g_buy_quote_rtm': 'Do you wish to install: **{item}**?\n• ◈ Cost: **{rtm} RTM**\n• 💳 Remaining balance: {cur_rtm} RTM ➔ **{rem_rtm} RTM**\n• ⚡ Yield: **{stat_gain_formatted}**\n• 📈 New total: **{stat_new_formatted}** *(currently {stat_current_formatted})*\n\n*Confirm your purchase with the buttons below.*',
    'g_buy_success': '> ✅ **Module Installed** · You successfully deployed: **{item}** for **{usd} USD** and **{rtm} RTM**!\n> Equipment bonus: **{stat_gain_formatted}** *(Total: {stat_new_formatted})*.',
    'g_buy_success_usd': '> ✅ **Module Installed** · You successfully deployed: **{item}** for **{usd} USD**!\n> Equipment bonus: **{stat_gain_formatted}** *(Total: {stat_new_formatted})*.',
    'g_buy_success_rtm': '> ✅ **Module Installed** · You successfully deployed: **{item}** for **{rtm} RTM**!\n> Equipment bonus: **{stat_gain_formatted}** *(Total: {stat_new_formatted})*.',
    'g_buy_quote_mining': 'Do you wish to install: **{item}**?\n• 💵 Cost: **{usd} USD**\n• 💳 Remaining balance: {cur_usd} USD ➔ **{rem_usd} USD**\n• 🪙 Mining power: **{stat_gain_formatted}** *(Total: {stat_new_formatted})*\n• 🧠 Memory (RAM): **{ram_gain_formatted}** *(Total: {ram_new_formatted})*\n\n*Confirm your purchase with the buttons below.*',
    'g_buy_success_mining': '> ✅ **Module Installed** · You successfully deployed: **{item}** for **{usd} USD**!\n> 🪙 Mining power: **{stat_gain_formatted}** *(Total: {stat_new_formatted})*\n> 🧠 Memory (RAM): **{ram_gain_formatted}** *(Total: {ram_new_formatted})*',
    'g_claim_success': '> ✅ **Mining Claimed** · You extracted **{amount} RTM** from your memory!\n> ◈ **New balance**: `{rtm_total} RTM`\n> 🧠 **Memory**: cleared — `0 o / {ram_total}` (0%)\n> 🪙 **Mining rate**: `{rate} RTM/min`{rep_bonus_note}{credits_hint}{rmd_hint}',
    'g_claim_rmd_rescheduled_hint': '\n> ⏰ **Reminder /rmd claim**: synchronized and postponed to **{time_to_full}** (100% saturation).',
    'g_claim_empty': '> 🧠 **Nothing to Claim** · Your memory holds no mined Rootium yet.\n> 🪙 **Mining rate**: `{rate} RTM/min`{rep_bonus_note} · 💾 Capacity: `{ram_total}`\n> ⏳ Memory full in **{time_to_full}**.{credits_hint}',
    'g_claim_no_miner': '> 🪙 **No Mining Module** · Install a mining module with `{prefix}buy mining` to start producing Rootium.',
    'g_claim_credits_hint': '\n> 🎫 **Autoclaim credits** : `{autoclaim_credits}` available (use `{prefix}claim auto <nb|all>`)',
    'g_claim_auto_started': '> 🤖 **Autoclaim activated** · **{activated_count}** automatic claim(s) queued as soon as RAM reaches 99.9%!\n> ⛏️ **Immediate claim**: **{amount} RTM** extracted · New balance: `{rtm_total} RTM` · Memory: `0 o / {ram_total}`\n> 🎫 **Remaining credits**: `{credits_remaining}` · **Active queued claims**: `{active_count}`\n> 📬 *You will receive the report of each claim via Direct Message (DM). Make sure your DMs are open on this server!*',
    'g_claim_auto_cancelled': '> 🛑 **Autoclaim cancelled** · **{refunded_count}** queued claim(s) have been cancelled and refunded.\n> 🎫 Autoclaim credits balance: **{autoclaim_credits}**.',
    'g_claim_auto_dm': '> 🤖 **Automatic claim executed** · Your memory reached **99.9%**!\n> ⛏️ **Rootium extracted**: **{amount} RTM**\n> ◈ **New balance**: `{rtm_total} RTM`\n> 🧠 **Memory**: cleared — `0 o / {ram_total}` (0%)\n> 🪙 **Mining rate**: `{rate} RTM/min`{rep_bonus_note}\n> 🎫 **Remaining queued claims**: `{remaining_active}` · Credits reserve: `{remaining_credits}`',
    'g_error_insufficient_autoclaim_credits': '> ❌ **Insufficient credits** · You have **{available}** autoclaim credit(s) (required: **{requested}**).',
    'g_error_invalid_autoclaim_count': '> ⚠️ **Invalid amount** · Usage: `{prefix}claim auto <nb|all>` or `{prefix}claim auto cancel`.',
    'g_error_no_miner_autoclaim': '> ⚠️ **No mining module** · You must own at least one mining module to activate autoclaim (`{prefix}buy mining`).',
    'g_error_no_active_autoclaim': '> ℹ️ **No active autoclaim** · You have no queued automatic claims to cancel.',
    'g_convert_quote': 'Do you want to sell your Rootium tokens?\n• 🪙 **Selling**: **{rtm} RTM**\n• 💵 **Received**: **{usd} USD**\n• 📈 **Rate**: **1 RTM = {rate} USD**\n• ◈ **RTM Balance**: {cur_rtm} RTM ➔ **{rem_rtm} RTM**\n• 💵 **USD Balance**: {cur_usd} USD ➔ **{rem_usd} USD**\n\n*Confirm the sale with the buttons below.*',
    'g_convert_success': '> ✅ **Tokens sold** · You sold **{rtm} RTM** for **{usd} USD**.\n> 📈 **Rate**: `1 RTM = {rate} USD`\n> 💵 **New balance**: `{usd_total} USD` · ◈ `{rtm_total} RTM`',
    'g_error_convert_usage': '> ⚠️ **Invalid Syntax** · Usage: `{prefix}convert <amount|all>` or `{prefix}sell all`\n🔹 Sell Rootium for dollars at a fixed rate.\n🔹 `{prefix}sell all` sells your entire RTM balance.\n\n💡 **Examples**:\n• `{prefix}convert 0.00002`\n• `{prefix}sell all`',
    'g_compile_quote': 'Do you want to start ATK production?\n• 🛠️ **Method**: **{method}**\n• 🎯 **Production**: **{atk} ATK**\n• ⚡ **Throughput**: **{bits}**\n• ◈ **Cost**: **{rtm} RTM**\n• ⏱️ **Duration**: **{duration}**\n\n*Confirm production with the buttons below.*',
    'g_compile_started': '> ⏳ **Production started** · **{atk} ATK** via **{method}** for **{rtm} RTM**.\n> • ⏱️ Estimated delivery: <t:{timestamp}:R> (<t:{timestamp}:f>).',
    'g_compile_delivered_dm': '> ⚔️ **Production complete** · **{atk} ATK** have been credited to your network.',
    'g_compile_method_unskilled': 'Unskilled humans',
    'g_compile_method_skilled': 'Skilled operators',
    'g_compile_method_ai': 'AI cluster',
    'g_upgrade_quote': 'Progression: **Level {current}** ➔ **Level {next}**\n• 💵 Cost: **{usd} USD**\n• 💳 Remaining balance: {cur_usd} USD ➔ {rem_usd}\n• ⏱️ Duration: **{duration}**\n\n✨ **Level {next} Advantages**:\n• 🛡️ **Network Defense**: **{defense_gain}** *(Total: {defense_next})*\n• 💰 **Hourly & Contracts Income**: Multiplied by **x{income_mult}** *(currently x{cur_income_mult})*\n• 🎁 **Event Bonus**: Event rewards multiplied by **x{multiplier}** *(currently x{cur_multiplier})*\n• 📦 **Unlocked Modules**: **{unlocked_modules}**{perks}\n\n*Do you want to confirm this upgrade?*',
    'g_upgrade_started': '> ⏳ **Upgrade in Progress** · Upgrade to **Level {level}** has started for **{usd} USD**!\n> • ⏱️ Estimated delivery: <t:{timestamp}:R> (<t:{timestamp}:f>).',
    'g_upgrade_delivered_dm': '> 🛡️ **Upgrade Complete** · Your firewall has been successfully upgraded to **Level {level}**!',
    'g_upgrade_success': '> ✅ **Upgrade Successful** · Your firewall has been upgraded to **Level {level}** for **{usd} USD**!',
    'g_top_title': '🏆 Leaderboard · {category_name}',
    'g_top_desc': 'Top Root network players in this category:\n',
    'g_top_empty': '> *No ranked players yet.*',
    'g_top_cat_reputation': '🌟 Reputation',
    'g_top_cat_usd': '💵 USD Treasury',
    'g_top_cat_rtm': '◈ Rootium Reserve',
    'g_top_cat_events': '🏆 Event Victories',
    'g_top_cat_hashrate': '⛏️ Hashrate Power (H/s)',
    'g_top_cat_hs': '⛏️ Hashrate Power (H/s)',
    'g_top_btn_rep': 'Reputation',
    'g_top_btn_usd': 'USD',
    'g_top_btn_rtm': 'Rootium',
    'g_top_btn_events': 'Events',
    'g_top_btn_hs': 'H/s',
    'g_top_footer': 'Root Leaderboard • Live Top 10',
    'g_top_footer_user': 'Root Leaderboard • Your position: #{rank} in Top 10',
    'g_hash_title': '🧩 HASH CHALLENGE',
    'g_hash_active_info': '🧩 **HASH CHALLENGE**\nTarget value between **{current_min}** and **{current_max}**.\n👥 **Competing players:** `{players_count}`\n⏱️ **Cooldown:** 1 guess every 8 minutes per player.\n⏳ **Your cooldown:** {cooldown_status}\n*Try your luck with `{prefix}hash <value>`*',
    'g_hash_cooldown_waiting': 'Available {remaining_ts} (`{remaining}`)',
    'g_hash_cooldown_ready': 'Available now ✅',
    'g_hash_player_cooldown': '⏳ **Rate limit!** You already submitted a guess for this hash.\nYou can try again {remaining_ts} (`{remaining}`).\n📊 Current range: **{current_min} — {current_max}**',
    'g_hash_too_low': '❌ **Too low.** (*Higher!*)\nRemaining range:\n**{current_min} — {current_max}**\n👥 **Competing players:** `{players_count}`',
    'g_hash_too_high': '❌ **Too high.** (*Lower!*)\nRemaining range:\n**{current_min} — {current_max}**\n👥 **Competing players:** `{players_count}`',
    'g_hash_won': '✅ **HASH VALIDATED**\n<@{winner}> won **${reward} USD**{mult_note}!',
    'g_hash_cooldown': '⏳ The last hash was found by {last_found_by} on server **{last_found_on}**.\nNext hash will be available in **{remaining}**.',
    'g_hash_cooldown_no_winner': '⏳ Next hash will be available in **{remaining}**.',
    'g_error_hash_usage': '⚠️ **Invalid Syntax** · Usage:\n• `{prefix}hash` ➔ View active challenge and remaining range\n• `{prefix}hash <value>` ➔ Submit a guess (1 try / 8 min)',
    'g_pin_title': '🔐 PIN CODE',
    'g_pin_active_info': '🔐 **PIN CODE**\nYour personal search range: **{current_min}** and **{current_max}**.\n🎯 Attempts: `{tries}` · 👥 **Competing players:** `{players_count}`\n*Try your luck with `{prefix}pin <value>`*',
    'g_pin_too_low': '❌ **Too low.** (*Higher!*)\nYour remaining range:\n**{current_min} — {current_max}**\n🎯 Attempts: `{tries}` · 👥 **Competing players:** `{players_count}`',
    'g_pin_too_high': '❌ **Too high.** (*Lower!*)\nYour remaining range:\n**{current_min} — {current_max}**\n🎯 Attempts: `{tries}` · 👥 **Competing players:** `{players_count}`',
    'g_pin_won': '✅ **PIN CODE CRACKED**\n<@{winner}> won **${reward} USD**{mult_note} in `{tries}` attempts!',
    'g_pin_cooldown': '⏳ The last PIN code was found by {last_found_by} on server **{last_found_on}**.\nNext PIN code will be available in **{remaining}**.',
    'g_pin_cooldown_no_winner': '⏳ Next PIN code will be available in **{remaining}**.',
    'g_error_pin_usage': '⚠️ **Invalid Syntax** · Usage:\n• `{prefix}pin` ➔ View active challenge and your remaining range\n• `{prefix}pin <value>` ➔ Submit a PIN code',
    'g_event_header': '📡 **LIVE NETWORK EVENTS**',
    'g_event_fw_banner': '> 🛡️ **Firewall Multiplier**: Event rewards multiplied by **x{fw_mult}** *(Firewall Level {fw_lvl})*.',
    'g_event_mult_bonus': ' *(Firewall Bonus x{mult})*',
    'g_event_hash_name': '🧩 **Hash Challenge** (`{prefix}hash`)',
    'g_event_hash_desc': 'Collective · 1,000 Range',
    'g_event_pin_name': '🔐 **PIN Code** (`{prefix}pin`)',
    'g_event_pin_desc': 'Individual · 150 Range',
    'g_event_status_active': '• Status: 🟢 **In progress** (*{desc}*) — `{prefix}{cmd}`',
    'g_event_status_cooldown': '• Status: ⏳ Available at **<t:{timestamp}:T>** (<t:{timestamp}:R>)',
    'g_event_last_winner': '• Last winner: {winner} on server **{server}**',
    'g_event_decode_name': '🔍 **Decryption** (`{prefix}decode`)',
    'g_event_decode_desc': '4x4 Grid · Coordinates sequence',
    'g_decode_title': '🔍 DECRYPTION',
    'g_decode_active_info': '🔍 **DECRYPTION IN PROGRESS**\nSequence to decode:\n▶ **{sequence}** ◀\n\n```\n{grid_display}\n```\n*Find the 4 corresponding letters and submit with `{prefix}decode <code>`*',
    'g_decode_wrong': '❌ **Incorrect code.** Check the coordinates and try again!\nSequence: **{sequence}**',
    'g_decode_won': '✅ **DECRYPTION SUCCESSFUL**\n<@{winner}> cracked the sequence first and won **${reward} USD**{mult_note}!\nValidated code: `{target}`',
    'g_decode_cooldown': '⏳ The last decryption was solved by {last_found_by} on server **{last_found_on}**.\nNext decryption will be available in **{remaining}**.',
    'g_decode_cooldown_no_winner': '⏳ Next decryption will be available in **{remaining}**.',
    'g_error_decode_usage': '⚠️ **Invalid Syntax** · Usage:\n• `{prefix}decode` ➔ View active grid and sequence\n• `{prefix}decode <code>` ➔ Submit decoded word',
    'g_event_anomaly_name': '⚠️ **Anomaly** (`{prefix}anomaly`)',
    'g_event_anomaly_desc': '10-line block · Glitched digit',
    'g_anomaly_title': '⚠️ ANOMALY DETECTION',
    'g_anomaly_active_info': '⚠️ **SYSTEM ANOMALY DETECTED**\nA rogue digit has infiltrated the 10-line data stream below.\nSpot the digit and count its line number (**from top to bottom, 1 to 10**).\n\n```\n{block_display}\n```\n*Submit the line number with `{prefix}anomaly <1-10>`*',
    'g_anomaly_wrong': '❌ **Wrong line.** The anomaly is not on line `{guess}`. Try again!',
    'g_anomaly_won': '✅ **ANOMALY NEUTRALIZED**\n<@{winner}> spotted the anomaly on line **{line}** (digit `{digit}`) and won **${reward} USD**{mult_note}!',
    'g_anomaly_cooldown': '⏳ The last anomaly was neutralized by {last_found_by} on server **{last_found_on}**.\nNext anomaly will be detected in **{remaining}**.',
    'g_anomaly_cooldown_no_winner': '⏳ Next anomaly will be detected in **{remaining}**.',
    'g_error_anomaly_usage': '⚠️ **Invalid line** · Please enter a line number between **1** and **10**.\nUsage: `{prefix}anomaly <1-10>`',
    'g_event_buffer_name': '📦 **Buffer** (`{prefix}buffer`)',
    'g_event_buffer_desc': '6 scrambled fragments · 6-letter code',
    'g_buffer_title': '📦 NETWORK BUFFER',
    'g_buffer_active_info': '📦 **SYSTEM BUFFER INTERCEPTED**\nReconstruct the 6-letter code by sorting fragments in order **1 to 6**.\n\n```\n{buffer_display}\n```\n*Submit reconstructed code with `{prefix}buffer <code>`*',
    'g_buffer_wrong': '❌ **Incorrect code.** The fragment order does not match. Try again!',
    'g_buffer_won': '✅ **BUFFER REORDERED**\n<@{winner}> realigned the buffer first and won **${reward} USD**{mult_note}!\nValidated code: `{target}`',
    'g_buffer_cooldown': '⏳ The last buffer was reconstructed by {last_found_by} on server **{last_found_on}**.\nNext buffer will be available in **{remaining}**.',
    'g_buffer_cooldown_no_winner': '⏳ Next buffer will be available in **{remaining}**.',
    'g_error_buffer_usage': '⚠️ **Invalid format** · Enter the 6-letter reconstructed code.\nUsage: `{prefix}buffer <code>`',
    'g_event_signal_name': '📡 **Signal** (`{prefix}signal`)',
    'g_event_signal_desc': '15-letter line · Majority letter',
    'g_signal_title': '📡 SIGNAL DETECTION',
    'g_signal_active_info': '📡 **NETWORK SIGNAL DETECTED**\nA short 15-letter stream has been intercepted.\nFind **the majority letter** that appears the most.\n\n```\n{block_display}\n```\n*Submit the letter with `{prefix}signal <letter>`*',
    'g_signal_wrong': '❌ **Wrong letter.** Letter `{guess}` is not the majority signal. Try again!',
    'g_signal_won': '✅ **SIGNAL IDENTIFIED**\n<@{winner}> isolated majority letter `{letter}` first and won **${reward} USD**{mult_note}!',
    'g_signal_cooldown': '⏳ The last signal was intercepted by {last_found_by} on server **{last_found_on}**.\nNext signal will broadcast in **{remaining}**.',
    'g_signal_cooldown_no_winner': '⏳ Next signal will broadcast in **{remaining}**.',
    'g_error_signal_usage': '⚠️ **Invalid letter** · Enter a single letter (A-Z).\nUsage: `{prefix}signal <letter>`',
    'g_event_packet_name': '🛰️ **Packet** (`{prefix}packet`)',
    'g_event_packet_desc': '1-10 stream · Missing packet',
    'g_packet_title': '🛰️ TRANSMISSION INTEGRITY',
    'g_packet_active_info': '🛰️ **INCOMPLETE TRANSMISSION DETECTED**\nA packet is missing from sequence **1 to 10**.\nIdentify the absent number among the 9 received packets below.\n\n```\n{block_display}\n```\n*Submit the missing packet with `{prefix}packet <1-10>`*',
    'g_packet_wrong': '❌ **Wrong packet.** Packet `{guess}` is not the missing one. Try again!',
    'g_packet_won': '✅ **TRANSMISSION RESTORED**\n<@{winner}> identified missing packet **#{missing}** first and won **${reward} USD**{mult_note}!',
    'g_packet_cooldown': '⏳ The last packet was recovered by {last_found_by} on server **{last_found_on}**.\nNext transmission will broadcast in **{remaining}**.',
    'g_packet_cooldown_no_winner': '⏳ Next transmission will broadcast in **{remaining}**.',
    'g_error_packet_usage': '⚠️ **Invalid packet** · Please enter a packet number between **1** and **10**.\nUsage: `{prefix}packet <1-10>`',
    # ── Scan PvP V2 ───────────────────────────────────────────────────────────
    'g_pvp_v2_scan_quote_header': '> {e_scan} **Network Scan** · Reconnaissance Quote',
    'g_pvp_v2_scan_quote_body': (
        "> {e_fw} **Target**: <@{target_id}> · Infrastructure Lv. **{victim_infra}**\n"
        "> {e_tmp} **Probe duration**: **{duration}s** (deferred job)\n"
        "> {e_pui} **Operational cost**: **{rtm_cost} RTM**\n"
        "{status_note}"
        "> *Confirm launching network scan?*"
    ),
    'g_pvp_v2_scan_started': (
        "> {e_scan} **Network scan started** · Probing <@{target_id}> for **{rtm_cost} RTM**.\n"
        "> • {e_tmp} **Estimated resolution**: <t:{timestamp}:R> (<t:{timestamp}:T>)"
    ),
    'g_pvp_v2_scan_report_header': '> {e_scan} **Network Probe Report** · <@{target_id}>',
    'g_pvp_v2_scan_quote_retaliation': '> ⚔️ *Active retaliation window (< 72h): level difference bypass granted.*\n',
    'g_pvp_v2_scan_dm_delivered': '> {e_scan} **Network Probe Completed** · The report for <@{target_id}> has been generated successfully.',
    'g_pvp_v2_scan_dm_victim_deleted': '> ⚠️ **Scan Failed** · Target <@{target_id}> was disconnected or removed from the network during the probe.',
    'g_error_scan_victim_deleted': '> ⚠️ **Scan failed** · Target was disconnected or removed from the network before resolution.',
    # ── PvP V2 — Offensive Operations & Diagnostics ──────────────────────────
    'g_pvp_v2_op_quote_header': '> {e_hack} **Offensive Deployment — Infection Quote** · <@{target_id}>',
    'g_pvp_v2_op_quote_body': (
        "> {e_ops} **Malware**: **{family_label}** · **Tier {tier}** `[{fingerprint}]`\n"
        "> {e_fw} **Target Defense**: **{victim_defense} DEF** *(slowdown ×{slowdown_mult:.2f})*\n"
        "> {e_tmp} **Installation Duration**: **{effective_duration}** *(base: {base_duration}s)*\n"
        "> {e_pui} **Persistent Effect**: Passive siphon of **15%** of target's Tier {tier} gross hashrate\n"
        "{status_note}"
        "> *Confirm stealth deployment with the buttons below.*"
    ),
    'g_pvp_v2_op_quote_retaliation': '> ⚔️ *Active retaliation window (< 72h): level difference bypass granted.*\n',
    'g_pvp_v2_op_started': (
        "> {e_hack} **Offensive Deployment Initiated**\n"
        "> Stealth installation of **{family_label} T{tier}** `[{fingerprint}]` underway targeting <@{target_id}>.\n"
        "> • {e_tmp} **Resolution & Activation**: <t:{timestamp}:R> (<t:{timestamp}:T>)\n"
        "> *The malware is installing silently in the background.*"
    ),
    'g_pvp_v2_op_dm_active': (
        "🦠 **OFFENSIVE OPERATION CONFIRMED**\n"
        "> Your **Hostile Miner T{tier}** `[{fingerprint}]` malware is now active on <@{victim_id}>'s network!\n"
        "> • ⚡ **Active Siphon**: 15% of their Tier {tier} gross mining is siphoned into your RAM buffer.\n"
        "> • 🛡️ *The infection will persist until the victim applies a defensive patch.*"
    ),
    'g_pvp_v2_op_dm_failed': (
        "⚠️ **OFFENSIVE OPERATION FAILED**\n"
        "> Your infection attempt on <@{victim_id}> has failed ({reason_label}).\n"
        "> • 💾 The software copy has been unlocked and returned to your inventory."
    ),
    'g_pvp_v2_diag_quote_header': '> {e_scan} **Network Integrity Diagnostic**',
    'g_pvp_v2_diag_quote_body': (
        "> {e_ops} **Deep Mining Traffic Analysis**\n"
        "> • 🪙 **Diagnostic Cost**: **{cost_rtm} RTM**\n"
        "> • ⏱️ **Execution Time**: Immediate\n\n"
        "*Run the diagnostic to detect any unauthorized siphoning or hostile malware on your miners.*"
    ),
    'g_pvp_v2_diag_clean': '> ✅ **Network integrity verified** · No hostile processes or active siphons detected on your miners.',
    'g_pvp_v2_diag_detected': (
        "> ⚠️ **NETWORK ANOMALY ALERT** · **{count}** hostile signature(s) detected on your miners!\n"
        "{malware_list}\n\n"
        "> 💡 *Develop and install a patch for the corresponding fingerprint to permanently neutralize the infection.*\n"
        "> 🔍 *Use `/hack trace` to analyze connections and identify the attacker.*"
    ),
    'g_pvp_v2_diag_malware_item': '> • 🦠 **{family_label} Tier {tier}** — Fingerprint: `{fingerprint}` *(Active since <t:{started_ts}:R>)*',
    # ── PvP V2 — Trace Analysis ───────────────────────────────────────────────
    'g_pvp_v2_trace_quote_header': '> 🔬 **Network Trace Analysis**',
    'g_pvp_v2_trace_quote_body': (
        "> 🔎 **Deep Hostile Traffic Analysis**\n"
        "> • 🦠 Signatures to analyze: **{count} malware(s)**\n"
        "> • 🪙 Analysis cost: **{cost_rtm} RTM**\n"
        "> • ⏱️ Delay: Immediate\n\n"
        "*Attempts to identify the attacker to gain a 72-hour retaliation right.*"
    ),
    'g_pvp_v2_trace_no_malware': '> ℹ️ **No trace detected** · No active malware present on your network.',
    'g_pvp_v2_trace_result_header': '> 🔬 **Network Trace Analysis Report**',
    'g_pvp_v2_trace_attacker_found': '> • 🎯 **Signature `[{fingerprint}]`** — Identified Author: <@{attacker_id}>',
    'g_pvp_v2_trace_attacker_unknown': '> • ❓ **Signature `[{fingerprint}]`** — Scrambled signal / Author self-protected with patch',
    'g_pvp_v2_trace_summary': (
        "> 📊 **{found}/{total}** attacker(s) identified.\n"
        "> ⚖️ *Active **72h** retaliation right granted against identified targets.*"
    ),
    # ── PvP V2 — Underground Market ───────────────────────────────────────────
    'g_pvp_v2_market_header': '> 🏪 **Root OS Underground Market** · Software & Patch Exchange',
    'g_pvp_v2_market_empty': '> ℹ️ No active listings on the market currently.',
    'g_pvp_v2_market_list_header': '🛒 **Available Marketplace Offers:**',
    'g_pvp_v2_market_my_listings_header': '💼 **Your Active Sale Listings:**',
    'g_pvp_v2_market_sell_quote_header': '> 🏷️ **Sell Listing — Quote**',
    'g_pvp_v2_market_sell_quote_body': (
        "> 📦 **Item**: **{family_label}** T{tier} `[{fingerprint}]`\n"
        "> 💵 **Asking Price**: **{price} USD**\n"
        "> 🏛️ **Market Fee** (5%): **{fee} USD**\n"
        "> 💰 **Estimated Net Gain**: **{net} USD**\n\n"
        "*Confirm publishing this listing? The item will be reserved.*"
    ),
    'g_pvp_v2_market_sell_started': (
        "> ✅ **Listing Published** · Your **{family_label}** T{tier} `[{fingerprint}]` is on sale for **{price} USD**.\n"
        "> • 🆔 Listing ID: `#{listing_id}`\n"
        "> • 💡 *Cancel anytime using `/market cancel {listing_id}`*"
    ),
    'g_pvp_v2_market_buy_quote_header': '> 🛒 **Market Purchase — Quote**',
    'g_pvp_v2_market_buy_quote_body': (
        "> 📦 **Item**: **{family_label}** T{tier} `[{fingerprint}]`\n"
        "> 👤 **Seller**: <@{seller_id}>\n"
        "> 💵 **Purchase Price**: **{price} USD**\n"
        "> 💳 **Balance After Transaction**: **{balance_after} USD**\n\n"
        "*Confirm direct purchase of this item?*"
    ),
    'g_pvp_v2_market_buy_success': (
        "> 🎉 **Purchase Complete!** · **{family_label}** T{tier} `[{fingerprint}]` added to your library.\n"
        "> • 💵 Paid: **{price} USD** · New Balance: **{new_balance} USD**"
    ),
    'g_pvp_v2_market_sold_dm': (
        "🏪 **MARKETPLACE SALE CONFIRMED**\n"
        "> Your **{family_label}** T{tier} `[{fingerprint}]` (Listing `#{listing_id}`) has been sold!\n"
        "> • 💰 **Net Earnings**: **+{net} USD** (New balance: **{new_balance} USD**)"
    ),
    'g_pvp_v2_market_cancel_success': '> ✅ **Listing `#{listing_id}` cancelled** successfully. Item returned to your library.',
    'g_error_market_listing_not_found': '> ❌ **Listing not found** or already closed.',
    'g_error_market_not_owner': '> ⛔ **Action Denied** · You do not own this listing.',
    'g_error_market_self_buy': '> 🚫 **Action Impossible** · You cannot purchase your own listing.',
    'g_error_market_not_resellable': '> ⛔ **Non-tradeable Item** · Stolen copies and installed patches cannot be resold.',
    'g_error_market_max_listings': '> ⛔ **Limit Reached** · You have reached the maximum of {max} active listings.',
    'g_error_market_item_reserved': '> ⏳ **Item Unavailable** · This item is already reserved in another listing or operation.',
    'g_error_market_usage': '> ⚠️ **Syntax**: `{prefix}market [list|mine|sell|buy|cancel]`',
    'g_error_trace_no_malware': '> ℹ️ **No trace** · No active malware on your network to analyze.',
    'g_error_insufficient_rootium': '> 💳 **Insufficient RTM** · You need **{rtm} RTM** to execute this action.',
    'g_error_ransomware_blocked': '> 🔒 **SYSTEM LOCKED BY RANSOMWARE**\n> Your economic commands are blocked by ransomware deployed by <@{attacker}>.\n> • 💰 Required ransom: **{ransom_rtm} RTM**\n> • 💡 Pay with `/pay` or develop a defensive patch with `/dev` to unlock your network.',
    'g_error_no_active_ransomware': '> ℹ️ No active ransomware locking your network currently.',
    # ── PvP V2 — Operation Errors ─────────────────────────────────────────────
    'g_error_no_software_copy': '> ⚠️ **Software copy required** · You do not own an available copy of this software (check `/library`).',
    'g_error_copy_already_reserved': '> ⏳ **Copy already reserved** · This software copy is already committed in another operation.',
    'g_error_victim_patched': '> 🛡️ **Target immunized** · The target network already has an active patch neutralizing this software fingerprint.',
    'g_error_fingerprint_already_active': '> ⚠️ **Infection already active** · Malware with the same fingerprint ({fingerprint}) is already active on this system.',
    'g_error_max_family_operations_reached': '> ⛔ **Limit reached** · You already have an active operation for family {family} (limit: 1 per family).',
    'g_error_max_total_operations_reached': '> ⛔ **Limit reached** · You have reached the limit of 3 concurrent offensive operations.',
    'g_error_op_self_target': '> 🚫 **Invalid target** · You cannot deploy malware against your own network.',
    'g_error_op_target_invulnerable': '> 🛡️ **Invulnerable target** · This network (Infrastructure Lv. 0) is out of PvP bounds.',
    'g_error_op_self_invulnerable': '> 🛡️ **Action not permitted** · Upgrade your infrastructure to Level 1 with `/upgrade` to participate in offensive operations.',
    'g_error_op_target_protected': '> 🔒 **Protected target** · You can only target networks with infrastructure level greater than or equal to yours (except under active retaliation < 72h).',
    'g_error_hack_usage_v2': '> ⚠️ **Invalid syntax** · Usage: `{prefix}hack <@target> [family] [tier] [confirm]` or `{prefix}hack diag` or `{prefix}hack trace`\n💡 **Examples**:\n• `{prefix}hack @Player` ➔ Quote to deploy Hostile Miner\n• `{prefix}hack diag` ➔ Network integrity diagnostic\n• `{prefix}hack trace` ➔ Network trace analysis',
    'g_scan_quote': '🔍 **Network scan of <@{target}>**\n• 🎯 Estimated probability: **{prob_base}%**\n• ◈ Base cost: **{rtm} RTM** · ⏱️ **90 seconds**\n• 💳 Remaining balance: {cur_rtm} RTM ➔ **{rem_rtm} RTM**\n\n*Choose your commitment level:*',
    'g_scan_btn_launch': '🚀 Launch ({prob}%) — {rtm} RTM',
    'g_scan_btn_boost2': '⚡ Boost ×2 ({prob}%) — {rtm} RTM',
    'g_scan_btn_boost5': '🔥 Boost ×5 ({prob}%) — {rtm} RTM',
    'g_scan_started': '> ⏳ **Scan launched** · Analyzing <@{target}>\'s network for **{rtm} RTM**.\n> • ⏱️ Estimated result: <t:{timestamp}:R>',
    'g_scan_success_dm': '> 🔑 **Scan successful!** · You breached <@{target}>\'s defenses!\n> • **Secret ID**: `{secret_id}`\n> • ⏳ Rotation: <t:{rotation_ts}:R>',
    'g_scan_failure_dm': '> ❌ **Scan failed** · <@{target}>\'s defenses repelled your intrusion.\n> • 💡 Boost your ATK stock with `/compile` or boost your next scan.',
    'g_scan_alert_anon': '> ⚠️ **Security Alert** · Your firewall (Lv. {level}) detected a scan attempt on your network.',
    'g_scan_alert_identified': '> ⚠️ **Security Alert** · <@{scanner}> attempted to scan your network!',
    'g_scan_expose_confirm': '⚠️ **You are about to publish Secret ID `{secret_id}` of <@{target}> in the public channel.**\nThis will allow **any player** to immediately launch a `/hack`. **Irreversible action.** Confirm?',
    'g_scan_exposed_public': '🔓 **DATA BREACH** · <@{scanner}> has exposed **{target_name}\'s** network!\n🔑 Secret ID: `{secret_id}`',
    'g_scan_expose_btn': '📢 Expose',
    'g_scan_keep_secret_btn': '🔒 Keep secret',
    'g_scan_expose_confirm_btn': '✅ Yes, expose',
    'g_scan_expose_cancel_btn': '❌ Cancel',
    'g_error_scan_in_progress': '> ⏳ **Scan already active** · Estimated result: <t:{timestamp}:R>.',
    'g_error_scan_no_atk': '> ⚔️ **No ATK stock** · Run `/compile` before scanning.',
    'g_error_scan_target_invulnerable': '> 🛡️ **Invulnerable target** · This network (Infrastructure Lv. 0) is outside the PvP zone.',
    'g_error_scan_self_invulnerable': '> 🛡️ **Action impossible** · Upgrade your infrastructure to Level 1 with `/upgrade` to participate in PvP.',
    'g_error_scan_target_protected': '> 🔒 **Protected target** · You can only target networks with an infrastructure level equal to or higher than yours (unless active retaliation under 72h).',
    'g_error_scan_usage': '> ⚠️ **Invalid syntax** · Usage: `{prefix}scan <@player> [confirm]`\n💡 **Example**: `{prefix}scan @Player`',
    'g_upgrade_quote_scan_alert_3': '🔎 **Scan detection**: you will be anonymously alerted of any intrusion attempt',
    'g_upgrade_quote_scan_alert_4': '🕵️ **Scanner identification**: the attacker\'s identity will be revealed to you',
    'g_upgrade_quote_perk_1': '⚔️ **PvP Arena Active**: Unlocks `/hack` attacks and `/scan` probes',
    'g_upgrade_quote_perk_5': '🏰 **Impenetrable Fortress**: Absolute maximum network protection (2,500 DEF)',
    'g_upgrade_modules_1': 'Attack T1 & T2, Mining T2, Defense T2',
    'g_upgrade_modules_2': 'Attack T3, Mining T3, Defense T3',
    'g_upgrade_modules_3': 'Attack T4, Mining T4, Defense T4',
    'g_upgrade_modules_4': 'Attack T5, Mining T5, Defense T5',
    'g_upgrade_modules_5': 'Maximum technological tier reached',
    # ── Hack (PvP) ────────────────────────────────────────────────────────────
    'g_hack_quote': '🖥️ **INTRUSION OPERATION**\n⚠️ Initializing offensive sequence\n• 🎯 Target system: `{secret_id}` (<@{target_id}>)\n• ⚡ Committed intrusion power: **{attack_points:,} ATK**\n• 🌐 Attack vector: **{zone_display}**\n• ⏱️ Estimated impact window: <t:{timestamp}:R> *(in 45 min)*\n• 💸 Resources available after deployment: **{remaining_atk:,} ATK**\n\n*Once the operation is launched, offensive resources will be locked and allocated to the intrusion protocol.*',
    'g_hack_btn_launch': '🔴 Deploy Attack ({attack_points:,} ATK)',
    'g_hack_started': '> 🖥️ **INTRUSION PROTOCOL INITIATED**\n> Deploying… **{attack_points:,} ATK** routed toward target node <@{target_id}>.\n> • 🌐 Attack vector: **{zone_display}**\n> • ⏱️ Protocol resolution: <t:{timestamp}:R>\n> *Your offensive resources are now locked until resolution.*',
    'g_hack_attacker_no_intrusion': '> 🖥️ **OPERATION REPORT — ACCESS DENIED**\n> `[ INTRUSION PROTOCOL TERMINATED ]`\n> • 🎯 Target node: <@{target_id}>\n> • ⚡ Deployed power: **{attack_points:,} ATK**\n> • 🛡️ Enemy resistance: **{total_defense:,} DEF** *(Firewall: {firewall_def:,} · Modules: {module_def:,})*\n> • 💥 Defenses neutralized: **{destroyed_defense:,} DEF**\n> • ❌ **INTRUSION FAILED** — Enemy defense protocol absorbed the assault. System access denied.',
    'g_hack_attacker_intrusion_attack': '> 🖥️ **OPERATION REPORT — ACCESS GRANTED**\n> `[ INTRUSION CONFIRMED ✓ ]`\n> • 🎯 Compromised node: <@{target_id}>\n> • ⚡ Deployed power: **{attack_points:,} ATK** vs 🛡️ **{total_defense:,} DEF**\n> • 💥 Defenses neutralized: **{destroyed_defense:,} DEF**\n> • 🔫 **PAYLOAD EXECUTED** — Enemy attack module **Tier {tier}** destroyed. Enemy strike capacity reduced.',
    'g_hack_attacker_intrusion_mining': '> 🖥️ **OPERATION REPORT — ACCESS GRANTED**\n> `[ INTRUSION CONFIRMED ✓ ]`\n> • 🎯 Compromised node: <@{target_id}>\n> • ⚡ Deployed power: **{attack_points:,} ATK** vs 🛡️ **{total_defense:,} DEF**\n> • 💥 Defenses neutralized: **{destroyed_defense:,} DEF**\n> • 📦 **EXFILTRATION SUCCESSFUL** — **Tier {tier}** mining module captured and integrated into your infrastructure.',
    'g_hack_attacker_intrusion_empty': '> 🖥️ **OPERATION REPORT — ACCESS GRANTED**\n> `[ INTRUSION CONFIRMED ✓ ]`\n> • 🎯 Compromised node: <@{target_id}>\n> • ⚡ Deployed power: **{attack_points:,} ATK** vs 🛡️ **{total_defense:,} DEF**\n> • 💥 Defenses neutralized: **{destroyed_defense:,} DEF**\n> • ⬛ **EMPTY SECTOR** — No exploitable assets detected in the targeted zone.',
    'g_hack_victim_no_intrusion': '> 🖥️ **ROOT OS — NETWORK ALERT**\n> `[ INTRUSION REPELLED ✓ ]`\n> Unauthorized access attempt detected from <@{attacker_id}> — **{attack_points:,} ATK** deployed against your system.\n> • 🛡️ System resistance: **{total_defense:,} DEF** — Breach neutralized before penetration.\n> • 💥 Defense modules damaged: **{destroyed_defense:,} DEF**\n> • 🔥 Firewall operational — Core node intact.\n> • ⚖️ Retaliation rights active against <@{attacker_id}> — **72h**\n> • 🔑 New Secret ID assigned: ||{new_secret_id}||',
    'g_hack_victim_intrusion_attack': '> 🖥️ **ROOT OS — CRITICAL ALERT**\n> `[ INTRUSION CONFIRMED — ACTIVE BREACH ]`\n> Your system was compromised by <@{attacker_id}> — **{attack_points:,} ATK** pierced your defenses ({total_defense:,} DEF).\n> • 💥 Defense modules damaged: **{destroyed_defense:,} DEF**\n> • 🔫 **CONFIRMED DAMAGE** — Attack module **Tier {tier}** destroyed by enemy payload.\n> • 🔥 Firewall operational — Core node intact.\n> • ⚖️ Retaliation rights active against <@{attacker_id}> — **72h**\n> • 🔑 New Secret ID assigned: ||{new_secret_id}||',
    'g_hack_victim_intrusion_mining': '> 🖥️ **ROOT OS — CRITICAL ALERT**\n> `[ INTRUSION CONFIRMED — ACTIVE BREACH ]`\n> Your system was compromised by <@{attacker_id}> — **{attack_points:,} ATK** pierced your defenses ({total_defense:,} DEF).\n> • 💥 Defense modules damaged: **{destroyed_defense:,} DEF**\n> • 📦 **EXFILTRATION DETECTED** — **Tier {tier}** mining module captured and transferred to the enemy infrastructure.\n> • 🔥 Firewall operational — Core node intact.\n> • ⚖️ Retaliation rights active against <@{attacker_id}> — **72h**\n> • 🔑 New Secret ID assigned: ||{new_secret_id}||',
    'g_hack_victim_intrusion_empty': '> 🖥️ **ROOT OS — CRITICAL ALERT**\n> `[ INTRUSION CONFIRMED — ACTIVE BREACH ]`\n> Your system was compromised by <@{attacker_id}> — **{attack_points:,} ATK** pierced your defenses ({total_defense:,} DEF).\n> • 💥 Defense modules damaged: **{destroyed_defense:,} DEF**\n> • ⬛ **EMPTY SECTOR** — The intruder found no exploitable assets in the targeted zone.\n> • 🔥 Firewall operational — Core node intact.\n> • ⚖️ Retaliation rights active against <@{attacker_id}> — **72h**\n> • 🔑 New Secret ID assigned: ||{new_secret_id}||',
    'g_error_hack_self_invulnerable': '> 🖥️ **ACCESS DENIED** — Your node is not registered in the PvP protocol. Activate your firewall with `/upgrade` to join operations.',
    'g_error_hack_target_invulnerable': '> 🖥️ **TARGET OFF-PROTOCOL** — This node (Firewall Lv. 0) is not reachable via the offensive network.',
    'g_error_hack_target_protected': '> 🖥️ **ACCESS DENIED — PROTECTED SIGNATURE** — You can only target nodes with a firewall ≥ yours. Exception: active retaliation rights (72h).',
    'g_error_hack_target_in_progress': '> 🖥️ **NODE LOCKED** — An intrusion operation is already running on this system. Wait for resolution.',
    'g_error_hack_insufficient_atk': '> 🖥️ **INSUFFICIENT RESOURCES** — Available offensive stock: **{available:,} ATK** · Required: **{requested:,} ATK**. Run `/compile` to produce attack points.',
    'g_error_hack_usage': '> ⚠️ **Invalid syntax** · Usage: `{prefix}hack <secret_id> <attack_points> <mining|attack> [confirm]`\n💡 **Example**: `{prefix}hack 482910 500 mining`',
    'g_hack_btn_cancel': '⛔ Abort',
    'g_error_beta_access_required': '> 🔒 **Restricted Beta Access** · The Root network is currently in closed beta for authorized players only. An active participant can sponsor you by awarding you a reputation point via `/rep <@you>` (make sure you initialized your network with `/network`).',
    'g_reputation_beta_granted': '\n🎉 **Beta Access Granted!** <@{recipient}> has been added to authorized players and can now access the full game.',
    'g_reputation_beta_autoclaim': '🎫 <@{giver}> receives **{credits} autoclaim credits** and **{combo_savers} Combo Saver credit** for this sponsorship.',
    'g_reputation_dm_beta_granted': '🎉 **Congratulations!** You have also received permanent access to the Root Beta! All game features are now open to you.',
    'g_error_contract_in_progress': '> ⏳ **Contract in Progress** · You already have an active work contract (deadline: <t:{timestamp}:R>).',
    'g_error_no_active_contract': '> 📄 **No Active Contract** · You do not have any contract in progress. Use `/contract` to pick a mission.',
    'g_error_contract_not_ready': '> ⏱️ **Contract in Progress** · Your mission is not completed yet. Come back in **{remaining}**!',
    'g_error_invalid_contract_duration': '> ⚠️ **Invalid Duration** · Choose a valid duration: `short` (30m), `medium` (2h), or `long` (6h).',
    'g_contract_special_badge': '⭐ **Special Mission (+40% USD active)**\n',
    'g_contract_offers': '{special_badge}**{agency}** · Available Contracts:\n\n> ⏱️ **Short** (30 min): `{short_usd} USD`\n> ⏱️ **Medium** (2 hours): `{medium_usd} USD`\n> ⏱️ **Long** (6 hours): `{long_usd} USD`\n\nAgency Loyalty: `{fidelity_bar}` **{fidelity}/{threshold}**{fidelity_hint}',
    'g_contract_active': '{special_badge}**{agency}** · Active Contract:\n\n> 💼 **Mission**: {title}\n> 💵 **Reward**: `{reward_usd} USD`\n> ⏱️ **Deadline**: <t:{expires_ts}:R> *(around <t:{expires_ts}:t>)*',
    'g_contract_ready': '{special_badge}**{agency}** · Contract Completed!\n\n> 💼 **Mission**: {title}\n> 💵 **Reward**: `{reward_usd} USD`\n\nClick below to collect your salary.',
    'g_contract_collected': '💵 **Payment Collected!** Mission *{title}* completed for **{agency}**.\n> 💵 **Reward**: `+{reward_usd} USD`\n> 💰 **New Balance**: `{new_dollars} USD`',
    'g_contract_btn_short': 'Short (30m)',
    'g_contract_btn_medium': 'Medium (2h)',
    'g_contract_btn_long': 'Long (6h)',
    'g_contract_btn_collect': 'Collect {usd} USD',
    # ── Reminders (/rmd) & Contrats ───────────────────────────────────────────
    'g_rmd_syntax': (
        "### `{prefix}rmd` Command Syntax\n\n"
        "**⚡ Automatic Game Reminders:**\n"
        "> • `{prefix}rmd all` — Enable all possible game reminders (hourly, claim, events).\n"
        "> • `{prefix}rmd hourly` — Alerts as soon as the hourly reward is ready.\n"
        "> • `{prefix}rmd claim` — Alerts when your mining RAM buffer hits 100%.\n"
        "> • `{prefix}rmd events` — Alerts when the next network mini-game starts.\n\n"
        "**⏱️ Custom Timers:**\n"
        "> • `{prefix}rmd <duration> [note]` — Custom timer from 10s to 30 days.\n"
        "> *(Examples: `{prefix}rmd 30m coffee`, `{prefix}rmd 2h check contracts`, `{prefix}rmd 45s`)*\n\n"
        "**📋 Manage Your Reminders:**\n"
        "> • `{prefix}rmd list` — Show all your pending reminders.\n"
        "> • `{prefix}rmd cancel <id>` — Cancel a specific reminder.\n"
        "> • `{prefix}rmd cancel all` — Clear all your active reminders.\n\n"
        "💡 *Delivered directly via DM (with channel fallback if your DMs are closed).*"
    ),
    'g_rmd_created_smart': '> ✅ **Reminder set** · {target_name} in **{duration}** (<t:{ts}:R>).',
    'g_rmd_created_custom': '> ✅ **Reminder set** · In **{duration}** (<t:{ts}:R>): **{message}**.',
    'g_rmd_created_all_title': '**Root Reminders Activation (/rmd all)**',
    'g_rmd_created_all_created': '> ✅ **{target_name}**: scheduled in **{duration}** (<t:{ts}:R>)',
    'g_rmd_created_all_available': '> ℹ️ **{target_name}**: already available! ({cmd})',
    'g_rmd_created_all_already': '> ⏳ **{target_name}**: already active (<t:{ts}:R>)',
    'g_rmd_created_all_no_miner': '> ⚠️ **{target_name}**: no active miner',
    'g_rmd_already_available': '> ℹ️ **{target_name} is already available!** You can use it right now with `{cmd}`.',
    'g_rmd_list_title': '**Your Active Reminders**',
    'g_rmd_list_empty': '> ℹ️ You have no active reminders pending.',
    'g_rmd_list_item': '> • **#{id}** · <t:{ts}:R> · `{type}` : {message}',
    'g_rmd_cancel_success': '> ✅ **Reminder #{id} cancelled** successfully.',
    'g_rmd_cancel_all_success': '> ✅ **All your reminders ({count}) have been cancelled**.',
    'g_rmd_dm_notification': '🔔 **ROOT OS REMINDER**\n> {message}\n> ⏱️ *Scheduled for <t:{ts}:t>*',
    'g_rmd_fallback_notification': '{user} 🔔 **Reminder** : {message}',
    'g_contract_expired_dm': '💼 **MISSION COMPLETED** · Your work contract for **{agency}** (*{title}*) has reached completion!\n> 💵 Available reward: **{reward_usd} USD**\n> 💡 Collect your payment now with `/contract collect`.',
    'g_error_reminder_limit_reached': '> ⛔ **Limit reached** · You already have {max_count} active reminders. Use `{prefix}rmd cancel <id|all>` to free up slots.',
    'g_error_invalid_duration': '> ⚠️ **Invalid duration format** · Valid examples: `30s`, `15min`, `2h`, `1h30m`, `1d`.',
    'g_error_duration_out_of_range': '> ⚠️ **Duration out of range** · Duration must be between 10 seconds and 30 days.',
    'g_error_reminder_not_found': '> ❌ **Reminder not found** or already expired.',
}

descriptions = {
    'network': 'Create or inspect your Root network.',
    'buy': 'Buy a module or defense after confirmation.',
    'upgrade': 'Upgrade your firewall.',
    'claim': 'Claim mined Rootium and empty your memory (RAM).',
    'rep': 'Give a reputation point.',
    'top': 'View leaderboards.',
    'hash': 'Participate in the Hash Challenge to crack the corrupted hash and win USD.',
    'pin': 'Crack the secret PIN code before other players to win USD.',
    'decode': 'Decode the coordinate sequence in the 4x4 grid to win USD.',
    'anomaly': 'Spot the rogue digit in the 10-line data stream to win USD.',
    'buffer': 'Reconstruct the secret code by reordering the 6 buffer fragments.',
    'signal': 'Isolate the majority letter in the 15-letter stream to win USD.',
    'packet': 'Identify the missing packet number between 1 and 10 to win USD.',
    'event': 'View status and remaining time before each network event.',
    'trade': 'Trade resources (USD and Rootium) with another player.',
    'convert': 'Sell Rootium for dollars at a fixed rate.',
    'compile': 'Produce a chosen amount of ATK from your attack module throughput.',
    'scan': 'Scan a player\'s network to discover their secret identifier.',
    'hack': 'Launch a PvP cyberattack against an enemy network.',
    'hourly': 'Claim your hourly USD reward with streak combo bonus.',
    'contract': 'Consult, accept, or collect guaranteed work contracts for USD.',
    'rmd': 'Schedule, view, or cancel time-based reminders.',
    'dev': 'Manage the software and patch development cycle.',
    'library': 'View your library of folders, software copies, and patches.',
    'market': 'Access the Underground Market for software, patches, and research folders.',
    'trace': 'Analyze network traces to identify hostile attackers.',
    'pay': 'Pay the ransom of an active ransomware.',
}

labels = {
    'attack': 'Attack',
    'bay_defense': 'Bay Defense',
    'category': 'Category',
    'defense': 'Defense',
    'firewall': 'Firewall',
    'invalid_selection': 'Invalid choice',
    'kind': 'Type',
    'mining': 'Mining',
    'network_defense': 'Network Defense',
    'next_reputation_at': 'Next Reputation UTC',
    'reputation': 'Reputation',
    'rtm': 'Rootium (RTM)',
    'score': 'Score',
    'status': 'Status',
    'success': 'Success',
    'target': 'Target',
    'tier': 'Tier',
    'type': 'Type',
    'usd': 'Dollars (USD)',
    'act_network': '🌐 Network Terminal',
    'act_buy': '🛒 Component Purchase',
    'act_upgrade': '🧱 Firewall Upgrade',
    'act_claim': '🪙 Mining Harvest',
    'act_hourly': '⏱️ Hourly Reward',
    'act_reputation': '⭐ Reputation Award',
    'act_top': '🏆 Global Leaderboard',
    'act_hash': '🧩 Hash Challenge',
    'act_pin': '🔐 PIN Code',
    'act_decode': '🔍 Decryption',
    'act_anomaly': '⚠️ System Anomaly',
    'act_buffer': '📦 Network Buffer',
    'act_signal': '📡 Network Signal',
    'act_packet': '🛰️ Network Packet',
    'act_event': '📡 Network Events',
    'act_trade': '🤝 Resource Trade',
    'act_convert': '💱 Token Sale',
    'act_compile': '⚔️ ATK Production',
    'act_scan': '🔍 Network Scan',
    'act_hack': '⚔️ PvP Attack',
    'act_contract': '💼 Work Contracts',
    'act_rmd': '🔔 Reminder & Alert',
    'act_dev': '💻 Software Development',
    'act_library': '💾 Software Library',
    'act_market': '🏪 Underground Market',
    'act_trace': '🔬 Trace Analysis',
    'act_pay': '🔓 Ransom Payment',
}
