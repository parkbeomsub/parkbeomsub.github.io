---
layout: single
title: "쿠버네티스 application으로 알아보는 Secret &ConfigMap"
categories: linux
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , Secret , ConfigMap  ]
toc: true
---



#  쿠버네티스 Secret , ConfigMap

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory24.png)

## ConfigMap
- Pod에 환경 변수이다.  configmap의 내용을 container에 envFrom 에서 확인 가능.
    ~~~
    env
    ~~~
위 명령어로 확인

### 사용 범위

 - 인프라환경에 관한 값 

    스프링을 예제로 환경이 개발/ 운영/ 검증인지
    ~~~
    spring_profiles_active: "dev"
    ~~~

 - 제어를 위한 값
    
    스프링을 예제로 서비스마다 구분하여 MSA로 많이 사용함
    ~~~
    application_role: "ALL"
    ~~~
 - 외부 환경을 앱으로 주입시키기 위한 값
    
    외부와 연결을 위한  예를 들면 DB를 연결하기 위한 path 값
    ~~~
    postgresql_filepath: "/usr/src/myapp/datasource/postgresql-info.yaml"
    ~~~

### 주의사항
  전부 ConfigMap으로 바꿀 수 있어서 좋아진게 맞지만, 레거시한 환경에서 모든 서비스가 kubernetes에 올라가지 않았기 때문에 담당자와 상의가 필요할 것 같고, 영역별로 고려해야할 사항이 있는지 확인이 필요하다.
   

## Secret 
- Pod에 볼륨은  파드와 특정 저장소를 연결하는 속성이고 시크릿을 연결하고 파드 안으로 들어가서 마운팅된 패스를 조회하면 시크릿에 스트링 데이터가 있는 것을 확인 가능하다. 5초마다 kubernetes에서 환경조회를 하기 때문에 파드 재실행이 필요없다.

  아래와 같이 생성을 하면 쓰기전용속성이고 실제 저장은 configmap과 같은 데이터라는 속성으로 저장디되는데 내용을 보면 키값은 있는 그대로 뒤에 value에 해당하는 부분이 base64인코딩된 값으로 바뀌어서 저장되어야한다.

-파일
~~~
postgresql-info.yaml: |
driver-class-name: "org.postgresql.Driver"
url: "jdbc:postgresql://postgresql:5431"
username: "dev"
password: "dev123"
~~~

인코딩된 내용

~~~

postgresql-info.yaml: >-
ZHJpdmVyLWNsYXNzL.....kZXYiCnBhc3N3b3JkOiAi
ZGtmaTNuZmFrK2RmajMiCg==
~~~


### 타입
 - opaque: 투명이라는 뜻으로 configmap 과 유사
 - docker-registry : 도커로그인에 필요한 아이디 패스워드값로 정해진 키값을 넣어야함
    - dockercfg : ~/.dockercfg   , dockerconfigjson : ~/.docker/config/json
 - tls : 인증서 관련   .crt .key 내용이 존재
 - ssh-auth: ssh를 위한 자격증명
 - basic-auth : 기본인증을 위한 증명
 - service-account-token :  임의 사용자 정의 데이터
 

### 데이터 암호화 권장
 - 파이프라인을 통해 생성하지 말고 클러스터 내부를 통해 생성할 수 있도록 권한 설정 (사용비권장 : dashboard, kubectl)
 - 특정 키를 통해 암호화된 문자파일 후 파이프라인을 통해 실행되나 복호화를 해야되는 경우 어플리케이션에서 복호화하는 기능을 구현하거나 was에서 제공해주는    > 추천 소프트웨어 : vault





## 마무리
데이터 암호화는 Secret과 무관하다고 봐야하며 다른 방법으로 진행해야할 것 같다. configmap에 중요한 정보값을 넣게 되면 Env명령어를 통해 쉽게 노출이 가능하여 해당 방법은 지양해야한다. < Applog에 노출가능성도 있음>