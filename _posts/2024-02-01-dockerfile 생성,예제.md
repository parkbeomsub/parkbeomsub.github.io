---
layout: single
title: "Dockerfile 예제 생성"
categories: docker
tags: [docker, dockerfile, dockeriamge ]
toc: true
---



# Dockerfile의 기본 구문


Dockerfile은 텍스트 형식의 파일로, 에디터 등을 사용하여 작성합니다. 확장자는 필요 없으
며, 'Dockerfile 이라는 이름의 파일에 인프라의 구성 정보를 기술합니다. 또한 Dockerfile 이외
의 파일명으로도 작동하지만, 이때는 Dockerfile에서 이미지를 빌드할 때 파일명을 명시적으로
지정해야 합니다.

![te](/Images/docker/Untitled48.png)

## 주석

Dockerfile에는  어떤 이미지로부터  생성할지'라는 정보를 반드시 기술, 해당 이미지는 베이스이미지라고 합니다.

```jsx
FROM [이미지명] 
FROM [이미지명]:[태그명]
FROM [이미지명]@[다이제스트]
```

예제 : 

```jsx
FROM centos:enctos7
```

```jsx
FROM nginx@sha256:10d1f5b58f74683ad34eb29287e07dab1e90f10af243f151bb50aa5dbb4d62e
```

![Untitled](/Images/docker/Untitled49.png)



## Dockerile의 빌드와 이미지 레이어

```jsx
docker build -t [생성할 이미지명]:[태그명] [Dockerfile위치]
```

![Untitled](/Images/docker/Untitled50.png)

이미지가 아닌 Dockerfile로 구성하면  이미지를 저장하는 저장공간 및 관리에 용이하다

베이스이미지가 PC에 없으면 레포지토리에서 다운로드/  PC에 있다면 PC이미지에서 다운로드

파일이름이 Dockerfile이 아닌 경우  

```jsx
docker build -t 이미지  -f Dockerfile.base .
```

- Github에선 Dockerfile의 파일명이 아니면  이미지 자동 생성 기능이 불가능

표준 입력에서의 빌드

```jsx
docker build - < Dockerfile
```

위 경우 빌드에 필요한 파일을 포함시킬 수 없어 ADD명령으로 이미지 안에 추가할 수 없다. Dockerfile과 빌드에 필요한 파일을 tar로 모아두고 표준 입력에서 지정

```jsx
$ tar tvfz docker.tar.gz
-2W-r--r-- docker/staff 92 2015-07-16 16:12 Dockerfile
-2W-r--r-- docker/staff  5 2015-07-16 16:13 dummyfile

s docker build - ^ docker.tar.gz
Sending build context to Docker daemon
229 B
Sending build context to Docker daemon
step 0 : FROM centos :centos7
---> 7322fbe74aa5
Step 1 : MAINTAINER 0.1 your-nameayour-domain.com
---> Running in eb2987cbbe61
---> e3dffaea3b65
Removing intermediate container eb2987cbbe61
Step 2 : ADD durmytile /tmp/dunmyfile ---> 9aca58965f2e
Removing intermediate container 59d2a9875bga
Successfully built gacas896sf2e
```

* 중간이미지 재사용

Docker는 이미지를 빌드할 때 자동으로 중간 이미지를 생성합니다. 그리고 다른 이미지를 빌드할 때 중
간 이미지를 내부적으로 재이용함으로써 빌드를 고속으로 수행

만약 캐시사용을 원하지 않으면  —no-cache 옵션 사용

![Untitled](/Images/docker/Untitled51.png)


## 이미지 레이어 구조

Dockerfile을 빌드하여 Docker 이미지를 작성하면 Dockerfile의 명령별로 이미지를 작성

작성된 여러 개의 이미지는 레이어 구조로 되어있음

이미지 작성 중 step으로 나타나는 것 들이 중간 이미지 작성이다.

해당 이미지 바탕으로  여러 개의 이미지를 생성하는 경우 베이즈 이미지 레이어가 공유되고, 이미지를 겹침으로써 Docker에서는 Disk용량이  효율적으로 사용


## Dockerfile만들기

예제

```jsx
git clone https://github.com/asashiho/dockertext2
cd dockertext2/chap05/multi-stage/
```

![Untitled](/Images/docker/Untitled52.png)

파일 설명

Build 이미지

Go 1.8.4 버전을 베이스 이미지를 두고 builder라는 별명(AS) 붙임

개발에 필요한  버전을 설치하여 로컬 환경에 있는 main.go파일을 컨테이너로 복사

명령어 go build로 greet라는  실행 가능 바이너리 파일을 작성

Product 이미지

busybox(기본적인 리눅스 명령어들을 하나의 파일로 모아 놓은 것)라는 이미지를 사용 , 개발용 환경의 docker이미지로 빌드한 greet라는 바이너리파일을  해당  이미지로 복사( —from 옵션을 활용하여  어느 이미지로 부터 복사할 것인지 설명)

```jsx
docker build -t greet .
docker container run -it --rm greet  asa
```



## 명령 및 데몬 실행 (RUN)

RUN은  도커이미지가 생성될 때 실행된다.

```jsx
RUN [하고 싶은 명령어]
```

RUN  사용 방법 

###  Shell 형식으로 기술

```jsx
RUN apt-get install -y nginx
```

/bin/sh -c 를 사용한 결과와 동일하게 동작

### Exec 형식으로 기술

shell형식으로 하면 /bin/sh에서 실행되지만 exec 형식으로 기술하면 쉘을 경유하지 않고 직접 실행합니다.

명령 인수에 $HOME과 같은 환경 변수를 지정할  수 없습니다

```jsx
RUN ["/bin/bash","-c","apt-get install -y nginx"]
```

추가 예제

```jsx
FROM ubuntu:latest

RUN echo This is  a Shell
RUN ["echo" , " This is a Shell"]
RUN ["/bin/bash" "-c", "echo 'This is a Shell , It use EXEC tyep' "]
```

```jsx
docker build -t run-sample .

docker history run-sample
---
Sending build context to Docker daemon 1.307 GB step 1/4 : FROM ubuntu: latest
--->
step 2/4 : RUN echo 안녕하세요 Shell 형식입니다. --> Running in b6ebeeef246a
안녕하세요 She11 형식입니다 ---> 
Removing intermediate container-> Running in 
안녕하세요 Exec 형식입니다 --> 
Removing intermediate container 
Step 4/4 : RUN ("/bin/bash", "-c", "echo' 안녕하세요 Exec 형식에서 bash를 사용해 보았습니다' 미]
--> Running in
안녕하세요 Exec 형식에서 bash를 사용해 보았습니다 ---> 
```

실행 결과를 확인하면 Shell 형식으로 기술한 RUN 명령은 /bin/sh, Exec 형식으로 기술한 RUN 명령은 쉘을 통하지 않고 실행되는 것을 알 수 있습니다. 또한 쉘을 명시적으로 지정하고 싶을 때는 Exec 형식을 사용하면 /bin/bash를 사용하여 명령이 실행되는 것을 알 수 있습니다. 따라서 /bin/sh를 경유하여 명령을 실행하고 싶을 때는 Shel 형식으로 기술하고, 그 외의 경우는 Exec 형식으로 기술하는 것이 좋습니다.

*이미지의 레이어

```jsx
#RUN 을 여러 줄로 기입. 모든 줄이 별도 레이어로 생성
RUN yum -y install httpd
RUN yum -y install php
RUN yum -y install php-mbstring
RUN yum -y install php-pear

#RUN을 한줄로 지정하는경우  하나의 레이어만 생성됨.  \ 을 통해 줄바꿈도 가능
RUN yum -y install  httpd php php-mbsting php-pear

#예제
RUN yum -y install\
					 httpd\
           php\ 
           php-mbsting\
           php-pear
```

---

데몬실행 (CMD)

RUN은 명령은 이미지를 작성하기 위해  기술,생성된 컨테이너 안에서 명령어 실행하려면 CMD사용 

여러 줄을 적으면 마지막 줄에 유효함 

```jsx
CMD [하고 싶은 명령어]
```

RUN 명령어와 문구는 동일 

```jsx
#EXEC 형식
CMD ["nginx", "-g", "daemon off;"]
#Shell 형식
CMD nginx -g daemon off;
```

ENTRYPOINT 명령의 파라미터로 기술

```jsx
# 베이스 이미지 설정
FROM ubuntu: 16.04
# Nginx 설치
RUN apt-get -y update && apt-get -y upgrade RUN apt-get -y install nginx
# 포트 지정 
EXPOSE 80
# 서버 실행
CMD ["nginx", "-g", "daemon off;"]
```



## 데몬 실행 (ENTRYPOINT)

해당 명령어는 Dockerfile 에서 빌드한 이미지로 부터 docker컨테이너를 시작하기 때문에 docker container run 명령어를 실행했을 때 실행됨

```jsx
ENTRYPOINT [명령어]

#EXEC 형식
ENTRYPOINT ["nginx", "-g", "daemon off;"]

#SHELL 형식
ENTRYPOINT nginx -g daemon off;
```

cmd 와의 차이는  컨테이너 시작 명령어 실행 때 동작에 있다. cmd는 컨테이너 시작 시에  실행하고 싶은 명령어를 정의해도 docker run 명령어 실행 시에 인수로 새로운 명령어를 지정한 경우 이것을 우선 실행함

ENTRYPOINT는  명령에서 지정한 명령은 반드시 컨테이너에서 실행되는데, 실행 시에 명령 인수를 지정하고 싶을 때는 CMD명령과 조합하여 사용해된다. Entrypoint 명령으로 실행하고 싶을 명령 자체를 지정하고 CMD명령으로는 그명령의 인수를 지정하면, 컨테이너를 실행했을 때의 기본 동작을 결정할 수 있습니다.

ENTRYPOINT 명령과 CMD 명령을 조합한 

```jsx
# Docker 이미지 취득
FROM ubuntu: 16.04
# TOP 실행 
ENTRYPOINT ["top"]
CMD ["-d", "10"]
```


## 빌드 완료 후에 실행되는 명령(ONBUILD)

ONBUILD 명령은 그 다음 빌드에서 실행할 명령을 이미지 안에 설정하기 위한 명령입니다.
예를 들어 Dockerfile에 ONBUILD 명령을 사용하여 어떤 명령을 실행하도록 설정하여 빌드하고 이미지를 작성합니다. 그리고 그 이미지를 다른 Dockerfile에서 베이스 이미지로 설정하 여 빌드했을 때 ONBUILD 명령에서 지정한 명령을 실행시킬 수 있음

```jsx
ONBUILD [실행하고 싶은 명령]
```

예를 들면 웹 시스템을 구축할 때 OS 설치 및 환경 설정이나 웹 서버 설치 및 각종 플러그인 설치 등과 같은 인프라 환경 구축과 관련된 부분을 베이스 이미지로 작성합니다. 이때 ONBUILD 명령으로 이미지 안에 개발한 프로그램을 전개하는 명령(ADD나 COPY 명령 등)을 지정합니다.
애플리케이션 개발자는 애플리케이션의 구축 부분을 코딩하고 이미 작성이 끝난 베이스 이미 지를 바탕으로 한 이미지를 작성합니다. 이 이미지 안에는 프로그래밍이 끝난 업무 애플리케이
션이 전개됩니다.

베이스이미지 작성

```jsx
# 베이스 이미지 설정
FROM ubuntu: 17.10
# Nginx 설치
RUN apt-get -y update && apt-get -y upgrade 
RUN apt-get -y install nginx
# 포트 지정 
EXPOSE 80
# 웹 콘텐츠 배치
ONBUILD ADD website.tar /var/www/html/
#Nginx 실행
CMD ("nginx", "-g", "daemon off;"]

---
#이미지 빌드
 docker build -t web-base -f Dockerfile.base .
```

이후  이미지를 빌드하게 되면 dockerfile 위치에 있는 website.tar(html,css,파일,사진)둬 신규 빌드 시 참조하도록 한다.

```jsx
docker build -t photoview-image .
---
docker container run -d -p 80:80 photoview-image
---
#상세보기
docker image inspect --format="\{\{.Config.OnBuild \)\}" web-base
```

onbuild를 통한 개발의 예

미들웨어/인프라구축 담당자가  베이스이미지를 구축하면  동일한 환경에서 개발팀에서 개발

---

시스템 콜 시그널의 설정(STOPSIGNAL 명령)

컨테이너를 종료할 때에 송신하는 시그널을 설정하려면 STOPSIGNAL 명령

```jsx
STOPSIGNAI [시그널]
```

---

컨테이너의 헬스 체크 명령(HEALTHCHECK 명령)

프로세스가 정상적으로 작동하고 있는지를 체크하고 싶을 때는 HEALTHCHECK 명령

```jsx
HEALTHCHBCK [옵션] CMD 실행할 명령
```

![Untitled](/Images/docker/Untitled53.png)

```jsx
HEALTHCHBCK --interval=5m --cimeout=3s CMD cur1 -f http://1ocalhost/ || exit 1
```

과는 docker container inspect 명령 Health 상태 확인가능 

---

환경 및 네트워크 설정

환경변수 설정(ENV 명령)

Dockerfile 안에서 환경변수를 설정하고 싶을 때는 ENV 명령을 사용

```jsx
ENV [key] [value]
ENV [key]=[value]
```

key value 형으로 지정하는 경우

단일 환경변수에 하나의 값을 설정합니다. 첫 번째 공백 앞을 key로 설정하면 그 이후는 모두 문자열로서 취급합

```jsx
BNV myName "Shiho ASA"
BNV myorder Gin Whisky Calvados 
ENV myNickname miya
```

key=value로 지정하는 경우

한 번에 여러 개의 값을 설정할 때는 환경변수를 key=value로 지정

```jsx
ENV myName="Shiho ASA" \
 myorder=Gin\ Whiskyl\ Calvados\ 
 myNickName=miya
```

하나의 ENY 명령으로 여러 개의 값을 설정하므로 만들어지는 Docker 이미지는 하나

변수 앞에 |를 추가하면 이스케이프 처리를 할 수 있습니다. 예를 들어 '(SmyName은 SmyName 이라는 리터럴로 치환

ENY 명령으로 지정한 환경변수는 킨테이너 실행 시의 docker container run 명령의 --eny 옵선을 사용하면 변경

---

작업 디렉토리 지정(WORKDIR 명령)

Dockerfile에서 정의한 명령을 실행하기 위한 작업용 디렉토리를 지정하려면 WORKDIR 명령을 설정

```jsx
WORKDIR [작업 디렉토리 경로]
```

WORKDIR 명령은 Dockerfile에 쓰여 있는 다음과 같은 명령을 실행하기 위한 작업용 디렉토리를 지정

RUN 명령
CMD명령
ENTRYPOINT 명령
COPY 명령

ADD 명령

지정한 디렉토리가 존재하지 않으면 새로 작성합니다. 또한 WORKDIR 명령은 Dockerfile 안에서 여러 번 사용할 수 있습니다. 상대 경로를 지정한 경우는 이전 WORKDIR 명령의 경로에 대한 상대 경로

```jsx
#/first/second/third가 출력
WORKDIR /first 
WORKDIR second 
WORKDIR third
RUN ["pwd"]

#환경변수 예
ENV DIRPATH /first 
ENV DIRNAME second
WORKDIR $DIRPATH/$DIRNAME 
RUN ["pwd"]
```

---

사용자 지정(USER 명령)

Dockerfile의 다음과 같은 명령을 실행하기 위한 사용자를 지정할 때는USER 명령

- RUN 명령
- CMD 명령
- ENTRYPOINT 명령

```jsx
USER [사용자명/UID]

#테스트
RUN ["adduser", "asa"]
RUN ["whoami"]
USER asa
RUN ["whoami]
```

![Untitled](/Images/docker/Untitled54.png)

---

라벨 지정(LABEL 명령)

이미지에 버전 정보나 작성자 정보, 코멘트 등과 같은 정보를 제공할 때는 LABBL 명령

```jsx
LABEL <키 명>=<값>

#예제
LABEL maintainer "shiho AsAcasashihosmail.asa.seoul>" 
LABEL title="WebAP"
LABEL version="1.0"
LABEI description=This image is WebApplicationServer"

#결과확인
docker image inspect --format="{(.Config.Labels \)\}" [이미지 이름]
```

---

포트 설정(EXPOSE 명령)

```jsx
EXPOSB <포트 번호>
```

EXPOSE 명령은 Docker에게 실행 중인 컨테이너가 listen 하고 있는 네트워크를 알려줍니다. 또한 docker container run 명령의 -p 옵션을 사용할 때 어떤 포트를 호스트에 공개할지를 정의

---

Dockerfile 내 변수의 설정(ARG 명령)

Dockerfile 안에서 사용할 변수를 정의할 때는 ARG 명령을 사용합니다. 이 ARG 명령을 사용 하면 변수의 값에 따라 생성되는 이미지의 내용을 바꿀 수 있습니다. **환경변수인 BNV와는 달리 이 변수는 Dockerfile 안에서만 사용**

```jsx
ARG <이름> [=기본값]
```

Dockerfile을 빌드할 때 **--build-arg** 옵션을 붙여 ARG 명령에서 지정한 YOURNAME'에 'shiho'라는 값을 설정하면  변경 가능

![Untitled](/Images/docker/Untitled55.png)



기본 쉘 설정(SHELL 명령)

```jsx
SHELL ["쉘의 경로", "파라미터"]

# ex
# 기본 쉘 지정
SHBLL ["/bin/bash", "-c"]
# RUN 명령 실행 
RUN echo hello
```

SHELL 명령을 지정하면 그 쉘은 그 이후에 Dockerfile 안에서 Shell 형식으로 지정한 RUN 명령이나 CMD 명령, ENTRYPOINT 명령에서 유효



## 파일 설정


파일 및 디렉토리 추가(ADD 명령)

이미지에 호스트상의 파일이나 디렉토리를 추가할 때는 ADD 명령

```jsx
ADD <호스트의 파일 경로> <Docker 이미지의 파일 경로>
ADD [" <호스트의 파일 경로>""<Docker 이미지의 파일 경로>"]

#ex
ADD host.html /docker_dir/

#patten
# [hos]로 시작하는 모든 파일을 추가 
ADD hos* /docker_dir/
#[hos]+임의의 한 문자 룰에 해당하는 파일을 추가 
ADD hos?.cxt /docker_dir/

#/docker_dir 안의 web이라는 디렉토리에 bost.html을 복사
WORKDIR /docker_dir 
ADD host.html web/
```

- 

이미지에 추가하고 싶은 파일이 원격 파일 URL인 경우, 추가한 파일은 퍼미션이 600(사용자만 읽기 쓰기 가능)이 됨

ADD 명령은 인증을 지원하지 않기 때문에 원격 파일의 다운로드에 인증이 필요한 경우는 RUN 명령에서 wget 명령이나 curl 명령

```jsx
ADD http://ww.wings.msn.to/index.php /docker_dir/web/
```

실행하면 [http://www.wings.msn.to/index.php를](http://www.wings.msn.to/index.php%EB%A5%BC) 다운로드하여 Docker 이 미지 안의 /docker_dir/web/index.php로 퍼미션이 600인 파일

![스크린샷 2023-12-12 오전 1.14.13.png](/Images/docker/1.14.13.png)

또한 이미지 안의 파일 지정이 파일(마지막이 슬래시가 아님)일 때는 URIL로부터 파일을 다운 로드하여 지정한 파일명을 추가합니다.
이미지 안의 파일 지정이 디렉토리(마지막이 슬래시)일 때는 파일명은 URL로 지정한 것이 됩 니다.
호스트의 파일이 tar 아카이브거나 압축 포맷(gzip, bzip2 등)일 때는 디렉토리로 압축을 풉니 다. 단, 원격 URL로부터 다운로드한 리소스는 압축이 풀리지 않으므로 주의

*빌드에 불필요한 파일 제외

Docker에서 빌드를 하면 빌드를 실행한 디레토리 아래에 있는 모든 파일이 Docker 데몬으로 전송됩니
다. 그렇기 때문에 빌드에서 제외하고 싶은 파일이 있는 경우는 'dockerignore'이라는 이름의 파일 안에 해당 파일명을 기술하기 바랍니다. 여러 개의 파일을 지정할 때는 줄 비꿈을 해서 파일명을 나열

---

파일 복사(COPY 명령)

```jsx
COPY <호스트의 파일 경로> <Docker 이미지의 파일 경로>
COPY ["<호스트의 파일 경로>" "<Docker 이미지의 파일 경로>"]
```

ADD 명령과 COPY 명령은 매우 비슷합니다. ADD 명령은 원격 파일의 다운로드나 아카이 브의 압축 해제 등과 같은 기능을 갖고 있지만, COPY 명령은 호스트상의 파일을 이미지 안으 로 복사하는' 처리만 합니다. 이 때문에 단순히 이미지 안에 파일을 배치하기만 하고 싶을 때는 COPY 명령

*Docker의 빌드에 필요 없는 파일은 Dockerile과 똑같은 디렉토리에 두지 않도록 주의

---

볼륨 마운트(VOLUME 명령)

이미지에 볼륨을 할당하려면 VOLUMB 명령

```jsx
VOLUMB["/마운트 포인트"]
```

VOLUMB 명령은 지정한 이름의 마운트 포인트를 작성하고, 호스트나 그 외 다른 컨테이너
로부터 볼륨의 외부 마운트를 수행합니다. 설정할 수 있는 값은 VOLUME ["/var/log/"]와 같은
JSON 배열, 또는 VOLUME /var/log4 VOLUME /var/log /var/db와 같은 여러 개의 인수로

된 문자열을 지정할 수 있습니다.
컨테이너는 영구 데이터를 저장하는 데는 적합하지 않습니다. 그래서 영구 저장이 필요한 데

이터는 컨테이너 밖의 스토리지에 저장하는 것이 좋습니다.
영구 데이터는 Docker의 호스트 머신상의 볼륨에 마운트하거나 공유 스토리지를 볼륨으로 마

운트 하는 것이 가능합니다.