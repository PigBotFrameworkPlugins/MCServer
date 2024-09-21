import json
import threading
import re
import time

from pbf.utils import MetaData, Utils
from pbf.setup import logger, pluginsManager
from pbf.utils.Register import Command, Message, adminPermission
from pbf.controller.Data import Event
from pbf.controller.Client import Msg
from pbf import config
from pbf.utils.Config import Config


try:
    import websocket
except ImportError:
    Utils.installPackage("websocket-client")
    import websocket


# 插件元数据
meta_data = MetaData(
    name="MC服务器",
    version="0.1.0",
    versionCode=10,
    description="MCServer Tools",
    author="xzystudio",
    license="MIT",
    keywords=["pbf", "plugin", "mc", "server"],
    readme="""
    # MCServer
    """
)


class MyConfig(Config):
    originData = {
        "client_id": 123,
        "client_secret": 123,
        "qn": [],
        "enable_chatimage": False,
        "ws_uri": "wss://socket.xzynb.top/ws"
    }

myConfig = MyConfig(config.plugins_config.get("mcserver", {}))
_ws_uri = myConfig.get("ws_uri")
_ws_client_id = myConfig.get("client_id")
_ws_client_secret = myConfig.get("client_secret")
_qn = myConfig.get("qn")
_enable_chatimage = myConfig.get("enable_chatimage")

def send(wsapp, type: str, data=None, flag: str = ""):
    if data is None:
        data = {}
    msg = {
        "type": type,
        "data": data,
        "flag": flag,
        "client_id": _ws_client_id,
        "client_secret": _ws_client_secret
    }
    try:
        wsapp.send(json.dumps(msg))
    except Exception:
        reconnect(wsapp)

def on_close(wsapp, close_status_code, close_msg):
    print("WebSocket Closed", close_status_code, close_msg)
    reconnect(wsapp)

def on_open(wsapp):
    logger.info("WebSocket Connected")
    send(wsapp, "init")

def on_message(wsapp, msg):
    msg = json.loads(msg)
    if msg.get("type") == "ping":
        return
    logger.info(f"WS Recv: {msg}")
    if msg.get("type") == "server_message":
        if pluginsManager.hasApi("banwords"):
            if pluginsManager.require('banwords').check(msg.get("data").get("msg")).get("result"):
                logger.info(f"Message Containers Banword: {msg.get('data').get('msg')}")
                return
        Msg(msg.get("data").get("msg")).send_to(group_id=int(msg.get("data").get("qn")))

def reconnect(wsapp):
    print("Reconnecting...")
    time.sleep(2)  # 等待2秒后重连
    wsapp.run_forever()

ws_app = websocket.WebSocketApp(_ws_uri,
                            on_message=on_message,
                            on_open=on_open,
                            on_close=on_close)
ws_thread = threading.Thread(target=ws_app.run_forever)

def _enter():
    ws_thread.start()

def _exit():
    # 向ws_thread发送消息结束ws_app
    logger.debug("Exiting MCServer Plugin")
    ws_app.close()

def parseMessage(message):
    regexList = [
        [r"\[CQ:reply(.*?)\]", ""],
        [r"\[CQ:forward(.*?)\]", ""],
        # [r"\[CQ:image(.*?),url=(.*?)\]", "[图片$1]", "url=(.*?)"],
        [r"\[CQ:face(.*?),id=(.*?)\]", r"[表情$1]", "id=(.*?)"],
        [r"\[CQ:record(.*?),url=(.*?)\]", r"[音频]"],
        [r"\[CQ:at,qq=(.*?)\]", r"@$1", r"qq=(\d+)"]
    ]
    message = message.replace("&amp;", "&")

    for i in regexList:
        if "$" in i[1]:
            flag = True
            for l in i[1].split("$"):
                if flag:
                    flag = False
                    continue
                num = int(l[0:1])
                pattern = re.compile(i[num + 1], re.I)
                m = pattern.match(message)
                if m is None:
                    continue
                i[1] = i[1].replace(f"${num}", re.sub("(.*?)=", "", m.group(0)))

        message = re.sub(i[0], i[1], message)

    return message


@Command(
    name="/",
    description="MCServer Command",
    usage="/<Command Content>",
    permission=adminPermission
)
def mcCommand(event: Event):
    send(ws_app, "command", {"cmd": event.raw_message[1:]})


@Message(name="MCServer Message Sync")
def messageHandler(event: Event):
    if event.group_id in _qn and not event.raw_message.startswith("/"):
        msg = f"<{event.sender.get('nickname')}> {parseMessage(event.raw_message)}"
        if _enable_chatimage:
            send(ws_app, "command", {"cmd": f"ci say {msg}"})
        else:
            send(ws_app, "command", {"cmd": f"ms say {msg}"})