---
layout: single
title: "AWS EKS CICD"
categories:  Devops
tags: [Linux, Container, Kubernetes , AWS , EKS, CICD, Jenkins, AgroCD ]
toc: true
---


## 실습 환경 구성

 > 첨부링크 :  https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick6.yaml

 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)


<details><summary>Amazon EKS (myeks) 윈클릭 배포</summary>


```bash

# YAML 파일 다운로드
curl -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/**eks-oneclick5.yaml**

# CloudFormation 스택 배포
예시) aws cloudformation deploy --template-file **eks-oneclick5.yaml** --stack-name **myeks** --parameter-overrides KeyName=**kp-gasida** SgIngressSshCidr=$(curl -s ipinfo.io/ip)/32  MyIamUser=**AKIA5...** MyIamUser =**'CVNa2...'** ClusterBaseName=**myeks** --region ap-northeast-2

# CloudFormation 스택 배포 완료 후 작업용 EC2 IP 출력
aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].**Outputs[0]**.OutputValue' --output text

# 작업용 EC2 SSH 접속
ssh -i **~/.ssh/kp-gasida.pem** **ec2-user**@$(aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].Outputs[0].OutputValue' --output text)
or
ssh -i **~/.ssh/kp-gasida.pem** **root**@$(aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].Outputs[0].OutputValue' --output text)
~ password: **qwe123**



- 기본 설정
# default 네임스페이스 적용
kubectl ns default

# 노드 정보 확인 : t3.medium
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone

# ExternalDNS
MyDomain=<자신의 도메인>
echo "export MyDomain=<자신의 도메인>" >> /etc/profile
MyDomain=gasida.link
echo "export MyDomain=gasida.link" >> /etc/profile
MyDnzHostedZoneId=$(aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text)
echo $MyDomain, $MyDnzHostedZoneId
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/externaldns.yaml
MyDomain=$MyDomain MyDnzHostedZoneId=$MyDnzHostedZoneId envsubst < externaldns.yaml | kubectl apply -f -

# kube-ops-view
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set env.TZ="Asia/Seoul" --namespace kube-system
kubectl patch svc -n kube-system kube-ops-view -p '{"spec":{"type":"LoadBalancer"}}'
kubectl annotate service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=kubeopsview.$MyDomain"
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080/#scale=1.5"

# AWS LB Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

# gp3 스토리지 클래스 생성
kubectl apply -f https://raw.githubusercontent.com/gasida/PKOS/main/aews/gp3-sc.yaml

# 노드 보안그룹 ID 확인
NGSGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text)
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr 192.168.1.100/32


# 사용 리전의 인증서 ARN 확인
CERT_ARN=`aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text`
echo $CERT_ARN

# repo 추가
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# 파라미터 파일 생성 : PV/PVC(AWS EBS) 삭제에 불편하니, 4주차 실습과 다르게 PV/PVC 미사용
cat <<EOT > monitor-values.yaml
prometheus:
  prometheusSpec:
    podMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false
    retention: 5d
    retentionSize: "10GiB"

  ingress:
    enabled: true
    ingressClassName: alb
    hosts: 
      - prometheus.$MyDomain
    paths: 
      - /*
    annotations:
      alb.ingress.kubernetes.io/scheme: internet-facing
      alb.ingress.kubernetes.io/target-type: ip
      alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}, {"HTTP":80}]'
      alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN
      alb.ingress.kubernetes.io/success-codes: 200-399
      alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'

grafana:
  defaultDashboardsTimezone: Asia/Seoul
  adminPassword: prom-operator
  defaultDashboardsEnabled: false

  ingress:
    enabled: true
    ingressClassName: alb
    hosts: 
      - grafana.$MyDomain
    paths: 
      - /*
    annotations:
      alb.ingress.kubernetes.io/scheme: internet-facing
      alb.ingress.kubernetes.io/target-type: ip
      alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}, {"HTTP":80}]'
      alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN
      alb.ingress.kubernetes.io/success-codes: 200-399
      alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'

alertmanager:
  enabled: false
EOT
cat monitor-values.yaml | yh

# 배포
kubectl create ns monitoring
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version 57.2.0 \
--set prometheus.prometheusSpec.scrapeInterval='15s' --set prometheus.prometheusSpec.evaluationInterval='15s' \
-f monitor-values.yaml --namespace monitoring

# Metrics-server 배포
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# 프로메테우스 ingress 도메인으로 웹 접속
echo -e "Prometheus Web URL = https://prometheus.$MyDomain"

# 그라파나 웹 접속 : 기본 계정 - admin / prom-operator
echo -e "Grafana Web URL = https://grafana.$MyDomain"



```


</details>



## Docker
- 초기 준비 : 도커 허브 가입 - 자신의 계정명 확인

 <details><summary>자신만의 웹 서버 도커 이미지 생성 후 도커 컨테이너 실행</summary>

~~~bash

# ubuntu 이미지 다운로드
docker pull ubuntu:20.04
docker images

# 실습을 위한 디렉터리 생성 및 이동
mkdir -p /root/myweb && cd /root/myweb

# Dockerfile 파일 생성
vi Dockerfile
FROM ubuntu:20.04
ENV TZ=Asia/Seoul VERSION=1.0.0 NICK=<자신의 닉네임>
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i 's/archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y apache2 figlet && \
    echo "$NICK Web Server $VERSION<br>" > /var/www/html/index.html && \
    echo "<pre>" >> /var/www/html/index.html && \
    figlet AEWS Study >> /var/www/html/index.html && \
    echo "</pre>" >> /var/www/html/index.html
EXPOSE 80
CMD ["usr/sbin/apache2ctl", "-DFOREGROUND"]

vi Dockerfile
FROM ubuntu:20.04
ENV TZ=Asia/Seoul VERSION=1.0.0 NICK=gasida
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i 's/archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y apache2 figlet && \
    echo "$NICK Web Server $VERSION<br>" > /var/www/html/index.html && \
    echo "<pre>" >> /var/www/html/index.html && \
    figlet AEWS Study >> /var/www/html/index.html && \
    echo "</pre>" >> /var/www/html/index.html
EXPOSE 80
CMD ["usr/sbin/apache2ctl", "-DFOREGROUND"]

# 이미지 빌드
cat Dockerfile
docker build -t myweb:v1.0.0 .
docker images
docker image history myweb:v1.0.0
docker image inspect myweb:v1.0.0 | jq

# 컨테이너 실행
docker run -d -p 80:80 --rm --name myweb myweb:v1.0.0
docker ps
curl localhost

# 웹 접속 확인
curl -s ipinfo.io/ip | awk '{ print "myweb = http://"$1"" }'

~~~


- 도커 허브 업로드

~~~ bash

#
DHUB=<도커 허브 계정>
DHUB=gasida
docker tag myweb:v1.0.0 $DHUB/myweb:v1.0.0
docker images

# 도커 허브 로그인
docker login
Username: <자신의 ID>
Password: <암호>
## 로그인 정보는 /[계정명]/.docker/config.json 에 저장됨. docker logout 시 삭제됨
## cat /root/.docker/config.json | jq

# push 로 이미지를 저장소에 업로드
docker push $DHUB/myweb:v1.0.0
~~~



![https://cafe.naver.com/kubeops](/Images/eks/eks_c01.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_c02.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_c03.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_c04.png)


</details>


- 해당 저장소 이미지 활용
~~~bash

# 컨테이너 종료
docker rm -f myweb
docker ps

# 로컬 이미지 삭제
docker rmi $DHUB/myweb:v1.0.0
docker images

# 
docker run -d -p 80:80 --rm --name myweb $DHUB/myweb:v1.0.0
docker iamges

# 확인
docker ps
curl localhost
curl -s ipinfo.io/ip | awk '{ print "myweb = http://"$1"" }'

# 삭제
docker rm -f myweb

~~~




## Jenkins

<details><summary>Jenkins 소개</summary>

- 지속적인 통합과 배포 → Work flow를 제어 - [Link](https://www.jenkins.io/)
    
    **CI(지속적 제공)/CD(지속적 배포) 워크플로 예제**
    
    1. 최신 코드 가져오기 : 개발을 위해 중앙 코드 리포지터리에서 로컬 시스템으로 애플리케이션의 최신 코드를 가져옴
    2. 단위 테스트 구현과 실행 : 코드 작성 전 단위 테스트 케이스를 먼저 작성
    3. 코드 개발 : 실패한 테스트 케이스를 성공으로 바꾸면서 코드 개발
    4. 단위 테스트 케이스 재실행 : 단위 테스트 케이스 실행 시 통과(성공!)
    5. 코드 푸시와 병합 : 개발 소스 코드를 중앙 리포지터리로 푸시하고, 코드 병합
    6. 코드 병합 후 컴파일 : 변경 함수 코드가 병함되면 전체 애플리케이션이 컴파일된다
    7. 병합된 코드에서 테스트 실행 : 개별 테스트뿐만 아니라 전체 통합 테스트를 실행하여 문제 없는지 확인
    8. 아티팩트 배포 : 애플리케이션을 빌드하고, 애플리케이션 서버의 프로덕션 환경에 배포
    9. 배포 애플리케이션의 E-E 테스트 실행 : 셀레늄 Selenium과 같은 User Interface 자동화 도구를 통해 애플리케이션의 전체 워크플로가 정상 동작하는지 확인하는 종단간 End-to-End 테스트를 실행.
    
    - The leading **open source** automation server, Jenkins provides hundreds of plugins to support building, deploying and automating any project.
    - Continuous Integration Server + Continuous Development, Build, Test, Deploy
    - 소프트웨어 **개발 프로세스**의 다양한 **단계**를 **자동화**하는 도구로서 중앙 소스 코드 리포지터리에서 최신 코드 가져오기, 소스 코드 컴파일, 단위 테스트 실행, 산출물을 다양한 유형으로 패키징, 산출물을 여러 종류의 환경으로 배포하기 등의 기능을 제공.
    - 젠킨스는 아파치 톰캣처럼 **서블릿 컨테이너** 내부에서 실행되는 서버 시스템이다. **자바**로 작성됐고, 소프트웨어 개발과 관련된 다양한 도구를 지원.
    - 젠킨스는 **DSL** Domain Specific Language (jenkins file)로 E-E 빌드 수명 주기 단계를 구축한다.
    - 젠킨스는 **파이프라인**이라고 부르는 **스크립트**를 작성할 수 있는데, 이를 사용해서 각 빌드 단계마다 젠킨스가 수행할 태스트 및 하위 태스크의 순서를 정의.
        - 순차적이고 종속적인 단계가 시작부터 끝까지 실행되면 최종적으로 사용자가 실행할 수 있는 빌드가 생성됨.
        - 만약 빌드 프로세스를 진행하는 중에 특정 단계에서 실패가 발생하며, 이 단계의 출력 결과를 사용하는 다음 단계는 실행되지 않으며 빌드 프로세스 전체가 실패한다.
    - 다양한 Plugins 연동
        - Build Plugins : Maven, Ant, Gradle …
        - VCS Plugins : Git, SVN …
        - Languages Plugins : Java, Python, Node.js …



</details>

<details><summary>설치 및 설정 </summary>

~~~bash

# 실습 편리를 위해서 root 계정 전환
sudo su -

# Add required dependencies for the jenkins package
# https://docs.aws.amazon.com/corretto/latest/corretto-17-ug/amazon-linux-install.html
sudo yum install fontconfig java-17-amazon-corretto -y
java -version
alternatives --display java
JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto.x86_64
echo $JAVA_HOME

# 젠킨스 설치
sudo wget -O /etc/yum.repos.d/jenkins.repo https://pkg.jenkins.io/redhat-stable/jenkins.repo
sudo rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key
sudo yum upgrade
sudo yum install jenkins -y
sudo systemctl daemon-reload
sudo systemctl enable jenkins && sudo systemctl start jenkins   # 다소 시간 걸림
sudo systemctl status jenkins

# 초기 암호 확인
sudo systemctl status jenkins
cat /var/lib/jenkins/secrets/initialAdminPassword

# 접속 주소 확인 
curl -s ipinfo.io/ip | awk '{ print "Jenkins = http://"$1":8080" }'

~~~


- 초기 암호 입력

- 플러그인 설치 : 제안 플러그인 설치하자 

- 관리자 계정 설정 : 계정명(admin) , 암호(qwe123), 이름(’각자 자신의 닉네임’)

- 설정 완료 후 젠킨스 접속 

![https://cafe.naver.com/kubeops](/Images/eks/eks_c05.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_c06.png
![https://cafe.naver.com/kubeops](/Images/eks/eks_c07.png)

> - item : 젠킨스에서 사용하는 작업의 최소 단위
> - 사람 : 계정 관련
> - Jenkins 관리 : 전역 설정 등






</details>



<details><summary>기본사용 / tools 설정 </summary>

1. Jenkis 관리 > Tools 
- JDK installations : jdk-17 , /usr/lib/jvm/java-17-amazon-corretto.x86_64 → Save

2. 초기 대시보드 > "새로운 Item" > 이름기입 ,Freestyle project > Build Step "excute Shell" > 박스에 "명령어실행" > 저장

3. 해당 프로젝트에 접근하여 왼쪽 > "지금 빌드"

4. 왼쪽 하단데 #의 버튼에 숫자를 눌러 Console Output을 클릭

![https://cafe.naver.com/kubeops](/Images/eks/eks_c06.png)

관련한 작업의 디렉토리는 서버에 
~~~bash

#
find / -name First-Project
/var/lib/jenkins/jobs/First-Project
/var/lib/jenkins/workspace/First-Project

# 프로젝트(job, item) 별 작업 공간 확인
tree /var/lib/jenkins/workspace/First-Project

~~~


</details>

<details><summary>Docker사용</summary>

- 준비 

~~~bash

# jenkins 유저로 docker 사용 가능하게 설정
grep -i jenkins /etc/passwd
usermod -s /bin/bash jenkins
grep -i jenkins /etc/passwd

# jenkins 유저 전환
su - jenkins
whoami
pwd
docker info
exit

#
chmod 666 /var/run/docker.sock
usermod -aG docker jenkins

# Jeknins 유저로 확인
su - jenkins
docker info

# Dockerhub로 로그인 하기
docker login
Username: <자신의 계정명>
Password: <자신의 암호>

# myweb:v2.0.0 컨테이너 이미지 생성을 위한 Dockerfile 준비
# 실습을 위한 디렉터리 생성 및 이동
mkdir -p ~/myweb2 && cd ~/myweb2

# Dockerfile 파일 생성
vi Dockerfile
FROM ubuntu:20.04
ENV TZ=Asia/Seoul VERSION=2.0.0 NICK=<자신의 닉네임>
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i 's/archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y apache2 figlet && \
    echo "$NICK Web Server $VERSION<br>" > /var/www/html/index.html && \
    echo "<pre>" >> /var/www/html/index.html && \
    figlet AEWS Study >> /var/www/html/index.html && \
    echo "</pre>" >> /var/www/html/index.html
EXPOSE 80
CMD ["usr/sbin/apache2ctl", "-DFOREGROUND"]

vi Dockerfile
FROM ubuntu:20.04
ENV TZ=Asia/Seoul VERSION=2.0.0 NICK=gasida
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone && \
    sed -i 's/archive.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    sed -i 's/security.ubuntu.com/mirror.kakao.com/g' /etc/apt/sources.list && \
    apt-get update && apt-get install -y apache2 figlet && \
    echo "$NICK Web Server $VERSION<br>" > /var/www/html/index.html && \
    echo "<pre>" >> /var/www/html/index.html && \
    figlet AEWS Study >> /var/www/html/index.html && \
    echo "</pre>" >> /var/www/html/index.html
EXPOSE 80
CMD ["usr/sbin/apache2ctl", "-DFOREGROUND"]

# 모니터링
watch -d 'docker images; echo; docker ps'

-----------
# (참고) 이미지 빌드
docker build -t myweb:v2.0.0 -f /var/lib/jenkins/myweb2/Dockerfile

# (참고) 컨테이너 실행
docker run -d -p 80:80 --rm --name myweb myweb:v2.0.0

~~~


- item : Docker-Project , freestyle



- item : **Docker-Project** , freestyle
- Build Steps : Execute shell
        
```bash

        docker **build** -t myweb:v2.0.0 .
        cd /var/lib/jenkins/myweb2

```
        
- Add build Steps : Execute shell
        
```bash

        docker run -d -p 80:80 --rm --name myweb myweb:v2.0.0

```
        
- **지금 빌드** → 확인
    
    
```bash

docker images
docker ps
curl localhost

```
    
- 실습 리소스 삭제
    
```bash

docker rm -f myweb
docker rmi myweb:v2.0.0

```
</details>

- Github 가입 : 자신의 계정명 확인 → https://github.com/gasida/aews-cicd.git 포크




<details><summary>파라미터, 빌드 유발(SCM - Git) 사용 : Trigger-Project</summary>

- Item : **Trigger-Project**, freestyle
    - 빌드 매개변수 : String
        - 변수명(VERSION), Default Vault(v1.0.0)
        - 변수명(NICK), Default Vault(<자신의 계정명>)
    - 소스 코드 관리 : Git
        - Repo URL : https://github.com/**<자신의 계정명>**/aews-cicd
        - Branch : */**main**
        - Additional Behaviours → Sparse Checkout paths (Path) : **1**
    - **빌드 유발** : Poll SCM (* * * * *)
    - Build Steps : Execute shell

~~~bash

cd /var/lib/jenkins/myweb2
rm -rf Dockerfile
wget https://raw.githubusercontent.com/$NICK/aews-cicd/main/1/Dockerfile

~~~
- Add build Steps : Execute shell

~~~bash

docker build -t myweb:$VERSION .
docker run -d -p 80:80 --rm --name myweb myweb:$VERSION

~~~



</details>


## Jenkins with Kubernetes


<details><summary>Jenkins 에서 k8s 사용을 위한 사전 준비</summary>

- root 계정에서

~~~bash

# jenkins 사용자에서 아래 작업 진행
whoami
mkdir ~/.kube

# root 계정에서 아래 복사 실행
cp ~/.kube/config /var/lib/jenkins/.kube/config
chown jenkins:jenkins /var/lib/jenkins/.kube/config

# jenkins 사용자에서 aws eks 사용(sts 호출 등)을 위한 자격증명 설정
aws configure
AWS Access Key ID [None]: AKIA5ILF2###
AWS Secret Access Key [None]: ###
Default region name [None]: ap-northeast-2

# jenkins 사용자에서 kubectl 명령어 사용 확인
kubectl get pods -A

~~~


</details>






<details><summary>파이프라인으로 디플로이먼트/서비스 배포</summary>

- 자신의 Github (웹) Repo 3/deploy/deployment-svc.yaml 파일에 image 부분 수정 → 자신의 도커 허브에 이미지가 있어야함

~~~bash

pipeline {
    agent any

    tools {
        jdk 'jdk-17'
    }

    environment {
        DOCKERHUB_USERNAME = 'gasida'
        GITHUB_URL = 'https://github.com/gasida/aews-cicd.git'
        // deployment-svc.yaml -> image: gasida/myweb:v1.0.0        
        DIR_NUM = '3'
    }

    stages {
        stage('Container Build') {
            steps {	
                // 릴리즈파일 체크아웃
                checkout scmGit(branches: [[name: '*/main']], 
                    extensions: [[$class: 'SparseCheckoutPaths', 
                    sparseCheckoutPaths: [[path: "/${DIR_NUM}"]]]], 
                    userRemoteConfigs: [[url: "${GITHUB_URL}"]])

                // 컨테이너 빌드 및 업로드
                sh "docker build -t ${DOCKERHUB_USERNAME}/myweb:v1.0.0 ./${DIR_NUM}"
                sh "docker push ${DOCKERHUB_USERNAME}/myweb:v1.0.0"
            }
        }

        stage('K8S Deploy') {
            steps {
                sh "kubectl apply -f ./${DIR_NUM}/deploy/deployment-svc.yaml"
            }
        }
    }
}

~~~


- 확인 


~~~bash

kubectl exec -it netpod -- curl myweb:8080
kubectl exec -it netpod -- curl myweb:8080 | grep Web
while true; do kubectl exec -it netpod -- curl myweb:8080 | grep Web; echo; done

# 작업공간 확인
tree /var/lib/jenkins/workspace/k8s-1
cat /var/lib/jenkins/workspace/k8s-1/Dockerfile

~~~

</details> 




## ArroCD

- **Argo** - [공홈](https://argoproj.github.io/) & [CD](https://argoproj.github.io/cd/) [Docs](https://argo-cd.readthedocs.io/en/stable/) & [Rollouts](https://argoproj.github.io/rollouts/) [Docs](https://argoproj.github.io/argo-rollouts/) & [Blog](https://blog.argoproj.io/)
- 참고 
['ArgoCD' 태그의 글 목록](https://malwareanalysis.tistory.com/tag/ArgoCD)







<details><summary>Argo CD 소개 및 설치 : Argo CD is a declarative, GitOps continuous delivery tool for Kubernetes</summary>


- 설치 - [Helm](https://artifacthub.io/packages/helm/argo/argo-cd) [Helm_AWS_ALB](https://artifacthub.io/packages/helm/argo/argo-cd#aws-application-load-balancer) [Docs](https://argo-cd.readthedocs.io/en/stable/)
    
```bash
# 간단 설치
    kubectl create namespace argocd
    kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml~~
    
    # helm 설치
    cat <<EOT > argocd-values.yaml
    global:
      domain: argocd.$MyDomain
    
    configs:
      params:
        server.insecure: true
    
    controller:
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
    
    server:
      ingress:
        enabled: true
        controller: aws
        ingressClassName: alb
        hostname: "argocd.$MyDomain"
        annotations:
          alb.ingress.kubernetes.io/scheme: internet-facing
          alb.ingress.kubernetes.io/target-type: ip
          alb.ingress.kubernetes.io/backend-protocol: HTTP
          alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":80}, {"HTTPS":443}]'
          alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN
          alb.ingress.kubernetes.io/ssl-redirect: '443'
        aws:
          serviceType: ClusterIP
          backendProtocolVersion: GRPC
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
    
    repoServer:
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
    
    applicationSet:
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
    
    notifications:
      metrics:
        enabled: true
        serviceMonitor:
          enabled: true
    EOT
    
    kubectl create ns **argocd**
    helm repo add argo https://argoproj.github.io/argo-helm
    helm install **argocd** argo/argo-cd --version 6.7.11 -f argocd-values.yaml --namespace argocd
    
    # 확인
    kubectl get ingress,pod,svc -n argocd
    **kubectl get crd | grep argo**
    applications.argoproj.io                     2024-04-14T08:12:16Z
    applicationsets.argoproj.io                  2024-04-14T08:12:17Z
    appprojects.argoproj.io                      2024-04-14T08:12:16Z
    
    # 최초 접속 암호 확인
    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d ;echo
    **MC3y8rzzECTIAHSB**
```

- 최초 접속 `https://argocd.<자신의도메인>`  **admin** / *<최초 접속 암호>*
- (옵션) 로그인 후 User info → UPDATE PASSWORD 변경 가능



</details>







<details><summary>아키텍처</summary>


- **Architecture** - [Docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/architecture/)
    
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_c14.png)
    
    https://argo-cd.readthedocs.io/en/stable/
    
    - **API Server : Web UI 대시보드, k8s api 처럼 API 서버 역할**
        - The API server is a gRPC/REST server which exposes the API consumed by the Web UI, CLI, and CI/CD systems. It has the following responsibilities:
        - application management and status reporting
        - invoking of application operations (e.g. sync, rollback, user-defined actions)
        - repository and cluster credential management (stored as K8s secrets)
        - authentication and auth delegation to external identity providers
        - RBAC enforcement
        - listener/forwarder for Git webhook events
    - **Repository Server : Git 연결 및 배포할 yaml 생성**
        - The repository server is an internal service which maintains a local cache of the Git repository holding the application manifests. It is responsible for generating and returning the Kubernetes manifests when provided the following inputs:
        - repository URL
        - revision (commit, tag, branch)
        - application path
        - template specific settings: parameters, helm values.yaml
    - **Application Controller : k8s 리소스 모니터링, Git과 비교**
        - The application controller is a Kubernetes controller which continuously monitors running applications and compares the current, live state against the desired target state (as specified in the repo). It detects `OutOfSync` application state and optionally takes corrective action. It is responsible for invoking any user-defined hooks for lifecycle events (PreSync, Sync, PostSync)
    - **Redis** : k8s api와 git 요청을 줄이기 위한 캐싱
    - **Notification** : 이벤트 알림, 트리거
    - **Dex** : 외부 인증 관리
    - **ApplicationSet Controller** : 멀티 클러스터를 위한 App 패키징 관리


</details>






<details><summary>App 배포 with Directory</summary>

- App 생성 : New App 클릭
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_c15.png)
    
    - Application Name : **first-myweb**
    - Project Name : **default**
    - SYNC POLICY : **Manual**
        - AUTO-CREATE NAMESPACE : 클러스터에 네임스페이스가 없을 시 argocd에 입력한 이름으로 자동 생성
        - APPLY OUT OF SYNC ONLY : 현재 동기화 상태가 아닌 리소스만 배포
    - PRUNE PROPAGATION POLICY
        - **foreground** : 부모(소유자, ex. deployment) 자원을 먼저 삭제함
        - background  : 자식(종속자, ex. pod) 자원을 먼저 삭제함
        - orphan  : 고아(소유자는 삭제됐지만, 종속자가 삭제되지 않은 경우) 자원을 삭제함
    - [체크] **AUTO-CREATE-NAMESPACE**
    - SOURCE
        - Repository URL : https://github.com/gasida/aews-cicd.git
        - Revision : **main**
        - Path : **3/deploy**
    - **DESTINATION**
        - Cluster URL : [https://kubernetes.default.svc](https://kubernetes.default.svc/)
        - Namespace : **first**
        - [선택] Directory *← 소스를 보고 자동으로 유형 선택됨*
    - **화면 상단 [CREATE] 클릭**
- **배포하기 - [SYNC] 클릭 > [SYNCHRONIZE] 클릭**
    - PRUNE : GIt에서 자원 삭제 후 배포시 K8S에서는 삭제되지 않으나, 해당 옵션을 선택하면 삭제시킴
    - FORCE : --force 옵션으로 리소스 삭제
    - APPLY ONLY : ArgoCD의 Pre/Post Hook은 사용 안함 (리소스만 배포)
    - DRY RUN : 테스트 배포 (배포에 에러가 있는지 한번 확인해 볼때 사용)
    
    ****
    
- 리소스 클릭 후 확인 : 각각 LIVE MANIFEST(쿠버네티스 정보) vs DESIRED MANIFEST(Git깃 정보)
    - 위 화면에서 Deployment 리소스 직접 수정 해보기 : EDIT 클릭 후 lables 아래 추가 → SAVE
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_c16.png)
    
    ```bash
    # 모니터링
    kubectl get deploy,svc -n first --show-labels
    **watch -d kubectl get deploy -n first --show-labels**
    ```
    
    - k8s에서 직접 수정 → argocd 싱크(반영) 확인
    
    ```bash
    # 아래 추가
    **kubectl edit deploy -n first myweb
    ...**
      labels:
        add: label-test
        **add2: k8s-test
    ...**
    ```
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_c17.png)
    - 현재 상태는, Git을 기준으로 보자면 LIVE MANIFEST(K8S)형상이 뒤떨어진것으로 볼 수 있다 → OutOfSync 상태니 Sync 하자
    
    - Git Repo화면에서 replicas 4로 변경 후 → Commit 후 ArgoCD에서 REFRESH 클릭 후 Sync 후 확인
    
- 실습 리소스 삭제 : Argocd 에서 DELETE
    
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_c18.png)
    
- 결론 : **GitOps를 하려거든 대상(k8s)에서 변경하지 말고, 소스(git)에서 변경하자!**


</details>








<details><summary>CLI 예제</summary>


- Argo CD CLI - [Install](https://argo-cd.readthedocs.io/en/stable/cli_installation/)
    
    ```bash
    #
    curl -sSL -o argocd-linux-amd64 https://github.com/argoproj/argo-cd/releases/latest/download/argocd-linux-amd64
    sudo install -m 555 argocd-linux-amd64 /usr/local/bin/argocd
    rm -f argocd-linux-amd64
    
    #
    **argocd version
    
    #
    argocd login argocd.$MyDomain**
    Username: **admin**
    Password: ###
    'admin:login' logged in successfully
    
    #
    **kubectl config get-contexts -o name**
    admin@myeks.ap-northeast-2.eksctl.io
    **argocd cluster add admin@myeks.ap-northeast-2.eksctl.io**
    y 입력
    
    #
    **argocd app list**
    NAME  CLUSTER  NAMESPACE  PROJECT  STATUS  HEALTH  SYNCPOLICY  CONDITIONS  REPO  PATH  TARGET
    ```
    
- Application 생성 with CLi
    
    ```bash
    #
    **kubectl config set-context --current --namespace=argocd**
    **argocd app create guestbook --repo https://github.com/argoproj/argocd-example-apps.git --path guestbook --dest-server https://kubernetes.default.svc --dest-namespace default**
    
    #
    **argocd app list**
    NAME              CLUSTER                         NAMESPACE  PROJECT  STATUS     HEALTH   SYNCPOLICY  CONDITIONS  REPO                                                 PATH       TARGET
    argocd/guestbook  https://kubernetes.default.svc  default    default  OutOfSync  Missing  <none>      <none>      https://github.com/argoproj/argocd-example-apps.git  guestbook  
    ```
    

![https://cafe.naver.com/kubeops](/Images/eks/eks_c19.png)
    
- Sync (Deploy) The Application
    
    ```bash
    #
    **argocd app get guestbook**
    ...
    
    # 모니터링
    watch -d kubectl get pod,svc,ep
    
    #
    **argocd app sync guestbook**
    ```
    
 
![https://cafe.naver.com/kubeops](/Images/eks/eks_c20.png)
    
- app 삭제
    
    ```bash
    **argocd app delete guestbook**
    Are you sure you want to delete 'guestbook' and all its resources? [y/n] **y**
    
    # ns default 로 변경
    **kubectl ns default**
    ```


</details>





<details><summary>Argo Rollouts</summary>




- Argo **Rollouts** 소개 및 설치 : Kubernetes Progressive Delivery Controller - [Docs](https://argoproj.github.io/argo-rollouts/)
    - Argo **Rollouts** : Argo Rollouts is a [Kubernetes controller](https://kubernetes.io/docs/concepts/architecture/controller/) and set of [CRDs](https://kubernetes.io/docs/concepts/extend-kubernetes/api-extension/custom-resources/) which provide **advanced deployment** capabilities such as **blue-green**, **canary**, canary analysis, experimentation, and progressive delivery features to Kubernetes.
        - Argo Rollouts (optionally) integrates with [ingress controllers](https://kubernetes.io/docs/concepts/services-networking/ingress/) and service meshes, leveraging their traffic shaping abilities to gradually shift traffic to the new version during an update. Additionally, Rollouts can query and interpret metrics from various providers to verify key KPIs and drive automated promotion or rollback during an update.
    - **Why** Argo Rollouts?
        - The native Kubernetes Deployment Object supports the `RollingUpdate` strategy which provides a basic set of safety guarantees (readiness probes) during an update. However the rolling update strategy faces many limitations:
        - Few controls over the speed of the rollout
        - Inability to control traffic flow to the new version
        - Readiness probes are unsuitable for deeper, stress, or one-time checks
        - No ability to query external metrics to verify an update
        - Can halt the progression, but unable to automatically abort and rollback the update
    - Controller **Features**
        - **Blue-Green** update strategy
            
            ![https://cafe.naver.com/kubeops](/Images/eks/eks_c21.png)
        
            
            https://argoproj.github.io/argo-rollouts/concepts/
            
        - Canary update strategy
            
         ![https://cafe.naver.com/kubeops](/Images/eks/eks_c22.png)
        
            
            https://argoproj.github.io/argo-rollouts/concepts/
            
        - Fine-grained, weighted traffic shifting
        - Automated rollbacks and promotions
        - Manual judgement
        - Customizable metric queries and analysis of business KPIs
        - Ingress controller integration: NGINX, ALB, Apache APISIX
        - Service Mesh integration: Istio, Linkerd, SMI
        - Simultaneous usage of multiple providers: SMI + NGINX, Istio + ALB, etc.
        - Metric provider integration: Prometheus, Wavefront, Kayenta, Web, Kubernetes Jobs, Datadog, New Relic, Graphite, InfluxDB
    - 아키텍처 - [Docs](https://argoproj.github.io/argo-rollouts/architecture/)
        
        ![https://cafe.naver.com/kubeops](/Images/eks/eks_c23.png)
        
        
        https://argoproj.github.io/argo-rollouts/architecture/
        
        - Argo Rollouts controller :
        - Rollout resource :
        - Replica sets for old and new version :
        - Ingress/Service :
        - AnalysisTemplate and AnalysisRun :
        - Metric providers :
        - CLI and UI :
        
    - 설치 - [Helm](https://artifacthub.io/packages/helm/argo/argo-rollouts) Docs
        
        ```bash
        #
        cat <<EOT > argorollouts-values.yaml
        dashboard:
          enabled: true
          ingress:
            enabled: true
            ingressClassName: alb
            hosts:
              - **argorollouts.$MyDomain**
            annotations:
              alb.ingress.kubernetes.io/scheme: internet-facing
              alb.ingress.kubernetes.io/target-type: ip
              alb.ingress.kubernetes.io/backend-protocol: HTTP
              alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":80}, {"HTTPS":443}]'
              alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN
              alb.ingress.kubernetes.io/ssl-redirect: '443'
        EOT
        
        kubectl create ns argo-rollouts
        helm install argo-rollouts argo/argo-rollouts --version 2.35.1 -f argorollouts-values.yaml --namespace argo-rollouts
        
        # 확인
        kubectl get all -n argo-rollouts
        kubectl get crd | grep argo
        ```
        
    - rollouts 대시보드 : 네임스페이스별 확인 가능 - [Docs](https://argoproj.github.io/argo-rollouts/dashboard/)
        
        `https://argorollouts.<자신의 도메인>/rollouts/`
        
    - rollouts cli …
        
        ```bash
        ~~#~~
        curl -LO https://github.com/argoproj/argo-rollouts/releases/download/v1.6.4/kubectl-argo-rollouts-linux-amd64
        chmod +x ./kubectl-argo-rollouts-linux-amd64
        mv ./kubectl-argo-rollouts-linux-amd64 /usr/local/bin/kubectl-argo-rollouts
        
        # 설치 확인
        **kubectl argo rollouts version**
        ```





</details>
<details><summary></summary>


- Getting Started - [Docs](https://argoproj.github.io/argo-rollouts/getting-started/)
    - Deploying a Rollout
        
        ```bash
        spec:
          replicas: 5
          strategy:
            **canary**:
              steps:
              - setWeight: 20
              - pause: {}
              - setWeight: 40
              - pause: {duration: 10}
              - setWeight: 60
              - pause: {duration: 10}
              - setWeight: 80
              - pause: {duration: 10}
        ```
        
        ```bash
        # Run the following command to deploy the initial Rollout and Service:
        kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-rollouts/master/docs/getting-started/basic/rollout.yaml
        kubectl apply -f https://raw.githubusercontent.com/argoproj/argo-rollouts/master/docs/getting-started/basic/service.yaml
        ```
        
    - CLI vs UI 확인 [https://argorollouts.<각자 자신의 도메인>/rollouts/](https://argorollouts.gasida.link/rollouts/argocd)default
        
        ```bash
        **kubectl argo rollouts get rollout rollouts-demo**
        Name:            rollouts-demo
        Namespace:       argocd
        Status:          ◌ Progressing
        Message:         updated replicas are still becoming available
        Strategy:        Canary
          Step:          8/8
          SetWeight:     100
          ActualWeight:  100
        Images:          argoproj/rollouts-demo:blue (stable)
        Replicas:
          Desired:       5
          Current:       5
          Updated:       5
          Ready:         4
          Available:     4
        
        NAME                                       KIND        STATUS               AGE   INFO
        ⟳ rollouts-demo                            Rollout     ◌ Progressing        113s  
        └──# revision:1                                                                   
           └──⧉ rollouts-demo-687d76d795           ReplicaSet  ◌ Progressing        113s  stable
              ├──□ rollouts-demo-687d76d795-bqtp6  Pod         ◌ ContainerCreating  113s  ready:0/1
              ├──□ rollouts-demo-687d76d795-hz5v8  Pod         ✔ Running            113s  ready:1/1
              ├──□ rollouts-demo-687d76d795-vjzfz  Pod         ✔ Running            113s  ready:1/1
              ├──□ rollouts-demo-687d76d795-vvdtj  Pod         ✔ Running            113s  ready:1/1
              └──□ rollouts-demo-687d76d795-xjx5v  Pod         ✔ Running            113s  ready:1/1
        
        **kubectl argo rollouts get rollout rollouts-demo --watch**
        ```
        
     ![https://cafe.naver.com/kubeops](/Images/eks/eks_c24.png)
        
    - Updating a Rollout
        
        ```bash
        #
        watch -d kubectl get pod -n argocd -l app=rollouts-demo -owide --show-labels
        
        # Run the following command to update the rollouts-demo Rollout with the "yellow" version of the container:
        kubectl argo **rollouts** set image rollouts-demo rollouts-demo=argoproj/rollouts-demo:yellow
        ```
        
        ![https://cafe.naver.com/kubeops](/Images/eks/eks_c25.png)
        
    - **Promoting a Rollout**
        
       ![https://cafe.naver.com/kubeops](/Images/eks/eks_c26.png)
        
        ```bash
        # 아래 입력 혹은 UI에서 Promote Yes 클릭
        kubectl argo rollouts promote rollouts-demo
        
        #
        kubectl argo rollouts get rollout rollouts-demo --watch
        ```
        
    - **Aborting a Rollout**
        
        ```bash
        # 
        kubectl argo rollouts set image rollouts-demo rollouts-demo=argoproj/rollouts-demo:red
        
        #
        kubectl argo rollouts abort rollouts-demo
        
        #
        kubectl argo rollouts set image rollouts-demo rollouts-demo=argoproj/rollouts-demo:yellow
        ```
        
    - **이후 처음부터 정상 배포 과정 확인 하기**


</details>

- Getting Started - AWS Load Balancer Controller - [Docs](https://argoproj.github.io/argo-rollouts/getting-started/alb/)
    
    [https://imxsuu.tistory.com/18#Getting Started - AWS Load Balancer Controller-1](https://imxsuu.tistory.com/18#Getting%20Started%20-%20AWS%20Load%20Balancer%20Controller-1)
    
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_c27.png)
    
- 이전 멤버 Argo Rollouts 정리 글
    
    [PKOS 2기 3주차 - Argo Rollout(feat. EKS)](https://mateon.tistory.com/105)
    
    [Advanced Argo Rollout | Cloud Catalyst](https://ddii.dev/kubernetes/argo-rollout-advanced/)



## 실습 삭제
~~~

eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME

~~~