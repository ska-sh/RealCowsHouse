import asyncio
import random
import string
from time import time
from urllib.parse import unquote, quote

import aiohttp
import json
from aiocfscrape import CloudflareScraper
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from pyrogram import Client
from pyrogram.errors import Unauthorized, UserDeactivated, AuthKeyUnregistered, FloodWait
from pyrogram.raw.functions.messages import RequestAppWebView
from pyrogram.raw import types
from .agents import generate_random_user_agent
from bot.config import settings

from bot.utils import logger
from bot.exceptions import InvalidSession
from .headers import headers
from .helper import format_duration


class Tapper:
    def __init__(self, tg_client: Client):
        self.session_name = tg_client.name
        self.tg_client = tg_client
        self.user_id = 0
        self.username = None
        self.first_name = None
        self.last_name = None
        self.fullname = None
        self.start_param = None
        self.peer = None
        self.first_run = None

        self.session_ug_dict = self.load_user_agents() or []

        headers['User-Agent'] = self.check_user_agent()

    async def generate_random_user_agent(self):
        return generate_random_user_agent(device_type='android', browser_type='chrome')

    def info(self, message):
        from bot.utils import info
        info(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def debug(self, message):
        from bot.utils import debug
        debug(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def warning(self, message):
        from bot.utils import warning
        warning(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def error(self, message):
        from bot.utils import error
        error(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def critical(self, message):
        from bot.utils import critical
        critical(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def success(self, message):
        from bot.utils import success
        success(f"<light-yellow>{self.session_name}</light-yellow> | {message}")

    def save_user_agent(self):
        user_agents_file_name = "user_agents.json"

        if not any(session['session_name'] == self.session_name for session in self.session_ug_dict):
            user_agent_str = generate_random_user_agent()

            self.session_ug_dict.append({
                'session_name': self.session_name,
                'user_agent': user_agent_str})

            with open(user_agents_file_name, 'w') as user_agents:
                json.dump(self.session_ug_dict, user_agents, indent=4)

            logger.success(f"<light-yellow>{self.session_name}</light-yellow> | User agent saved successfully")

            return user_agent_str

    def load_user_agents(self):
        user_agents_file_name = "user_agents.json"

        try:
            with open(user_agents_file_name, 'r') as user_agents:
                session_data = json.load(user_agents)
                if isinstance(session_data, list):
                    return session_data

        except FileNotFoundError:
            logger.warning("User agents file not found, creating...")

        except json.JSONDecodeError:
            logger.warning("User agents file is empty or corrupted.")

        return []

    def check_user_agent(self):
        load = next(
            (session['user_agent'] for session in self.session_ug_dict if session['session_name'] == self.session_name),
            None)

        if load is None:
            return self.save_user_agent()

        return load

    async def get_tg_web_data(self, proxy: str | None) -> str:
        if proxy:
            proxy = Proxy.from_str(proxy)
            proxy_dict = dict(
                scheme=proxy.protocol,
                hostname=proxy.host,
                port=proxy.port,
                username=proxy.login,
                password=proxy.password
            )
        else:
            proxy_dict = None

        self.tg_client.proxy = proxy_dict

        try:
            with_tg = True

            if not self.tg_client.is_connected:
                with_tg = False
                try:
                    await self.tg_client.connect()
                except (Unauthorized, UserDeactivated, AuthKeyUnregistered):
                    raise InvalidSession(self.session_name)

            self.start_param = random.choices([settings.REF_ID, "kentId7392018078"], weights=[75, 25], k=1)[0]
            peer = await self.tg_client.resolve_peer('RealCowsHouse_bot')
            InputBotApp = types.InputBotAppShortName(bot_id=peer, short_name="cowshouse")

            web_view = await self.tg_client.invoke(RequestAppWebView(
                peer=peer,
                app=InputBotApp,
                platform='android',
                write_allowed=True,
                start_param=self.start_param
            ))

            auth_url = web_view.url
            tg_web_data = unquote(
                string=auth_url.split('tgWebAppData=', maxsplit=1)[1].split('&tgWebAppVersion', maxsplit=1)[0])

            try:
                if self.user_id == 0:
                    information = await self.tg_client.get_me()
                    self.user_id = information.id
                    self.first_name = information.first_name or ''
                    self.last_name = information.last_name or ''
                    self.username = information.username or ''
            except Exception as e:
                print(e)

            if with_tg is False:
                await self.tg_client.disconnect()

            return tg_web_data

        except InvalidSession as error:
            raise error

        except Exception as error:
            logger.error(
                f"<light-yellow>{self.session_name}</light-yellow> | Unknown error during Authorization: {error}")
            await asyncio.sleep(delay=3)

    async def login(self, http_client: aiohttp.ClientSession, initdata):
        try:
            while True:
                    pr = {"startParam": settings.REF_ID}
                    resp = await http_client.post("https://realcowshouse.fun/api/auth", json=pr, ssl=False)
                    if resp.status == 520:
                        self.warning('Relogin')
                        await asyncio.sleep(delay=3)
                        continue
                    resp_json = await resp.json()
                    initialized = resp_json.get("user").get('initialized')
                    if not initialized:
                        await http_client.post("https://realcowshouse.fun/api/user/initial-check", ssl=False)
                    return resp_json.get("user")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Login error {error}")
            return None, None

    async def daily_reward(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post('https://realcowshouse.fun/api/task/daily-reward', ssl=False)
            resp_json = await resp.json()
            if resp_json['available']:
                resp = await http_client.post('https://realcowshouse.fun/api/task/claim-daily', ssl=False)
                resp_json = await resp.json()
                if resp_json['status'] == u'success':
                    self.success(f"daily reward, days: {resp_json['days']}, balance: {resp_json['user']['point']}")
            else:
                self.info(f"daily reward")

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Start complete error {error}")

    async def claim_social(self, http_client: aiohttp.ClientSession, user_info: dict):
        try:
            if user_info.get('tasks') is not None:
                for task in user_info.get('tasks'):
                    if task.get('claimed') is False:
                        await asyncio.sleep(random.randint(5, 10))
                        json_data = {"task": task['name']}
                        resp = await http_client.post('https://realcowshouse.fun/api/task/claim-social', json=json_data, ssl=False)
                        resp_json = await resp.json()
                        if resp_json['status'] == u'success':
                            self.success(f"claim {task['name']}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | claim_social error {error}")

    async def get_tasks(self, http_client: aiohttp.ClientSession):
        try:
            resp = await http_client.post('https://realcowshouse.fun/api/task/get/all', ssl=False)
            if resp.status not in [200, 201]:
                return False

            resp_json = await resp.json()
            for task in resp_json['tasks']:
                await self.social_check(http_client=http_client, task=task['task'])

        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Get tasks error {error}")

    async def social_check(self, http_client: aiohttp.ClientSession, task: str):
        try:
            await asyncio.sleep(random.randint(5, 10))
            json_data = {"task": task}
            resp = await http_client.post('https://realcowshouse.fun/api/task/social-check', json=json_data, ssl=False)
            resp_json = await resp.json()
            if resp_json['status'] == u'success':
                self.success(f"check success: {task}")
                await self.claim_social(http_client=http_client, user_info=resp_json.get('user'))
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | social check error {error}")

    async def daily_milk(self, http_client: aiohttp.ClientSession, daily_milk: int):
        try:
            while daily_milk > 0:
                self.info(f"start play milk")
                await asyncio.sleep(random.randint(30, 40))
                ton_amount = "%.3f" % random.uniform(settings.TON_AMOUNT[0], settings.TON_AMOUNT[1])
                bonus = random.randint(settings.POINTS[0], settings.POINTS[1])
                json_data = {"tonAmount": str(ton_amount),
                             "bonus": bonus}
                resp = await http_client.post('https://realcowshouse.fun/api/user/save-ton', json=json_data, ssl=False)
                resp_json = await resp.json()
                if resp_json['user']['dailyMilk'] > 0:
                    self.success(f"play milk tonAmount: {ton_amount}, bonus: {bonus}, dailyMilk: {resp_json['user']['dailyMilk']}")
                    self.info(f"point: {resp_json['user']['point']}, ton: {resp_json['user']['ton']}")
                    daily_milk = daily_milk - 1
                    await asyncio.sleep(random.randint(5, 10))
        except Exception as e:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Error occurred during play game: {e}")

    async def check_proxy(self, http_client: aiohttp.ClientSession, proxy: Proxy) -> None:
        try:
            response = await http_client.get(url='https://httpbin.org/ip', timeout=aiohttp.ClientTimeout(5))
            ip = (await response.json()).get('origin')
            logger.info(f"<light-yellow>{self.session_name}</light-yellow> | Proxy IP: {ip}")
        except Exception as error:
            logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Proxy: {proxy} | Error: {error}")

    async def run(self, proxy: str | None) -> None:
        random_delay = random.randint(1, 15)
        logger.info(f"{self.tg_client.name} | Bot will start in <light-red>{random_delay}s</light-red>")
        await asyncio.sleep(delay=random_delay)
        login_need = True

        proxy_conn = ProxyConnector().from_url(proxy) if proxy else None

        http_client = CloudflareScraper(headers=headers, connector=proxy_conn)

        if proxy:
            await self.check_proxy(http_client=http_client, proxy=proxy)
        while True:
            try:
                if login_need:
                    if "Authorization" in http_client.headers:
                        del http_client.headers["Authorization"]
                    init_data = await self.get_tg_web_data(proxy=proxy)
                    http_client.headers["Authorization"] = f"tma {init_data}"
                    user_info = await self.login(http_client=http_client, initdata=init_data)
                    self.info(f"登录成功!")
                    login_need = False

                if settings.DO_TASKS:
                    await self.claim_social(http_client=http_client, user_info=user_info)
                    await self.get_tasks(http_client=http_client)

                await self.daily_reward(http_client=http_client)

                await self.daily_milk(http_client=http_client, daily_milk=user_info.get('dailyMilk'))


            except InvalidSession as error:
                raise error
            except Exception as error:
                logger.error(f"<light-yellow>{self.session_name}</light-yellow> | Unknown error: {error}")
                await asyncio.sleep(delay=3)


async def run_tapper(tg_client: Client, proxy: str | None):
    try:
        await Tapper(tg_client=tg_client).run(proxy=proxy)
    except InvalidSession:
        logger.error(f"{tg_client.name} | Invalid Session")
