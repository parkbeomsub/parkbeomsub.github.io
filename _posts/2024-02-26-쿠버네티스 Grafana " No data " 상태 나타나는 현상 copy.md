---
layout: single
title: "쿠버네티스 Calico - File is already up to date, skipping file="/host/opt/cni/bin/bandwidth" 나타나는 현상"
categories: linux
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , monitoring, promethus, grafana, calico  ]
toc: true
---



#  Calico - File is already up to date, skipping file="/host/opt/cni/bin/bandwidth" 


## 증상
File is already up to date, skipping file="/host/opt/cni/bin/bandwidth"

## 원인
systemctl status kube-proxy
System clock synchronized: no 라서 발생


## 해결방법
~~~
systemctl restart chronyd.service
~~~
