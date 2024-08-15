import json
import threading
import re

from pbf.utils import MetaData, Utils
from pbf.setup import logger, pluginsManager
from pbf.utils.Register import Command, Message
from pbf.controller.Data import Event
from pbf.controller.Client import Msg


try:
    import websocket
except ImportError:
    Utils.installPackage("websocket-client")
    import websocket


# 插件元数据
meta_data = MetaData(
    name="mcserver",
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


_ws_uri = "wss://socket.xzynb.top/ws"
_ws_client_id = "123"
_ws_client_secret = "123"
_qn = [
    983519118
]
banwords = pluginsManager.require("banwords")

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
    wsapp.send(json.dumps(msg))

def on_open(wsapp):
    logger.info("WebSocket Connected")
    send(wsapp, "init")

def on_message(wsapp, msg):
    msg = json.loads(msg)
    if msg.get("type") == "ping":
        return
    logger.info(f"WS Recv: {msg}")
    if msg.get("type") == "server_message":
        if banwords.check(msg.get("data").get("msg")).get("result"):
            logger.info(f"Message Containers Banword: {msg.get('data').get('msg')}")
            return
        Msg(msg.get("data").get("msg")).send_to(group_id=int(msg.get("data").get("qn")))

ws_app = websocket.WebSocketApp(_ws_uri,
                                on_message=on_message,
                                on_open=on_open)
ws_thread = threading.Thread(target=ws_app.run_forever)


def _enter():
    # 以非阻塞方式运行ws_app
    ws_thread.start()

def parseMessage(message):
    regexList = [
        [r"\[CQ:reply(.*?)\]", ""],
        [r"\[CQ:forward(.*?)\]", ""],
        [r"\[CQ:image(.*?),url=(.*?)\]", "[图片$1]", "url=(.*?)"],
        [r"\[CQ:face(.*?),id=(.*?)\]", r"[表情$1]", "id=(.*?)"],
        [r"\[CQ:record(.*?),url=(.*?)\]", r"[音频]"],
        [r"\[CQ:at,qq=(.*?)\]", r"@$1", r"qq=(\d+)"]
    ]

    for i in regexList:
        if "$" in i[1]:
            flag = True
            for l in i[1].split("$"):
                if flag:
                    flag = False
                    continue
                num = int(l[0:1])
                print(i[num + 1])
                pattern = re.compile(i[num + 1], re.I)
                m = pattern.match(message)
                if m is None:
                    print(m, message, i[num + 1])
                    continue
                i[1] = i[1].replace(f"${num}", re.sub("(.*?)=", "", m.group(0)))

        message = re.sub(i[0], i[1], message)

    return message

@Command(name="/", description="执行字零号", usage="/<command>")
def execCommand(event: Event):
    send(ws_app, "command", {"cmd": event.raw_message[1:]})


@Message(name="MCServer Message Sync")  # 注册消息处理器，会处理所有消息
def messageHandler(event: Event):
    if event.group_id in _qn and not event.raw_message.startswith("/"):
        send(ws_app, "message", {"msg": f"<{event.sender.get('nickname')}> {parseMessage(event.raw_message)}"})
