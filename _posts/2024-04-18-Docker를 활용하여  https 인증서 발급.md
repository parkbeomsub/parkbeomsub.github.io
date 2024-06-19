---
layout: single
title: "Docker를 활용하여  https 인증서 발급"
categories:  Devops
tags: [linux, certbot, ssl , DevOps ,Docker ]
toc: true
---


## Docker를 활요하여 인증서 발급

- certbot 을 사용하기 위해 Python, pip, certbot 등 여러가지 패키지를 설치해야하지만 docker를 이용하는 유저라면 간단하게 진행이 가능하다. 아래의 커멘트를 확인해보자.
- 나의 Domain : *.base-on.co.kr

~~~bash

docker run -it --rm --name certbot   -v '/etc/letsencrypt:/etc/letsencrypt'   -v '/var/lib/letsencrypt:/var/lib/letsencrypt'   certbot/certbot certonly -d '*.base-on.co.kr' --manual --preferred-challenges dns --server https://acme-v02.api.letsencrypt.org/directory --register-unsafely-without-email

~~~

![https://cafe.naver.com/kubeops](/Images/base/ssl1.png)


- 사진을 확인하면 DNS서버에 특정 도메인에 TXT로 넣어라는 내용이 있는데 사용하시는 DNS서버에 설정만 해줍니다.

____ 

- 저는 AWS Route53을 사용하기에 사진과 같이 작업했습니다.
  

![https://cafe.naver.com/kubeops](/Images/base/ssl2.png)


- https://toolbox.googleapps.com/apps/dig/#TXT/_acme-challenge.base-on.co.kr
- 위와 같이 txt가 적용되었는지 확인할 수 있는 링크를 CMD창으로 알려주고 접근해서 확인이 된다면 엔터를 눌러 마무리한다.







- 결과값이 : /etc/letsencrypt 경로로 쌓이게 되고  해당 경로에서 인증서를 가져오면된다.

~~~bash

/etc/letsencrypt/live/yourdomain.com/
~~~



관련하여 참고 링크는 아래와 같고 도커에 대한 이야기와 명령어에 대한 설명이 있음

1. [참고1](https://lynlab.co.kr/blog/72?source=post_page-----8b00a29a8bd3--------------------------------)




* PROJECT ID : boEv7B6h
* UUID : ac4f0cfe-dd11-4bcb-9a84-0e32e4e0b7c5
* email : chyu@sgacorp.kr
* 요청일시 : 2024-05-08 14:59
* 기타 요청사항
    * 신청 유형 : Volume 생성
    * Volume 명 : prd2user
    * 용량 : 300
    * Snapshot : true
    * VPC : 0282c629-1772-4153-b21a-8531eed82598, 192.168.16.0/20
    * Subnet : d9862e0e-ab5e-48ba-900b-1b5206b6e0bd, 192.168.20.0/24
    * NAS 명 : -
    * regionCode: GOV

