---
layout: single
title: "NHN Cloud Ingress에 https 설정"
categories:  Devops
tags: [linux, certbot, ssl , DevOps ,Docker , NHN Cloud ]
toc: true
---


## NHN Cloud Ingress에 https 설정


[인증서발급](https://parkbeomsub.github.io/devops/Docker%EB%A5%BC-%ED%99%9C%EC%9A%A9%ED%95%98%EC%97%AC-https-%EC%9D%B8%EC%A6%9D%EC%84%9C-%EB%B0%9C%EA%B8%89/)

#### 위 링크에서 인증서를 획득했다면 아래와 같이 설정하여 진행하고 접속 테스트해보자

1. Ingress 아이피 확인 및 Domain 등록

~~~bash

# 인그레스 컨트롤러 LB확인 
kubectl get svc -n ingress-nginx

# 해당 아이피를 DNS에  도메인으로 등록  및 secret 생성

cd 인증서가 있는 경로로 이동
kubectl create secret tls  bscert  --cert  cert.pem  --key privkey.pem


~~~


2. 테스트 서비스 

~~~bash

apiVersion: apps/v1
kind: Deployment
metadata:
  name: coffee
spec:
  replicas: 3
  selector:
    matchLabels:
      app: coffee
  template:
    metadata:
      labels:
        app: coffee
    spec:
      containers:
      - name: coffee
        image: nginxdemos/nginx-hello:plain-text
        ports:
        - containerPort: 8080
---
apiVersion: v1
kind: Service
metadata:
  name: coffee-svc
spec:
  ports:
  - port: 80
    targetPort: 8080
    protocol: TCP
    name: http
  selector:
    app: coffee
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: cafe-ingress-host
spec:
  ingressClassName: nginx
  rules:
  - host: [yourDomain]
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: coffee-svc
            port:
              number: 80
  tls:
  - hosts:
    -  [yourDomain]
    secretName: bscert



~~~


3. 실행 후 Inress 에 Address가 정상적으로 생긴 것을 확인하고 접속 시도




