---
layout: single
title: "nginx ingress x-forwarded-header 사용하기"
categories: kubernetes
tags: [kubernetes, ingress, how to use a x-forwarded-headed in nginx ingress ]
toc: true
---


# nginx ingress x-forwarded-header 사용하기
Nginx controller에서  XFH을 사용이 필요한 경우에 하기의 방법으로 진행해보자.

- 준비물

K8S환경
nginx ingress 설치




##  DSR만 존재하는 경우

Ingress에 LB를 사용하여 배포하면  유입 순서가  client ->  LB ->  Ingress -> Svc 이다.

여기서 Nginx Ingress가 reverse proxy역활을 하기 때문에 Sevive로 전달되는 트레픽에는 Ingress에서 전달해주는 X-forward-* 값을 사용하게 된다. 위 경우에 Nginx-forwarded-for 옵션이 false로 지정되고 클라이언트가 보내는 x-forwarded-*이 있더라도 무시해도 덮어쓴다.



## 앞에 Reverse Proxy가 존재하는경우

아래의 순서일 경우 

Client -> LB(DRS) -> L7(Proxy) -> Ingress -> Service


실제로 클라이언트을 트래픽이 서비스까지 가기 위해  Reverse Proxy를 2번 거치게 된다.  nginx ingress 입장에서는 L7 proxy에서 전달되는 X-forwarded-* 값을 신회하고 연결되는 서비스로 넘겨줘야한다. 이 경우에는   controller에 use-forwarded-for : true로 지정한다.
~~~
apiVersion: v1
kind: ConfigMap
metadata:
  labels:
    app.kubernetes.io/name: ingress-nginx
    app.kubernetes.io/part-of: ingress-nginx
  name: ingress-forwarded
  namespace: ingress-nginx
data:
  ## ... other values 생략.. ##
  use-forwarded-headers: "true"
  ~~~

  
