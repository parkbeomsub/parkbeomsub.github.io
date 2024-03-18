---
layout: single
title: "Kubernetes Jenkins Pipeline - 기초부터 blue/green 까지 "
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins ,CI/DC ,Jenkens ]
toc: true
---


# 파이프라인 만들기

> 이전에  각 스테이지를 만들고  소스빌드, 컨네이너빌드, 어플리케이션 배포를  별도로 구성했다.
>
> 이번엔  파이프라인을 만들어 한번에 진행해보겠다.

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory85.png)


- 위 사진에 Step 1,2,3  순서로 진행 예정이다


- 우선 아이탬을 정리하겠습니다.
  
### Item 정리하기

1. "+" 눌러  뷰정하기
   
 ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory86.png)

2. 뷰 이름을 정하고,  List View로 선택
   
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory87.png)

3. 리스트에 넣을 아이템 선택
   
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory88.png)


## Step 1   Jenkins Pipeline 기본 구성 만들기

### 아이템 만들기

> 이름 /  Pipeline 선택

> 2211-jenkins_pipeline-step1

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory89.png)

### 파이프라인 스크립트 삽입 

<details><summary>코드보기</summary> 

```jsx
Pipeline script - DOCKERHUB_USERNAME 및 GITHUB_URL 주소 (본인의 Username으로 변경)
```







```jsx
pipeline {
    agent any

    tools {
        gradle 'gradle-7.6.1'
        jdk 'jdk-17'
    }

    environment {
        // 본인의 username으로 하실 분은 수정해주세요.
        DOCKERHUB_USERNAME = '1pro'
        GITHUB_URL = 'https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2.git'
        // deployment.yaml -> image: 1pro/api-tester:v1.0.0        

        // 실습 넘버링 - (수정x)
        CLASS_NUM = '2211'
    }

    stages {
        stage('Source Build') {
            steps {
                // 소스파일 체크아웃
                git branch: 'main', url: 'https://github.com/k8s-1pro/kubernetes-anotherclass-api-tester.git'

                // 소스 빌드
                // 755권한 필요 (윈도우에서 Git으로 소스 업로드시 권한은 644)
                sh "chmod +x ./gradlew"
                sh "gradle clean build"
            }
        }

        stage('Container Build') {
            steps {	
                // 릴리즈파일 체크아웃
                checkout scmGit(branches: [[name: '*/main']], 
                    extensions: [[$class: 'SparseCheckoutPaths', 
                    sparseCheckoutPaths: [[path: "/${CLASS_NUM}"]]]], 
                    userRemoteConfigs: [[url: "${GITHUB_URL}"]])

                // jar 파일 복사
                sh "cp ./build/libs/app-0.0.1-SNAPSHOT.jar ./${CLASS_NUM}/build/docker/app-0.0.1-SNAPSHOT.jar"

                // 컨테이너 빌드 및 업로드
                sh "docker build -t ${DOCKERHUB_USERNAME}/api-tester:v1.0.0 ./${CLASS_NUM}/build/docker"
                script{
                    if (DOCKERHUB_USERNAME == "1pro") {
                        echo "docker push ${DOCKERHUB_USERNAME}/api-tester:v1.0.0"
                    } else {
                        sh "docker push ${DOCKERHUB_USERNAME}/api-tester:v1.0.0"
                    }
                }
            }
        }

        stage('K8S Deploy') {
            steps {
                // 쿠버네티스 배포 
                sh "kubectl apply -f ./${CLASS_NUM}/deploy/k8s/namespace.yaml"
				sh "kubectl apply -f ./${CLASS_NUM}/deploy/k8s/configmap.yaml"
				sh "kubectl apply -f ./${CLASS_NUM}/deploy/k8s/secret.yaml"
				sh "kubectl apply -f ./${CLASS_NUM}/deploy/k8s/service.yaml"
				sh "kubectl apply -f ./${CLASS_NUM}/deploy/k8s/deployment.yaml"
            }
        }
    }
}
```

</details>


### 저장


   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory90.png)


### 실행하기 (지금 빌드)

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory91.png)


- 관련 문제 확인 법
  - 우선 sslhandshake 관련한 문제가 발생
  > 우선  설치한 Java , Gradle  환경 설정과 버전을 확인하고, 실패되는 명령어를 CICD에서 실행해본다. 


### Pipeline 설명

1. 기본 틀
   
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory92.png)
   
   - Agent 
     - agent any: 사용 가능한 에이저트에서 파이프라인을  stage를 실행
     - agent label(node) : 지정된 레이블에서 stage가 실행
     - agent docker : Docker 빌드를 제공해주는 agent 사용
     - agent dockerfile : Dockerfile을 직접 쓸 수 있는 Agent 사용


## Step 2 Github 연결 및 파이프라인 세분화

### 아이템 만들기


> 이름 /  Pipeline 선택

> Pipeline  : 2212-jenkins_pipeline-step2
> 
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory93.png)

###  Configure > General > GitHub project에 Project url 입력

> Project url : https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2/

 > Github URL - k8s-1pro를 (본인의 Username으로 변경)

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory94.png)

### Configure > Advanced Project Options > Pipeline 구성 (1/2)
###  Configure > Advanced Project Options > Pipeline (2/2) 

> Repository URL : https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2.git

> Branch Specifier : */main

> Path : 2212

>Script Path : 2212/Jenkinsfile

>
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory95.png)

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory96.png)

### [저장] 후 [지금 빌드] 실행

###  Stage View 결과 확인


   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory97.png)

-  2-5. 젠킨스 스크립트 확인

   https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2/blob/main/2212/Jenkinsfile

​

- 2-6. 실습 후 정리

* 실습 후 다음 실습에 방해가 되지 않도록 [kubectl delete ns anotherclass-221]를 한번 해주세요



##  Step 3 Blue/Green 배포 만들기 및 특징 실습

### item name 입력 및 Pipeline 선택

```bash

Enter an item name : 2213-jenkins_pipeline-step3
Copy from : 2212-jenkins_pipeline-step2

```


   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory98.png)

### Configure > Additional Behaviours 및 Script Path 수정 후 저장

~~~bash

Path : 2213
Script Path : 2213/Jenkinsfile

~~~

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory99.png)


### Master Node에서 version 조회 시작

~~~bash

[root@k8s-master ~]# while true; do curl http://192.168.56.30:32213/version; sleep 1; echo '';  done;


~~~


###  [지금 빌드] 실행

###  [수동배포 시작] yes 클릭 - Green이 배포됨

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory100.png)

### 젠킨스 스크립트 확인

> https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2/blob/main/2213/Jenkinsfile
> 
>  
* 실습 후 다음 실습에 방해가 되지 않도록 [kubectl delete ns anotherclass-221]를 한번 해주세요



## Step 4  Blue/Green 자동 배포 Script 만들기

###  item name 입력 및 Pipeline 선택

```bash

Enter an item name : 2214-jenkins_pipeline-step4
Copy from : 2213-jenkins_pipeline-step3


```


### Configure > Additional Behaviours 및 Script Path 수정 후 저장

```bash

Path : 2214
Script Path : 2214/Jenkinsfile

```


   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory101.png)

###  Master Node에서 version 조회 시작

```bash

while true; do curl http://192.168.56.30:32214/version; sleep 1; echo '';  done;


```


### 진행 과정 확인

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory102.png)



- [Green 배포 확인중] v2.0.0으로 변경됨 확인

### 젠킨스 스크립트 확인

~~~bash

https://github.com/k8s-1pro/kubernetes-anotherclass-sprint2/blob/main/2214/Jenkinsfile

​~~~


* 실습 후 다음 실습에 방해가 되지 않도록 [kubectl delete ns anotherclass-221]를 한번 해주세요
