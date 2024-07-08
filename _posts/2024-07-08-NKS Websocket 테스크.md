---
layout: single
title: "NKS Web Socket 테스트"
categories:  NKS
tags: [ DevOps , Kubernetes , NKS ]
toc: true
---


## NKS 웹소켓 테스트

웹 소켓을 pytho으로 구현해보고 server측을 dockerfile로 만든 후 NKS에 배포를 해보자.

준비
NKS
dockerhub 계정
docker
python

### python 코드 구현 및 테스트

#### server.py

만약 모듈이 없다면 pip에서 다운로드를 한다.
> pip install "Modual_Name"
~~~bash

import asyncio
import websockets

async def echo(websocket, path):
    async for message in websocket:
        print(f"Received message from client: {message}")
        await websocket.send(f"Echo: {message}")

async def main():
    async with websockets.serve(echo, "0.0.0.0", 8765):
        print("Server started. Listening on ws://0.0.0.0:8765")
        await asyncio.Future()  # Run forever

if __name__ == "__main__":
    asyncio.run(main())

~~~

#### client.py
~~~bash

import asyncio
import websockets

async def hello():
    uri = "ws://localhost:8765"
    async with websockets.connect(uri) as websocket:
        message = "Hello, WebSocket!"
        print(f"Sending message to server: {message}")
        await websocket.send(message)
        response = await websocket.recv()
        print(f"Received message from server: {response}")

if __name__ == "__main__":
    asyncio.run(hello())

~~~


#### Local 환경에서 테스트
~~~bash

1.
python server.py

2.
python client.py

~~~

커멘트창으로 통신이 되는 이력이 조회된다.



### dockerfile로 만들기

> server.py에 localhost를  0.0.0.0으로 변경

설치된 모듈을 requirments.txt 파일로 옮기기
~~~bash

pip freeze > requirements.txt

~~~


#### Dockerfile 예제
~~~bash

# Use the official Python image from the Docker Hub
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install -r requirments.txt

# Make port 8765 available to the world outside this container
EXPOSE 8765

# Run server.py when the container launches
CMD ["python", "server.py"]

~~~


#### 도커 이미지 빌드 및 레포지토리에 push
~~~bash

docker build -t [docker_hub_name]/[image_name]:[tag] .
docker push [docker_hub_name]/[image_name]:[tag] 

~~~



### NKS로 Pod 생성 및 배포
#### kubectl 명령어로 생성
~~~bash

kubectl create deploy [deploy_name]  --image [docker_hub_name]/[image_name]:[tag] --port 8765

kubectl expose deploy [deploy_name] --type=LoadBalancer 

~~~
#### Service yaml 수정
~~~bash

kubectl edit svc [service_name]

```
추가 
  annotations:
    TCP-80.loadbalancer.nhncloud/pool-session-persistence: SOURCE_IP


변경
  port: 80
   
```
~~~



### Local에서 NKS에 호출

#### client.py 파일 코드 변경
~~~bash
변경
uri = "ws://[LB에 exteral IP]:80"

### 변경 후 python 실행 
python client.py


~~~