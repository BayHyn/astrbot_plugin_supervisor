import os
import random
from astrbot.api import logger
from astrbot.api.event import filter
from astrbot.api.star import Context, Star, register
from astrbot.core import AstrBotConfig
import astrbot.core.message.components as Comp
from astrbot.core.platform import AstrMessageEvent
from astrbot.core.star.filter.event_message_type import EventMessageType


@register(
    "astrbot_plugin_supervisor",
    "Zhalslar",
    "赛博监工，检测到某人水群，就提醒他滚去干活",
    "1.0.1",
    "https://github.com/Zhalslar/astrbot_plugin_supervisor",
)
class SupervisorPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.image_dir = os.path.join(
            "data", "plugins", "astrbot_plugin_supervisor", "image"
        )
        os.makedirs(self.image_dir, exist_ok=True)
        self.supervisor_prompt = config.get(
            "supervisor_prompt", "督促这黑奴别水群滚去干活"
        )
        logger.info(f"监工插件已加载白名单QQ号: {self.config['whitelist_qq']}")

    @filter.command("监督")
    async def add_supervisor(
        self, event: AstrMessageEvent, input_id: str | None = None
    ):
        """监督某人"""
        target_id = self.get_target_id(event, input_id)
        self.config["whitelist_qq"].append(target_id)
        self.config.save_config(replace_config=self.config)
        yield event.plain_result(f"已监督: {target_id}")
        logger.info(f"监工插件当前白名单QQ号: {self.config['whitelist_qq']}")

    @filter.command("解除监督")
    async def remove_supervisor(
        self, event: AstrMessageEvent, input_id: str | None = None
    ):
        """解除监督某人"""
        target_id = self.get_target_id(event, input_id)
        self.config["whitelist_qq"].remove(target_id)
        self.config.save_config(replace_config=self.config)
        yield event.plain_result(f"已解除监督: {target_id}")
        logger.info(f"监工插件当前白名单QQ号: {self.config['whitelist_qq']}")

    def get_target_id(self, event: AstrMessageEvent, input_id: str | None = None):
        """获取目标id"""
        return input_id or next(
            (
                str(seg.qq)
                for seg in event.get_messages()
                if (isinstance(seg, Comp.At)) and str(seg.qq) != event.get_self_id()
            )
        )

    @filter.event_message_type(EventMessageType.ALL)
    async def on_supervisor(self, event: AstrMessageEvent):
        sender_id = event.get_sender_id()

        if sender_id not in self.config["whitelist_qq"]:
            return
        event_random = random.random()  # 触发概率
        chain = []
        if event_random < 0.4:
            if image_path := self.get_random_image(self.image_dir):
                chain = [Comp.At(qq=sender_id), Comp.Image(image_path)]

        elif event_random < 0.8:
            message_str = event.get_message_str()
            if ai_plain := await self.ai_supervisor(message_str):
                chain = [Comp.Plain(ai_plain)]

        else:
            await self.poke_supervisor(event)

        yield event.chain_result(chain)  # type: ignore

    @staticmethod
    def get_random_image(image_dir: str):
        """随机选图"""
        entries = os.listdir(image_dir)
        if not entries:
            logger.warning("监工失败: 没有可选用的图片")
            return None
        random_entry = random.choice(entries)
        return os.path.join(image_dir, random_entry)

    async def ai_supervisor(self):
        """让LLM监工"""

        func_tools_mgr = self.context.get_llm_tool_manager()

        system_prompt = self.supervisor_prompt

        try:
            llm_response = await self.context.get_using_provider().text_chat(
                prompt="他来水群了",
                contexts=[{"role": "system", "content": system_prompt}],
                image_urls=[],
                func_tool=func_tools_mgr,
            )

            return " " + llm_response.completion_text
        except Exception as e:
            logger.error(f"LLM 监工失败: {e}")

    async def poke_supervisor(self, event: AstrMessageEvent):
        """戳一戳监工"""
        if event.get_platform_name() == "aiocqhttp":
            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
                AiocqhttpMessageEvent,
            )

            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            user_id = event.get_sender_id()
            group_id = event.get_group_id()
            try:
                await client.send_poke(user_id=int(user_id), group_id=int(group_id))
            except Exception as e:
                logger.error(f"戳一戳监工失败: {e}")
