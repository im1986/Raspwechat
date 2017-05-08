#!/bin/sh

echo “SETUP”

sudo pip install web.py
#添加树莓派开机启动
sudo cp -f weichat /etc/init.d/weichat
sudo chmod 755 /etc/init.d/weichat
sudo update-rc.d weichat defaults