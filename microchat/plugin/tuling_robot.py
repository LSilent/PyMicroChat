import json
from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from bs4 import BeautifulSoup
from .logger_wrapper import logger

# 图灵机器人接口
TULING_HOST = 'openapi.tuling123.com'
TULING_API = 'http://openapi.tuling123.com/openapi/api/v2'
# 图灵机器人key
TULING_KEY = '460a124248234351b2095b57b88cffd2'

# 图灵机器人
def tuling_robot(msg):
    # 本条消息是否回复
    need_reply = False
    # 消息内容预处理
    send_to_tuling_content = msg.raw.content
    reply_prefix = ''
    reply_at_wxid = ''
    # 群聊消息:只回复@自己的消息/消息内容过滤掉sender_wxid
    if msg.from_id.id.endswith('@chatroom'):
        # 首先判断本条群聊消息是否at我:
        try:
            soup = BeautifulSoup(msg.ex_info,'html.parser')
            at_user_list = soup.msgsource.atuserlist.contents[0].split(',')
            if Util.wxid in at_user_list:                                                               # 群聊中有@我的消息
                # 群聊消息以'sender_wxid:\n'起始
                send_to_tuling_content = msg.raw.content[msg.raw.content.find('\n') + 1:]
                # 解析@我的人的昵称
                reply_nick_name = Util.find_str(msg.xmlContent, '<pushcontent content="', '在群聊中@了你" nickname="')
                if reply_nick_name:
                    # 回复消息前缀
                    reply_prefix = '@{}'.format(reply_nick_name)                                        # 回复群聊消息时@发消息人
                # 解析@我的人的wxid
                reply_at_wxid = msg.raw.content[:msg.raw.content.find(':\n')]
                # 取@我之后的消息内容
                send_to_tuling_content = msg.raw.content[msg.raw.content.rfind('\u2005') + 1:]           # at格式: @nick_name\u2005
                if reply_prefix and reply_at_wxid:
                    # 本条消息需要回复
                    need_reply = True
        except:
            return
    # 公众号消息不回复
    elif msg.from_id.id.startswith('gh_'):  
        return
    else:
        # 本条消息需要回复
        need_reply = True
        pass 

    if need_reply:
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
            if reply_prefix and reply_at_wxid:
                # 消息前缀: @somebody  并at发消息人
                interface.new_send_msg(msg.from_id.id, (reply_prefix + ' ' + robot_ret['results'][0]['values']['text']).encode(encoding="utf-8"), [reply_at_wxid])
            else:
                interface.new_send_msg(msg.from_id.id, robot_ret['results'][0]['values']['text'].encode(encoding="utf-8"))
        except:
            logger.info('tuling api 调用异常!', 1)
    return