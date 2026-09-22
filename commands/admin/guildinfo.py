"""
Commande d'administration : Inspection détaillée d'un serveur Discord (GuildInfo).

Fonctionnalités :
1. Réservée aux administrateurs détenant le rôle OP (OP_ROLE_ID).
2. Commande préfixée textuelle uniquement (non disponible en slash command) : `!guildinfo id`.
3. Embed épuré et lisible hors-serveur (aucun profil, salon ou rôle cliquable sous forme de mention).
4. Informations affichées :
   - Identité & Général (Nom, ID, Propriétaire, Date de création, Date d'arrivée du bot, Qui a invité le bot, Langue, Shard, Vanity).
   - Membres & Présences (Compte total, Membres en cache, Présences approx., Capacité max).
   - Salons & Organisation (Total, décompte textuel/vocal/catégorie/forum/fils, Salons clés en texte brut).
   - Rôles (Nombre total, Plus haut rôle et rôle booster en texte brut).
5. Deux boutons interactifs :
   - 'Liste des membres' (exporte la liste complète avec l'intent des membres).
   - 'Liste des salons' (exporte la liste détaillée et structurée de tous les salons du serveur).
"""

import io
from datetime import datetime, timezone

import discord
from discord.ext import commands

from utils import text
from utils.check import Check


class GuildInfoView(discord.ui.View):
    """Vue interactive attachée à l'Embed guildinfo proposant l'export des membres et des salons."""

    def __init__(self, bot: commands.Bot, guild: discord.Guild, author_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.author_id = author_id

    @discord.ui.button(label="Liste des membres", style=discord.ButtonStyle.primary, emoji="👥")
    async def show_members(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Déclenche la récupération exhaustive et l'envoi du listing des membres."""
        check = Check()
        # Contrôle de sécurité : l'auteur de la commande ou un membre OP peut consulter
        if interaction.user.id != self.author_id and not await check.is_op(self.bot, interaction.user.id):
            return await interaction.response.send_message(
                text.get(interaction, "guildinfo_no_permission"),
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        members = []

        # 1. Chunking si intents.members est activé pour peupler le cache
        if getattr(self.bot.intents, "members", False) and not getattr(self.guild, "chunked", False):
            try:
                await self.guild.chunk()
            except Exception:
                pass

        # 2. Récupération exhaustive via fetch_members si intents.members est présent
        if getattr(self.bot.intents, "members", False):
            try:
                async for member in self.guild.fetch_members(limit=None):
                    members.append(member)
            except Exception:
                members = list(self.guild.members)
        else:
            # 3. Repli direct via l'API HTTP REST si intents.members est inactif côté client
            try:
                after = None
                while True:
                    batch = await self.bot.http.get_members(self.guild.id, limit=1000, after=after)
                    if not batch:
                        break
                    for d in batch:
                        members.append(discord.Member(data=d, guild=self.guild, state=self.guild._state))
                    if len(batch) < 1000:
                        break
                    after = batch[-1]["user"]["id"]
            except Exception:
                members = list(self.guild.members)

        if not members:
            members = list(self.guild.members)

        total_members = len(members)
        humans = sum(1 for m in members if not m.bot)
        bots = sum(1 for m in members if m.bot)

        # Tri hiérarchique : rôle le plus élevé puis ordre alphabétique
        sorted_members = sorted(
            members,
            key=lambda m: (getattr(getattr(m, "top_role", None), "position", 0), m.name.lower()),
            reverse=True,
        )

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "=" * 80,
            f"LISTE DES MEMBRES DU SERVEUR : {self.guild.name} (ID: {self.guild.id})",
            f"Total : {total_members} membres | Humains : {humans} | Bots : {bots}",
            f"Généré le : {now_utc}",
            "=" * 80,
            "",
        ]

        for idx, m in enumerate(sorted_members, start=1):
            bot_tag = "[BOT]" if m.bot else "[USER]"
            joined = m.joined_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(m, "joined_at", None) else "N/A"
            created = m.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if getattr(m, "created_at", None) else "N/A"
            roles = ", ".join(f"@{str(getattr(r, 'name', r))}" for r in m.roles[1:]) if len(m.roles) > 1 else "Aucun"
            top_role = f"@{str(getattr(m.top_role, 'name', 'Aucun'))}" if hasattr(m, "top_role") else "Aucun"

            lines.append(f"[{idx:04d}] {m.name} (Surnom: {m.display_name}) {bot_tag}")
            lines.append(f"       ID : {m.id}")
            lines.append(f"       Créé le : {created} | Rejoint le : {joined}")
            lines.append(f"       Rôle supérieur : {top_role}")
            lines.append(f"       Rôles : {roles}")
            lines.append("-" * 80)

        report_bytes = "\n".join(lines).encode("utf-8")
        file_attachment = discord.File(io.BytesIO(report_bytes), filename=f"membres-{self.guild.id}.txt")

        embed = discord.Embed(
            title=text.get(interaction, "guildinfo_members_title", guild_name=self.guild.name),
            description=text.get(
                interaction,
                "guildinfo_members_summary",
                total=total_members,
                humans=humans,
                bots=bots,
            ),
            color=discord.Color.blurple(),
        )

        await interaction.followup.send(embed=embed, file=file_attachment, ephemeral=True)

    @discord.ui.button(label="Liste des salons", style=discord.ButtonStyle.secondary, emoji="💬")
    async def show_channels(self, button: discord.ui.Button, interaction: discord.Interaction):
        """Déclenche la récupération et l'envoi du listing détaillé de tous les salons."""
        check = Check()
        if interaction.user.id != self.author_id and not await check.is_op(self.bot, interaction.user.id):
            return await interaction.response.send_message(
                text.get(interaction, "guildinfo_no_permission"),
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)

        channels = list(self.guild.channels)
        total_channels = len(channels)
        text_channels = list(self.guild.text_channels)
        voice_channels = list(self.guild.voice_channels)
        categories = list(self.guild.categories)
        stage_channels = list(self.guild.stage_channels)
        forum_channels = list(self.guild.forum_channels)
        threads = list(self.guild.threads) if hasattr(self.guild, "threads") else []

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "=" * 80,
            f"LISTE DES SALONS DU SERVEUR : {self.guild.name} (ID: {self.guild.id})",
            f"Total : {total_channels} salons | Textuels : {len(text_channels)} | Vocaux : {len(voice_channels)} | Catégories : {len(categories)}",
            f"Généré le : {now_utc}",
            "=" * 80,
            "",
        ]

        # 1. Salons orphelins (sans catégorie)
        orphan_channels = [c for c in channels if getattr(c, "category", None) is None and c.type != discord.ChannelType.category]
        if orphan_channels:
            lines.append("📁 [HORS CATÉGORIE]")
            for ch in sorted(orphan_channels, key=lambda c: getattr(c, "position", 0)):
                ch_type = str(ch.type).replace("ChannelType.", "")
                lines.append(f"  ├── #{ch.name} (ID: {ch.id}) [{ch_type}]")
            lines.append("")

        # 2. Salons classés par catégorie
        for cat in sorted(categories, key=lambda c: getattr(c, "position", 0)):
            lines.append(f"📁 CATÉGORIE : {cat.name.upper()} (ID: {cat.id})")
            cat_channels = sorted(cat.channels, key=lambda c: getattr(c, "position", 0))
            if not cat_channels:
                lines.append("  └── (Aucun salon dans cette catégorie)")
            else:
                for idx, ch in enumerate(cat_channels, start=1):
                    prefix = "└──" if idx == len(cat_channels) else "├──"
                    details = []
                    if isinstance(ch, discord.TextChannel):
                        details.append(f"Position: {ch.position}")
                        if ch.topic:
                            topic_clean = ch.topic.replace("\n", " ")[:60]
                            details.append(f"Sujet: {topic_clean}")
                    elif isinstance(ch, discord.VoiceChannel):
                        details.append(f"Bitrate: {ch.bitrate // 1000}kbps")
                        if ch.user_limit:
                            details.append(f"Limite: {ch.user_limit} pers.")
                    ch_type = str(ch.type).replace("ChannelType.", "")
                    detail_str = f" - {', '.join(details)}" if details else ""
                    lines.append(f"  {prefix} #{ch.name} (ID: {ch.id}) [{ch_type}]{detail_str}")
            lines.append("")

        # 3. Fils de discussion actifs (Threads) si existants
        if threads:
            lines.append("🧵 FILS DE DISCUSSION ACTIFS (THREADS)")
            for th in threads:
                lines.append(f"  ├── #{th.name} (ID: {th.id}) [Parent: #{th.parent.name if th.parent else 'Inconnu'}]")
            lines.append("")

        report_bytes = "\n".join(lines).encode("utf-8")
        file_attachment = discord.File(io.BytesIO(report_bytes), filename=f"salons-{self.guild.id}.txt")

        embed = discord.Embed(
            title=text.get(interaction, "guildinfo_channels_title", guild_name=self.guild.name),
            description=text.get(
                interaction,
                "guildinfo_channels_summary",
                total_channels=total_channels,
            ),
            color=discord.Color.blue(),
        )

        embed.add_field(
            name="📊 Détails des salons",
            value=(
                f"• **Salons textuels** : {len(text_channels)}\n"
                f"• **Salons vocaux** : {len(voice_channels)}\n"
                f"• **Catégories** : {len(categories)}\n"
                f"• **Scènes** : {len(stage_channels)} | **Forums** : {len(forum_channels)}\n"
                f"• **Fils actifs (Threads)** : {len(threads)}"
            ),
            inline=False,
        )

        await interaction.followup.send(embed=embed, file=file_attachment, ephemeral=True)


class GuildInfo(commands.Cog):
    """Cog d'administration affichant les détails exhaustifs d'un serveur Discord."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check = Check()

    @commands.command(name="guildinfo")
    async def guildinfo(self, ctx: commands.Context, guild_id: int = None):
        """Affiche les informations complètes d'un serveur Discord par son ID (réservé OP)."""
        # 1. Vérification stricte du rôle OP
        if not await self.check.is_op(self.bot, ctx.author.id):
            return

        # 2. Résolution du serveur cible
        if guild_id is None:
            if ctx.guild is not None:
                guild_id = ctx.guild.id
            else:
                return await ctx.send(text.get(ctx, "guildinfo_usage"))

        guild = self.bot.get_guild(guild_id)
        if guild is None:
            try:
                guild = await self.bot.fetch_guild(guild_id, with_counts=True)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                guild = None

        if guild is None:
            return await ctx.send(text.get(ctx, "guildinfo_not_found", guild_id=guild_id))

        # Synchronisation éventuelle des salons et rôles si guild issue de fetch_guild
        if not guild.channels:
            try:
                await guild.fetch_channels()
            except Exception:
                pass
        if not guild.roles:
            try:
                await guild.fetch_roles()
            except Exception:
                pass

        # Synchronisation des membres en cache si intents.members est activé
        if getattr(self.bot.intents, "members", False) and not getattr(guild, "chunked", False):
            try:
                await guild.chunk()
            except Exception:
                pass

        # 3. Résolution du propriétaire (texte brut, aucun lien/mention cliquable)
        owner = guild.owner
        if owner is None and guild.owner_id:
            try:
                owner = await self.bot.fetch_user(guild.owner_id)
            except Exception:
                owner = None
        owner_display = (
            f"{owner.name} (ID: `{guild.owner_id}`)"
            if owner
            else f"ID: `{guild.owner_id}`"
        )

        # 4. Résolution de la date de join du bot et de qui l'a fait join
        bot_member = guild.me or guild.get_member(self.bot.user.id)
        if bot_member is None and hasattr(guild, "fetch_member"):
            try:
                bot_member = await guild.fetch_member(self.bot.user.id)
            except Exception:
                bot_member = None

        if bot_member and getattr(bot_member, "joined_at", None):
            bot_joined_ts = int(bot_member.joined_at.timestamp())
            bot_joined_str = f"<t:{bot_joined_ts}:F> (<t:{bot_joined_ts}:R>)"
        else:
            bot_joined_str = "Inconnue"

        inviter_display = "Inconnu (Audit Logs inaccessibles)"
        try:
            bot_me = guild.me
            if bot_me and getattr(getattr(bot_me, "guild_permissions", None), "view_audit_log", False):
                async for entry in guild.audit_logs(action=discord.AuditLogAction.bot_add, limit=10):
                    if getattr(entry, "target", None) and entry.target.id == self.bot.user.id:
                        if entry.user:
                            inviter_display = f"{entry.user.name} (ID: `{entry.user.id}`)"
                        break
        except Exception:
            pass

        # 5. Construction de l'Embed (100% lisible hors-serveur, zéro mention cliquable)
        embed = discord.Embed(
            title=f"🏛️ Informations Serveur · {guild.name}",
            color=discord.Color.blurple(),
        )

        if guild.description:
            embed.description = f"*{guild.description}*"

        # Visuels : icône en miniature, bannière ou splash en grande image
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        elif guild.splash:
            embed.set_image(url=guild.splash.url)

        # Champ 1 : Identité & Général
        created_ts = int(guild.created_at.timestamp())
        general_lines = [
            f"• **Nom** : `{guild.name}`",
            f"• **ID** : `{guild.id}`",
            f"• **Propriétaire** : {owner_display}",
            f"• **Création du serveur** : <t:{created_ts}:F> (<t:{created_ts}:R>)",
            f"• **Arrivée du bot** : {bot_joined_str}",
            f"• **Bot ajouté par** : {inviter_display}",
            f"• **Langue préférée** : `{guild.preferred_locale}`",
            f"• **Shard assigné** : Shard `{guild.shard_id}`",
        ]
        if getattr(guild, "vanity_url_code", None):
            general_lines.append(f"• **Lien personnalisé (Vanity)** : `discord.gg/{guild.vanity_url_code}`")
        embed.add_field(name="📌 Général", value="\n".join(general_lines), inline=False)

        # Champ 2 : Membres & Présences
        total_members = guild.member_count or len(guild.members) or "N/A"
        member_lines = [f"• **Membres totaux** : **{total_members}**"]
        if guild.members:
            humans = sum(1 for m in guild.members if not m.bot)
            bots = sum(1 for m in guild.members if m.bot)
            member_lines.append(f"• **Membres en cache** : {len(guild.members)} ({humans} humains, {bots} bots)")
        if getattr(guild, "approximate_presence_count", None) is not None:
            member_lines.append(f"• **Présences en ligne approx.** : {guild.approximate_presence_count}")
        if getattr(guild, "max_members", None):
            member_lines.append(f"• **Capacité maximale** : {guild.max_members} membres")
        embed.add_field(name="👥 Membres & Présences", value="\n".join(member_lines), inline=True)

        # Champ 3 : Rôles (en texte brut non cliquable)
        roles_count = len(guild.roles)
        highest_role = f"@{guild.roles[-1].name} (ID: `{guild.roles[-1].id}`)" if roles_count > 1 else "@everyone"
        booster_role = f"@{guild.premium_subscriber_role.name}" if guild.premium_subscriber_role else "Aucun"
        role_lines = [
            f"• **Total de rôles** : {roles_count}",
            f"• **Plus haut rôle** : {highest_role}",
            f"• **Rôle Nitro Booster** : {booster_role}",
        ]
        embed.add_field(name="🎭 Rôles", value="\n".join(role_lines), inline=True)

        # Champ 4 : Salons & Organisation (en texte brut non cliquable)
        channels_total = len(guild.channels)
        text_count = len(guild.text_channels)
        voice_count = len(guild.voice_channels)
        category_count = len(guild.categories)
        stage_count = len(guild.stage_channels)
        forum_count = len(guild.forum_channels)
        threads_count = len(guild.threads) if hasattr(guild, "threads") else 0

        channel_lines = [
            f"• **Total Salons** : {channels_total}",
            f"• **Détails** : 💬 {text_count} textuels | 🔊 {voice_count} vocaux | 📁 {category_count} catégories",
        ]
        if stage_count or forum_count or threads_count:
            channel_lines.append(f"• **Autres** : 🎙️ {stage_count} scènes | 📑 {forum_count} forums | 🧵 {threads_count} fils")

        special_channels = []
        if guild.system_channel:
            special_channels.append(f"Système : #{guild.system_channel.name} (ID: `{guild.system_channel.id}`)")
        if guild.rules_channel:
            special_channels.append(f"Règles : #{guild.rules_channel.name} (ID: `{guild.rules_channel.id}`)")
        if guild.public_updates_channel:
            special_channels.append(f"Mises à jour : #{guild.public_updates_channel.name} (ID: `{guild.public_updates_channel.id}`)")
        if guild.afk_channel:
            special_channels.append(f"AFK : 🔊 {guild.afk_channel.name} ({guild.afk_timeout // 60}m)")

        if special_channels:
            channel_lines.append(f"• **Salons clés** : {' • '.join(special_channels)}")

        embed.add_field(name="💬 Salons & Organisation", value="\n".join(channel_lines), inline=False)

        # Pied de page
        embed.set_footer(text=f"ID Serveur : {guild.id} • Root Admin")
        embed.timestamp = guild.created_at

        # 6. Vue avec 2 boutons : 'Liste des membres' et 'Liste des salons'
        view = GuildInfoView(self.bot, guild, ctx.author.id)
        await ctx.send(embed=embed, view=view)


def setup(bot: commands.Bot):
    """Charge le cog GuildInfo dans l'instance du bot."""
    bot.add_cog(GuildInfo(bot))
