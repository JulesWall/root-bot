"""Offline checks for the standalone demo; never starts or logs in the bot."""
import importlib.util
import itertools
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

import discord

SPEC = importlib.util.spec_from_file_location(
    "root_demo", Path(__file__).resolve().parents[1] / "demo_embeds.py"
)
demo = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(demo)


class Emoji(discord.PartialEmoji):
    def __init__(self, name, identifier, animated=False, usable=True):
        super().__init__(name=name, id=identifier, animated=animated)
        self.usable = usable

    def is_usable(self):
        return self.usable


def components(items):
    for item in items:
        yield item
        yield from components(item.get("components", []))


class DemoTests(unittest.IsolatedAsyncioTestCase):
    def make_emojis(self):
        return {name: Emoji(f"root_{name}", 100000000000000000 + i, animated=True)
                for i, name in enumerate(demo.FALLBACKS)}

    def button(self, view, command):
        return next(item for item in view.walk_children()
                    if isinstance(item, discord.ui.Button)
                    and item.custom_id == f"root_demo:{command}")

    async def click(self, view, command):
        interaction = SimpleNamespace(response=SimpleNamespace(edit_message=AsyncMock()))
        await self.button(view, command).callback(interaction)
        interaction.response.edit_message.assert_awaited_once_with(view=view)

    async def test_emoji_selection(self):
        static = Emoji("root_scan", 200)
        animated = Emoji("root_scan", 100, animated=True)
        unavailable = Emoji("root_scan", 300, animated=True, usable=False)
        unrelated = Emoji("scan", 400)
        result = demo.select_emojis([animated, static, unavailable, unrelated])
        self.assertEqual(result, {"scan": animated})
        self.assertEqual(str(result["scan"]), "<a:root_scan:100>")

    async def test_all_layouts_and_states(self):
        for page, detail, collected, status, image in itertools.product(
            range(3), (None, "hardware", "software", "connections", "journal"),
            (False, True), (0, 1, 2), (None, "attachment://root-os-banner.png"),
        ):
            view = demo.DemoView(image_url=image, emojis=self.make_emojis())
            view.page, view.detail, view.collected = page, detail, collected
            view.diagnosed, view.isolated = status >= 1, status == 2
            view.rebuild()
            payload = view.to_components()
            flat = list(components(payload))
            self.assertTrue(view.is_components_v2())
            self.assertLessEqual(len(flat), 40)
            self.assertLessEqual(sum(len(i.get("content", "")) for i in flat), 4000)
            if image:
                self.assertEqual(payload[0]["components"][0]["type"], 12)
            ids = [i["custom_id"] for i in flat if i["type"] == 2]
            self.assertEqual(len(ids), len(set(ids)))
            for item in flat:
                if item["type"] == 1:
                    self.assertLessEqual(len(item["components"]), 5)
                if item["type"] == 2:
                    self.assertTrue(item["emoji"]["name"].startswith("root_"))
                    self.assertTrue(item["emoji"]["animated"])
            json.dumps(payload)

    async def test_navigation_scan_and_isolation(self):
        view = demo.DemoView()
        await self.click(view, "page:1")
        await self.click(view, "scan")
        self.assertTrue(view.diagnosed)
        self.assertFalse(view.isolated)
        await self.click(view, "detail:connections")
        await self.click(view, "isolate")
        self.assertTrue(view.isolated)
        await self.click(view, "back")
        self.assertTrue(self.button(view, "isolate").disabled)
        await self.click(view, "page:0")
        text = json.dumps(view.to_components(), ensure_ascii=False)
        self.assertIn("0,015 RTM/h", text)
        self.assertNotIn("0,01425", text)

    async def test_collection_and_detail_buttons(self):
        view = demo.DemoView()
        await self.click(view, "collect")
        self.assertTrue(view.collected)
        self.assertTrue(self.button(view, "collect").disabled)
        for detail in ("hardware", "software"):
            await self.click(view, f"detail:{detail}")
            self.assertEqual(view.detail, detail)
            await self.click(view, "back")
            self.assertIsNone(view.detail)
        await self.click(view, "page:2")
        await self.click(view, "detail:journal")
        await self.click(view, "back")
        self.assertEqual(view.page, 2)

    async def test_old_public_button_keeps_its_action(self):
        view = demo.DemoView()
        old_collect = self.button(view, "collect")
        await self.click(view, "page:1")
        interaction = SimpleNamespace(response=SimpleNamespace(edit_message=AsyncMock()))
        await old_collect.callback(interaction)
        self.assertTrue(view.collected)
        self.assertFalse(view.diagnosed)

    def context(self, emojis=()):
        return SimpleNamespace(
            guild=SimpleNamespace(fetch_emojis=AsyncMock(return_value=emojis), emojis=emojis),
            defer=AsyncMock(), respond=AsyncMock(),
            interaction=SimpleNamespace(original_response=AsyncMock(return_value=SimpleNamespace())),
        )

    async def test_public_send_and_local_banner(self):
        ctx = self.context(list(self.make_emojis().values()))
        await demo.send_demo(ctx)
        ctx.defer.assert_awaited_once_with(ephemeral=False)
        args = ctx.respond.call_args.kwargs
        self.assertFalse(args["ephemeral"])
        self.assertEqual(args["view"].image_url, "attachment://root-os-banner.png")
        self.assertEqual(args["files"][0].filename, "root-os-banner.png")
        self.assertEqual(len(args["view"].emojis), len(demo.FALLBACKS))

    async def test_custom_banner_and_cache_fallback(self):
        ctx = self.context(list(self.make_emojis().values()))
        ctx.guild.fetch_emojis.side_effect = discord.HTTPException(
            SimpleNamespace(status=503, reason="Unavailable"), "Offline test"
        )
        await demo.send_demo(ctx, SimpleNamespace(content_type="image/png", url="https://example.com/demo.png"))
        args = ctx.respond.call_args.kwargs
        self.assertEqual(args["view"].image_url, "https://example.com/demo.png")
        self.assertFalse(args["files"])
        self.assertTrue(args["view"].emojis)

    async def test_validation_messages_are_public(self):
        ctx = self.context()
        await demo.send_demo(ctx, SimpleNamespace(content_type="text/plain"))
        self.assertFalse(ctx.respond.call_args.kwargs["ephemeral"])
        ctx.defer.assert_not_awaited()
        ctx.guild = None
        await demo.send_demo(ctx)
        self.assertFalse(ctx.respond.call_args.kwargs["ephemeral"])

    async def test_timeout_disables_buttons(self):
        view = demo.DemoView()
        view.message = SimpleNamespace(flags=SimpleNamespace(ephemeral=False),
                                       channel=SimpleNamespace(type=discord.ChannelType.text),
                                       edit=AsyncMock(return_value=None))
        await view.on_timeout()
        self.assertTrue(all(button.disabled for button in view.walk_children()
                            if isinstance(button, discord.ui.Button)))
        view.message.edit.assert_awaited_once_with(view=view)


if __name__ == "__main__":
    unittest.main()
