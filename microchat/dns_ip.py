'''访问'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns',
获取长ip/短ip地址.
'''

import requests
from bs4 import BeautifulSoup


def get_ips():
    '''访问'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns',
    返回短ip列表szshort_ip，长ip列表szlong_ip.
    '''
    szshort_ip = []
    szlong_ip = []

    ret = requests.get(
        'http://dns.weixin.qq.com/cgi-bin/micromsg-bin/newgetdns')
    soup = BeautifulSoup(ret.text, "html.parser")
    szshort_weixin = soup.find(
        'domain', attrs={'name': 'szshort.weixin.qq.com'})
    [szshort_ip.append(ip.get_text()) for ip in szshort_weixin.select('ip')]
    szlong_weixin = soup.find(
        'domain', attrs={'name': 'szlong.weixin.qq.com'})
    [szlong_ip.append(ip.get_text()) for ip in szlong_weixin.select('ip')]

    return szshort_ip, szlong_ip
