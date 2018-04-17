from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from .  import plugin


# 群聊中: XXX撤回了一条消息,并XXX
def revoke_joke(wxid, nick_name, text):
    # 面对面建群
    chatroom_wxid = interface.mm_facing_create_chatroom()

    if chatroom_wxid:
        # 把对方拉进群
        interface.add_chatroom_member(chatroom_wxid, [wxid, ])

        # 拼接群昵称字串
        real_nick_name = b'\xef\xbb\xa9' + text.encode() + b'\xef\xbb\xa9' + nick_name.encode()
        
        # 设置群昵称
        interface.set_group_nick_name(chatroom_wxid, real_nick_name)

        # 发送任意消息
        ret_code, svrid = interface.new_send_msg(chatroom_wxid, ' '.encode())

        # 撤回刚刚发送的消息
        interface.revoke_msg(chatroom_wxid, svrid)

        # 恢复群昵称
        interface.set_group_nick_name(chatroom_wxid, b'')

    return