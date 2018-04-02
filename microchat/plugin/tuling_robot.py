import json
from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from .logger_wrapper import logger

# 图灵机器人接口
TULING_HOST = 'openapi.tuling123.com'
TULING_API = 'http://openapi.tuling123.com/openapi/api/v2'
# 图灵机器人key
TULING_KEY = '460a124248234351b2095b57b88cffd2'

# 图灵机器人
def tuling_robot(msg):
    # 消息内容预处理
    send_to_tuling_content = msg.raw.content
    # 群聊消息:过滤掉sender_wxid
    if msg.from_id.id.endswith('@chatroom'):                                    
        if msg.raw.content.find('\n') > -1:                                                             # 群聊消息以'sender_wxid:\n'起始
            send_to_tuling_content = msg.raw.content[msg.raw.content.find('\n') + 1:]
    # 公众号消息不回复
    elif msg.from_id.id.startswith('gh_'):  
        return
    else:
        pass      

    # 使用图灵接口获取自动回复信息
    data = {
        'reqType': 0,
        'perception':
        {
            "inputText":
            {
                "text": send_to_tuling_content
            },
        },
        'userInfo':
        {
            "apiKey": TULING_KEY,
            "userId": Util.GetMd5(msg.from_id.id)
        }
    }
    try:
        robot_ret = eval(Util.post(TULING_HOST, TULING_API,json.dumps(data)).decode())
        logger.debug('tuling api 返回:{}'.format(robot_ret))
        # 自动回消息
        interface.new_send_msg(msg.from_id.id, robot_ret['results'][0]['values']['text'].encode(encoding="utf-8"))
    except:
        logger.info('tuling api 调用异常!',1)
    return