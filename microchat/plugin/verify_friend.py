import xmltodict
from .. import define
from .. import interface
from .. import mm_pb2
from .. import Util
from .logger_wrapper import logger
from bs4 import BeautifulSoup

#自动通过好友请求黑名单列表,在表中的wxid将不自动同意
auto_verify_blacklist = []


#自动通过好友申请
def auto_verify_friend(msg):
    #消息类型判定：来自于'fmessage'
    if not (37 == msg.type) or not (msg.from_id.id == 'fmessage'):
        return
    #解析消息，取fromusername,encryptusername,scene,ticket
    try:
        soup = BeautifulSoup(msg.raw.content,'html.parser')
        fromusername = soup.msg.attrs['fromusername']                       # wxid
        encryptusername = soup.msg.attrs['encryptusername']                 # v1_name
        scene =  soup.msg.attrs['scene']
        ticket = soup.msg.attrs['ticket']                                   # v2_name
        #过滤黑名单
        if fromusername in auto_verify_blacklist:
            logger.info('[{}]在黑名单中,忽略该好友申请!'.format(fromusername))
            return
        #通过好友请求   
        if interface.verify_user(3,fromusername,encryptusername,ticket,'',''):
            logger.info('已通过[{}]的好友请求!'.format(fromusername),9)
        else:
            logger.info('自动通过[{}]的好友请求失败!'.format(fromusername))
    except:
        logger.info('msg解析失败,忽略该消息!')
    return
