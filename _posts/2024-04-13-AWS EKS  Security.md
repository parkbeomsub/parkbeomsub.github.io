---
layout: single
title: "AWS EKS  Security"
categories:  Devops
tags: [linux, container, kubernetes , AWS , EKS, Monitoring ]
toc: true
---


## 실습 환경 구성

 > 첨부링크 :  https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick5.yaml

 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)


<details><summary>Amazon EKS (myeks) 윈클릭 배포 (bastion ec2 2대) & 기본 설정</summary>


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
```

- 기본 설정

```bash
# default 네임스페이스 적용
kubectl ns default

# 노드 정보 확인 : t3.medium
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone

# ExternalDNS
MyDomain=<자신의 도메인>
echo "export MyDomain=<자신의 도메인>" >> /etc/profile
*MyDomain=gasida.link*
*echo "export MyDomain=gasida.link" >> /etc/profile*
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

# 노드 IP 확인 및 PrivateIP 변수 지정
N1=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2a -o jsonpath={.items[0].status.addresses[0].address})
N2=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2b -o jsonpath={.items[0].status.addresses[0].address})
N3=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2c -o jsonpath={.items[0].status.addresses[0].address})
echo "export N1=$N1" >> /etc/profile
echo "export N2=$N2" >> /etc/profile
echo "export N3=$N3" >> /etc/profile
echo $N1, $N2, $N3

# 노드 보안그룹 ID 확인
NGSGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text)
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr **192.168.1.100/32**
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr **192.168.1.200/32**

# 워커 노드 SSH 접속
for node in $N1 $N2 $N3; do ssh -o StrictHostKeyChecking=no ec2-user@$node hostname; done
for node in $N1 $N2 $N3; do ssh ec2-user@$node hostname; done
```

- 프로메테우스 & 그라파나(**admin / prom-operator**) 설치 : 대시보드 추천 **15757 17900 15172**

```bash
# 사용 리전의 인증서 ARN 확인
CERT_ARN=`aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text`
echo $CERT_ARN

# repo 추가
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# 파라미터 파일 생성 : PV/PVC(AWS EBS) 삭제에 불편하니, 4주차 실습과 다르게 PV/PVC 미사용
cat <<EOT > monitor-values.yaml
**prometheus**:
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

**grafana**:
  defaultDashboardsTimezone: Asia/Seoul
  adminPassword: prom-operator
  **defaultDashboardsEnabled: false**

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
**kubectl create ns monitoring**
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version **57.2.0** \
--**set** prometheus.prometheusSpec.scrapeInterval='15s' --**set** prometheus.prometheusSpec.evaluationInterval='15s' \
-f **monitor-values.yaml** --namespace monitoring

# Metrics-server 배포
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
****
# 프로메테우스 ingress 도메인으로 웹 접속
echo -e "Prometheus Web URL = https://prometheus.$MyDomain"

# 그라파나 웹 접속 : 기본 계정 - **admin / prom-operator**
echo -e "Grafana Web URL = https://grafana.$MyDomain"
```

</details>



---








## K8S 인증/인가
- `**K8S(API 접근) 인증/인가 소개` : 출처 - 김태민 기술 블로그 - [링크](https://kubetm.github.io/k8s/07-intermediate-basic-resource/authentication/) [링크2](https://kubetm.github.io/k8s/07-intermediate-basic-resource/authorization/)**
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei1.png)
    https://kubernetes.io/blog/2019/03/21/a-guide-to-kubernetes-admission-controllers/
    
    
    - **서비스 어카운트(**Service Account)
    - **API 서버 사용** : kubectl(config, 다수 클러스터 관리 가능), 서비스 어카운트, https(x.509 Client Certs) ⇒ `X.509 발음`을 어떻게 하시나요? - [링크](https://youglish.com/pronounce/x.509/english)
    - **API 서버 접근 과정** : 인증 → 인가 → Admission Control(API 요청 검증, 필요 시 변형 - 예. ResourceQuota, LimitRange) - [참고](https://blog.naver.com/alice_k106/221546328906)
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei2.png)
    
   
    
    **`인증(Authentication)`**
    
    - **X.509 Client Certs** : kubeconfig 에 **CA crt**(발급 기관 인증서) , **Client crt**(클라이언트 인증서) , **Client key**(클라이언트 개인키) 를 통해 인증
    - **kubectl** : 여러 클러스터(**kubeconfig**)를 관리 가능 - **contexts** 에 클러스터와 유저 및 **인증서**/**키** 참고
    - **Service Account** : 기본 서비스 어카운트(default) - 시크릿(CA crt 와 token)
    
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei3.png)
    
    `**인가(Authorization)**`
    
    - **인가 방식** : **RBAC(Role, RoleBinding)**, ABAC, Webhook, Node Authorization⇒ `RBAC 발음`을 어떻게 하시나요?
    - **RBAC** : 역할 기반의 권한 관리, 사용자와 역할을 별개로 선언 후 두가지를 조합(binding)해서 사용자에게 권한을 부여하여 kubectl or API로 관리 가능
        - Namespace/Cluster - Role/ClusterRole, RoleBinding/ClusterRoleBinding, Service Account
        - Role(롤) - (RoleBinding 롤 바인딩) - Service Account(서비스 어카운트) : 롤 바인딩은 롤과 서비스 어카운트를 연결
        - Role(네임스페이스내 자원의 권한) vs ClusterRole(클러스터 수준의 자원의 권한)
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei4.png)




<details><summary>.kube/config파일 내용</summary>


- clusters : kubectl 이 사용할 쿠버네티스 API 서버의 접속 정보 목록. 원격의 쿠버네티스 API 서버의 주소를 추가해 사용 가능
- users : 쿠버네티스의 API 서버에 접속하기 위한 사용자 인증 정보 목록. (서비스 어카운트의 토큰, 혹은 인증서의 데이터 등)
- contexts : cluster 항목과 users 항목에 정의된 값을 조합해 최종적으로 사용할 쿠버네티스 클러스터의 정보(컨텍스트)를 설정.
    - 예를 들어 clusters 항목에 클러스터 A,B 가 정의돼 있고, users 항목에 사용자 a,b 가 정의돼 있다면 cluster A + user a 를 조합해,
    'cluster A 에 user a 로 인증해 쿠버네티스를 사용한다' 라는 새로운 컨텍스트를 정의할 수 있습니다.
    - kubectl 을 사용하려면 여러 개의 컨텍스트 중 하나를 선택.

```bash
cat .kube/config
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUM1ekNDQWMrZ0F3SUJBZ0lCQURBTkJna3Foa2lHOXcwQkFRc0ZBREFWTVJNd0VRWURWUVFERXdwcmRXSmwKY201bGRHVnpNQjRYRFRJeE1Ea3dNVEl5TkRjMU1sb1hEVE14TURnek1ESXlORGMxTWxvd0ZURVRNQkVHQTFVRQpBeE1LYTNWaVpYSnVaWFJsY3pDQ0FTSXdEUVlKS29aSWh2Y05BUUVCQlFBRGdnRVBBRENDQVFvQ2dnRUJBTG1qCml1cW11UUxWTXN6UE83VUpxTkdCNHdXQ3RnYTl1cFcwYUVNVmUrZm41YXZZMWxUWUZqZjBCb1VlQXhOWmc5YXoKRU1FZVJMWCt1ZzhqTDNETjhCTzEwdUEwSzF6b3ZpQVVtbDlCU2dNWU9FOHpUMFJsV2tvcnBtVDNGai9td1lJagpEemRxYld6MlpuQ1FoQ3dvYURzdlpoUVNMRTh6dnFwU0F5c0hNSUdzV3J0anI4aC9QaW52dnF5bUo0UlFhWlY3CnNuZ0lzMDBqakdGbFowcUVueWZMSGtBeHpjSktVUnJHamFsZm1RdmZ3WkZ2Z0pjam5rSG9jb3g0T0JKUEh0N2EKdFE1OEpBTTF3cng0b3pFSjh1MExsa21LOWYwWGVzQmRGeUhFamZ1elhTYml0Q09sbTR1Q1o3UkVRVmRjZWk1SAo3Tjg1M1RjbWRIck9tRkQwZVpVQ0F3RUFBYU5DTUVBd0RnWURWUjBQQVFIL0JBUURBZ0trTUE4R0ExVWRFd0VCCi93UUZNQU1CQWY4d0hRWURWUjBPQkJZRUZLRVYvZFNBUkJteVhyLytxUkVnb1h5QUg3UTZNQTBHQ1NxR1NJYjMKRFFFQkN3VUFBNElCQVFDQ0M4cDRQRmdoVVFDbW5weWk1SDAxYVRNYXp0Si9pdkw0amxiMWJNdXc3ZjJNZmM0UQpDRGw2UWVNd2FpYk9raHNrVGhMTEtRckQwQ0xqWXNCSy9iNVhQSTNtMmoxS0cvc1ExREFPL0hNdmt6RmkzUDdrCmJHOUErdWk1YXJPREs5eWJFQ2NtUG5adnVmWkFSY3d3dkp1ZGRMUy9QZERkOW9ZVGgzV3FQMjloVk9tZnZUS3kKNFhzeVg0cHk5dzVTNkYxaGVpUE9odnprMWRzNWFZZENBR1E5R0ZRb3BIQSs1Wm9YOWJjazFuN0FiMDVua0UrUQprMTVnc1VhQWFEMGVGUlRHY0tRTzM5dW1ZdkxhVnUrL20xcDFFRWU0YWdLdktvUGZlZ1VJTFQ0dGtLdjFwcWYvCmhIZldDUFo3Vy9ldmRZODI5WmtudE1HWHZ5QXZaWHFUZE1KZwotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg==
    server: https://192.168.100.10:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    namespace: default
    user: kubernetes-admin
  name: admin@k8s
current-context: admin@k8s
kind: Config
preferences: {}
**users**:
- name: kubernetes-admin
  **user**:
    **client-certificate-data**: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSURJVENDQWdtZ0F3SUJBZ0lJUzFnbmhwU0N5Q2d3RFFZSktvWklodmNOQVFFTEJRQXdGVEVUTUJFR0ExVUUKQXhNS2EzVmlaWEp1WlhSbGN6QWVGdzB5TVRBNU1ERXlNalEzTlRKYUZ3MHlNakE1TURFeU1qUTNOVFZhTURReApGekFWQmdOVkJBb1REbk41YzNSbGJUcHRZWE4wWlhKek1Sa3dGd1lEVlFRREV4QnJkV0psY201bGRHVnpMV0ZrCmJXbHVNSUlCSWpBTkJna3Foa2lHOXcwQkFRRUZBQU9DQVE4QU1JSUJDZ0tDQVFFQW52eXoxc1R1SXRpKzE3WmQKVVRXTFVxMUxIL2VJN01lMkI0K2ZNZlhKSStlM2xCVnp5RXpIV0ZOR1phM2JYbkYvS0VJaDJRcmpOcXh0bGswSgpIOW83dUtVZmRyVjhNL3IzZmxidUN1VG9lZnN3UFROQmJhbGladzVPRXl0VWV6V3ZxK3VUZzFmeExZVUl6Zk4xCldxMzhiU2pjYlhQa3Q3UWJZVThqUEpMMmlKalBlbVFRN1FnTW9pUmlsNXM2TzRCZnNYbzNCbDNrdUY0VDlCK1MKVzE2VmpQTnRMQ0pxQW1ENEt1ZWdBcWl3RHdDNFVScjhNbDhJaHJmL2FzT2JTZnVqTG5HL1Npd2V6dnJ4bHJnUgo0QVBlNjFSOU1RZFFjaldsT1Z2TXQrSXhlSnlrbWdmeHJsNFJmbytFOWVNK0VTNzFHaVhnQmtycFp0NGxQWURsClllSVZQd0lEQVFBQm8xWXdWREFPQmdOVkhROEJBZjhFQkFNQ0JhQXdFd1lEVlIwbEJBd3dDZ1lJS3dZQkJRVUgKQXdJd0RBWURWUjBUQVFIL0JBSXdBREFmQmdOVkhTTUVHREFXZ0JTaEZmM1VnRVFac2w2Ly9xa1JJS0Y4Z0IrMApPakFOQmdrcWhraUc5dzBCQVFzRkFBT0NBUUVBa0ZqdDJPNW5ZQUkxRHRrZnh6R1RPbFdGT1F3b3FKelBHQXJSCmRoTnFXL3JjUlhyYkgzZ3FHaXF4cmQ2anczblJiYThCRWxOazE0YUtYWGVYRnU0U0YyYTJCY3RzKzhkNE9VSkwKeU1pUVBpN0g2Q3RrQ0o2QzRCZDU4Vk5XaVM0YVg4b0ExQWloZWp0cURRc2U2MCtna2JoSlJwdnM0WGRVUkNTdgpFL3NqZWgvc1JIVjBJYWNrNzlTVEduSUdlVVUrbUxwVlF1bHZkd1lkVDhXK08zMkpRbFk1Z3pTZllFMkI2YjB4Ci9TK1dORU9QTzhhaTlmQkQ5cWJ1dWdRd2wzSkNYT005amZLV1gzOTBZZzhYcWhndEhuR0JDdlcwbjQxY0ZLUDgKQVFFdXRnbDNhQ0ZibWZFZ2Z3cWlUVFc3R3EzSklZSTZrZ3EwNGxUbVdKa1gvQnZmaXc9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg==
    **client-key-data**: LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFb3dJQkFBS0NBUUVBbnZ5ejFzVHVJdGkrMTdaZFVUV0xVcTFMSC9lSTdNZTJCNCtmTWZYSkkrZTNsQlZ6CnlFekhXRk5HWmEzYlhuRi9LRUloMlFyak5xeHRsazBKSDlvN3VLVWZkclY4TS9yM2ZsYnVDdVRvZWZzd1BUTkIKYmFsaVp3NU9FeXRVZXpXdnErdVRnMWZ4TFlVSXpmTjFXcTM4YlNqY2JYUGt0N1FiWVU4alBKTDJpSmpQZW1RUQo3UWdNb2lSaWw1czZPNEJmc1hvM0JsM2t1RjRUOUIrU1cxNlZqUE50TENKcUFtRDRLdWVnQXFpd0R3QzRVUnI4Ck1sOElocmYvYXNPYlNmdWpMbkcvU2l3ZXp2cnhscmdSNEFQZTYxUjlNUWRRY2pXbE9Wdk10K0l4ZUp5a21nZngKcmw0UmZvK0U5ZU0rRVM3MUdpWGdCa3JwWnQ0bFBZRGxZZUlWUHdJREFRQUJBb0lCQUQzOHFPR0R4cFV2akxqdQpFVlFvWERuUDl3cHZxS01vK24vWUwybDdPd0VVeHk2bGJvOFo0RjgvbUtMc05pdU1kTmR0Y1dUK0tiaVhZZUxJCkJsYTA3N1ArTFZaTFRERzRGK2JhWGRWQmlxS0VuVG8vVWJNLzUyM20xZW9EYXR6ZkFhODJHajJMZkMwVFFXdUwKRUtaYVQ2RC8zWEdQVGcyUjIxc0ZUK2UrSlFEOGRnc25oNE9vVlQrTkRacC9kU0JHYXZNQTFZUmo0bFhwY1U5RAo5bW15ckxRZFlRcE56K1U4cGZKdHhIcXlGSWhOakZmK0JkNHdRdEhrN3NOODE4Um9JalZHV3RYeGVhZXFOMXVtCnFlWEhFNHVDRG5tYS9qTElLLzBRaWlMZTZ1WGVTMk1udG1UUjJ1d0paOWh5V3NsYnlTb2oyQmNONVBaaHpGK3kKMUtyZEFZRUNnWUVBenNEeUFtZ1dUUXI5M083ZnlSR1U5azBad01LRFVSK25Lb0xQcUNhSmxQeE4xaG1zTkJmWApKWURsZ3cwVTk5R1lmRGJZUTdjS3BaRE8xWHZpWTI4K1UxY21nM2xVMVFVOTdFR0N3ejVxMnNjUFY0SDBhZmxnCmNUQko5dGo1ZTkzVS9sVDFpd0M1eEFONlpjektTbzhYSytNQ29nUkEyeEFZZjFJZnJTZmhoVzBDZ1lFQXhOc2kKQ2oxS29FQzV0TjlEaW41eFQzMUVBTjlwVmtONkZlcy9nZC9JSFREWXJLSytaMnNpVVNhR1NyaHYwZkc1ZGVwagpIMjdEeVF6cW1aUUlpaE44cFB5TzRSOXMya21la3RISUZqMjRnSUpQZDNzS3BaS1QwQjJmZUErTXVCOFlsclRGCk0ycTJ2V1JHeHFmMERMZmpWNm5JVkZkQ1hJWFZLMjlRcWprdkZkc0NnWUFmUGRxVDhJU0dLY1lJajNQelh4dkMKU0E0L0tXVk1hZHNKdW5DRWVTWkxCQUVDL0NnZ1N3WHduZFNRZy9hS0ovckJza3ZsbDVBZFNvOW1oT3pGbDdhMApRelFIbzlya3dZRUU1VFZNS1c5ZUZieEV2ZGRmK0JYUnBMbFllcHJnVTdudW9Jbmw4anNmMm1LeFpVdWdEcFV5CnhYL05XWlV2UlBSZXNOc21nQ004MVFLQmdRQ0xSOFFJM0o3TlRaNVhNOVJVeSt1ZDR6SlhMN3NXMXIwdGZ2bTcKQ1R0TU5BQkovUWVjb25kd1ZVS1U0WFAwWmdQalF3Z0krRlM4RGxCNmd2dWJ2ZmZsdisvVHBtbGM5Tk9tYTVrVwo2MnA4T2piQmdhUGh6QmliR2lwM1J3RTRVSUFVT1NpQm5aSlg0L2dUbkVlWExCQkZPUkpOWWtQSXRNUkRiQW4xCnRtbnpHd0tCZ0J3NHhLanNEUUozcCtxWW50cTdtVzhLS2hPWTFMRWczOVJ4Snd1aEord0VSZUh5TGhIcEU5SFkKUndxbUVCYjdvY2dDcmV6bWR5WndUSXZkMGEzaStBbWpucTd1QU1DUFpNUjU0a2FkNUpmZmVib0FzbXcwSW5aeApvVGltQXNya3BmRlVxZzZsSVBIMEtuUEVTVWQxQlJLS2I5dTUzTWpwZEZiVkhWZVZhVEtlCi0tLS0tRU5EIFJTQSBQUklWQVRFIEtFWS0tLS0tCg==
```


</details>

### 실습 환경
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei5.png)

- 쿠버네티스에 사용자를 위한 서비스 어카운트(Service Account, SA)를 생성 : dev-k8s, infra-k8s
- 사용자는 각기 다른 권한(Role, 인가)을 가짐 : dev-k8s(dev-team 네임스페이스 내 모든 동작) , infra-k8s(dev-team 네임스페이스 내 모든 동작)
- 각각 별도의 kubectl 파드를 생성하고, 해당 파드에 SA 를 지정하여 권한에 대한 테스트를 진행

<details><summary>어카운트 생성 확인</summary>


- 파드 기동 시 서비스 어카운트 한 개가 할당되며, 서비스 어카운트 기반 인증/인가를 함, 미지정 시 기본 서비스 어카운트가 할당
- 서비스 어카운트에 자동 생성된 시크릿에 저장된 토큰으로 쿠버네티스 API에 대한 인증 정보로 사용 할 수 있다 ← 1.23 이전 버전의 경우에만 해당

```bash
# 네임스페이스(Namespace, NS) 생성 및 확인
**kubectl create namespace dev-team
kubectl create ns infra-team**

# 네임스페이스 확인
kubectl get ns

# 네임스페이스에 각각 서비스 어카운트 생성 : serviceaccounts 약자(=sa)
**kubectl create sa dev-k8s -n dev-team
kubectl create sa infra-k8s -n infra-team**

# 서비스 어카운트 정보 확인
kubectl get sa -n dev-team
kubectl get sa dev-k8s -n dev-team -o yaml | yh

kubectl get sa -n infra-team
kubectl get sa infra-k8s -n infra-team -o yaml | yh
```

</details>





----

 - (심화 참고) dev-k8s 서비스어카운트의 토큰 정보 확인  - https://jwt.io/ → Bearer type - JWT(JSON Web Token) - [링크](https://coffeewhale.com/kubernetes/authentication/http-auth/2020/05/03/auth02/)
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei6.png)

    
    https://coffeewhale.com/kubernetes/authentication/http-auth/2020/05/03/auth02/
    
    ```bash

    # dev-k8s 서비스어카운트의 토큰 정보 확인 
    DevTokenName=$(kubectl get sa dev-k8s -n dev-team -o jsonpath="{.secrets[0].name}")
    DevToken=$(kubectl get secret -n dev-team $DevTokenName -o jsonpath="{.data.token}" | base64 -d)
    echo $DevToken.

    ```
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei7.png)

    `**Bearer type - JWT(JSON Web Token)**`
    
    - Bearer type 경우, 서버에서 지정한 어떠한 문자열도 입력할 수 있습니다. 하지만 굉장히 허술한 느낌을 받습니다.
    - 이를 보완하고자 쿠버네티스에서 Bearer 토큰을 전송할 때 주로 **JWT** (JSON Web Token) 토큰을 사용합니다.
    - **JWT**는 X.509 Certificate와 마찬가지로 private key를 이용하여 토큰을 서명하고 public key를 이용하여 서명된 메세지를 검증합니다.
    - 이러한 메커니즘을 통해 해당 토큰이 쿠버네티스를 통해 생성된 valid한 토큰임을 인증할 수 있습니다.
    - X.509 Certificate의 lightweight JSON 버전이라고 생각하면 편리합니다.
    - jwt는 JSON 형태로 토큰 형식을 정의한 스펙입니다. jwt는 쿠버네티스에서 뿐만 아니라 다양한 웹 사이트에서 인증, 권한 허가, 세션관리 등의 목적으로 사용합니다.
        - Header: 토큰 형식와 암호화 알고리즘을 선언합니다.
        - Payload: 전송하려는 데이터를 JSON 형식으로 기입합니다.
        - Signature: Header와 Payload의 변조 가능성을 검증합니다.
    - 각 파트는 base64 URL 인코딩이 되어서 `.`으로 합쳐지게 됩니다.



<details><summary>서비스 어카운트를 지정하여 파드 생성 후 권한 테스트</summary>

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei8.png)
https://kubetm.github.io/practice/intermediate/object-authentication/




```bash
# 각각 네임스피이스에 kubectl 파드 생성 - [컨테이너이미지](https://hub.docker.com/r/bitnami/kubectl/)
# docker run --rm --name kubectl -v /path/to/your/kube/config:/.kube/config bitnami/kubectl:latest
cat <<EOF | kubectl create -f -
apiVersion: v1
kind: Pod
metadata:
  name: **dev-kubectl**
  namespace: dev-team
spec:
  serviceAccountName: **dev-k8s**
  containers:
  - name: kubectl-pod
    image: bitnami/kubectl:**1.28.5**
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF

cat <<EOF | kubectl create -f -
apiVersion: v1
kind: Pod
metadata:
  name: **infra-kubectl**
  namespace: infra-team
spec:
  serviceAccountName: **infra-k8s**
  containers:
  - name: kubectl-pod
    image: bitnami/kubectl:**1.28.5**
    command: ["tail"]
    args: ["-f", "/dev/null"]
  terminationGracePeriodSeconds: 0
EOF

# 확인
kubectl get pod -A
kubectl get pod -o dev-kubectl -n dev-team -o yaml
 serviceAccount: dev-k8s
 ...
kubectl get pod -o infra-kubectl -n infra-team -o yaml
 serviceAccount: infra-k8s
...

# 파드에 기본 적용되는 서비스 어카운트(토큰) 정보 확인
**kubectl exec -it dev-kubectl -n dev-team -- ls /run/secrets/kubernetes.io/serviceaccount**
kubectl exec -it dev-kubectl -n dev-team -- cat /run/secrets/kubernetes.io/serviceaccount/token
kubectl exec -it dev-kubectl -n dev-team -- cat /run/secrets/kubernetes.io/serviceaccount/namespace
kubectl exec -it dev-kubectl -n dev-team -- cat /run/secrets/kubernetes.io/serviceaccount/ca.crt

# 각각 파드로 Shell 접속하여 정보 확인 : 단축 명령어(alias) 사용
alias **k1**='kubectl exec -it dev-kubectl -n dev-team -- kubectl'
alias **k2**='kubectl exec -it infra-kubectl -n infra-team -- kubectl'

# 권한 테스트
**k1** get pods # **kubectl exec -it dev-kubectl -n dev-team -- kubectl** get pods 와 동일한 실행 명령이다!
**k1** run nginx --image nginx:1.20-alpine
**k1** get pods -n kube-system

**k2** get pods # **kubectl exec -it infra-kubectl -n infra-team -- kubectl** get pods 와 동일한 실행 명령이다!
**k2** run nginx --image nginx:1.20-alpine
**k2** get pods -n kube-system

# (옵션) kubectl auth can-i 로 kubectl 실행 사용자가 특정 권한을 가졌는지 확인
**k1** auth can-i get pods
**no**
```


</details>




<details><summary>각각 네임스페이스에 롤(Role)를 생성 후 서비스 어카운트 바인딩</summary>

- **롤(Role)** : apiGroups 와 resources 로 지정된 리소스에 대해 **verbs** 권한을 인가
- **실행 가능한 조작(verbs)** : *(모두 처리), create(생성), delete(삭제), get(조회), list(목록조회), patch(일부업데이트), update(업데이트), watch(변경감시)

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei9.png)


https://kubetm.github.io/practice/intermediate/object-authorization/

```bash
# 각각 네임스페이스내의 모든 권한에 대한 롤 생성
cat <<EOF | kubectl create -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: **Role**
metadata:
  name: role-dev-team
  namespace: dev-team
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
EOF

cat <<EOF | kubectl create -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: **Role**
metadata:
  name: role-infra-team
  namespace: infra-team
rules:
- apiGroups: ["*"]
  resources: ["*"]
  verbs: ["*"]
EOF

# 롤 확인 
kubectl get roles -n dev-team
kubectl get roles -n infra-team
kubectl get roles -n dev-team -o yaml
kubectl describe roles role-dev-team -n dev-team
...
PolicyRule:
  Resources  Non-Resource URLs  Resource Names  Verbs
  ---------  -----------------  --------------  -----
  *.*        []                 []              [*]

# 롤바인딩 생성 : '서비스어카운트 <-> 롤' 간 서로 연동
cat <<EOF | kubectl create -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: **RoleBinding**
metadata:
  name: roleB-dev-team
  namespace: dev-team
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: role-dev-team
subjects:
- kind: ServiceAccount
  name: dev-k8s
  namespace: dev-team
EOF

cat <<EOF | kubectl create -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: **RoleBinding**
metadata:
  name: roleB-infra-team
  namespace: infra-team
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: role-infra-team
subjects:
- kind: ServiceAccount
  name: infra-k8s
  namespace: infra-team
EOF

# 롤바인딩 확인
kubectl get rolebindings -n dev-team
kubectl get rolebindings -n infra-team
kubectl get rolebindings -n dev-team -o yaml
kubectl describe rolebindings roleB-dev-team -n dev-team
...
Role:
  Kind:  Role
  Name:  role-dev-team
Subjects:
  Kind            Name     Namespace
  ----            ----     ---------
  ServiceAccount  dev-k8s  dev-team
```


</details>




<details><summary>서비스 어카운트를 지정하여 생성한 파드에서 다시 권한 테스트</summary>


```bash
# 각각 파드로 Shell 접속하여 정보 확인 : 단축 명령어(alias) 사용
alias **k1**='kubectl exec -it dev-kubectl -n dev-team -- kubectl'
alias **k2**='kubectl exec -it infra-kubectl -n infra-team -- kubectl'

# 권한 테스트
**k1** get pods 
**k1** run nginx --image nginx:1.20-alpine
**k1** get pods
**k1** delete pods nginx
**k1 get pods -n kube-system**
**k1** get nodes

**k2** get pods 
**k2** run nginx --image nginx:1.20-alpine
**k2** get pods
**k2** delete pods nginx
**k2 get pods -n kube-system**
**k2** get nodes

# (옵션) kubectl auth can-i 로 kubectl 실행 사용자가 특정 권한을 가졌는지 확인
**k1** auth can-i get pods
**yes**
```

</details>


- **리소스 삭제** :  `kubectl delete ns dev-team infra-team`



## EKS 인증/인가

- 동작 : 사용자/애플리케이션 → k8s 사용 시 ⇒ 인증은 AWS IAM, 인가는 K8S RBAC
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei10.png)
https://kimalarm.tistory.com/65


<details><summary>RBAC 관련 krew 플러그인</summary>

```bash
# 설치
**kubectl krew install access-matrix rbac-tool rbac-view rolesum whoami**

# k8s 인증된 주체 확인
**kubectl whoami**
arn:aws:iam::9112...:user/admin

# Show an RBAC access matrix for server resources
**kubectl access-matrix** # Review access to cluster-scoped resources
kubectl access-matrix --namespace default # Review access to namespaced resources in 'default'

# RBAC Lookup by subject (user/group/serviceaccount) name
kubectl rbac-tool lookup
**kubectl rbac-tool lookup system:masters**
  SUBJECT        | SUBJECT TYPE | SCOPE       | NAMESPACE | ROLE
+----------------+--------------+-------------+-----------+---------------+
  system:masters | Group        | ClusterRole |           | cluster-admin

kubectl rbac-tool lookup system:nodes # eks:node-bootstrapper
kubectl rbac-tool lookup system:bootstrappers # eks:node-bootstrapper
**kubectl describe ClusterRole eks:node-bootstrapper**

# RBAC List Policy Rules For subject (user/group/serviceaccount) name
kubectl rbac-tool policy-rules
kubectl rbac-tool policy-rules -e '^system:.*'
kubectl rbac-tool policy-rules -e '^system:authenticated'

# Generate ClusterRole with all available permissions from the target cluster
kubectl rbac-tool show

# Shows the subject for the current context with which one authenticates with the cluster
**kubectl rbac-tool whoami**
{**Username**: "arn:aws:iam::911283...:user/admin",      *<<-- 과거 "kubernetes-admin"에서 변경됨*
 UID:      "aws-iam-authenticator:911283.:AIDA5ILF2FJI...",
 Groups:   ["system:authenticated"],                 *<<-- 과거 "system:master"는 안보임*
 Extra:    {****:  ["AKIA5ILF2FJI....."],
            arn:          ["arn:aws:iam::9112834...:user/admin"],
            canonicalArn: ["arn:aws:iam::9112834...:user/admin"],
            **principalId**:  ["AIDA5ILF2FJI...."],
            sessionName:  [""]}}

# Summarize RBAC roles for subjects : ServiceAccount(default), User, Group
kubectl rolesum -h
**kubectl rolesum aws-node -n kube-system**
kubectl rolesum -k User system:kube-proxy
kubectl rolesum -k Group system:masters
**kubectl rolesum -k Group system:authenticated**
*Policies:
• [CRB] */system:basic-user ⟶  [CR] */system:basic-user
  Resource                                       Name  Exclude  Verbs  G L W C U P D DC  
  selfsubjectaccessreviews.authorization.k8s.io  [*]     [-]     [-]   ✖ ✖ ✖ ✔ ✖ ✖ ✖ ✖   
  selfsubjectreviews.authentication.k8s.io       [*]     [-]     [-]   ✖ ✖ ✖ ✔ ✖ ✖ ✖ ✖   
  selfsubjectrulesreviews.authorization.k8s.io   [*]     [-]     [-]   ✖ ✖ ✖ ✔ ✖ ✖ ✖ ✖   
• [CRB] */system:discovery ⟶  [CR] */system:discovery
• [CRB] */system:public-info-viewer ⟶  [CR] */system:public-info-viewer*

# [터미널1] A tool to visualize your RBAC permissions
**kubectl rbac-view**
INFO[0000] Getting K8s client
INFO[0000] serving RBAC View and http://localhost:8800

## 이후 해당 작업용PC 공인 IP:8800 웹 접속 : 최초 접속 후 정보 가져오는데 다시 시간 걸림 (2~3분 정도 후 화면 출력됨) 
echo -e "RBAC View Web http://$(curl -s ipinfo.io/ip):8800"

```


</details>



<details><summary>인증/인가 완벽 분석 해보기</summary>

<iframe width="576" height="324" src="https://www.youtube.com/embed/bksogA-WXv8" title="Amazon EKS 마이그레이션 요점정리 - 강인호 솔루션즈 아키텍트, AWS :: AWS Summit Korea 2022" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>
kubectl 사용 시 흐름 11:09 ~  

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei11.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei12.png)

https://devlos.tistory.com/75

- **핵심** : 인증은 AWS IAM, 인가는 K8S RBAC에서 처리

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei13.png)


https://docs.aws.amazon.com/eks/latest/userguide/cluster-auth.html

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei14.png)


[https://awskoreamarketingasset.s3.amazonaws.com/2022 Summit/pdf/T10S1_EKS 환경을 더 효율적으로 더 안전하게.pdf](https://awskoreamarketingasset.s3.amazonaws.com/2022%20Summit/pdf/T10S1_EKS%20%ED%99%98%EA%B2%BD%EC%9D%84%20%EB%8D%94%20%ED%9A%A8%EC%9C%A8%EC%A0%81%EC%9C%BC%EB%A1%9C%20%EB%8D%94%20%EC%95%88%EC%A0%84%ED%95%98%EA%B2%8C.pdf)

1. kubectl 명령 → aws eks get-token → EKS Service endpoint(STS)에 토큰 요청 ⇒ 응답값 디코드(Pre-Signed URL 이며 GetCallerIdentity..) - [링크](https://docs.aws.amazon.com/ko_kr/IAM/latest/UserGuide/id_credentials_temp_request.html)
    - **STS** Security Token Service : AWS 리소스에 대한 액세스를 제어할 수 있는 임시 보안 자격 증명(STS)을 생성하여 신뢰받는 사용자에게 제공할 수 있음
        
        https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventSource=sts.amazonaws.com
        
    - **AWS CLI** 버전 1.16.156 이상에서는 별도 aws-iam-authenticator 설치 없이 **aws eks get-token**으로 사용 가능 - [Docs](https://docs.aws.amazon.com/eks/latest/userguide/install-aws-iam-authenticator.html)
    
    ```bash
    # sts caller id의 ARN 확인
    **aws sts get-caller-identity --query Arn**
    "arn:aws:iam::<자신의 Account ID>:user/**admin**"
    
    # kubeconfig 정보 확인
    **cat ~/.kube/config | yh**
    ...
    - name: admin@myeks.ap-northeast-2.eksctl.io
      **user**:
        exec:
          apiVersion: **client.authentication.k8s.io/v1beta1**
          args:
          **- eks
          - get-token
          - --output
          - json
          - --cluster-name
          - myeks
          - --region
          - ap-northeast-2**
          command: **aws**
          env:
          - name: **AWS_STS_REGIONAL_ENDPOINTS**
            value: regional
          interactiveMode: IfAvailable
          provideClusterInfo: false
    
    # Get  a token for authentication with an Amazon EKS cluster.
    # This can be used as an **alternative to the aws-iam-authenticator**.
    **aws eks get-token help**
    
    **#** 임시 보안 자격 증명(토큰)을 요청 **:** expirationTimestamp **시간경과 시 토큰 재발급됨**
    **aws eks get-token --cluster-name $CLUSTER_NAME** | jq
    aws eks get-token --cluster-name $CLUSTER_NAME | jq -r '.status.token'
    ```
    
2. kubectl의 [Client-Go](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#client-go-credential-plugins) 라이브러리는 **Pre-Signed URL**을 Bearer Token으로 EKS API Cluster Endpoint로 요청을 보냄
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei15.png)

    
    https://sharing-for-us.tistory.com/39
    
    - ~~토큰을 [jwt](https://jwt.io/) 사이트에 복붙으로 디코드 정보 확인(HS384 → HS256) PAYLOAD 정보 확인~~ : 일반적인 AWS API 호출과 유사합니다!
        
       ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei16.png)

        
        출처 : https://youtu.be/zIZ6_tYujts?t=231 'AWS 보안 웨비나'
        
    - ~~PAYLOAD의 값을 URL Decode Online 에서 DECODE로 확인~~ - [링크](https://url-decode.com/)
        
        ```bash
        https://**sts**.ap-northeast-2.amazonaws.com/?
        
        Action=**GetCallerIdentity**&
        
        Version=2011-06-15&
        
        X-Amz-Algorithm=AWS4-HMAC-SHA256&
        
        X-Amz-**Credential**=**AKIA5ILF**.../20230525/ap-northeast-2/sts/aws4_request&
        
        X-Amz-**Date**=20230525T120720Z&
        
        X-Amz-**Expires**=60&
        
        X-Amz-**SignedHeaders**=host;**x-k8s-aws-id**&
        
        X-Amz-**Signature**=6e09b846da702767f38c78831986cb558.....
        ```
        
    
3. EKS API는 **Token Review** 를 **Webhook token authenticator**에 요청 ⇒ (STS GetCallerIdentity 호출) AWS IAM 해당 **호출 인증 완료** 후 User/Role에 대한 **ARN 반환**
    - 참고로 [Webhook token authenticator](https://kubernetes.io/docs/reference/access-authn-authz/authentication/#webhook-token-authentication) 는 aws-iam-authenticator 를 사용 - [링크](https://blog.naver.com/alice_k106/221967218283) [Github](https://github.com/kubernetes-sigs/aws-iam-authenticator)
        
        https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=GetCallerIdentity
        
    
    ```bash
    # tokenreviews api 리소스 확인 
    **kubectl api-resources | grep authentication**
    tokenreviews                                   authentication.k8s.io/v1               false        TokenReview
    
    # List the fields for supported resources.
    **kubectl explain tokenreviews**
    ...
    DESCRIPTION:
         TokenReview attempts to authenticate a token to a known user. Note:
         TokenReview requests may be cached by the **webhook token authenticator
         plugin in the kube-apiserver**.
    ```
    
4. 이제 쿠버네티스 **RBAC 인가**를 처리합니다. 개인적인 생각이지만 플랫폼간 인증 이외에 인가까지 처리 통합은 쉽지 않은 것 같습니다 ~~*okta도*~~
    - 해당 IAM User/Role 확인이 되면 k8s aws-auth configmap에서 **mapping 정보**를 확인하게 됩니다.
    - aws-auth 컨피그맵에 'IAM 사용자, 역할 arm, K8S 오브젝트' 로 권한 확인 후 **k8s 인가 허가**가 되면 최종적으로 동작 실행을 합니다.
    - 참고로 **EKS를 생성한 IAM principal**은 aws-auth 와 상관없이 kubernetes-admin Username으로 **system:masters 그룹**에 권한을 가짐 - [링크](https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html)
    
    ```bash
    # Webhook api 리소스 확인 
    **kubectl api-resources | grep Webhook**
    mutatingwebhookconfigurations                  admissionregistration.k8s.io/v1        false        MutatingWebhookConfiguration
    **validatingwebhookconfigurations**                admissionregistration.k8s.io/v1        false        ValidatingWebhookConfiguration
    
    # validatingwebhookconfigurations 리소스 확인
    **kubectl get validatingwebhookconfigurations**
    NAME                                        WEBHOOKS   AGE
    eks-aws-auth-configmap-validation-webhook   1          50m
    vpc-resource-validating-webhook             2          50m
    aws-load-balancer-webhook                   3          8m27s
    
    **kubectl get validatingwebhookconfigurations eks-aws-auth-configmap-validation-webhook -o yaml | kubectl neat | yh**
    
    # aws-auth 컨피그맵 확인
    **kubectl get cm -n kube-system aws-auth -o yaml | kubectl neat | yh**
    apiVersion: v1
    kind: ConfigMap
    metadata: 
      name: aws-auth
      namespace: kube-system
    data: 
      **mapRoles**: |
        - groups:
          - system:bootstrappers
          - system:nodes
          rolearn: arn:aws:iam::91128.....:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-1OS1WSTV0YB9X
          username: system:node:{{EC2PrivateDNSName}}
    *#---<아래 생략(추정), ARN은 EKS를 설치한 IAM User , 여기 있었을경우 만약 실수로 삭제 시 복구가 가능했을까?---
      **mapUsers**: |
        - groups:
          - **system:masters**
          userarn: arn:aws:iam::111122223333:user/**admin**
          username: **kubernetes-admin***
    
    # EKS 설치한 IAM User 정보 >> system:authenticated는 어떤 방식으로 추가가 되었는지 궁금???
    **kubectl rbac-tool whoami**
    {Username: "~~kubernetes-admin~~",
     UID:      "aws-iam-authenticator:9112834...:AIDA5ILF2FJIR2.....",
     Groups:   [~~"system:masters",~~
                "system:authenticated"],
    ...
    
    # system:masters , system:authenticated 그룹의 정보 확인
    kubectl rbac-tool lookup system:masters
    kubectl rbac-tool lookup system:authenticated
    kubectl rolesum -k Group system:masters
    kubectl rolesum -k Group system:authenticated
    
    # system:masters 그룹이 사용 가능한 클러스터 롤 확인 : cluster-admin
    **kubectl describe clusterrolebindings.rbac.authorization.k8s.io cluster-admin**
    Name:         cluster-admin
    Labels:       kubernetes.io/bootstrapping=rbac-defaults
    Annotations:  rbac.authorization.kubernetes.io/autoupdate: true
    Role:
      Kind:  ClusterRole
      Name:  **cluster-admin**
    Subjects:
      Kind   Name            Namespace
      ----   ----            ---------
      Group  **system:masters**
    
    # cluster-admin 의 PolicyRule 확인 : 모든 리소스  사용 가능!
    **kubectl describe clusterrole cluster-admin**
    Name:         cluster-admin
    Labels:       kubernetes.io/bootstrapping=rbac-defaults
    Annotations:  rbac.authorization.kubernetes.io/autoupdate: true
    PolicyRule:
      **Resources**  **Non-Resource URLs**  Resource Names  Verbs
      ---------  -----------------  --------------  -----
      ***.***        []                 []              [*****]
                 [*****]                []              [*]
    
    # system:authenticated 그룹이 사용 가능한 클러스터 롤 확인
    kubectl describe ClusterRole **system:discovery**
    kubectl describe ClusterRole **system:public-info-viewer**
    kubectl describe ClusterRole **system:basic-user**
    kubectl describe ClusterRole **eks:podsecuritypolicy:privileged**
    ```


</details>



<details><summary>데브옵스 신입 사원을 위한 myeks-bastion-2에 설정 해보기</summary>

1. [myeks-bastion] testuser 사용자 생성 
    
    ```bash
    # testuser 사용자 생성
    aws iam create-user --user-name **testuser**
    
    # 사용자에게 프로그래밍 방식 액세스 권한 부여
    aws iam create-access-key --user-name **testuser**
    {
        "  ": {
            "UserName": "testuser",
            "****": "##",
            "Status": "Active",
            "** **": "TxhhwsU8##",
            "CreateDate": "2023-05-23T07:40:09+00:00"
        }
    }
    # testuser 사용자에 정책을 추가
    aws iam attach-user-policy --policy-arn arn:aws:iam::aws:policy/**AdministratorAccess** --user-name **testuser**
    
    # get-caller-identity 확인
    aws sts get-caller-identity --query Arn
    "arn:aws:iam::911283464785:user/admin"
    
    **kubectl whoami**
    
    # EC2 IP 확인 : myeks-bastion-EC2-2 PublicIPAdd 확인
    **aws ec2 describe-instances --query "Reservations[*].Instances[*].{PublicIPAdd:PublicIpAddress,PrivateIPAdd:PrivateIpAddress,InstanceName:Tags[?Key=='Name']|[0].Value,Status:State.Name}" --filters Name=instance-state-name,Values=running --output table**
    ```
    
2. [myeks-bastion-2] testuser 자격증명 설정 및 확인
    
    ```bash
    # get-caller-identity 확인 >> 왜 안될까요?
    **aws sts get-caller-identity --query Arn**
    
    # testuser 자격증명 설정
    **aws configure**
    AWS Access Key ID [None]: *AKIA5ILF2F...*
    AWS Secret Access Key [None]: *ePpXdhA3cP....*
    Default region name [None]: ***ap-northeast-2***
    
    # get-caller-identity 확인
    **aws sts get-caller-identity --query Arn**
    "arn:aws:iam::911283464785:user/**testuser**"
    
    # kubectl 시도 >> testuser도 **AdministratorAccess** 권한을 가지고 있는데, 실패 이유는?
    **kubectl get node -v6**
    ls ~/.kube
    ```
    
3. [myeks-bastion] testuser에 system:masters 그룹 부여로 EKS 관리자 수준 권한 설정
    
    ```bash
    # 방안1 : eksctl 사용 >> iamidentitymapping 실행 시 aws-auth 컨피그맵 작성해줌
    # Creates a mapping from IAM role or user to Kubernetes user and groups
    eksctl get iamidentitymapping --cluster $CLUSTER_NAME
    eksctl create **iamidentitymapping** --cluster $**CLUSTER_NAME** --username **testuser** --group **system:masters** --arn arn:aws:iam::$ACCOUNT_ID:user/**testuser**
    
    # 확인
    **kubectl get cm -n kube-system aws-auth -o yaml | kubectl neat | yh**
    ...
    
    kubectl get **validatingwebhookconfigurations** eks-aws-auth-configmap-validation-webhook -o yaml | kubectl neat | yh
    ~~# 방안2 : 아래 edit로 mapUsers 내용 직접 추가!
    **kubectl edit cm -n kube-system aws-auth**
    ---
    apiVersion: v1
    data: 
      mapRoles: |
        - groups:
          - system:bootstrappers
          - system:nodes
          rolearn: arn:aws:iam::911283464785:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-LHQ7DWHQQRZJ
          username: system:node:{{EC2PrivateDNSName}}
      **mapUsers: |
        - groups:
          - system:masters
          userarn: arn:aws:iam::911283464785:user/testuser
          username: testuser**
    ...~~
    
    # 확인 : 기존에 있는 **role**/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-YYYYY 는 어떤 역할/동작을 하는 걸까요?
    **eksctl get iamidentitymapping --cluster $CLUSTER_NAME**
    ARN											USERNAME				GROUPS					ACCOUNT
    arn:aws:iam::911283464785:**role**/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-LHQ7DWHQQRZJ	system:node:{{EC2PrivateDNSName}}	system:bootstrappers,system:nodes	
    arn:aws:iam::911283464785:**user**/testuser							testuser				system:masters
    ```
    
4. [myeks-bastion-2] testuser kubeconfig 생성 및 kubectl 사용 확인
    
    ```bash
    # testuser kubeconfig 생성 >> aws eks update-kubeconfig 실행이 가능한 이유는?, 3번 설정 후 약간의 적용 시간 필요
    aws eks **update-kubeconfig** --name $CLUSTER_NAME --user-alias **testuser**
    
    # 첫번째 bastic ec2의 config와 비교해보자
    **cat ~/.kube/config | yh**
    
    # kubectl 사용 확인
    kubectl ns default
    kubectl get node -v6
    
    # rbac-tool 후 확인 >> 기존 계정과 비교해보자 >> system:authenticated 는 system:masters 설정 시 따라오는 것 같은데, 추가 동작 원리는 모르겠네요???
    **kubectl krew install rbac-tool && kubectl rbac-tool whoami**
    {Username: "**testuser**",
     UID:      "aws-iam-authenticator:911283464785:AIDA5ILF2FJIV65KG6RBM",
     Groups:   ["system:masters",
                "system:authenticated"],
                arn:          ["arn:aws:iam::911283464785:user/testuser"],
                canonicalArn: ["arn:aws:iam::911283464785:user/testuser"],
    ...
    ```
    
5. [myeks-bastion] testuser 의 Group 변경(system:masters → **system:authenticated**)으로 RBAC 동작 확인
    
    ```bash
    # 방안2 : 아래 edit로 mapUsers 내용 직접 수정 **system:authenticated**
    ~~~~**kubectl edit cm -n kube-system aws-auth**
    ...
    
    # 확인
    eksctl get iamidentitymapping --cluster $CLUSTER_NAME
    ```
    
6. [myeks-bastion-2] testuser kubectl 사용 확인
    
    ```bash
    # 시도
    kubectl get node -v6
    **kubectl api-resources -v5**
    ```
    
7. [myeks-bastion]에서 testuser IAM 맵핑 삭제
    
    ```bash
    # testuser IAM 맵핑 삭제
    eksctl **delete** iamidentitymapping --cluster $CLUSTER_NAME --arn  arn:aws:iam::$ACCOUNT_ID:user/testuser
    
    # Get IAM identity mapping(s)
    eksctl get iamidentitymapping --cluster $CLUSTER_NAME
    kubectl get cm -n kube-system aws-auth -o yaml | yh
    ```
    
8. [myeks-bastion-2] testuser kubectl 사용 확인
    
    ```bash
    # 시도
    kubectl get node -v6
    **kubectl api-resources -v5**
    ```
    
    https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventSource=sts.amazonaws.com
    
    https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=GetCallerIdentity
    
9. (참고) config 샘플 - [링크](https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html)
    
    ```bash
    # Please edit the object below. Lines beginning with a '#' will be ignored,
    # and an empty file will abort the edit. If an error occurs while saving this file will be
    # reopened with the relevant failures.
    #
    apiVersion: v1
    data:
      **mapRoles**: |
        *- groups:*
          - system:bootstrappers
          - system:nodes
          rolearn: arn:aws:iam::111122223333:role/my-role
          username: system:node:{{EC2PrivateDNSName}}
        *- groups:*
          - eks-console-dashboard-full-access-group
          rolearn: arn:aws:iam::111122223333:role/my-console-viewer-role
          username: my-console-viewer-role
      **mapUsers**: |
        *- groups:*
          - system:masters
          userarn: arn:aws:iam::111122223333:user/admin
          username: admin
        *- groups:*
          - eks-console-dashboard-restricted-access-group      
          userarn: arn:aws:iam::444455556666:user/my-user
          username: my-user
    ```


</details>






<details><summary>- **EC2 Instance Profile**(IAM Role)에 맵핑된 k8s rbac 확인 해보기</summary>

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei17.png)



https://docs.aws.amazon.com/eks/latest/userguide/access-entries.html#creating-access-entries

[pkos 스터디 5주차 1편 -  AWS EC2 인스턴스 메타데이터](https://malwareanalysis.tistory.com/578)

[pkos 스터디 5주차 2편 - pod에서 인스턴스 메타데이터 접근 가능하면 생기는 위험](https://malwareanalysis.tistory.com/579)

1. 노드 mapRoles 확인 - [링크](https://docs.aws.amazon.com/eks/latest/userguide/add-user-role.html)
    
    ```bash
    # 노드에 STS ARN 정보 확인 : Role 뒤에 인스턴스 ID!
    **for node in $N1 $N2 $N3; do ssh ec2-user@$node aws sts get-caller-identity --query Arn; done**
    "arn:aws:sts::911283464785:assumed-role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-LHQ7DWHQQRZJ/i-07c9162ed08d23e6f"
    "arn:aws:sts::911283464785:assumed-role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-LHQ7DWHQQRZJ/i-00d9d24c0af0d6815"
    "arn:aws:sts::911283464785:assumed-role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-LHQ7DWHQQRZJ/i-031e672f89572abe8"
    
    # aws-auth 컨피그맵 확인 >> system:nodes 와 system:bootstrappers 의 권한은 어떤게 있는지 찾아보세요!
    # username 확인! 인스턴스 ID? EC2PrivateDNSName?
    kubectl describe configmap -n kube-system aws-auth
    ...
    mapRoles:
    ----
    - groups:
      **- system:nodes
      - system:bootstrappers**
      **rolearn**: arn:aws:iam::911283464785:role/eksctl-myeks-nodegroup-ng-f6c38e4-**NodeInstanceRole**-1OU85W3LXHPB2
      **username**: **system:node:{{EC2PrivateDNSName}}**
    ...
    
    # Get IAM identity mapping(s)
    eksctl get iamidentitymapping --cluster $CLUSTER_NAME
    ARN												USERNAME		GROUPS					ACCOUNT
    arn:aws:iam::911283464785:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-1OS1WSTV0YB9X	system:node:{{EC2PrivateDNSName}}	system:bootstrappers,system:nodes
    ...
    ```
    
2. **awscli 파드**를 추가하고, 해당 노드(EC2)의 IMDS 정보 확인 : AWS CLI v2 파드 생성 - [링크](https://docs.aws.amazon.com/ko_kr/cli/latest/userguide/install-cliv2-docker.html) [공식이미지링크](https://hub.docker.com/r/amazon/aws-cli)
    
    ```bash
    # awscli 파드 생성
    cat <<EOF | kubectl create -f -
    apiVersion: apps/v1
    kind: **Deployment**
    metadata:
      name: awscli-pod
    spec:
      **replicas: 2**
      selector:
        matchLabels:
          app: awscli-pod
      template:
        metadata:
          labels:
            app: awscli-pod
        spec:
          containers:
          - name: awscli-pod
            image: **amazon/aws-cli**
            command: ["tail"]
            args: ["-f", "/dev/null"]
          terminationGracePeriodSeconds: 0
    EOF
    
    # 파드 생성 확인
    kubectl get pod -owide
    
    # 파드 이름 변수 지정
    APODNAME1=$(kubectl get pod -l app=awscli-pod -o jsonpath={.items[0].metadata.name})
    APODNAME2=$(kubectl get pod -l app=awscli-pod -o jsonpath={.items[1].metadata.name})
    echo $APODNAME1, $APODNAME2
    
    # awscli 파드에서 EC2 InstanceProfile(IAM Role)의 ARN 정보 확인
    kubectl exec -it $APODNAME1 -- aws sts get-caller-identity --query Arn
    kubectl exec -it $APODNAME2 -- aws sts get-caller-identity --query Arn
    
    # awscli 파드에서 EC2 InstanceProfile(IAM Role)을 사용하여 AWS 서비스 정보 확인 >> 별도 IAM 자격 증명이 없는데 어떻게 가능한 것일까요?
    # > 최소권한부여 필요!!! >>> 보안이 허술한 아무 컨테이너나 탈취 시, IMDS로 해당 노드의 IAM Role 사용 가능!
    kubectl exec -it $APODNAME1 -- **aws ec2 describe-instances --region ap-northeast-2 --output table --no-cli-pager**
    kubectl exec -it $APODNAME2 -- **aws ec2 describe-vpcs --region ap-northeast-2 --output table --no-cli-pager**
     
    # EC2 메타데이터 확인 : IDMSv1은 Disable, IDMSv2 활성화 상태, IAM Role - [링크](https://docs.aws.amazon.com/ko_kr/AWSEC2/latest/UserGuide/iam-roles-for-amazon-ec2.html)
    kubectl exec -it $APODNAME1 -- bash
    -----------------------------------
    **아래부터는 파드에 bash shell 에서 실행**
    curl -s http://169.254.169.254/ -v
    ...
    
    # Token 요청 
    curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" ; echo
    curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600" ; echo
    
    # Token을 이용한 IMDSv2 사용
    TOKEN=$(curl -s -X PUT "http://169.254.169.254/latest/api/token" -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
    echo $TOKEN
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" –v http://169.254.169.254/ ; echo
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" –v http://169.254.169.254/latest/ ; echo
    **curl -s -H "X-aws-ec2-metadata-token: $TOKEN" –v http://169.254.169.254/latest/meta-data/iam/security-credentials/ ; echo**
    
    # 위에서 출력된 IAM Role을 아래 입력 후 확인
    curl -s -H "X-aws-ec2-metadata-token: $TOKEN" –v http://169.254.169.254/latest/meta-data/iam/security-credentials/**eksctl-myeks-nodegroup-ng1-NodeInstanceRole-1DC6Y2GRDAJHK
    {
      "Code" : "Success",
      "LastUpdated" : "2023-05-27T05:08:07Z",
      "Type" : "AWS-HMAC",
      "Expiration" : "2023-05-27T11:09:07Z"
    }**
    ## 출력된 정보는 AWS API를 사용할 수 있는 어느곳에서든지 Expiration 되기전까지 사용 가능
    
    # 파드에서 나오기
    **exit**
    ---
    ```
    
    - 워커 노드에 연결된 IAM 역할(정책)을 관리콘솔에서 확인해보자
    
    ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei18.png)

    
    https://sharing-for-us.tistory.com/39
    
3. awscli 파드에 kubeconfig (mapRoles) 정보 생성 및 확인
    
    ```bash
    # node 의 IAM Role ARN을 변수로 지정
    eksctl get iamidentitymapping --cluster $CLUSTER_NAME
    NODE_ROLE=<각자 자신의 노드 Role 이름>
    NODE_ROLE=eksctl-myeks-nodegroup-ng1-NodeInstanceRole-1DC6Y2GRDAJHK
    
    # awscli 파드에서 kubeconfig 정보 생성 및 확인 >> kubeconfig 에 정보가 기존 iam user와 차이점은?
    kubectl exec -it $APODNAME1 -- **aws eks update-kubeconfig** --name $CLUSTER_NAME --role-arn $NODE_ROLE
    kubectl exec -it $APODNAME1 -- cat /root/.kube/config | yh
    ...
      - **--role**
      - **eksctl-myeks-nodegroup-ng1-NodeInstanceRole-3GQR27I04PAJ**
    
    kubectl exec -it $APODNAME2 -- aws eks update-kubeconfig --name $CLUSTER_NAME --role-arn $NODE_ROLE
    kubectl exec -it $APODNAME2 -- cat /root/.kube/config | yh
    ```

</details>









<details><summary>신기능A deep dive into **simplified** Amazon **EKS access</summary>


management controls** - [Link](https://aws.amazon.com/blogs/containers/a-deep-dive-into-simplified-amazon-eks-access-management-controls/) & **Access Management** - [Link](https://catalog.workshops.aws/eks-immersionday/en-US/access-management)
    - EKS → 액세스 : IAM 액세스 항목
        
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei19.png)
        
    https://aws.amazon.com/blogs/containers/a-deep-dive-into-simplified-amazon-eks-access-management-controls/
    
    - EKS → 액세스 구성 모드 확인 : EKS API 및 ConfigMap ← **정책 중복 시 EKS API 우선되며 ConfigMap은 무시됨**
        
 ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei20.png)
        
    - 기본 정보 확인 : access policy, access entry, associated-access-policy - [Link](https://catalog.workshops.aws/eks-immersionday/en-US/access-management/2-managed-access-polices) [Docs](https://docs.aws.amazon.com/eks/latest/userguide/access-policies.html#access-policy-permissions) [User-facing_roles](https://kubernetes.io/docs/reference/access-authn-authz/rbac/#user-facing-roles)
        
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei121.png)
        https://docs.aws.amazon.com/eks/latest/userguide/access-policies.html#access-policy-permissions

```bash
        # EKS API 액세스모드로 변경
        **aws eks update-cluster-config --name $CLUSTER_NAME --access-config authenticationMode=API**
        
        # List all access policies : 클러스터 액세스 관리를 위해 지원되는 액세스 정책
        ## AmazonEKSClusterAdminPolicy – 클러스터 관리자
        ## AmazonEKSAdminPolicy – 관리자
        ## AmazonEKSEditPolicy – 편집
        ## AmazonEKSViewPolicy – 보기
        **aws eks list-access-policies** | jq
        
        # 맵핑 클러스터롤 정보 확인
        **kubectl get clusterroles -l 'kubernetes.io/bootstrapping=rbac-defaults' | grep -v 'system:'**
        NAME                                                                   CREATED AT
        admin                                                                  2024-04-06T05:58:32Z
        cluster-admin                                                          2024-04-06T05:58:32Z
        edit                                                                   2024-04-06T05:58:32Z
        view                                                                   2024-04-06T05:58:32Z
        
        **kubectl describe clusterroles admin
        kubectl describe clusterroles cluster-admin
        kubectl describe clusterroles edit
        kubectl describe clusterroles view**
        
        #
        **aws eks list-access-entries --cluster-name $CLUSTER_NAME | jq**
        {
          "accessEntries": [
            "arn:aws:iam::911283...:**role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole**-t4MD9Py4ZCyK",
            "**arn:aws:iam::911283...:user/admin**"
          ]
        }
        
        # 
        **aws eks list-associated-access-policies --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/admin | jq**
        {
          "**associatedAccessPolicies**": [
            {
              "policyArn": "arn:aws:eks::aws:cluster-access-policy/**AmazonEKSClusterAdminPolicy**",
              "**accessScope**": {
                "type": "**cluster**",
                "namespaces": []
              },
              "associatedAt": "2024-04-06T14:53:36.982000+09:00",
              "modifiedAt": "2024-04-06T14:53:36.982000+09:00"
            }
          ],
          "**clusterName**": "myeks",
          "**principalArn**": "arn:aws:iam::91128...:user/admin"
        }
        
        #
        **aws eks list-associated-access-policies --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole**-t4MD9Py4ZCyK **| jq**
        {
          "associatedAccessPolicies": [],
          "clusterName": "myeks",
          "principalArn": "arn:aws:iam::9112834...:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-t4MD9Py4ZCyK"
        }
        
        #
        aws eks describe-access-entry **--cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/admin | jq
        ...**
            "kubernetesGroups": [],
            ...
            "username": "arn:aws:iam::9112...:user/admin",
            "type": "**STANDARD**"
        **...**
        
        aws eks describe-access-entry **--cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole**-t4MD9Py4ZCyK **| jq**
        ...
            "kubernetesGroups": [
              "**system:nodes**"
            ...
            "username": "system:node:{{EC2PrivateDNSName}}",
            "type": "**EC2_LINUX**"
        ...
```
        
 - testuser 설정
        
```bash
        # testuser 의 access entry 생성
        **aws eks create-access-entry --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser**
        aws eks list-access-entries --cluster-name $CLUSTER_NAME | jq -r .accessEntries[]
        
        # testuser에 AmazonEKSClusterAdminPolicy 연동
        aws eks associate-access-policy --cluster-name $**CLUSTER_NAME** --principal-arn arn:aws:iam::$ACCOUNT_ID:user/**testuser \**
          --policy-arn arn:aws:eks::aws:cluster-access-policy/**AmazonEKSClusterAdminPolicy** --access-scope type=**cluster**
        
        #
        **aws eks list-associated-access-policies --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser | jq**
        aws eks describe-access-entry **--cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser | jq**
```
        
  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei22.png)


        
- [**myeks-bastion-2**]에서 **testuser**로 확인
        
        ```bash
        # testuser 정보 확인
        **aws sts get-caller-identity --query Arn**
        **kubectl whoami**
        
        # kubectl 시도
        **kubectl get node -v6
        kubectl api-resources -v5
        kubectl rbac-tool whoami
        kubectl auth can-i delete pods --all-namespaces**
        kubectl get cm -n kube-system aws-auth -o yaml | kubectl neat | yh
        eksctl get iamidentitymapping --cluster $CLUSTER_NAME
```
        
    - **Access entries and Kubernetes groups** - [Link](https://catalog.workshops.aws/eks-immersionday/en-US/access-management/3-kubernetes-groups)
        
```bash

        # 기존 testuser access entry 제거
        **aws eks delete-access-entry --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser**
        aws eks list-access-entries --cluster-name $CLUSTER_NAME | jq -r .accessEntries[]
        
        #
        **cat <<EoF> ~/pod-viewer-role.yaml**
        apiVersion: rbac.authorization.k8s.io/v1
        kind: **ClusterRole**
        metadata:
          name: pod-**viewer**-role
        rules:
        - apiGroups: [""]
          resources: ["pods"]
          **verbs: ["list", "get", "watch"]**
        **EoF**
        
        **cat <<EoF> ~/pod-admin-role.yaml**
        apiVersion: rbac.authorization.k8s.io/v1
        kind: **ClusterRole**
        metadata:
          name: pod-**admin**-role
        rules:
        - apiGroups: [""]
          resources: ["pods"]
          **verbs: ["*"]**
        **EoF**
        
        **kubectl apply -f ~/pod-viewer-role.yaml
        kubectl apply -f ~/pod-admin-role.yaml**
        
        #
        kubectl create **clusterrolebinding** viewer-role-binding --clusterrole=pod-viewer-role --group=**pod-viewer**
        kubectl create **clusterrolebinding** admin-role-binding --clusterrole=pod-admin-role --group=**pod-admin**
        
        #
        aws eks create-access-entry --cluster-name $**CLUSTER_NAME** --principal-arn arn:aws:iam::$ACCOUNT_ID:user/**testuser** --kubernetes-group **pod-viewer**
        ...
            "accessEntry": {
                "clusterName": "myeks",
                "principalArn": "arn:aws:iam::91128...:user/**testuser**",
                "**kubernetesGroups**": [
                    "**pod-viewer**"
                ],
        
        #
        aws eks list-associated-access-policies --cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser
        aws eks describe-access-entry **--cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser | jq**
        ...
            "**kubernetesGroups**": [
              "**pod-viewer**"
            ],
        ...
```
        
- [**myeks-bastion-2**]에서 **testuser**로 확인
        
```bash
        # testuser 정보 확인
        **aws sts get-caller-identity --query Arn**
        **kubectl whoami**
        
        # kubectl 시도
        **kubectl get pod -v6
        kubectl api-resources -v5
        kubectl auth can-i get pods --all-namespaces
        kubectl auth can-i delete pods --all-namespaces**
```
        
 - kubernetesGroups 업데이트 적용

```bash
        #
        aws eks **update**-access-entry --cluster-name $**CLUSTER_NAME** --principal-arn arn:aws:iam::$ACCOUNT_ID:user/**testuser** --kubernetes-group **pod-admin** | jq -r .accessEntry
        ...
          "kubernetesGroups": [
            "pod-admin"
        ...
        aws eks describe-access-entry **--cluster-name $CLUSTER_NAME --principal-arn arn:aws:iam::$ACCOUNT_ID:user/testuser | jq**
        ...
            "**kubernetesGroups**": [
              "**pod-admin**"
            ],
        ...
```
        
 - [**myeks-bastion-2**]에서 **testuser**로 확인
      
```bash
      # testuser 정보 확인
      **aws sts get-caller-identity --query Arn**
      **kubectl whoami**
      
      # kubectl 시도
      **kubectl get pod -v6
      kubectl api-resources -v5
      kubectl auth can-i get pods --all-namespaces
      kubectl auth can-i delete pods --all-namespaces**
```
        
    - **Migrate from ConfigMap to access entries** - [Link](https://catalog.workshops.aws/eks-immersionday/en-US/access-management/4-migrate) : 직접 실습 해보시기 바랍니다.




- **Migrate from ConfigMap to access entries** - [Link](https://catalog.workshops.aws/eks-immersionday/en-US/access-management/4-migrate) : 직접 실습 해보시기 바랍니다.
</details>





## EKS IRSA & Pod Identitty

[AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/42c950df-b0c6-41bf-9d45-2cc9e3a7ba76/AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf)

- **EC2 Instance Profile** : 사용하기 편하지만, 최소 권한 부여 원칙에 위배하며 보안상 권고하지 않음 - [링크](https://malwareanalysis.tistory.com/579) → **IRSA**를 쓰시라
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei23.png)
    
    https://sharing-for-us.tistory.com/40
    
```bash

    # 설정 예시 1 : eksctl 사용 시
    **eksctl create** cluster --name $CLUSTER_NAME ... **--external-dns-access --full-ecr-access --asg-access**
    
    # 설정 예시 2 : eksctl로 yaml 파일로 노드 생성 시
    **cat myeks.yaml | yh**
    ...
    managedNodeGroups:
    - amiFamily: AmazonLinux2
      iam:
        withAddonPolicies:
          albIngress: false
          appMesh: false
          appMeshPreview: false
          **autoScaler: true**
          awsLoadBalancerController: false
          **certManager: true**
          **cloudWatch: true**
          ebs: false
          efs: false
          **externalDNS: true**
          fsx: false
          **imageBuilder: true**
          xRay: false
    ...
    
    # 설정 예시 3 : 테라폼
    ...

```
[EKS 스터디 - 6주차 2편 - EKS pod가 IMDS API를 악용하는 시나리오](https://malwareanalysis.tistory.com/607)
    
<iframe width="720" height="405" src="https://www.youtube.com/embed/0aIfpNReeBc" title="EKS pod가 IMDS API를 악용하는 시나리오" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

`동작` : **k8s파드 → AWS 서비스 사용 시 ⇒ AWS STS/IAM ↔ IAM OIDC Identity Provider(EKS IdP) 인증/인가**


<details><summary>소개</summary>

`Service Account Token Volume Projection` : '**서비스 계정 토큰**'의 시크릿 기반 볼륨 대신 '**projected volume**' 사용

- **Service Account Token Volume Projection** - [링크](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#serviceaccount-token-volume-projection)
    - 서비스 계정 토큰을 이용해서 서비스와 서비스, 즉 파드(pod)와 파드(pod)의 호출에서 자격 증명으로 사용할 수 있을까요?
    - 불행히도 기본 서비스 계정 토큰으로는 사용하기에 부족함이 있습니다. 토큰을 사용하는 **대상**(audience), **유효 기간**(expiration) 등 토큰의 속성을 지정할 필요가 있기 때문입니다.
    - `Service Account Token Volume Projection` 기능을 사용하면 이러한 부족한 점들을 해결할 수 있습니다.
    
```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: nginx
    spec:
      containers:
      - image: nginx
        name: nginx
        volumeMounts:
        - mountPath: /var/run/secrets/tokens
          name: vault-token
      serviceAccountName: build-robot
      volumes:
      - name: vault-token
        projected:
          sources:
          - serviceAccountToken:
              path: vault-token
              expirationSeconds: **7200**
              audience: **vault**
```
    

- **Bound Service Account Token Volume 바인딩된 서비스 어카운트 토큰 볼륨** - [링크](https://kubernetes.io/ko/docs/reference/access-authn-authz/service-accounts-admin/#%EB%B0%94%EC%9D%B8%EB%94%A9%EB%90%9C-%EC%84%9C%EB%B9%84%EC%8A%A4-%EC%96%B4%EC%B9%B4%EC%9A%B4%ED%8A%B8-%ED%86%A0%ED%81%B0-%EB%B3%BC%EB%A5%A8) [영어](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/#bound-service-account-token-volume)
    - **FEATURE STATE:** `Kubernetes v1.22 [stable]`
    - [**서비스 어카운트 어드미션 컨트롤러**](https://kubernetes.io/ko/docs/reference/access-authn-authz/service-accounts-admin/#%EC%84%9C%EB%B9%84%EC%8A%A4%EC%96%B4%EC%B9%B4%EC%9A%B4%ED%8A%B8-serviceaccount-%EC%96%B4%EB%93%9C%EB%AF%B8%EC%85%98-%EC%BB%A8%ED%8A%B8%EB%A1%A4%EB%9F%AC)는 토큰 컨트롤러에서 생성한 만료되지 않은 서비스 계정 토큰에 **시크릿 기반 볼륨** 대신 다음과 같은 **프로젝티드 볼륨**을 추가한다.
    
```yaml
    - name: kube-api-access-<random-suffix>
      projected:
        defaultMode: 420 # 420은 rw- 로 소유자는 읽고쓰기 권한과 그룹내 사용자는 읽기만, 보통 0644는 소유자는 읽고쓰고실행 권한과 나머지는 읽고쓰기 권한
        sources:
          - serviceAccountToken:
              expirationSeconds: 3607
              path: token
          - configMap:
              items:
                - key: ca.crt
                  path: ca.crt
              name: kube-root-ca.crt
          - downwardAPI:
              items:
                - fieldRef:
                    apiVersion: v1
                    fieldPath: metadata.namespace
                  path: namespace
```
    
    프로젝티드 볼륨은 세 가지로 구성된다.
    
 1. `kube-apiserver`로부터 TokenRequest API를 통해 얻은 `서비스어카운트토큰(ServiceAccountToken)`. 서비스어카운트토큰은 기본적으로 1시간 뒤에, 또는 파드가 삭제될 때 만료된다. 서비스어카운트토큰은 파드에 연결되며 kube-apiserver를 위해 존재한다.
    2. kube-apiserver에 대한 연결을 확인하는 데 사용되는 CA 번들을 포함하는 `컨피그맵(ConfigMap)`.
    3. 파드의 네임스페이스를 참조하는 `DownwardA`

- **Configure a Pod to Use a Projected Volume for Storage** : 시크릿 컨피그맵 downwardAPI serviceAccountToken의 볼륨 마운트를 하나의 디렉터리에 통합 - [링크](https://kubernetes.io/docs/tasks/configure-pod-container/configure-projected-volume-storage/)
    - This page shows how to use a `[projected](https://kubernetes.io/docs/concepts/storage/volumes/#projected)` Volume to mount several existing volume sources into the same directory. Currently, `secret`, `configMap`, `downwardAPI`, and `serviceAccountToken` volumes can be projected.
    - **Note:** `serviceAccountToken` **is not a volume type.**
    
    ```yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: test-projected-volume
    spec:
      containers:
      - name: test-projected-volume
        image: busybox:1.28
        args:
        - sleep
        - "86400"
        volumeMounts:
        - name: all-in-one
          mountPath: "/projected-volume"
          readOnly: true
      volumes:
      - name: all-in-one
        **projected**:
          sources:
          - secret:
              name: user
          - secret:
              name: pass
    ```
    
```bash
    # Create the Secrets:
    ## Create files containing the username and password:
    echo -n "admin" > ./username.txt
    echo -n "1f2d1e2e67df" > ./password.txt
    
    ## Package these files into secrets:
    kubectl create secret generic user --from-file=./username.txt
    kubectl create secret generic pass --from-file=./password.txt
    
    # 파드 생성
    kubectl apply -f https://k8s.io/examples/pods/storage/projected.yaml
    
    # 파드 확인
    kubectl get pod test-projected-volume -o yaml | kubectl neat | yh
    ...
    volumes:
      - name: all-in-one
        **projected**:
          defaultMode: 420
          sources:
          - secret:
              name: user
          - secret:
              name: pass
      - name: kube-api-access-n6n9v
        **projected**:
          defaultMode: 420
          sources:
          - serviceAccountToken:
              expirationSeconds: 3607
              path: token
          - configMap:
              items:
              - key: ca.crt
                path: ca.crt
              name: kube-root-ca.crt
          - downwardAPI:
              items:
              - fieldRef:
                  apiVersion: v1
                  fieldPath: metadata.namespace
                path: namespace
    
    # 시크릿 확인
kubectl exec -it test-projected-volume -- ls /projected-volume/
    ***password.txt  username.txt***
    
    kubectl exec -it test-projected-volume -- cat /projected-volume/username.txt ;echo
    ***admin***
    
    kubectl exec -it test-projected-volume -- cat /projected-volume/password.txt ;echo
    ***1f2d1e2e67df***
    
    # 삭제
    kubectl delete pod test-projected-volume && kubectl delete secret user pass
```
    

`k8s api 접근 단계`

- **AuthN** → **AuthZ** → **Admisstion Control** 권한이 있는 사용자에 한해서 관리자(Admin)가 특정 행동을 제한(validate) 혹은 변경(mutate) - [링크](https://coffeewhale.com/kubernetes/admission-control/2021/04/28/opa1/) [Slack](https://slack.engineering/simple-kubernetes-webhook/)
- AuthN & AuthZ - **MutatingWebhook** - Object schema validation - **ValidatingWebhook** → etcd

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei24.png)

https://kubernetes.io/blog/2019/03/21/a-guide-to-kubernetes-admission-controllers/

- Admission Control도 Webhook으로 사용자에게 API가 열려있고, 사용자는 자신만의 Admission Controller를 구현할 수 있으며,
이를 **Dynamic** Admission Controller라고 부르고, 크게 **MutatingWebhook** 과 **ValidatingWebhook** 로 나뉩니다.
- `MutatingWebhook`은 사용자가 요청한 request에 대해서 관리자가 임의로 값을 변경하는 작업입니다.
- `ValidatingWebhook`은 사용자가 요청한 request에 대해서 관리자기 허용을 막는 작업입니다.

```bash

kubectl get **validatingwebhook**configurations
kubectl get **mutatingwebhook**configurations

```

`JWT` : **Bearer type - JWT(JSON Web Token)** X.509 Certificate의 **lightweight JSON** 버전

- Bearer type 경우, 서버에서 지정한 어떠한 문자열도 입력할 수 있습니다. 하지만 굉장히 허술한 느낌을 받습니다.
- 이를 보완하고자 쿠버네티스에서 **Bearer 토큰**을 전송할 때 주로 **JWT** (JSON Web Token) 토큰을 사용합니다.
- **JWT**는 X.509 Certificate와 마찬가지로 private key를 이용하여 토큰을 서명하고 public key를 이용하여 서명된 메세지를 검증합니다.
- 이러한 메커니즘을 통해 해당 토큰이 쿠버네티스를 통해 생성된 valid한 토큰임을 인증할 수 있습니다.
- X.509 Certificate의 **lightweight JSON** 버전이라고 생각하면 편리합니다.
- **jwt**는 **JSON** 형태로 **토큰** 형식을 정의한 **스펙**입니다. jwt는 쿠버네티스에서 뿐만 아니라 다양한 웹 사이트에서 인증, 권한 허가, 세션관리 등의 목적으로 사용합니다.
    - **Header**: 토큰 형식와 암호화 알고리즘을 선언합니다.
    - **Payload**: 전송하려는 데이터를 JSON 형식으로 기입합니다.
    - **Signature**: Header와 Payload의 변조 가능성을 검증합니다.
- 각 파트는 base64 URL 인코딩이 되어서 `.`으로 합쳐지게 됩니다.

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei25.png)

https://research.securitum.com/jwt-json-web-token-security/

`OIDC` : 사용자를 **인증**해 사용자에게 **액세스 권한**을 부여할 수 있게 해주는 프로토콜 ⇒ [커피고래]님 블로그 OpenID Connect - [링크](https://coffeewhale.com/kubernetes/authentication/oidc/2020/05/04/auth03/)

- **OAuth 2.0** : 권한허가 처리 프로토콜, 다른 서비스에 접근할 수 있는 권한을 획득하거나 반대로 다른 서비스에게 권한을 부여할 수 있음 - [생활코딩](https://www.youtube.com/watch?v=hm2r6LtUbk8&list=PLuHgQVnccGMA4guyznDlykFJh28_R08Q-&ab_channel=%EC%83%9D%ED%99%9C%EC%BD%94%EB%94%A9)
    - **위임 권한 부여** Delegated **Authorization**, 사용자 인증 보다는 제한된 사람에게(혹은 시스템) 제한된 권한을 부여하는가, 예) 페이스북 posting 권한
    - **Access Token** : 발급처(OAuth 2.0), 서버의 리소스 접근 권한
- **OpenID** : 비영리기관인 OpenID Foundation에서 추진하는 개방형 표준 및 분산 **인증 Authentication** 프로토콜, 사용자 인증 및 사용자 정보 제공(id token) - [링크](https://openid.net/)
    - **ID Token** : 발급처(OpenID Connect), 유저 프로필 정보 획득
- **OIDC** OpenID Connect = OpenID **인증** + OAuth2.0 **인가**, JSON 포맷을 이용한 RESful API 형식으로 인증 - [링크](https://hudi.blog/open-id/)
    - `iss`: 토큰 발행자
    - `sub`: 사용자를 구분하기 위한 유니크한 구분자
    - `email`: 사용자의 이메일
    - `iat`: 토큰이 발행되는 시간을 Unix time으로 표기한 것
    - `exp`: 토큰이 만료되는 시간을 Unix time으로 표기한 것
    - `aud`: ID Token이 어떤 Client를 위해 발급된 것인지.
- **IdP** Open Identify Provider : 구글, 카카오와 같이 OpenID 서비스를 제공하는 신원 제공자.
    - OpenID Connect에서 IdP의 역할을 OAuth가 수행 - [링크](https://coffeewhale.com/kubernetes/authentication/oidc/2020/05/04/auth03/)
- **RP** Relying Party : 사용자를 인증하기 위해 IdP에 의존하는 주체




---

- IRSA 소개 : 파드가 특정 IAM 역할로 Assume 할때 토큰을 AWS에 전송하고, AWS는 토큰과 EKS IdP를 통해 해당 IAM 역할을 사용할 수 있는지 검증



![https://cafe.naver.com/kubeops](/Images/eks/eks_sei26.png)

https://github.com/awskrug/security-group/blob/main/files/
AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf

[19:23초 부터 시작~](https://youtu.be/wgH9xL_48vM?t=1163)

19:23초 부터 시작~

![https://youtu.be/iyMcOpXRVWk?si=6uvHWIKH7kwk_EEq&t=1402](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/90b704a4-893c-43a4-bde0-55d93f110f94/Untitled.png)

<iframe width="673" height="378" src="https://www.youtube.com/embed/wgH9xL_48vM" title="EKS 환경을 더 효율적으로, 더 안전하게 - 신은수 시큐리티 스페셜리스트 솔루션즈 아키텍트, AWS :: AWS Summit Korea 2022" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

[EKS에서 쿠버네티스 포드의 IAM 권한 제어하기: Pod Identity Webhook](https://tech.devsisters.com/posts/pod-iam-role/)

- The IAM service uses these public keys to validate the token. The workflow is as follows - **JWT**(JSON Web Token), **JWKS**(JSON Web Key Set)

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei27.png)



https://aws.amazon.com/ko/blogs/containers/diving-into-iam-roles-for-service-accounts/

  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei28.png)

[https://awskoreamarketingasset.s3.amazonaws.com/2022 Summit/pdf/T10S1_EKS 환경을 더 효율적으로 더 안전하게.pdf](https://awskoreamarketingasset.s3.amazonaws.com/2022%20Summit/pdf/T10S1_EKS%20%ED%99%98%EA%B2%BD%EC%9D%84%20%EB%8D%94%20%ED%9A%A8%EC%9C%A8%EC%A0%81%EC%9C%BC%EB%A1%9C%20%EB%8D%94%20%EC%95%88%EC%A0%84%ED%95%98%EA%B2%8C.pdf)

- AWS SDK는 **AWS_ROLE_ARN** 및 **AWS_WEB_IDENTITY_TOKEN_FILE** 이름의 환경변수를 읽어들여 Web Identity 토큰으로 **AssumeRoleWithWebIdentify**를 호출함으로써 Assume Role을 시도하여 임시 자격 증명을 획득하고, 특정 IAM Role 역할을 사용할 수 있게 됩니다.
- 이때 Assume Role 동작을 위한 인증은 AWS가 아닌 외부 Web IdP(**EKS IdP**)에 위임하여 처리합니다.

  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei29.png)
https://tech.devsisters.com/posts/pod-iam-role/

- EKS IdP를 identity provider로 등록하고, 파드가 Web Identify 토큰을 통해 IAM 역할을 Assume 할 수 있게 Trust Relationship 설정이 필요합니다.

https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=AssumeRoleWithWebIdentity


  ![https://cafe.naver.com/kubeops](/Images/eks/eks_sei30.png)
    https://learnk8s.io/authentication-kubernetes

</details>




<details><summary>실습1</summary>

```bash
# 파드1 생성
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: eks-iam-test1
spec:
  containers:
    - name: my-aws-cli
      image: amazon/aws-cli:latest
      args: ['s3', 'ls']
  restartPolicy: Never
  **automountServiceAccountToken: false**
  terminationGracePeriodSeconds: 0
EOF

# 확인
kubectl get pod
kubectl describe pod

# 로그 확인
kubectl logs eks-iam-test1

# 파드1 삭제
kubectl delete pod eks-iam-test1
```

- CloudTrail 이벤트 ListBuckets 확인 → 기록 표시까지 약간의 시간 필요

https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=ListBuckets



열 편집 : 체크(오류 코드, 이벤트 유형), 체크해제(리소스 유형, 리소스 이름)

```bash
{
...
  "**userIdentity**": {
    "type": "AssumedRole",
    "principalId": "xxxx",
    "arn": "arn:aws:sts::111122223333:assumed-role/eksctl-eks-oidc-demo-nodegroup-ng-NodeInstanceRole-xxxx/xxxx",
    "accountId": "111122223333",
    " ": "AKIAIOSFODNN7EXAMPLE",
    "sessionContext": {
      "sessionIssuer": {
        "type": "Role",
        "principalId": "xxxx",
        "arn": "arn:aws:iam::xxxx:role/eksctl-eks-oidc-demo-nodegroup-ng-NodeInstanceRole-xxxx",
        "accountId": "111122223333",
        "userName": "eksctl-eks-oidc-demo-nodegroup-ng-NodeInstanceRole-xxxx"
      },
      "webIdFederationData": {},
      "attributes": {
        "creationDate": "2021-12-04T14:54:49Z",
        "mfaAuthenticated": "false"
      },
      "ec2RoleDelivery": "2.0"
    }
  },
  "eventTime": "2021-12-04T15:09:20Z",
  "eventSource": "s3.amazonaws.com",
  "eventName": "ListBuckets",
  "awsRegion": "us-east-2",
  "sourceIPAddress": "192.0.2.1",
  "userAgent": "[aws-cli/2.4.5 Python/3.8.8 Linux/5.4.156-83.273.amzn2.x86_64 docker/x86_64.amzn.2 prompt/off command/s3.ls]",
  "errorCode": "AccessDenied",
  "errorMessage": "Access Denied",
  "requestParameters": {
    "Host": "s3.us-east-2.amazonaws.com"
  },
...
}
```


</details>



<details><summary>실습2</summary>

- Kubernetes Pods are given an identity through a Kubernetes concept called a [Kubernetes Service Account](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/).
- When a **Service Account** is created, a **JWT token** is automatically created as a **Kubernetes Secret**.
- This Secret can then be mounted into Pods and used by that Service Account to authenticate to the Kubernetes API Server.

```bash
# 파드2 생성
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: **eks-iam-test2**
spec:
  containers:
    - name: my-aws-cli
      image: amazon/aws-cli:latest
      command: ['sleep', '36000']
  restartPolicy: Never
  terminationGracePeriodSeconds: 0
EOF

# 확인
kubectl get pod
kubectl describe pod
kubectl get pod eks-iam-test2 -o yaml | kubectl neat | yh
kubectl exec -it eks-iam-test2 -- ls /var/run/secrets/kubernetes.io/serviceaccount
kubectl exec -it eks-iam-test2 -- cat /var/run/secrets/kubernetes.io/serviceaccount/token ;echo

# aws 서비스 사용 시도
kubectl exec -it eks-iam-test2 -- **aws s3 ls**

# 서비스 어카운트 토큰 확인
SA_TOKEN=$(kubectl exec -it eks-iam-test2 -- cat /var/run/secrets/kubernetes.io/serviceaccount/token)
echo $SA_TOKEN

# jwt 혹은 아래 JWT 웹 사이트 이용 https://jwt.io/
jwt decode $SA_TOKEN --json --iso8601
...
~~~~
#헤더
{
  "alg": "RS256",
  "kid": "1a8fcaee12b3a8f191327b5e9b997487ae93baab"
}

# 페이로드 : OAuth2에서 쓰이는 aud, exp 속성 확인! > projectedServiceAccountToken 기능으로 토큰에 audience,exp 항목을 덧붙힘
## iss 속성 : EKS Open**ID** Connect **P**rovider(EKS IdP) 주소 > 이 EKS IdP를 통해 쿠버네티스가 발급한 토큰이 유요한지 검증
{
  "aud": [
    "**https://kubernetes.default.svc**"  # 해당 주소는 k8s api의 ClusterIP 서비스 주소 도메인명, kubectl get svc kubernetes
  ],
  "exp": 1716619848,
  "iat": 1685083848,
  "iss": "**https://oidc.eks.ap-northeast-2.amazonaws.com/id/F6A7523462E8E6CDADEE5D41DF2E71F6**",
  "kubernetes.io": {
    "namespace": "default",
    "**pod**": {
      "name": "**eks-iam-test2**",
      "uid": "10dcccc8-a16c-4fc7-9663-13c9448e107a"
    },
    "**serviceaccount**": {
      "name": "**default**",
      "uid": "acb6c60d-0c5f-4583-b83b-1b629b0bdd87"
    },
    "warnafter": 1685087455
  },
  "nbf": 1685083848,
  "sub": "**system:serviceaccount:default:default**"
}

# 파드2 삭제
kubectl delete pod eks-iam-test2
```

- As you can see in the payload of this **JWT**, the **issuer** is an OIDC Provider. The audience for the token is `https://kubernetes.default.svc`. This is the address inside a cluster used to reach the Kubernetes API Server.
- This compliant OIDC token now gives us a foundation to build upon to find a token that can be used to authenticate to AWS APIs. However, we will need an additional component to inject a **second token** for use with AWS APIs into our Kubernetes Pods. Kubernetes supports **validating** and **mutating** webhooks, and AWS has created an [identity webhook](https://github.com/aws/amazon-eks-pod-identity-webhook/) that comes **preinstalled** in an EKS cluster. This **webhook** **listens** to create **pod API calls** and can inject an **additional** **Token** into our pods. This webhook can also be installed into self-managed Kubernetes clusters on AWS using [this guide](https://github.com/aws/amazon-eks-pod-identity-webhook/blob/master/SELF_HOSTED_SETUP.md).


</details>






<details><summary>실습3</summary>

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei31.png)
https://dev.to/aws-builders/auditing-aws-eks-pod-permissions-4637

- For the **webhook** to inject a new **Token** into our Pod, we are going to create a new Kubernetes Service Account, **annotate** our **Service Account** with an AWS IAM role ARN, and then reference this new Kubernetes Service Account in a Kubernetes Pod. The eksctl tool can be used to automate a few steps for us, but all of these steps can also be done manually.
- The `eksctl create iamserviceaccount` command creates:
    1. A Kubernetes **Service Account**
    2. An **IAM role** with the specified IAM policy
    3. A **trust policy** on that IAM role
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei32.png)
    
    https://sharing-for-us.tistory.com/40
    
- Finally, it will also annotate th**e Kubernetes Service Account** with the **IAM Role Arn** created.

```bash
# Create an iamserviceaccount - AWS IAM role bound to a Kubernetes service account
eksctl create **iamserviceaccount** \
  --name **my-sa** \
  --namespace **default** \
  --cluster $CLUSTER_NAME \
  --approve \
  --attach-policy-arn $(aws iam list-policies --query 'Policies[?PolicyName==`AmazonS3ReadOnlyAccess`].Arn' --output text)

# 확인 >> 웹 관리 콘솔에서 CloudFormation Stack >> IAM Role 확인
# aws-load-balancer-controller IRSA는 어떤 동작을 수행할 것 인지 생각해보자!
eksctl get iamserviceaccount --cluster $CLUSTER_NAME

# Inspecting the newly created Kubernetes Service Account, we can see the role we want it to assume in our pod.
**kubectl get sa**
**kubectl describe sa my-sa**
Name:                my-sa
Namespace:           default
Labels:              app.kubernetes.io/managed-by=eksctl
Annotations:         **eks.amazonaws.com/role-arn: arn:aws:iam::911283464785:role/eksctl-myeks-addon-iamserviceaccount-default-Role1-1MJUYW59O6QGH**
Image pull secrets:  <none>
Mountable secrets:   <none>
Tokens:              <none>
Events:              <none>
```

- Let’s see how this IAM role looks within the AWS Management Console. Navigate to IAM and then IAM Roles and search for the role. You will see the Annotations field when you describe your service account. ⇒ **IAM Role 확인**
- Select the **Trust relationships** tab and select **Edit trust relationship** to view the policy document.
- You can see that this policy is allowing an identity `system:serviceaccount:default:my-sa` to assume the role using `sts:AssumeRoleWithWebIdentity` action. The principal for this policy is an OIDC provider.

```bash
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "**Federated**": "arn:aws:iam::911283464785:oidc-provider/oidc.eks.ap-northeast-2.amazonaws.com/id/F6A7523462E8E6CDADEE5D41DF2E71F6"
            },
            "Action": "**sts:AssumeRoleWithWebIdentity**",
            "Condition": {
                "StringEquals": {
                    "oidc.eks.ap-northeast-2.amazonaws.com/id/F6A7523462E8E6CDADEE5D41DF2E71F6:sub": "**system:serviceaccount:default:my-sa**",
                    "oidc.eks.ap-northeast-2.amazonaws.com/id/F6A7523462E8E6CDADEE5D41DF2E71F6:aud": "sts.amazonaws.com"
                }
            }
        }
    ]
}
```

- Now let’s see what happens when we use this new Service Account within a Kubernetes Pod : 신규 파드 만들자!

```bash
# 파드3번 생성
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: eks-iam-test3
spec:
  **serviceAccountName: my-sa**
  containers:
    - name: my-aws-cli
      image: amazon/aws-cli:latest
      command: ['sleep', '36000']
  restartPolicy: Never
  terminationGracePeriodSeconds: 0
EOF

# 해당 SA를 파드가 사용 시 mutatingwebhook으로 Env,Volume 추가함
kubectl get mutatingwebhookconfigurations pod-identity-webhook -o yaml | kubectl neat | yh

**# 파드 생성 yaml에 없던 내용이 추가됨!!!!!**
# **Pod Identity Webhook**은 **mutating** webhook을 통해 아래 **Env 내용**과 **1개의 볼륨**을 추가함
kubectl get pod eks-iam-test3
**kubectl get pod eks-iam-test3 -o yaml | kubectl neat | yh**
...
    volumeMounts: 
    - mountPath: /var/run/secrets/eks.amazonaws.com/serviceaccount
      name: aws-iam-token
      readOnly: true
  ...
  volumes: 
  - name: aws-iam-token
    projected: 
      sources: 
      - serviceAccountToken: 
          audience: sts.amazonaws.com
          expirationSeconds: 86400
          path: token
...

**kubectl** exec -it eks-iam-test3 -- ls /var/run/secrets/eks.amazonaws.com/serviceaccount
token

**kubectl** exec -it eks-iam-test3 -- cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token ; echo
...

**kubectl describe pod eks-iam-test3**
...
**Environment**:
      AWS_STS_REGIONAL_ENDPOINTS:   regional
      AWS_DEFAULT_REGION:           ap-northeast-2
      AWS_REGION:                   ap-northeast-2
      AWS_ROLE_ARN:                 arn:aws:iam::911283464785:role/eksctl-myeks-addon-iamserviceaccount-default-Role1-GE2DZKJYWCEN
      AWS_WEB_IDENTITY_TOKEN_FILE:  /var/run/secrets/eks.amazonaws.com/serviceaccount/token
    Mounts:
      /var/run/secrets/eks.amazonaws.com/serviceaccount from aws-iam-token (ro)
      /var/run/secrets/kubernetes.io/serviceaccount from kube-api-access-69rh8 (ro)
...
**Volumes:**
  **aws-iam-token**:
    Type:                    **Projected** (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  86400
  kube-api-access-sn467:
    Type:                    Projected (a volume that contains injected data from multiple sources)
    TokenExpirationSeconds:  3607
    ConfigMapName:           kube-root-ca.crt
    ConfigMapOptional:       <nil>
    DownwardAPI:             true
...

# 파드에서 aws cli 사용 확인
eksctl get iamserviceaccount --cluster $CLUSTER_NAME
**kubectl exec -it eks-iam-test3 -- aws sts get-caller-identity --query Arn**
"arn:aws:sts::911283464785:assumed-role/eksctl-myeks-addon-iamserviceaccount-default-Role1-GE2DZKJYWCEN/botocore-session-1685179271"

# 되는 것고 안되는 것은 왜그런가?
kubectl exec -it eks-iam-test3 -- **aws s3 ls**
kubectl exec -it eks-iam-test3 -- **aws ec2 describe-instances --region ap-northeast-2**
kubectl exec -it eks-iam-test3 -- **aws ec2 describe-vpcs --region ap-northeast-2**
```

https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=AssumeRoleWithWebIdentity

- If we inspect the Pod using Kubectl and jq, we can see there are now **two volumes** mounted into our Pod.
The second one has been mounted via that [mutating webhook](https://github.com/aws/amazon-eks-pod-identity-webhook).
The `aws-iam-token` is still being generated by the Kubernetes API Server, but with a new OIDC JWT audience.

```bash
# 파드에 볼륨 마운트 2개 확인
**kubectl get pod eks-iam-test3 -o json | jq -r '.spec.containers | .[].volumeMounts'**
[
  {
    "mountPath": "/var/run/secrets/kubernetes.io/serviceaccount",
    "name": "kube-api-access-sn467",
    "readOnly": true
  },
  {
    "mountPath": "/var/run/secrets/eks.amazonaws.com/serviceaccount",
    "name": "aws-iam-token",
    "readOnly": true
  }
]

# aws-iam-token 볼륨 정보 확인 : JWT 토큰이 담겨져있고, exp, aud 속성이 추가되어 있음
**kubectl get pod eks-iam-test3 -o json | jq -r '.spec.volumes[] | select(.name=="aws-iam-token")'**
{
  "name": "**aws-iam-token**",
  "**projected**": {
    "defaultMode": 420,
    "sources": [
      {
        "**serviceAccountToken**": {
          "**audience**": "sts.amazonaws.com",
          "**expirationSeconds**": 86400,
          "path": "**token**"
        }
      }
    ]
  }
}

# api 리소스 확인
**kubectl api-resources |grep hook**
mutatingwebhookconfigurations                  admissionregistration.k8s.io/v1        false        MutatingWebhookConfiguration
validatingwebhookconfigurations                admissionregistration.k8s.io/v1        false        ValidatingWebhookConfiguration

#
**kubectl explain mutatingwebhookconfigurations**

#
**kubectl get MutatingWebhookConfiguration**
NAME                            WEBHOOKS   AGE
pod-identity-webhook            1          147m
vpc-resource-mutating-webhook   1          147m

# pod-identity-webhook 확인
**kubectl** describe MutatingWebhookConfiguration **pod-identity-webhook** 
**kubectl get MutatingWebhookConfiguration pod-identity-webhook -o yaml | yh**
```

- If we exec into the running **Pod** and **inspect** this **token**, we can see that it looks slightly different from the previous SA Token.
- You can see that the intended audience for this token is now `sts.amazonaws.com`, the **issuer** who has created and signed this token is still our OIDC provider, and finally, the expiration of the token is much shorter at 24 hours. We can modify the expiration duration for the service account using `eks.amazonaws.com/token-expiration` annotation in our Pod definition or Service Account definition.
- The **mutating webhook** does more than just mount an additional token into the Pod. The mutating webhook also **injects** environment variables.

https://jwt.io/

```bash
# AWS_WEB_IDENTITY_TOKEN_FILE 확인
IAM_TOKEN=$(kubectl exec -it eks-iam-test3 -- cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token)
echo $IAM_TOKEN

# JWT 웹 확인 
{
  "aud": [
    "sts.amazonaws.com"
  ],
  "exp": 1685175662,
  "iat": 1685089262,
  "iss": "https://oidc.eks.ap-northeast-2.amazonaws.com/id/F6A7523462E8E6CDADEE5D41DF2E71F6",
  "kubernetes.io": {
    "namespace": "default",
    "pod": {
      "name": "eks-iam-test3",
      "uid": "73f66936-4d66-477a-b32b-853f7a1c22d9"
    },
    "**serviceaccount**": {
      "name": "**my-sa**",
      "uid": "3b31aa85-2718-45ed-8c1c-75ed012c1a68"
    }
  },
  "nbf": 1685089262,
  "sub": "**system:serviceaccount:default:my-sa**"
}

# env 변수 확인
**kubectl get pod eks-iam-test3 -o json | jq -r '.spec.containers | .[].env'**
[
  {
    "name": "AWS_STS_REGIONAL_ENDPOINTS",
    "value": "regional"
  },
  {
    "name": "AWS_DEFAULT_REGION",
    "value": "ap-northeast-2"
  },
  {
    "name": "AWS_REGION",
    "value": "ap-northeast-2"
  },
  {
    "name": "AWS_ROLE_ARN",
    "value": "arn:aws:iam::911283464785:role/eksctl-myeks-addon-iamserviceaccount-default-Role1-1MJUYW59O6QGH"
  },
  {
    "name": "AWS_WEB_IDENTITY_TOKEN_FILE",
    "value": "/var/run/secrets/eks.amazonaws.com/serviceaccount/token"
  }
]
```

- Now that our workload has a **token** it can use to attempt to **authenticate** with IAM, the next part is getting AWS **IAM** to trust these tokens. AWS IAM supports [federated identities using OIDC identity providers](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html). This feature allows **IAM** to authenticate AWS API calls with supported identity providers after receiving a **valid OIDC JWT**. This token can then be passed to AWS STS `AssumeRoleWithWebIdentity` API operation to get temporary IAM credentials.
- The **OIDC JWT token** we have in our Kubernetes workload is cryptographically signed, and IAM should trust and validate these tokens before the AWS STS `AssumeRoleWithWebIdentity` API operation can send the temporary credentials. As part of the [Service Account Issuer Discovery](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#service-account-issuer-discovery) feature of Kubernetes, EKS is hosting a **public OpenID provider c**onfiguration document (Discovery endpoint) and the public keys to validate the token signature (**JSON Web Key Sets** – **JWKS**) at `https://OIDC_PROVIDER_URL/.well-known/openid-configuration`.

```bash
# Let’s take a look at this endpoint. We can use the aws eks describe-cluster command to get the OIDC Provider URL.
IDP=$(aws eks describe-cluster --name myeks --query cluster.identity.oidc.issuer --output text)

# Reach the Discovery Endpoint
**curl -s $IDP/.well-known/openid-configuration | jq -r '.'**

# In the above output, you can see the **jwks (JSON Web Key set)** field, which contains the set of keys containing the public keys used to verify JWT (JSON Web Token). 
# Refer to the documentation to get details about the JWKS properties.
**curl -s $IDP/keys | jq -r '.'**
```

https://ap-northeast-2.console.aws.amazon.com/cloudtrail/home?region=ap-northeast-2#/events?EventName=AssumeRoleWithWebIdentity

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei33.png)

- **IRSA를 가장 취약하게 사용하는 방법** : 정보 탈취 시 키/토큰 발급 약용 가능 - [링크](https://medium.com/@7424069/aws-how-to-use-eks-irsa-in-the-most-vulnerable-way-5d8f4c8d6d20)
- **AWS는 JWT 토큰의 유효성만 확인** 하지만 **토큰 파일과 서비스 계정에 지정된 실제 역할 간의 일관성을 보장하지는 않음 → Condition 잘못 설정 시, 토큰과 역할 ARN만 있다면 동일 토큰으로 다른 역할을 맡을 수 있음**

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei33.png))
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei35.png)

https://github.com/awskrug/security-group/blob/main/files/AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/0e83164f-390f-4a23-9c55-dcafb49c9caa/Untitled.png)

![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/6318c51d-3647-4715-8c42-144385e20065/Untitled.png)

- IAM Channelge Level 6 문제
    - https://bigiamchallenge.com/challenge/1
    - https://lonelynova.tistory.com/375
    - https://malwareanalysis.tistory.com/645

```bash
# AWS_WEB_IDENTITY_TOKEN_FILE 토큰 값 변수 지정
IAM_TOKEN=$(kubectl exec -it eks-iam-test3 -- cat /var/run/secrets/eks.amazonaws.com/serviceaccount/token)
echo $IAM_TOKEN

# ROLE ARN 확인 후 변수 직접 지정
eksctl get iamserviceaccount --cluster $CLUSTER_NAME
ROLE_ARN=<각자 자신의 ROLE ARN>
ROLE_ARN=*arn:aws:iam::911283464785:role/eksctl-myeks-addon-iamserviceaccount-default-Role1-1W8J3Q0GAMA6U*

# assume-role-with-web-identity STS 임시자격증명 발급 요청
**aws sts assume-role-with-web-identity** --role-arn $ROLE_ARN --role-session-name **mykey** --web-identity-token $IAM_TOKEN | jq
{
  "Credentials": {
    " ": "   ",
    " ": "IvuD2BEt/TtScyv6uq3U5mF3RStuxya5gHydlz2Z",
    "Expiration": "2023-06-03T09:44:03+00:00"
  },
  "SubjectFromWebIdentityToken": "system:serviceaccount:default:my-sa",
  "AssumedRoleUser": {
    "AssumedRoleId": "AROA5ILF2FJI7UWTLJWKW:mykey",
    "Arn": "arn:aws:sts::911283464785:assumed-role/eksctl-myeks-addon-iamserviceaccount-default-Role1-1W8J3Q0GAMA6U/mykey"
  },
  "Provider": "arn:aws:iam::911283464785:oidc-provider/oidc.eks.ap-northeast-2.amazonaws.com/id/8883A42CB049E2FA9B642086E7021450",
  "Audience": "sts.amazonaws.com"
}
```

- I hope you have enjoyed this journey and now have a good understanding of what really happens behind the scenes when we try to access AWS services from Pods. We have seen how AWS credentials will default to the EC2 instance profile if the workload cannot find any credentials and how Kubernetes Service Accounts and Service Account tokens can be used to give Pods Identities. Finally, we have seen how IAM can use an external OIDC identity provider and validate tokens to give temporary IAM credentials.
- **실습 확인 후 파드 삭제 및 IRSA 제거**

```bash

#
kubectl delete pod eks-iam-test3
eksctl delete iamserviceaccount --cluster $CLUSTER_NAME --name my-sa --namespace default
eksctl get iamserviceaccount --cluster $CLUSTER_NAME
kubectl get sa

```


</details>


<details><summary>신기능  EKS Pod Identity </summary>


![https://cafe.naver.com/kubeops](/Images/eks/eks_sei36.png)
https://github.com/awskrug/security-group/blob/main/files/AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf

- Amazon EKS **Pod Identity**: a new way for applications on EKS to obtain IAM credentials - [Link](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/)
- Amazon EKS **Pod Identity** simplifies IAM permissions for applications on Amazon EKS clusters - [Link](https://aws.amazon.com/blogs/aws/amazon-eks-pod-identity-simplifies-iam-permissions-for-applications-on-amazon-eks-clusters/)
- [EKS Workshop] EKS **Pod Identity** - [Link](https://www.eksworkshop.com/docs/security/amazon-eks-pod-identity/)

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei37.png)

https://youtu.be/iyMcOpXRVWk?si=fFiMV9c7E0pg8Img&t=1409

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei38.png)

https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/

![https://cafe.naver.com/kubeops](/Images/eks/eks_sei39.png)

https://github.com/awskrug/security-group/blob/main/files/AWSKRUG_2024_02_EKS_ROLE_MANAGEMENT.pdf

- eks-pod-identity-agent 설치
    
```bash
    #
    ADDON=eks-pod-identity-agent
    **aws eks describe-addon-versions \
        --addon-name $**ADDON **\
        --kubernetes-version 1.28 \
        --query "addons[].addonVersions[].[addonVersion, compatibilities[].defaultVersion]" \
        --output text**
    v1.2.0-eksbuild.1
    True
    v1.1.0-eksbuild.1
    False
    v1.0.0-eksbuild.1
    False
    
    # 모니터링
    watch -d kubectl get pod -A
    
    # 설치
    aws eks **create-addon** --cluster-name $CLUSTER_NAME --addon-name **eks-pod-identity-agent
    혹은**
    **eksctl create addon** --cluster $CLUSTER_NAME --name eks-pod-identity-agent *--version 1.2.0*
    
    # 확인
    eksctl get addon --cluster $CLUSTER_NAME
    kubectl -n kube-system get daemonset eks-pod-identity-agent
    kubectl -n kube-system get pods -l app.kubernetes.io/name=eks-pod-identity-agent
    **kubectl get ds -n kube-system eks-pod-identity-agent -o yaml | kubectl neat | yh**
    ...
          containers: 
          - **args**: 
            - --port
            - "**80**"
            - --cluster-name
            - myeks
            - --probe-port
            - "**2703**"
            command: 
            - /go-runner
            - /eks-pod-identity-agent
            - server
          ....
          **ports**: 
            - containerPort: 80
              name: proxy
              protocol: TCP
            - containerPort: 2703
              name: probes-port
              protocol: TCP
          ...
    ****        **securityContext**: 
              capabilities: 
                add: 
                - **CAP_NET_BIND_SERVICE**
          ...
          **hostNetwork: true**
    ...
    
    # 네트워크 정보 확인
    ## EKS Pod Identity Agent uses the **hostNetwork** of the node and it uses port **80** and port **2703** on a **link-local address** on the **node**. 
    ## This address is 169.254.170.23 for IPv4 and [fd00:ec2::23] for IPv6 clusters.
    for node in $N1 $N2 $N3; do ssh ec2-user@$node sudo ss -tnlp | grep eks-pod-identit; echo "-----";done
    for node in $N1 $N2 $N3; do ssh ec2-user@$node sudo ip -c route; done
    for node in $N1 $N2 $N3; do ssh ec2-user@$node sudo ip -c -br -4 addr; done
    for node in $N1 $N2 $N3; do ssh ec2-user@$node sudo ip -c addr; done
    ```
    
- (참고) 노드 EC2 Profile에 작년 기능 출시 이후 Policy에 업데이트됨 : 워커노드 IAM Role 정보 확인
    
    ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/199871ca-57ce-4e7f-8a4e-e06b65b40e69/Untitled.png)
    
    ```bash
    {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "**WorkerNodePermissions**",
                "Effect": "Allow",
                "Action": [
                    "ec2:DescribeInstances",
                    "ec2:DescribeInstanceTypes",
                    "ec2:DescribeRouteTables",
                    "ec2:DescribeSecurityGroups",
                    "ec2:DescribeSubnets",
                    "ec2:DescribeVolumes",
                    "ec2:DescribeVolumesModifications",
                    "ec2:DescribeVpcs",
                    "eks:DescribeCluster",
                    "**eks-auth:AssumeRoleForPodIdentity**"
                ],
                "Resource": "*"
            }
        ]
    }
    ```
    
- podidentityassociation 설정
    
    ```bash
    # 
    eksctl create **podidentityassociation** \
    --cluster $CLUSTER_NAME \
    --namespace **default** \
    --service-account-name **s3-sa** \
    --role-name **s3-eks-pod-identity-role** \
    --**permission-policy-arns** arn:aws:iam::aws:policy/**AmazonS3ReadOnlyAccess** \
    --region $AWS_REGION
    
    # 확인
    kubectl get sa
    **eksctl get podidentityassociation --cluster $CLUSTER_NAME**
    ASSOCIATION ARN											                                                      NAMESPACE	SERVICE ACCOUNT NAME	IAM ROLE ARN
    arn:aws:eks:ap-northeast-2:911283464785:podidentityassociation/myeks/a-blaanudo8dc1dbddw	default		s3-sa			            arn:aws:iam::911283464785:role/s3-eks-pod-identity-role
    
    **aws eks list-pod-identity-associations --cluster-name $CLUSTER_NAME | jq**
    {
      "associations": [
        {
          "clusterName": "myeks",
          "namespace": "default",
          "serviceAccount": "s3-sa",
          "associationArn": "arn:aws:eks:ap-northeast-2:911283464785:podidentityassociation/myeks/a-pm07a3bg79bqa3p24",
          "associationId": "a-pm07a3bg79bqa3p24"
        }
      ]
    }
    
    # ABAC 지원을 위해 sts:Tagsession 추가
    **aws iam get-role --query 'Role.AssumeRolePolicyDocument' --role-name s3-eks-pod-identity-role | jq .**
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Principal": {
            "Service": "pods.eks.amazonaws.com"
          },
          "Action": [
            "sts:AssumeRole",
            "sts:**TagSession**"
          ]
        }
      ]
    }

```
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei40.png)

    
  - EKS → 액세스 : Pod Identity 연결 확인 → 편집 클릭 해보기
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei41.png)
    
- 테스트용 파드 생성 및 확인 : **AssumeRoleForPodIdentity** - [Link](https://docs.aws.amazon.com/cli/latest/reference/eks-auth/assume-role-for-pod-identity.html)
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei42.png)
    
    https://youtu.be/iyMcOpXRVWk?si=J4q7vOe-W4UhQ1wu&t=2501
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei43.png)
    
    https://ap-northeast-2.console.aws.amazon.com/cloudtrailv2/home?region=ap-northeast-2#/events?EventName=AssumeRoleForPodIdentity
    
```bash
    # 서비스어카운트, 파드 생성
    **kubectl create sa s3-sa**
    
    **cat <<EOF | kubectl apply -f -**
    apiVersion: v1
    kind: Pod
    metadata:
      name: **eks-pod-identity**
    spec:
      **serviceAccountName: s3-sa**
      containers:
        - name: my-aws-cli
          image: amazon/aws-cli:latest
          command: ['sleep', '36000']
      restartPolicy: Never
      terminationGracePeriodSeconds: 0
    **EOF**
    
    #
    **kubectl get pod eks-pod-identity -o yaml** | kubectl neat| yh
    kubectl exec -it **eks-pod-identity** -- aws sts get-caller-identity --query Arn
    kubectl exec -it **eks-pod-identity** -- aws s3 ls
    kubectl exec -it **eks-pod-identity** -- env | grep AWS
    WS_CONTAINER_CREDENTIALS_FULL_URI=http://169.254.170.23/v1/credentials
    AWS_CONTAINER_AUTHORIZATION_TOKEN_FILE=/var/run/secrets/pods.eks.amazonaws.com/serviceaccount/eks-pod-identity-token
    AWS_STS_REGIONAL_ENDPOINTS=regional
    AWS_DEFAULT_REGION=ap-northeast-2
    AWS_REGION=ap-northeast-2
    
    # 토큰 정보 확인
    kubectl exec -it **eks-pod-identity** -- ls /var/run/secrets/pods.eks.amazonaws.com/serviceaccount/
    kubectl exec -it **eks-pod-identity** -- cat /var/run/secrets/pods.eks.amazonaws.com/serviceaccount/**eks-pod-identity-token**
    ```
    
- 실습 리소스 삭제
    
```bash
    eksctl delete podidentityassociation --cluster $**CLUSTER_NAME** --namespace default --service-account-name **s3-sa**
    kubectl delete pod eks-pod-identity
    kubectl delete sa s3-sa
```
    
- IAM Session tags → **Support for session tags 실습 도전해보세요 - [Link](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/) [Blog](https://whchoi98.gitbook.io/aws-iam/iam-tag)**
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei44.png)
    
    https://youtu.be/iyMcOpXRVWk?si=dGAnJ6x2qCc6YaQY&t=1680
    
![https://cafe.naver.com/kubeops](/Images/eks/eks_sei44.png)
    
- IRSA vs EKS Pod Identity
    
    
    |  | IRSA | EKS Pod Identity |
    | --- | --- | --- |
    | Role extensibility | You have to update the IAM role’s trust policy with the new EKS cluster OIDC provider endpoint each time you want to use the role in a new cluster. | You have to setup the role one time, to establish trust with the newly introduced EKS service principal “pods.eks.amazonaws.com”. After this one-time step, you don’t need to update the role’s trust policy each time it is used in a new cluster. |
    | Account scalability | EKS cluster has an https://openid.net/connect/(OIDC) issuer URL associated with it. To use IRSA, a unique OpenID connect provider needs to be created in IAM for each EKS cluster. IAM OIDC provider has a default global https://docs.aws.amazon.com/general/latest/gr/iam-service.html of 100 per AWS account. Keep this limit in consideration as you grow the number of EKS clusters per account. | EKS Pod Identity doesn’t require users to setup IAM OIDC provider, so this limit doesn’t apply. |
    | Role scalability | In IRSA, you define the trust relationship between an IAM role and service account in the role’s trust policy. By default, the length of trust policy size is 2048. This means that you can typically define four trust relationships in a single policy. While you can get the trust policy length limit increased, you are typically limited to a maximum of eight trust relationships within a single policy. | EKS Pod Identity doesn’t require users to define trust relationship between IAM role and service account in IAM trust policy, so this limit doesn’t apply. |
    | Role reusability | IAM https://docs.aws.amazon.com/IAM/latest/UserGuide/access_tags.html are not supported. | IAM credentials supplied by EKS Pod Identity include support for https://docs.aws.amazon.com/eks/latest/userguide/pod-id-abac.html#pod-id-abac-tags. Role session tags enable administrators to author a single IAM role that can be used with multiple service accounts, with different effective permissions, by allowing access to AWS resources based on tags attached to them. |
    | Cluster readiness | IAM roles used in IRSA need to wait for the cluster to be in a “Ready” state, to get the cluster’s OpenID Connect Provider URL to complete the IAM role trust policy configuration | IAM roles used in Pod identity can be created ahead of time. |
    | Environments supported | IRSA can be used in EKS, EKS-A, ROSA, self-managed Kubernetes clusters on Amazon EC2 | EKS Pod Identity is purpose built for EKS. |
    | Supported EKS versions | All supported EKS versions | EKS version 1.24 and above. See EKS https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html#pod-id-cluster-versions for details. |
    | Cross account access | Cross account here refers to the scenario where your EKS cluster is in one AWS account and the AWS resources that are being accessed by your applications is in another AWS account. In IRSA, you can configure cross account IAM permissions either by creating an IAM identity provider in the account your AWS resources live or by using chained AssumeRole operation. See EKS user guide on IRSA https://docs.aws.amazon.com/eks/latest/userguide/cross-account-access.html for details. | EKS Pod Identity supports cross account access through resource policies and chained AssumeRole operation. See the previous section “How to perform cross account access with EKS Pod Identity” for details. |
    | Mapping inventory | You can find the mapping of IAM roles to service accounts by parsing individual IAM role’s trust policy or by inspecting the annotations added to service accounts. | EKS Pod Identity offers a new ListPodIdentityAssociations API to centrally see the mapping of roles to service accounts. |
- **고려사항**
    - SDK 최신 버전 확인 - [Link](https://docs.aws.amazon.com/eks/latest/userguide/pod-id-minimum-sdk.html)
    - 워커노드에 IAM Policy 확인 : Action(eks-auth:AssumeRoleForPodIdentity)
    - 보안 솔루션으로 링크 로컬 주소 사용 가능 여부 확인, 혹은 이미 사용 중인 주소인지, iptables 로 막혀있는지 확인
    - How to migrate from IRSA to EKS Pod Identity : 기존 IRSA → PodIdentity 마이그레이션 - [Link](https://aws.amazon.com/blogs/containers/amazon-eks-pod-identity-a-new-way-for-applications-on-eks-to-obtain-iam-credentials/)
        
        ![Untitled](https://prod-files-secure.s3.us-west-2.amazonaws.com/a6af158e-5b0f-4e31-9d12-0d0b2805956a/2f0a3b28-faec-43f3-81d0-ab95315d4b7f/Untitled.png)
        
- **현재 지원 불가능** - [Link](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html#pod-id-considerations)
- EKS Pod Identities are available on the following:
- Amazon **EKS** cluster **versions** listed in the previous topic [EKS Pod Identity cluster versions](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html#pod-id-cluster-versions).
- **Worker** nodes in the cluster that are Linux Amazon EC2 instances.
- EKS Pod Identities aren't available on the following:
 - **China** Regions.
 - AWS GovCloud (**US**).
 - AWS **Outposts**.
 - Amazon EKS **Anywhere**.
 - Kubernetes clusters that you create and run on Amazon EC2. The EKS Pod Identity components are only available on Amazon EKS.
    - You can't use EKS Pod Identities with:
        - Pods that run anywhere except Linux Amazon EC2 instances. Linux and Windows pods that run on **AWS Fargate** (Fargate) aren't supported. Pods that run on **Windows Amazon EC**2 instances aren't supported.
        - ***Amazon EKS add-ons*** that need **IAM credentials**. The EKS add-ons can only use *IAM roles for service accounts* instead. The list of EKS add-ons that use IAM credentials include:
            - Amazon VPC CNI plugin for Kubernetes
            - AWS Load Balancer Controller
            - The CSI storage drivers: EBS CSI, EFS CSI, Amazon FSx for Lustre CSI driver, Amazon FSx for NetApp ONTAP CSI driver, Amazon FSx for OpenZFS CSI driver, Amazon File Cache CSI driver


</details>




