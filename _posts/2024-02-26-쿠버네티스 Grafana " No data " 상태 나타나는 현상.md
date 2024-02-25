---
layout: single
title: "쿠버네티스  Grafana " No data " 상태 나타나는 현상"
categories: linux
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , monitoring, promethus, grafana, loki  ]
toc: true
---



#  Grafana " No data " 상태 나타나는 현상
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory13.png)

- 원인
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory14.png)
System clock synchronized: no 라서 발생


- 해결방법
~~~
systemctl restart chronyd.service
~~~
