#!/usr/bin/env bash

uv sync --all-packages

RAR_VERSION=711
cd /tmp
wget "https://www.rarlab.com/rar/rarlinux-x64-$RAR_VERSION.tar.gz"
tar -xzf "rarlinux-x64-$RAR_VERSION.tar.gz"
cd rar
sudo install -m 755 rar /usr/local/bin/
sudo install -m 755 unrar /usr/local/bin/

sudo apt update && sudo apt install texlive-full -y
