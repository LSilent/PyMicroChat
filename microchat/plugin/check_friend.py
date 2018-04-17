import threading
from .. import interface
from .. import mm_pb2
from .. import Util
from .  import plugin
from .logger_wrapper import logger

# 单向好友列表
check_friend_list = {}

# 测试群
test_chatroom_wxid = ''

# 打印检测结果
def show():
    if check_friend_list:
        logger.info('[单向好友检测结果]扎心了,老铁!', 13)
        for i in check_friend_list:
            logger.info('wxid:{} 昵称:{} 类型:{}'.format(i, check_friend_list[i][0], check_friend_list[i][1]), 11)
    else:
        logger.info('[单向好友检测结果]恭喜,暂未检测到单向好友!', 11)
    return

# 单向好友检测(扎心,慎用!!!)
# 删除我后对方开启好友验证或拉黑我,拉人入群对方无任何消息通知
# 删除我后对方关闭好友验证(双方仍可互发消息),拉人入群会向对方发送群聊邀请!
# TODO:寻找其他静默检测单向好友方法
def check(chatroom_wxid = '', test_add_chatroom_member = False):
    global check_friend_list, test_chatroom_wxid
    check_friend_list = {}
    # 设置测试群(不设置默认新建面对面群测试)
    if chatroom_wxid:
        test_chatroom_wxid = chatroom_wxid
    # 获取好友列表
    friend_list = interface.get_contact_list()
    for friend in friend_list:
        # 获取好友信息,返回ticket表示被对方拉黑或删除
        __, ticket = interface.get_contact(friend[0])
        if ticket.ticket:
            logger.info('wxid:{} v2数据:{}'.format(ticket.wxid, ticket.ticket))
            # 把加入单向好友列表
            if friend[0] not in check_friend_list.keys():
                # 备注名存在使用备注名;否则使用好友昵称
                check_friend_list[friend[0]] = [friend[2], '删好友'] if friend[2] else [friend[1], '删好友']
            if test_add_chatroom_member:
                if not test_chatroom_wxid:
                    # 面对面建群
                    test_chatroom_wxid = interface.mm_facing_create_chatroom()
                if test_chatroom_wxid:
                    # 拉单向好友入群(慎用)
                    interface.add_chatroom_member(test_chatroom_wxid, [friend[0]])
                    pass
    # 3秒后打印检测结果
    threading.Timer(3, show).start()
    return

# 单向好友类型判断(拉黑或删好友)
def check_type(msg):
    global check_friend_list
    try:
        # 过滤拉好友入群失败消息
        if test_chatroom_wxid == msg.from_id.id and 10000 == msg.type and Util.wxid == msg.to_id.id:
            if msg.raw.content.endswith('拒绝加入群聊'):
                # 取昵称
                nick_name = msg.raw.content[:msg.raw.content.rfind('拒绝加入群聊')]
                for i in check_friend_list:
                    if nick_name == check_friend_list[i][0]:
                        check_friend_list[i][1] = '拉黑'
                        break
    except:
        pass
    return