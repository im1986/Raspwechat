#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import web
import time
import threading
import urllib2
import hashlib
import RPi.GPIO as GPIO
from array import *
from lxml import etree
from weixin import WeiXinClient
from weixin import APIError
from weixin import AccessTokenError
from yeelink import YeeLinkClient
from yeelink import current_time

#传感器位置

channel = 4
 
urls = (
'/weixin','WeixinInterface'
)


my_appid = 'wxc2b8f6925c3ec62' #填写你的appid
my_secret = '7a446fb3c18404f3e2c01b0eb119256' #填写你的app secret
my_yeekey = '27917ff3453e3da5fd2a395c3db2562'#填写你的 yeekey
 
def _check_hash(data):
    signature=data.signature
    timestamp=data.timestamp
    nonce=data.nonce
    #自己的token
    token="ming100" #这里改写你在微信公众平台里输入的token
    #字典序排序
    list=[token,timestamp,nonce]
    list.sort()
    sha1=hashlib.sha1()
    map(sha1.update,list)
    hashcode=sha1.hexdigest()
    #sha1加密算法        
 
    #如果是来自微信的请求，则回复echostr
    if hashcode == signature:
        return True
    return False
 

def _do_event_subscribe(server, fromUser, toUser, xml):
    return server._reply_text(fromUser, toUser, u'欢迎关注此微信号，具体功能请点击下方菜单')
    
def _do_event_unsubscribe(server, fromUser, toUser, xml):
    return server._reply_text(fromUser, toUser, u'bye!')

def _do_event_SCAN(server, fromUser, toUser, xml):
    pass

def _do_event_LOCATION(server, fromUser, toUser, xml):
    pass

def _do_event_CLICK(server, fromUser, toUser, xml):
    key = xml.find('EventKey').text
    try:
        return _weixin_click_table[key](server, fromUser, toUser, xml)
    except KeyError, e:
        print '_do_event_CLICK: %s' %e
        return server._reply_text(fromUser, toUser, u'Unknow click: '+key)

_weixin_event_table = {
    'subscribe'     :   _do_event_subscribe,
    'unsbscribe'    :   _do_event_unsubscribe,
    'SCAN'          :   _do_event_SCAN,
    'LOCATION'      :   _do_event_LOCATION,
    'CLICK'         :   _do_event_CLICK,
}


def _do_click_SNAPSHOT(server, fromUser, toUser, xml):
    data = None 
    err_msg = 'snapshot fail: '
    try:
        data = _take_snapshot('127.0.0.1', 8080, server.client)
    except Exception, e:
        err_msg += str(e)
        print '_do_click_SNAPSHOT', err_msg
        return server._reply_text(fromUser, toUser, err_msg)
    return server._reply_image(fromUser, toUser, data.media_id)

def _take_snapshot(addr, port, client):
    url = 'http://%s:%d/?action=snapshot' %(addr, port)
    req = urllib2.Request(url)
    resp = urllib2.urlopen(req, timeout = 2)
    return client.media.upload.file(type='image', pic=resp)

def _do_click_V1001_TEMPERATURES(server, fromUser, toUser, xml):
  data = []
  j = 0

  GPIO.setmode(GPIO.BCM)
  time.sleep(1)
  GPIO.setup(channel, GPIO.OUT)
  GPIO.output(channel, GPIO.LOW)
  time.sleep(0.02)
  GPIO.output(channel, GPIO.HIGH)
  GPIO.setup(channel, GPIO.IN)

  while GPIO.input(channel) == GPIO.LOW:
       continue

  while GPIO.input(channel) == GPIO.HIGH:
       continue

  while j < 40:
       k = 0
       while GPIO.input(channel) == GPIO.LOW:
           continue

       while GPIO.input(channel) == GPIO.HIGH:
           k += 1
           if k > 100:
               break
       if k < 15:
           data.append(0)
       else:
           data.append(1)

       j += 1

  #print "sensor is working."
  #print data

  humidity_bit = data[0:8]
  humidity_point_bit = data[8:16]
  temperature_bit = data[16:24]
  temperature_point_bit = data[24:32]
  check_bit = data[32:40]

  humidity_point = 0
  temperature_point = 0
  check = 0
  temperature = 0
  humidity = 0

  for i in range(8):
       humidity += humidity_bit[i] * 2 ** (7 - i)
       humidity_point += humidity_point_bit[i] * 2 ** (7 - i)
       temperature += temperature_bit[i] * 2 ** (7 - i)
       temperature_point += temperature_point_bit[i] * 2 ** (7 - i)
       check += check_bit[i] * 2 ** (7 - i)

  tmp = humidity + humidity_point + temperature + temperature_point
  GPIO.cleanup()
  if check==tmp:
      reply_temp = "温度: %d℃\n湿度: %d％" %(temperature, humidity)
      return server._reply_text(fromUser, toUser, reply_temp)
        
  else:
      print "something is worong the humidity,humidity_point,temperature,temperature_point,check is",humidity,humidity_point,temperature,temperature_point,check
      return _do_click_V1001_TEMPERATURES(server, fromUser, toUser, xml)
           
def _do_click_V1001_HELP(server, fromUser, toUser, xml):
    return server._reply_text(fromUser, toUser, u'''此微信公众平台基于树莓派，可以随时随地的以微信端为控制器，与终端进行交互。具体功能请点击菜单选项 ''')


    
_weixin_click_table = {
    
    'V1001_SNAPSHOT'        :   _do_click_SNAPSHOT,
    'V1001_TEMPERATURES'    :   _do_click_V1001_TEMPERATURES,
    'V1001_HELP'            :   _do_click_V1001_HELP,

	
}


class WeixinInterface:
 
    def __init__(self):
        self.app_root = os.path.dirname(__file__)
        self.templates_root = os.path.join(self.app_root, 'templates')
        self.render = web.template.render(self.templates_root)
        self.client = WeiXinClient(my_appid, my_secret, fc=True, path='/tmp')
        self.client.request_access_token()
        self.yee = YeeLinkClient(my_yeekey)
        
 
    def _recv_text(self, fromUser, toUser, xml):
        content = xml.find('Content').text
        reply_msg = content
        return self._reply_text(fromUser, toUser, u'我还不能理解你说的话:' + reply_msg)
        

    def _recv_event(self, fromUser, toUser, xml):
        event = xml.find('Event').text
        try:
            return _weixin_event_table[event](self, fromUser, toUser, xml)
        except KeyError, e:
            print '_recv_event: %s' %e
            return server._reply_text(fromUser, toUser, u'Unknow event: '+event)

    def _recv_image(self, fromUser, toUser, xml):
        url = xml.find('PicUrl').text
        req = urllib2.Request(url)
        try:
            resp = urllib2.urlopen(req, timeout = 2)
            print self.yee.image.upload('12345', '27360', fd = resp) #12345替换为自己的yeelink设备的id
        except urllib2.HTTPError, e:
            print e
            return self._reply_text(fromUser, toUser, u'上传图片失败！')
        view = 'http://www.yeelink.net/devices/' #自己的YEELINK页面
        return self._reply_text(fromUser, toUser, u'图片已收到已上传到此地址:'+view)

    def _recv_voice(self, fromUser, toUser, xml):
        return self.render.reply_text(fromUser,toUser,int(time.time()),u"接收声音处理的功能正在开发中")

    def _recv_video(self, fromUser, toUser, xml):
        return self.render.reply_text(fromUser,toUser,int(time.time()),u"接收视频处理的功能正在开发中")

    def _recv_location(self, fromUser, toUser, xml):
        return self.render.reply_text(fromUser,toUser,int(time.time()),u"接收位置处理的功能正在开发中")

    def _recv_link(self, fromUser, toUser, xml):
        return self.render.reply_text(fromUser,toUser,int(time.time()),u"接收链接处理的功能正在开发中")

    def _reply_text(self, toUser, fromUser, msg):
        return self.render.reply_text(toUser, fromUser, int(time.time()),msg)

    def _reply_image(self, toUser, fromUser, media_id):
        return self.render.reply_image(toUser, fromUser, int(time.time()), media_id)

    def _reply_news(self, toUser, fromUser, title, descrip, picUrl, hqUrl):
        return self.render.reply_news(toUser, fromUser, int(time.time()), title, descrip, picUrl, hqUrl)


    def GET(self):
        #获取输入参数
	data = web.input()
        if _check_hash(data):
            return data.echostr

        
    def POST(self):        
        str_xml = web.data() #获得post来的数据
        xml = etree.fromstring(str_xml)#进行XML解析
        msgType=xml.find("MsgType").text
        fromUser=xml.find("FromUserName").text
        toUser=xml.find("ToUserName").text
        
        if msgType == 'text':
            return self._recv_text(fromUser, toUser, xml)
	    
        if msgType == 'event':
            return self._recv_event(fromUser, toUser, xml)
	    
        if msgType == 'image':
            return self._recv_image(fromUser, toUser, xml)
	   
        if msgType == 'voice':
            return self._recv_voice(fromUser, toUser, xml)
	    
        if msgType == 'video':
            return self._recv_video(fromUser, toUser, xml)
	    
        if msgType == 'location':
            return self._recv_location(fromUser, toUser, xml)
	    
        if msgType == 'link':
            return self._recv_link(fromUser, toUser, xml)
	    
        else:
            return self._reply_text(fromUser, toUser, u'Unknow msg:' + msgType)


application = web.application(urls, globals())

if __name__ == "__main__":
    application.run()
