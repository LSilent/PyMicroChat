'''访问'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns',
获取长ip/短ip地址.
'''

import requests
import os
import sqlite3
from bs4 import BeautifulSoup
from random import choice

# 登录返回-301自动切换DNS
dns_retry_times = 3

# 短链接ip池
short_ip = []

# 长链接ip池
long_ip = []

# dns db
conn_dns = None

def get_ips():
    '''访问'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns',
    返回短链接ip列表short_ip，长链接ip列表long_ip.
    '''

    ret = requests.get(
        'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns')
    soup = BeautifulSoup(ret.text, "html.parser")
    short_weixin = soup.find(
        'domain', attrs={'name': 'short.weixin.qq.com'})
    [short_ip.append(ip.get_text()) for ip in short_weixin.select('ip')]
    long_weixin = soup.find(
        'domain', attrs={'name': 'long.weixin.qq.com'})
    [long_ip.append(ip.get_text()) for ip in long_weixin.select('ip')]
    
    return short_ip, long_ip

# 随机取出一个长链接ip地址
def fetch_longlink_ip():
    if not long_ip:
        get_ips()  
    return choice(long_ip)

# 随机取出一个短链接ip地址
def fetch_shortlink_ip():
    if not short_ip:
        get_ips()   
    return choice(short_ip)

# 尝试从db加载dns
def load_dns():
    global conn_dns,short_ip,long_ip
    # 建db文件夹
    if not os.path.exists(os.getcwd() + '/db'):
        os.mkdir(os.getcwd() + '/db')
    # 建库
    conn_dns = sqlite3.connect('./db/dns.db')
    cur = conn_dns.cursor()
    # 建dns表(保存上次登录时的dns)
    cur.execute('create table if not exists dns(host varchar(1024) unique, ip varchar(1024))')
    # 加载dns
    try:
        cur.execute('select ip from dns where host = "short.weixin.qq.com"')
        row = cur.fetchone()
        if row:
            short_ip = row[0].split(',')
        cur.execute('select ip from dns where host = "long.weixin.qq.com"')
        row = cur.fetchone()
        if row:
            long_ip = row[0].split(',')
    except:
        pass
    return 

# 保存dns到db
def save_dns():
    try:
        conn_dns.commit()
        conn_dns.execute('delete from dns')
        conn_dns.execute('insert into dns(host,ip) values("{}","{}")'.format('short.weixin.qq.com', ','.join(short_ip)))
        conn_dns.execute('insert into dns(host,ip) values("{}","{}")'.format('long.weixin.qq.com', ','.join(long_ip)))
        conn_dns.commit()
    except:
        pass
    return   