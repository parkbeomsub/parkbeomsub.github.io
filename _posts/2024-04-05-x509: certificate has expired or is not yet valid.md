---
layout: single
title: "Error response from daemon: Get \"https://registry-1.docker.io/v2/\": x509: certificate has expired or is not yet valid:"
categories:  Devops
tags: [linux, container, kubernetes , DevOps ,Docker ]
toc: true
---



# Error response from daemon: Get "[https://registry-1.docker.io/v2/](https://registry-1.docker.io/v2/)": x509: certificate has expired or is not yet valid: 문제

## 현상
로그인하면 아래와 같이 문제가 발생한다.
![https://cafe.naver.com/kubeops](/Images/time.png)

## 시간 동시화로 인한 문제
확인해보니 시간이 현재 시간과 다른 부분을 확인 
![https://cafe.naver.com/kubeops](/Images/time2.png)

## 해결방법
- 원인은 Server에 시간 동기화가 안되어 있는 경우이여  동기화를 위해  설정파일 변경
- 나는 chronyd를 사용하지만 ntpd를 사용하시는 분이라면 알맞게 수정
![https://cafe.naver.com/kubeops](/Images/time3.png)