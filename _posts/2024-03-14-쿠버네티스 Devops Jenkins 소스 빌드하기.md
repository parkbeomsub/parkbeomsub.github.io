---
layout: single
title: "쿠버네티스 Devops Jenkins 소스 빌드하기"
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins , 1pro ]
toc: true
---


# Jenkins 소스 빌드하기
- 이전에  설치한 K8S환경이 필요합니다.
- [윈도우](https://parkbeomsub.github.io/linux/%EC%BF%A0%EB%B2%84%EB%84%A4%ED%8B%B0%EC%8A%A4-%EC%84%A4%EC%B9%98%ED%95%98%EA%B8%B0(%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD-window)/)
- [MAC](https://parkbeomsub.github.io/linux/%EC%BF%A0%EB%B2%84%EB%84%A4%ED%8B%B0%EC%8A%A4-%EC%84%A4%EC%B9%98%ED%95%98%EA%B8%B0(%EA%B0%9C%EB%B0%9C%ED%99%98%EA%B2%BD-mac)/)

구성도 

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory48.png)

- **설명** 
- 이번 실습때  신규 서버에  jenkins , docker , gradle, openjdk, git 관련하여 설치/설정을 할 것이다. 설정해야되는 부분이 많아 놓치는 부분이 없도록 유의 부탁드립니다.
- 
 


---

### Jenkins  설정
---
<details><summary>Jenkins 로그인 및 admin 설정</summary>

1. 초기 비밀번호
~~~
[root@cicd-server ~]# cat /var/lib/jenkins/secrets/initialAdminPassword
~~~



2. 로그인 
  http://192.168.64.20:8080/login
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory49.png)

3. 플러그 설치
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory50.png)  

4. Admin 사용자 생성
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory51.png)  
5.  [Save and Finish]  -> [Start using Jenkins]  -저장
</details>

---
<details><summary> 전역 설정 (JDK ,GRADLE) </summary>

1. 전역 설정창 진입
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory52.png)  

2. JDK 세팅 (CI/CD 서버에서 진헹)

~~~

[root@cicd-server ~]# find / -name java | grep java-17-openjdk
/usr/lib/jvm/java-17-openjdk-17.0.9.0.9-2.el9.aarch64/bin/java  

~~~

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory53.png)  
* Gradle , JDK 버전 확인 가능

3. JAVA_HOME에 넣기
~~~

# Name : jdk-17
# JAVA_HOME : /usr/lib/jvm/java-17-openjdk-17.0.9.0.9-2.el9.aarch64


~~~

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory54.png)
* OS에 JDK 버전을 확인하자  /bin/java/ 는 제외하여 입력

4. Gradle 세팅

~~~

# Name : gradle-7.6.1
# GRADLE_HOME : /opt/gradle/gradle-7.6.1


~~~

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory54.png)
* Install automatically를 해제하면 수동으로 입력이 가능해짐


-  **저장**

</details>

---
### Docker 계정 생성

~~~
https://hub.docker.com/signup
~~~
---
### Docker 사용 설정
~~~

# jeknins가 Docker를 사용할 수 있도록 권한 부여
[root@cicd-server ~]# chmod 666 /var/run/docker.sock
[root@cicd-server ~]# usermod -aG docker jenkins

# Jeknins로 사용자 변경 
[root@cicd-server ~]# su - jenkins -s /bin/bash

# 자신의 Dockerhub로 로그인 하기
[jenkins@cicd-server ~]$ docker login
Username: 
Password: 

~~~


![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory56.png)

### Master node에서 kube-config 복사
* CI/CD 서버(jenkins 계정 )에서 진행
~~~

# 폴더 생성
[jenkins@cicd-server ~]$ mkdir ~/.kube

# Master Node에서 인증서 가져오기
[jenkins@cicd-server ~]$ scp root@192.168.64.30:/root/.kube/config ~/.kube/

# 인증서 가져오기 실행 후 [fingerprint] yes 와 [password] [본인의 password] 입력

# kubectl 명령어 사용 확인
[jenkins@cicd-server ~]$ kubectl get pods -A


~~~


### Github 가입
~~~

https://github.com/signup

~~~


#### 빌드/ 배포 소스 복사해보기 

링크 :  https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2

쿠버네티스 어나더클래스 GitHub Repository 접속 및 Fork 클릭
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory58.png)

- 다음 창 : Create fork

#### Deploy 수정하기

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory59.png)

- 경로 : 2121/deploy/k8s/deployment.yaml 에서

- 자신의 DockerHub Username 입력해 주세요.  (okas123852 X )

  


### 빌드 /배포 파이프라인을 위한 스크립트 작성 및 실행

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory60.png)

#### 소스 빌드(Build) 하기 - gradle

1. 프로젝트 생성
   >  Item Name: 2121-source-build
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory61.png)

2. Dashboard > 2121-source-build > Configuration > General > GitHub project 선택
   > Project url : https://github.com/k8s-1pro/kubernetes-anotherclass-api-tester
   
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory62.png)


3. 소스 코드 관리
   > Repository URL : https://github.com/k8s-1pro/kubernetes-anotherclass-api-tester.git

   > Branch Specifier : */main  
   
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory62.png)
4. Build Steps > Invoke Gradle script
   > Gradle Version : gradle-7.6.1

   > Tasks : clean build

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory64.png)


5. [저장]
6. Dashboard > 2121-source-build > 지금 빌드 및 로그확인
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory65.png)
7. CICD 서버에서 JAR파일 확인
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory66.png)



####  컨테이너 빌드 하기 - docker

1. 프로젝트 생성
   >  Item Name: Project 2121-container-build

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory75.png)
2.  Dashboard > 2121-container-build > Configuration > General > GitHub project 선택

      ~~~

      Project url : https://github.com/<Your-Github-Uesrname>/kubernetes-anotherclass-sprint2/

      ~~~

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory67.png)

3.  소스 코드 관리
      ~~~

      Repository URL : https://github.com/<Your-Github-Uesrname>/ kubernetes-anotherclass-sprint2.git
      Branch Specifier : */main


      ~~~

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory68.png)



4. 소스 코드 관리 > Additional Behavioures > Sparse Checkout paths
   > Path : 2121/build/docker

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory69.png)


5. Build Steps > Execute shell
   
      ~~~
      # jar 파일 복사
      cp /var/lib/jenkins/workspace/2121-source-build/build/libs/app-0.0.1-SNAPSHOT.jar ./2121/build/docker/app-0.0.1-SNAPSHOT.jar

      # 도커 빌드
      docker build -t <Your_DockerHub_Username>/api-tester:v1.0.0 ./2121/build/docker
      docker push <Your_DockerHub_Username>/api-tester:v1.0.0

      ~~~

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory70.png)
      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory71.png)

6. [저장]
7.  Dashboard > 2121-container-build > 지금 빌드 및 로그 확인

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory72.png)

      DockerFile 확인
      > cat /var/lib/jenkins/workspace/2121-container-build/2121/build/docker/Dockerfile

      ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory73.png)

#### 배포 하기 - kubectl

1. 프로젝트 생성
   >  item name : 2121-deploy

   >  Copy from : 2121-container-build

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory74.png)


2. 소스 코드 관리 > Additional Behavioures > Sparse Checkout paths
   > Path : 2121/deploy/k8s

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory79.png)


3.  Build Steps > Execute shell
   ~~~
   kubectl apply -f ./2121/deploy/k8s/namespace.yaml
   kubectl apply -f ./2121/deploy/k8s/pv.yaml
   kubectl apply -f ./2121/deploy/k8s/pvc.yaml
   kubectl apply -f ./2121/deploy/k8s/configmap.yaml
   kubectl apply -f ./2121/deploy/k8s/secret.yaml
   kubectl apply -f ./2121/deploy/k8s/service.yaml
   kubectl apply -f ./2121/deploy/k8s/hpa.yaml
   kubectl apply -f ./2121/deploy/k8s/deployment.yaml
   ~~~

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory80.png)

4. [저장]
5.  Dashboard > 2121-deploy > 지금 빌드 및 로그 확인
   