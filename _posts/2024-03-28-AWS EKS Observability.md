---
layout: single
title: "AWS EKS Observability "
categories:  Devops
tags: [linux, container, kubernetes , AWS , EKS, Monitoring ]
toc: true
---




# AWS EKS Observability



## 실습 환경 구성

 > 첨부링크 : https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick3.yaml

 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)


<details><summary>펼치기</summary>

```bash

# YAML 파일 다운로드
curl -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/**eks-oneclick3.yaml**

# CloudFormation 스택 배포
예시) aws cloudformation deploy --template-file **eks-oneclick3.yaml** --stack-name **myeks** --parameter-overrides KeyName=**kp-gasida** SgIngressSshCidr=$(curl -s ipinfo.io/ip)/32  MyIamUserAccessKeyID=**AKIA5...** MyIamUserSecretAccessKey=**'CVNa2...'** ClusterBaseName=**myeks** --region ap-northeast-2

# CloudFormation 스택 배포 완료 후 작업용 EC2 IP 출력
aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].**Outputs[0]**.OutputValue' --output text

# 작업용 EC2 SSH 접속
ssh -i **~/.ssh/kp-gasida.pem** **ec2-user**@$(aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].Outputs[0].OutputValue' --output text)
or
ssh -i **~/.ssh/kp-gasida.pem** **root**@$(aws cloudformation describe-stacks --stack-name **myeks** --query 'Stacks[*].Outputs[0].OutputValue' --output text)
~ password: **qwe123**

```

- 기본 설정 및 **EFS** 확인

```bash

# default 네임스페이스 적용
**kubectl ns default**

# 노드 정보 확인 : t3.xlarge
**kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone**
eksctl get iamidentitymapping --cluster myeks
****
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
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr 192.168.1.100/32

# 워커 노드 SSH 접속
for node in $N1 $N2 $N3; do ssh ec2-user@$node hostname; done

```

- AWS LB/ExternalDNS/EBS, kube-ops-view 설치

```bash

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
kubectl **annotate** service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=**kubeopsview**.$MyDomain"
echo -e "Kube Ops View URL = http://**kubeopsview**.$MyDomain:8080/#scale=1.5"

# AWS LB Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

# EBS csi driver 설치 확인
eksctl get addon --cluster ${CLUSTER_NAME}
kubectl get pod -n kube-system -l 'app in (ebs-csi-controller,ebs-csi-node)'
kubectl get csinodes

# gp3 스토리지 클래스 생성
kubectl get sc
**kubectl apply -f https://raw.githubusercontent.com/gasida/PKOS/main/aews/gp3-sc.yaml**
kubectl get sc

```

![구성](/Images/eks/eks_o1.png)
![구성](/Images/eks/eks_o2.png)



- 설치 정보 확인

```bash

# 이미지 정보 확인
**kubectl get pods --all-namespaces -o jsonpath="{.items[*].spec.containers[*].image}" | tr -s '[[:space:]]' '\n' | sort | uniq -c**

# eksctl 설치/업데이트 addon 확인
**eksctl get addon --cluster $CLUSTER_NAME**

# IRSA 확인
**eksctl get iamserviceaccount --cluster $CLUSTER_NAME**

# EC2 Instance Profile에 IAM Role 정보 확인
**cat myeks.yaml | grep managedNodeGroups -A20 | yh**
managedNodeGroups: 
- amiFamily: AmazonLinux2
  desiredCapacity: 3
  disableIMDSv1: true
  disablePodIMDS: false
  **iam**: 
    **withAddonPolicies**: 
      albIngress: false
      appMesh: false
      appMeshPreview: false
      autoScaler: false
      awsLoadBalancerController: false  >> **IRSA 사용**
      certManager: true
      **cloudWatch: true**
      **ebs: true**
      efs: false
      **externalDNS: true**
      fsx: false
      imageBuilder: true
      **xRay: true**

```

![구성](/Images/eks/eks_o3.png)

</details>
 


## EKS Console
[참고](https://www.eksworkshop.com/docs/observability/resource-view/)
- 소개 : 쿠버네티스 API를 통해서 리소스 및 정보를 확인 할 수 있음 - Docs permissions
<details><summary>실습</summary>

```bash

**kubectl get ClusterRole | grep eks**
eks:addon-manager                                                      2023-05-08T04:22:45Z
eks:az-poller                                                          2023-05-08T04:22:42Z
eks:certificate-controller-approver                                    2023-05-08T04:22:42Z
...

```
- 클러스터 ARN 확인 : IAM > 역할 > eksctl-myeks-cluster-~~~

- **Console 각 메뉴 확인** : 워크숍 링크 활용 - [링크](https://www.eksworkshop.com/docs/observability/resource-view/)
    1. Workloads : Pods, ReplicaSets, Deployments, and DaemonSets
        - **Pods** : 네임스페이스 필터, **구조화된 보기** structured view vs **원시 보기** raw view
    2. Cluster : Nodes, Namespaces and API Services
        - **Nodes** : 노드 상태 및 정보, Taints, Conditions, **Labels**, Annotations 등
    3. Service and Networking : Pods as Service, Endpoints and Ingresses
        - **Service** : 서비스 정보, **로드 밸런서**(CLB/NLB) URL 정보 등
    4. Config and Secrets : ConfigMap and Secrets
        - ConfigMap & **Secrets** : 정보 확인, **디코드** Decode 지원
    5. Storage : PVC, PV, Storage Classes, Volume Attachments, CSI Drivers, CSI Nodes
        - **PVC** : 볼륨 정보, 주석, 이벤트
        - Volume Attachments : PVC가 연결된 CSI Node 정보
    6. Authentication : Service Account
        - **Service Account** : IAM 역할 arn , add-on 연동
    7. Authorization : Cluster Roles, Roles, ClusterRoleBindings and RoleBindings
        - Cluster Roles & Roles : **Roles 에 규칙** 확인
    8. Policy : Limit Ranges, Resource Quotas, Network Policies, Pod Disruption Budgets, Pod Security Policies
        - **Pod Security Policies** : (기본값) **eks.privileged** 정보 확인
    9. Extensions : *Custom Resource Definitions*, *Mutating Webhook Configurations*, and *Validating Webhook Configurations*
        - CRD 및 Webhook 확인
        
        ![구성](/Images/eks/eks_o11.png)

        https://www.eksworkshop.com/docs/observability/resource-view/extensions/webhook-configurations

</details>


## Logging in EKS

[EKS 스터디 - 4주차 1편 - 컨트롤 플레인 로깅](https://malwareanalysis.tistory.com/600)


`로깅` : **control plane** logging, **node** logging, and **application** logging - [Docs](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/eks-observe.html)

<details><summary>Control Plane logging</summary>

- 로그 이름( /aws/eks/<cluster-name>/cluster ) - [Docs](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/control-plane-logs.html)
    
     ![구성](/Images/eks/eks_o5.png)

    1. Kubernetes API server component logs (`**api**`) – `kube-apiserver-<nnn...>`
    2. Audit (`**audit**`) – `kube-apiserver-audit-<nnn...>`
    3. Authenticator (`**authenticator**`) – `authenticator-<nnn...>`
    4. Controller manager (`**controllerManager**`) – `kube-controller-manager-<nnn...>`
    5. Scheduler (`**scheduler**`) – `kube-scheduler-<nnn...>`
    
    ```bash
    # 모든 로깅 활성화
    aws eks **update-cluster-config** --region $AWS_DEFAULT_REGION --name $CLUSTER_NAME \
        --logging '{"clusterLogging":[{"types":["**api**","**audit**","**authenticator**","**controllerManager**","**scheduler**"],"enabled":**true**}]}'
    
    ```
    ![구성](/Images/eks/eks_o6.png)


    ```bash

    # 로그 그룹 확인
    aws logs describe-log-groups | jq
    
    # 로그 tail 확인 : aws logs tail help
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster | more
    
    # 신규 로그를 바로 출력
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster --follow
    
    # 필터 패턴
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster --filter-pattern <필터 패턴>
    
    # 로그 스트림이름
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster --log-stream-name-prefix <로그 스트림 prefix> --follow
    **aws logs tail /aws/eks/$CLUSTER_NAME/cluster --log-stream-name-prefix kube-controller-manager --follow
    kubectl scale deployment -n kube-system coredns --replicas=1**
    kubectl scale deployment -n kube-system coredns --replicas=2
    
    # 시간 지정: 1초(s) 1분(m) 1시간(h) 하루(d) 한주(w)
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster --since 1h30m
    
    # 짧게 출력
    aws logs tail /aws/eks/$CLUSTER_NAME/cluster --since 1h30m --format short
    ```
    
    
    - CloudWatch Log Insights - [링크](https://www.eksworkshop.com/docs/observability/logging/cluster-logging/log-insights)
    
    ```bash
    # EC2 Instance가 NodeNotReady 상태인 로그 검색
    fields @timestamp, @message
    | filter @message like /**NodeNotReady**/
    | sort @timestamp desc
    
    # kube-apiserver-audit 로그에서 userAgent 정렬해서 아래 4개 필드 정보 검색
    fields userAgent, requestURI, @timestamp, @message
    | filter @logStream ~= "**kube-apiserver-audit**"
    | stats count(userAgent) as count by userAgent
    | sort count desc
    
    #
    fields @timestamp, @message
    | filter @logStream ~= "**kube-scheduler**"
    | sort @timestamp desc
    
    #
    fields @timestamp, @message
    | filter @logStream ~= "**authenticator**"
    | sort @timestamp desc
    
    #
    fields @timestamp, @message
    | filter @logStream ~= "**kube-controller-manager**"
    | sort @timestamp desc
    ```
    
    - CloudWatch Log Insight Query with AWS CLI
    
    ```bash
    # CloudWatch Log Insight Query
    aws logs get-query-results --query-id $(aws logs start-query \
    --log-group-name '/aws/eks/myeks/cluster' \
    --start-time `date -d "-1 hours" +%s` \
    --end-time `date +%s` \
    --query-string 'fields @timestamp, @message | filter @logStream ~= "kube-scheduler" | sort @timestamp desc' \
    | jq --raw-output '.queryId')
    ```
    
    ![구성](/Images/eks/eks_o7.png)

    - 로깅 끄기
    
    ```bash

    # EKS Control Plane 로깅(CloudWatch Logs) 비활성화
    eksctl utils **update-cluster-logging** --cluster $CLUSTER_NAME --region $AWS_DEFAULT_REGION **--disable-types all** --approve
    
    # 로그 그룹 삭제
    aws logs **delete-log-group** --log-group-name /aws/eks/$CLUSTER_NAME/cluster

    ```


    ![구성](/Images/eks/eks_o8.png)
    ![구성](/Images/eks/eks_o9.png)
    ![구성](/Images/eks/eks_o10.png)
     ![구성](/Images/eks/eks_o12.png)
</details>



<details><summary>참고</summary>

```bash

# 메트릭 패턴 정보 : metric_name{"tag"="value"[,...]} value
**kubectl get --raw /metrics** | more

```


![구성](/Images/eks/eks_o13.png)





- Managing etcd database size on Amazon EKS clusters - [링크](https://aws.amazon.com/ko/blogs/containers/managing-etcd-database-size-on-amazon-eks-clusters/)

```bash

# How to monitor etcd database size?
**kubectl get --raw /metrics | grep "apiserver_storage_size_bytes"**
apiserver_storage_size_bytes{cluster="etcd-0"} 4.919296e+06

# CW Logs Insights 쿼리
fields @timestamp, @message, @logStream
| filter @logStream like /**kube-apiserver-audit**/
| filter @message like /**mvcc: database space exceeded**/
| limit 10

# How do I identify what is consuming etcd database space?
**kubectl get --raw=/metrics | grep apiserver_storage_objects |awk '$2>100' |sort -g -k 2**
**kubectl get --raw=/metrics | grep apiserver_storage_objects |awk '$2>50' |sort -g -k 2**
apiserver_storage_objects{resource="clusterrolebindings.rbac.authorization.k8s.io"} 78
apiserver_storage_objects{resource="clusterroles.rbac.authorization.k8s.io"} 92

# CW Logs Insights 쿼리 : Request volume - Requests by User Agent:
fields userAgent, requestURI, @timestamp, @message
| filter @logStream like /**kube-apiserver-audit**/
| stats count(*) as count by userAgent
| sort count desc

# CW Logs Insights 쿼리 : Request volume - Requests by Universal Resource Identifier (URI)/Verb:
filter @logStream like /**kube-apiserver-audit**/
| stats count(*) as count by requestURI, verb, user.username
| sort count desc

# Object revision updates
fields requestURI
| filter @logStream like /**kube-apiserver-audit**/
| filter requestURI like /pods/
| filter verb like /patch/
| filter count > 8
| stats count(*) as count by requestURI, responseStatus.code
| filter responseStatus.code not like /500/
| sort count desc

#
fields @timestamp, userAgent, responseStatus.code, requestURI
| filter @logStream like /**kube-apiserver-audit**/
| filter requestURI like /pods/
| filter verb like /patch/
| filter requestURI like /name_of_the_pod_that_is_updating_fast/
| sort @timestamp

```
</details>

- 로깅 확인을 위한 pod 배포 (Nginx)

<details><summary>예제 pod 배포</summary>


```bash

# NGINX 웹서버 **배포**
helm repo add bitnami https://charts.bitnami.com/bitnami

# 사용 리전의 인증서 ARN 확인
CERT_ARN=$(aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text)
echo $CERT_ARN

# 도메인 확인
echo $MyDomain

# 파라미터 파일 생성 : 인증서 ARN 지정하지 않아도 가능! 혹시 https 리스너 설정 안 될 경우 인증서 설정 추가(주석 제거)해서 배포 할 것
cat <<EOT > nginx-values.yaml
service:
  type: NodePort
  
networkPolicy:
  enabled: false

ingress:
  enabled: true
  ingressClassName: **alb**
  hostname: **nginx.$MyDomain**
  pathType: **Prefix**
  path: **/**
  annotations: 
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}, {"HTTP":80}]'
    ~~#alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN~~
    alb.ingress.kubernetes.io/success-codes: 200-399
    **alb.ingress.kubernetes.io/load-balancer-name: $CLUSTER_NAME-ingress-alb
    alb.ingress.kubernetes.io/group.name: study**
    alb.ingress.kubernetes.io/ssl-redirect: '443'
EOT
cat nginx-values.yaml | yh

# 배포
**helm install nginx bitnami/nginx --version 15.14.0 -f nginx-values.yaml**

# 확인
kubectl get ingress,deploy,svc,ep nginx
kubectl get targetgroupbindings # ALB TG 확인

# 접속 주소 확인 및 접속
echo -e "Nginx WebServer URL = https://nginx.$MyDomain"
curl -s https://nginx.$MyDomain
kubectl logs deploy/nginx -f

**## 외부에서는 접속이 잘되나, myeks EC2에서 url 접속이 잘 되지 않을 경우 : 이전 aws DNS cache 영향(추정)**
dig +short nginx.$MyDomain
dig +short nginx.$MyDomain @192.168.0.2
dig +short nginx.$MyDomain @1.1.1.1
dig +short nginx.$MyDomain @8.8.8.8
cat /etc/resolv.conf
**sed -i "s/^nameserver 192.168.0.2/nameserver 1.1.1.1/g" /etc/resolv.conf**
cat /etc/resolv.conf
dig +short nginx.$MyDomain
dig +short nginx.$MyDomain @8.8.8.8
dig +short nginx.$MyDomain @192.168.0.2
curl -s https://nginx.$MyDomain
----

# 반복 접속
while true; do curl -s https://nginx.$MyDomain -I | head -n 1; date; sleep 1; done




# (참고) 삭제 시
helm uninstall nginx

```
![구성](/Images/eks/eks_o14.png)



![구성](/Images/eks/eks_o15.png)




</details>

<details><summary>컨테이너 로그 환경의 로그 표준 출력 stdout/stderr로 보내는 것을 권고</summary>

- 해당 권고에 따라 작성된 컨테이너 애플리케이션의 로그는 해당 파드 안으로 접속하지 않아도 사용자는 외부에서 kubectl logs 명령어로 애플리케이션 종류에 상관없이,
애플리케이션마다 로그 파일 위치에 상관없이, 단일 명령어로 조회 가능

```bash

# 로그 모니터링
kubectl **logs** deploy/nginx -f

# nginx 웹 접속 시도

# 컨테이너 로그 파일 위치 확인
**kubectl exec -it deploy/nginx -- ls -l /opt/bitnami/nginx/logs/**
total 0
lrwxrwxrwx 1 root root 11 Feb 18 13:35 access.log -> /dev/stdout
lrwxrwxrwx 1 root root 11 Feb 18 13:35 error.log -> /dev/stderr

```

- (참고) nginx docker log collector 예시 - [링크](https://github.com/bitnami/containers/blob/main/bitnami/nginx/1.23/debian-11/Dockerfile#L42-L43) [링크](https://github.com/nginxinc/docker-nginx/blob/8921999083def7ba43a06fabd5f80e4406651353/mainline/jessie/Dockerfile#L21-L23)
    
    ```bash
    
    RUN ln -sf **/dev/stdout** **/opt/bitnami/nginx/logs/access.log**
    RUN ln -sf **/dev/stderr** **/opt/bitnami/nginx/logs/error.log**
    
    ```
   

    ```bash

    # forward request and error logs to docker log collector
    RUN ln -sf /dev/stdout /var/log/nginx/access.log \
     && ln -sf /dev/stderr /var/log/nginx/error.log

    ```
     
    ![구성](/Images/eks/eks_o16.png)

- 또한 종료된 파드의 로그는 kubectl logs로 조회 할 수 없다
- kubelet 기본 설정은 로그 파일의 최대 크기가 10Mi로 10Mi를 초과하는 로그는 전체 로그 조회가 불가능함

- (참고) nginx docker log collector 예시 - [링크](https://github.com/bitnami/containers/blob/main/bitnami/nginx/1.23/debian-11/Dockerfile#L42-L43) [링크](https://github.com/nginxinc/docker-nginx/blob/8921999083def7ba43a06fabd5f80e4406651353/mainline/jessie/Dockerfile#L21-L23)
    
    ```bash

    RUN ln -sf **/dev/stdout** **/opt/bitnami/nginx/logs/access.log**
    RUN ln -sf **/dev/stderr** **/opt/bitnami/nginx/logs/error.log**

    ```
    
    ```bash

    # forward request and error logs to docker log collector
    RUN ln -sf /dev/stdout /var/log/nginx/access.log \
     && ln -sf /dev/stderr /var/log/nginx/error.log

    ```
    
- 또한 종료된 파드의 로그는 kubectl logs로 조회 할 수 없다
- kubelet 기본 설정은 로그 파일의 최대 크기가 10Mi로 10Mi를 초과하는 로그는 전체 로그 조회가 불가능함


</details>

- `파드 로깅` : **CloudWatch Container Insights + Fluent Bit로 파드 로그 수집 가능 ⇒ 아래에서 메트릭과 함께 다룸**

- https://www.eksworkshop.com/docs/observability/logging/pod-logging/fluentbit-setup

- [EKS 스터디 - 4주차 2편 - pod로깅](https://malwareanalysis.tistory.com/601)




 ## Container Insights metrics in Amazon CloudWatch & Fluent Bit (Logs)
 [Announcing Amazon CloudWatch Container Insights with Enhanced Observability for Amazon EKS on EC2 | Amazon Web Services](https://aws.amazon.com/ko/blogs/mt/new-container-insights-with-enhanced-observability-for-amazon-eks/)
> https://www.eksworkshop.com/docs/observability/container-insights/visualize-metrics-cloudwatch

- 목적 : CloudWatch Container Insight : 노드에 CW Agent 파드와 Fluent Bit 파드가 데몬셋으로 배치되어 Metrics 와 Logs 수집

<details><summary>Fluent Bit</summary>
- as a DaemonSet to send logs to CloudWatch **Logs** Integration in **CloudWatch Container Insights** for EKS - [Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-logs-FluentBit.html) [Blog](https://aws.amazon.com/ko/blogs/containers/fluent-bit-integration-in-cloudwatch-container-insights-for-eks/) [Fluentd](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-logs.html) [TS](https://hyperconnect.github.io/2023/05/02/troubleshooting-fluent-bit-segmentation-fault.html)
    
    


![구성](/Images/eks/eks_o27.png)

> https://aws.amazon.com/ko/blogs/containers/fluent-bit-integration-in-cloudwatch-container-insights-for-eks/
    
    - **[수집]** **플루언트비트** Fluent Bit 컨테이너를 **데몬셋**으로 동작시키고, 아래 **3가지** 종류의 **로그**를 **CloudWatch Logs** 에 전송
        1. /aws/containerinsights/*`Cluster_Name`*/**application** : 로그 소스(All log files in `/var/log/containers`), 각 **컨테이너/파드 로그**
        2. /aws/containerinsights/*`Cluster_Name`*/**host** : 로그 소스(Logs from `/var/log/dmesg`, `/var/log/secure`, and `/var/log/messages`), **노드(호스트) 로그**
        3. /aws/containerinsights/*`Cluster_Name`*/**dataplane** : 로그 소스(`/var/log/journal` for `kubelet.service`, `kubeproxy.service`, and `docker.service`), **쿠버네티스 데이터플레인 로그**
    - **[저장]** : CloudWatch Logs 에 로그를 저장, 로그 그룹 별 로그 보존 기간 설정 가능
    - **[시각화]** : CloudWatch 의 Logs Insights 를 사용하여 대상 로그를 분석하고, CloudWatch 의 대시보드로 시각화한다
    - (참고) [Fluent Bit](https://fluentbit.io/) is a **lightweight log processor** and **forwarder** that allows you to collect data and logs from different sources, enrich them with filters and send them to multiple destinations like CloudWatch, Kinesis Data Firehose, Kinesis Data Streams and Amazon OpenSearch Service.

![구성](/Images/eks/eks_o28.png)


</details>


<details><summary>소개: collect, aggregate, and summarize metrics and logs from your containerized applications and microservices</summary>

- **CloudWatch Container Insight**는 컨테이너형 애플리케이션 및 마이크로 서비스에 대한 **모니터링**, **트러블 슈팅** 및 **알람**을 위한 **완전 관리형 관측 서비스**입니다.
- CloudWatch 콘솔에서 **자동화된 대시보드**를 통해 container metrics, Prometeus metrics, application logs 및 performance log events를 탐색, 분석 및 시각화할 수 있습니다.
- CloudWatch Container Insight는 CPU, 메모리, 디스크 및 네트워크와 같은 인프라 메트릭을 자동으로 수집합니다.
- EKS 클러스터의 crashloop backoffs와 같은 진단 정보를 제공하여 문제를 격리하고 신속하게 해결할 수 있도록 지원합니다.
- 이러한 대시보드는 Amazon ECS, Amazon EKS, AWS ECS Fargate 그리고 EC2 위에 구동되는 k8s 클러스터에서 사용 가능합니다.

![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/a7a347c4-71a8-4542-be6c-fa1006d0ed88/Untitled.png)


</details>



<details><summary>노드의 로그 확인</summary>

1. application 로그 소스(All log files in /var/log/containers → 심볼릭 링크 /var/log/pods/<컨테이너>, 각 컨테이너/파드 로그

```bash

# 로그 위치 확인
#ssh ec2-user@$N1 sudo tree /var/log/containers
#ssh ec2-user@$N1 sudo ls -al /var/log/containers
for node in $N1 $N2 $N3; do echo ">>>>> $node <<<<<"; ssh ec2-user@$node sudo tree /var/log/containers; echo; done
for node in $N1 $N2 $N3; do echo ">>>>> $node <<<<<"; ssh ec2-user@$node sudo ls -al /var/log/containers; echo; done

# 개별 파드 로그 확인 : 아래 각자 디렉터리 경로는 다름
*ssh ec2-user@$N1 sudo tail -f /var/log/pods/default_nginx-685c67bc9-pkvzd_69b28caf-7fe2-422b-aad8-f1f70a206d9e/nginx/0.log*

```

2. host 로그 소스(Logs from /var/log/dmesg, /var/log/secure, and /var/log/messages), 노드(호스트) 로그

```bash

# 로그 위치 확인
#ssh ec2-user@$N1 sudo tree /var/log/ -L 1
#ssh ec2-user@$N1 sudo ls -la /var/log/
for node in $N1 $N2 $N3; do echo ">>>>> $node <<<<<"; ssh ec2-user@$node sudo tree /var/log/ -L 1; echo; done
for node in $N1 $N2 $N3; do echo ">>>>> $node <<<<<"; ssh ec2-user@$node sudo ls -la /var/log/; echo; done

# 호스트 로그 확인
#ssh ec2-user@$N1 sudo tail /var/log/dmesg
#ssh ec2-user@$N1 sudo tail /var/log/secure
#ssh ec2-user@$N1 sudo tail /var/log/messages
for log in dmesg secure messages; do echo ">>>>> Node1: /var/log/$log <<<<<"; ssh ec2-user@$N1 sudo tail /var/log/$log; echo; done
for log in dmesg secure messages; do echo ">>>>> Node2: /var/log/$log <<<<<"; ssh ec2-user@$N2 sudo tail /var/log/$log; echo; done
for log in dmesg secure messages; do echo ">>>>> Node3: /var/log/$log <<<<<"; ssh ec2-user@$N3 sudo tail /var/log/$log; echo; done

```

![구성](/Images/eks/eks_o17.png)


3. dataplane 로그 소스(/var/log/journal for kubelet.service, kubeproxy.service, and docker.service), 쿠버네티스 데이터플레인 로그

```bash

# 로그 위치 확인
#ssh ec2-user@$N1 sudo tree /var/log/journal -L 1
#ssh ec2-user@$N1 sudo ls -la /var/log/journal
for node in $N1 $N2 $N3; do echo ">>>>> $node <<<<<"; ssh ec2-user@$node sudo tree /var/log/journal -L 1; echo; done

# 저널 로그 확인 - [링크](https://www.lesstif.com/system-admin/linux-journalctl-82215080.html)
ssh ec2-user@$N3 sudo journalctl -x -n 200
ssh ec2-user@$N3 sudo journalctl -f

```
![구성](/Images/eks/eks_o18.png)


</details>




<details><summary>CloudWatch Container observability 설치</summary>

- [Link](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/ContainerInsights.html) cloudwatch-agent & fluent-bit 
- [링크](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-EKS-quickstart.html#Container-Insights-setup-EKS-quickstart-FluentBit) & Setting up Fluent Bit 
- [Docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-logs-FluentBit.html#Container-Insights-FluentBit-setup)

```bash

    # 설치
    aws eks **create-addon** --cluster-name $CLUSTER_NAME --addon-name **amazon-cloudwatch-observability**
    aws eks list-addons --cluster-name myeks --output table

```
   
![구성](/Images/eks/eks_o19.png)

```bash

# 설치 확인
kubectl get-all -n amazon-cloudwatch
kubectl get ds,pod,cm,sa,amazoncloudwatchagent -n amazon-cloudwatch
kubectl describe **clusterrole cloudwatch-agent-role amazon-cloudwatch-observability-manager-role**    # 
    
```
    
![구성](/Images/eks/eks_o20.png)
![구성](/Images/eks/eks_o21.png)

```bash
    
    클러스터롤 확인
    kubectl describe **clusterrolebindings cloudwatch-agent-role-binding amazon-cloudwatch-observability-manager-rolebinding**  # 클러스터롤 바인딩 확인
    kubectl -n amazon-cloudwatch logs -l app.kubernetes.io/component=amazon-cloudwatch-agent -f # 파드 로그 확인
    kubectl -n amazon-cloudwatch logs -l k8s-app=fluent-bit -f    # 파드 로그 확인
    
    # cloudwatch-agent 설정 확인
    **kubectl describe cm cloudwatch-agent-agent -n amazon-cloudwatch**
 ```

```bash

    #Fluent bit 파드 수집하는 방법 : Volumes에 HostPath를 살펴보자! >> / 호스트 패스 공유??? 보안상 안전한가? 좀 더 범위를 좁힐수는 없을까요?
 
    **kubectl describe -n amazon-cloudwatch ds cloudwatch-agent
    ...**
      Volumes:
       ...
       rootfs:
        Type:          HostPath (bare host directory volume)
        Path:          /
        HostPathType:  
    
    ...
    ssh ec2-user@$N1 sudo tree /dev/disk
    ...

```
  ![구성](/Images/eks/eks_o22.png)

```bash
    # Fluent Bit 로그 INPUT/FILTER/OUTPUT 설정 확인 - [링크](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Container-Insights-setup-logs-FluentBit.html#ContainerInsights-fluentbit-multiline)
    ## 설정 부분 구성 : application-log.conf , dataplane-log.conf , fluent-bit.conf , host-log.conf , parsers.conf
    **kubectl describe cm fluent-bit-config -n amazon-cloudwatch
    ...
    application-log.conf**:
    ----
    [**INPUT**]
        Name                tail
        Tag                 **application.***
        Exclude_Path        /var/log/containers/cloudwatch-agent*, /var/log/containers/fluent-bit*, /var/log/containers/aws-node*, /var/log/containers/kube-proxy*
        **Path                /var/log/containers/*.log**
        multiline.parser    docker, cri
        DB                  /var/fluent-bit/state/flb_container.db
        Mem_Buf_Limit       50MB
        Skip_Long_Lines     On
        Refresh_Interval    10
        Rotate_Wait         30
        storage.type        filesystem
        Read_from_Head      ${READ_FROM_HEAD}
    
    [**FILTER**]
        Name                kubernetes
        Match               application.*
        Kube_URL            https://kubernetes.default.svc:443
        Kube_Tag_Prefix     application.var.log.containers.
        Merge_Log           On
        Merge_Log_Key       log_processed
        K8S-Logging.Parser  On
        K8S-Logging.Exclude Off
        Labels              Off
        Annotations         Off
        Use_Kubelet         On
        Kubelet_Port        10250
        Buffer_Size         0
    
    [**OUTPUT**]
        Name                cloudwatch_logs
        Match               application.*
        region              ${AWS_REGION}
        **log_group_name      /aws/containerinsights/${CLUSTER_NAME}/application**
        log_stream_prefix   ${HOST_NAME}-
        auto_create_group   true
        extra_user_agent    container-insights
    **...**
```
![구성](/Images/eks/eks_o23.png)

```bash

    # Fluent Bit 파드가 수집하는 방법 : Volumes에 HostPath를 살펴보자!
    **kubectl describe -n amazon-cloudwatch ds fluent-bit**
    ...
    ssh ec2-user@$N1 sudo tree /var/log
    ...
    
    # (참고) 삭제
    aws eks **delete-addon** --cluster-name $CLUSTER_NAME --addon-name **amazon-cloudwatch-observability**

  ```
    


![구성](/Images/eks/eks_o20.png)

- Fluent bit 파드가 수집하는 방법 : Volumes에 HostPath - [링크](https://xn--vj5b11biyw.kr/309)
    - host에서 사용하는 docker.sock가 Pod에 mount 되어있는 상태에서 악의적인 사용자가 해당 Pod에 docker만 설치할 수 있다면, mount된 dock.sock을 이용하여 host의 docker에 명령을 보낼 수 있게 된다(docker가 client-server 구조이기 때문에 가능).이는 container escape라고도 할 수 있다.
    
![구성](/Images/eks/eks_o29.png)
        
- 로깅 확인 : CW → 로그 그룹
        
![구성](/Images/eks/eks_o30.png)
        
- 메트릭 확인 : CW → 인사이트 → Container Insights
        
![구성](/Images/eks/eks_o31.png)

</details>

<details><summary>Nginx 로그 확인</summary>

```bash

# 부하 발생
curl -s https://nginx.$MyDomain
yum install -y httpd
**ab** -c 500 -n 30000 https://nginx.$MyDomain/

# 파드 직접 로그 모니터링
kubectl logs deploy/nginx -f

```
- 로그 그룹 → application → 로그 스트림 : nginx 필터링 ⇒ 클릭 후 확인 ⇒ ApacheBench 필터링 확인

- Logs Insights

```bash

# **Application log errors** by container name : 컨테이너 이름별 애플리케이션 로그 오류
# 로그 그룹 선택 : /aws/containerinsights/<CLUSTER_NAME>/**application**
stats count() as error_count by kubernetes.container_name 
| filter stream="stderr" 
| sort error_count desc

# All **Kubelet errors/warning logs** for for a given EKS worker node
# 로그 그룹 선택 : /aws/containerinsights/<CLUSTER_NAME>/**dataplane**
fields @timestamp, @message, ec2_instance_id
| filter  message =~ /.*(E|W)[0-9]{4}.*/ and ec2_instance_id="<YOUR INSTANCE ID>"
| sort @timestamp desc

# **Kubelet errors/warning count** per EKS worker node in the cluster
# 로그 그룹 선택 : /aws/containerinsights/<CLUSTER_NAME>/**dataplane**
fields @timestamp, @message, ec2_instance_id
| filter   message =~ /.*(E|W)[0-9]{4}.*/
| stats count(*) as error_count by ec2_instance_id

**# performance 로그 그룹**
# 로그 그룹 선택 : /aws/containerinsights/<CLUSTER_NAME>/**performance**
# 노드별 평균 CPU 사용률
STATS avg(node_cpu_utilization) as avg_node_cpu_utilization by NodeName
| SORT avg_node_cpu_utilization DESC

# 파드별 재시작(restart) 카운트
STATS avg(number_of_container_restarts) as avg_number_of_container_restarts by PodName
| SORT avg_number_of_container_restarts DESC

# 요청된 Pod와 실행 중인 Pod 간 비교
fields @timestamp, @message 
| sort @timestamp desc 
| filter Type="Pod" 
| stats min(pod_number_of_containers) as requested, min(pod_number_of_running_containers) as running, ceil(avg(pod_number_of_containers-pod_number_of_running_containers)) as pods_missing by kubernetes.pod_name 
| sort pods_missing desc

# 클러스터 노드 실패 횟수
stats avg(cluster_failed_node_count) as CountOfNodeFailures 
| filter Type="Cluster" 
| sort @timestamp desc

**# 파드별 CPU 사용량**
stats pct(container_cpu_usage_total, 50) as CPUPercMedian by kubernetes.container_name 
| filter Type="Container"
| sort CPUPercMedian desc

```


</details>


- 메트릭 확인 : CloudWatch → Insights → Container Insights : 우측 상단(Local Time Zone, 30분) ⇒ 리소스 : myeks 선택


![구성](/Images/eks/eks_o35.png)


<details><summary>보기</summary>

![구성](/Images/eks/eks_o32.png)
![구성](/Images/eks/eks_o33.png)

</details>

##  Metrics-server & kwatch & botkube



<details><summary>Metrics-server & kwatch & botkube
 내용 </summary>


- `Metrics-server` 확인* : kubelet으로부터 수집한 리소스 메트릭을 수집 및 집계하는 클러스터 애드온 구성 요소 - [EKS](https://docs.aws.amazon.com/eks/latest/userguide/metrics-server.html) [Github](https://github.com/kubernetes-sigs/metrics-server) [Docs](https://kubernetes.io/ko/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/) [CMD](https://kubernetes.io/docs/reference/generated/kubectl/kubectl-commands#top)
    - **cAdvisor :** kubelet에 포함된 컨테이너 메트릭을 수집, 집계, 노출하는 데몬
    
  ![구성](/Images/eks/eks_o34.png)
    
    https://kubernetes.io/ko/docs/tasks/debug/debug-cluster/resource-metrics-pipeline/
    
    ```bash
    # 배포
    **kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml**
    
    # 메트릭 서버 확인 : 메트릭은 15초 간격으로 cAdvisor를 통하여 가져옴
    kubectl get pod -n kube-system -l k8s-app=metrics-server
    kubectl api-resources | grep metrics
    kubectl get apiservices |egrep '(AVAILABLE|metrics)'
    
    # 노드 메트릭 확인
    kubectl top node
    
    # 파드 메트릭 확인
    kubectl top pod -A
    kubectl top pod -n kube-system --sort-by='cpu'
    kubectl top pod -n kube-system --sort-by='memory'
    ```
    
- `kwatch 소개` 및 설치/사용 : **kwatch** helps you monitor all changes in your Kubernetes(K8s) cluster, detects crashes in your running apps in realtime, and publishes notifications to your channels (Slack, Discord, etc.) instantly - [링크](https://github.com/abahmed/kwatch) [Helm](https://artifacthub.io/packages/helm/kwatch/kwatch) [Blog](https://kwatch.dev/blog/monitor-pvc-usage)
    
    <aside>
    👉🏻 아래 저희 **팀의 슬랙 웹훅 URL** 대신, 자신이 사용하는 **슬랙 웹훅 URL**을 사용하시는 것도 좋습니다!
    ⇒ webhook 팀 슬랙 채널 참여 후 알람은 꺼두세요!
    
    </aside>
    
    <aside>
    🚨 아래 **웹훅 URL**은 **블로깅** 하실때 **가려주시거나 제거**해주시기 바랍니다. 공개된 웹훅으로 무작위 메시지 전송이 가능하기 때문입니다!
    
    </aside>
    
    ```bash

    # 닉네임
    NICK=<각자 자신의 닉네임>
    *NICK=gasida*
    
    # configmap 생성
    cat <<EOT > ~/kwatch-config.yaml
    apiVersion: v1
    kind: Namespace
    metadata:
      name: kwatch
    ---
    apiVersion: v1
    kind: ConfigMap
    metadata:
      name: kwatch
      namespace: kwatch
    data:
      config.yaml: |
        **alert**:
          **slack**:
            webhook: '**https://hooks.slack.com/services/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**'
            title: $NICK-EKS
            #text: Customized text in slack message
        **pvcMonitor**:
          enabled: true
          interval: 5
          threshold: 70
    EOT
    **kubectl apply -f kwatch-config.yaml**
    
    # 배포
    kubectl apply -f https://raw.githubusercontent.com/abahmed/kwatch/v0.8.5/deploy/**deploy.yaml**

    ```
  
![구성](/Images/eks/eks_o35.png)


- 잘못된 이미지 파드 배포 및 확인
    
  ```bash

    # 터미널1
    watch kubectl get pod
    
    # 잘못된 이미지 정보의 파드 배포
    **kubectl apply -f https://raw.githubusercontent.com/junghoon2/kube-books/main/ch05/nginx-error-pod.yml**
    **kubectl get events -w**
    
    # 이미지 업데이트 방안2 : set 사용 - iamge 등 일부 리소스 값을 변경 가능!
    kubectl set 
    kubectl set image pod nginx-19 nginx-pod=nginx:1.19
    
    # 삭제
    **kubectl delete pod nginx-19**
    ```
    
    <aside>
    👉🏻 파드 + PVC 배포 후 **PVC**의 저장 공간을 70% 이상 채운 후 kwatch **PVC 알람** 발생하는지 테스트 해보자
    
    </aside>
    
    - kwatch 삭제:  `kubectl delete -f https://raw.githubusercontent.com/abahmed/kwatch/v0.8./deploy/deploy.yaml`
    
- `Botkube` - [공홈](https://botkube.io/) [Blog](https://aws.amazon.com/ko/blogs/containers/streaming-kubernetes-events-in-slack/) [Youtube](https://youtu.be/6VTEOOfIbIk)
    
    <aside>
    🚨 아래 **TOKEN**은 **블로깅** 하실때 **가려주시거나 제거**해주시기 바랍니다!
    
    </aside>
    
---

1. 슬랙 앱 설정 : SLACK_API_**BOT_TOKEN** 과 SLACK_API_**APP_TOKEN** 생성 - [Docs](https://docs.botkube.io/installation/slack/)
        
    ```bash
      
      export SLACK_API_BOT_TOKEN='xoxb-YYYY'
      export SLACK_API_APP_TOKEN='xapp-YYYXXXXX'
      
    ```
        
    2. 설치
        
        ```bash
        # repo 추가
        helm repo add botkube https://charts.botkube.io
        helm repo update
        
        # 변수 지정
        export ALLOW_KUBECTL=true
        export ALLOW_HELM=true
        export SLACK_CHANNEL_NAME=webhook3
        
        #
        cat <<EOT > botkube-values.yaml
        actions:
          'describe-created-resource': # kubectl describe
            enabled: true
          'show-logs-on-error': # kubectl logs
            enabled: true
        
        executors:
          k8s-default-tools:
            botkube/helm:
              enabled: true
            botkube/kubectl:
              enabled: true
        EOT
        
        # 설치
        helm install --version **v1.0.0** botkube --namespace botkube --create-namespace \
        --set communications.default-group.socketSlack.enabled=true \
        --set communications.default-group.socketSlack.channels.default.name=${SLACK_CHANNEL_NAME} \
        --set communications.default-group.socketSlack.appToken=${SLACK_API_APP_TOKEN} \
        --set communications.default-group.socketSlack.botToken=${SLACK_API_BOT_TOKEN} \
        --set settings.clusterName=${CLUSTER_NAME} \
        --set 'executors.k8s-default-tools.botkube/kubectl.enabled'=${ALLOW_KUBECTL} \
        --set 'executors.k8s-default-tools.botkube/helm.enabled'=${ALLOW_HELM} \
        -f **botkube-values.yaml** botkube/botkube
        
        # 참고 : 삭제 시
        helm uninstall botkube --namespace botkube

        ```
        
    3. 사용 - [Docs](https://docs.botkube.io/usage/)
        
        ```bash
        # 연결 상태, notifications 상태 확인
        **@Botkube** ping
        **@Botkube** status notifications
        
        # 파드 정보 조회
        **@Botkube** k get pod
        **@Botkube** kc get pod --namespace kube-system
        **@Botkube** kubectl get pod --namespace kube-system -o wide
        
        # Actionable notifications
        **@Botkube** kubectl
        ```
        
    4. 잘못된 이미지 파드 배포 및 확인
        
        ```bash
        # 터미널1
        watch kubectl get pod
        
        # 잘못된 이미지 정보의 파드 배포
        **kubectl apply -f https://raw.githubusercontent.com/junghoon2/kube-books/main/ch05/nginx-error-pod.yml**
        **kubectl get events -w**
        **@Botkube** k get pod
        
        # 이미지 업데이트 방안2 : set 사용 - iamge 등 일부 리소스 값을 변경 가능!
        kubectl set 
        kubectl set image pod nginx-19 nginx-pod=nginx:1.19
        **@Botkube** k get pod
        
        # 삭제
        **kubectl delete pod nginx-19**
        ```
        
    5. 삭제:  `helm uninstall botkube --namespace botkube`
    

`ChatGPT 활용`

https://github.com/robusta-dev/kubernetes-chatgpt-bot

https://github.com/k8sgpt-ai/k8sgpt

</details>






## 프로메테우스-스택



**Prometheus: The Documentary**

https://youtu.be/rT4fJNbfe14

- Prometheus Kubernetes **쌍둥이 음모설** : P8S vs K8S 축약, 둘 다 10글자, 로고 보색 관계(주황 vs 파랑)

`프로메테우스 오퍼레이터` : 프로메테우스 및 프로메테우스 오퍼레이터를 이용하여 메트릭 수집과 알람 기능 실습 ← **최성욱**님이 정리해주셨습니다 👍🏻

[pkos 스터디 4주차 - 메트릭 오픈소스 프로메테우스](https://malwareanalysis.tistory.com/566)

`Thanos 타노드` : 프로메테우스 확장성과 고가용성 제공 ← **한승호**님이 **타노스**에 대해서 잘 정리해주셨습니다 👍🏻

[PKOS 2기 4주차 - 쿠버네티스 모니터링(Kubernetes Monitoring) | HanHoRang Tech Blog](https://hanhorang31.github.io/post/pkos2-4-monitoring/)



<details><summary>소개</summary>

`제공 기능`

- a multi-dimensional [data model](https://prometheus.io/docs/concepts/data_model/) with **time series data**(=**TSDB, 시계열 데이터베이스**) identified by metric name and **key/value** pairs
- **PromQL**, a [flexible query language](https://prometheus.io/docs/prometheus/latest/querying/basics/) to leverage this dimensionality
- no reliance on distributed storage; single server nodes are autonomous
- time series collection happens via a **pull** model over **HTTP** ⇒ **질문** **Push** 와 **Pull** 수집 방식 장단점? - [링크](https://velog.io/@zihs0822/Push-vs-Pull-%EB%AA%A8%EB%8B%88%ED%84%B0%EB%A7%81-%EB%8D%B0%EC%9D%B4%ED%84%B0-%EC%88%98%EC%A7%91-%EB%B0%A9%EC%8B%9D)
- [pushing time series](https://prometheus.io/docs/instrumenting/pushing/) is supported via an intermediary gateway
- targets are discovered via **service discovery** or **static** configuration
- multiple modes of **graphing** and **dashboarding** support

![구성](/Images/eks/eks_o47.png)
https://prometheus.io/docs/introduction/overview/

`구성 요소`

- the main [**Prometheus server**](https://github.com/prometheus/prometheus) which scrapes and stores **time series data**
- [**client libraries**](https://prometheus.io/docs/instrumenting/clientlibs/) for instrumenting application code
- a [**push gateway**](https://github.com/prometheus/pushgateway) for supporting short-lived jobs
- special-purpose [**exporters**](https://prometheus.io/docs/instrumenting/exporters/) for services like HAProxy, StatsD, Graphite, etc.
- an [**alertmanager**](https://github.com/prometheus/alertmanager) to handle alerts
- various support tools




</details>












<details><summary>프로메테우스-스택 설치</summary>

```bash

# 모니터링
kubectl create ns **monitoring**
watch kubectl get pod,pvc,svc,ingress -n monitoring

# 사용 리전의 인증서 ARN 확인 : 정상 상태 확인(만료 상태면 에러 발생!)
**CERT_ARN=`aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text`**
echo $CERT_ARN

****# repo 추가
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# 파라미터 파일 생성
cat <<EOT > monitor-values.yaml
**prometheus**:
  prometheusSpec:
    podMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false
    retention: 5d
    retentionSize: "10GiB"
    **storageSpec**:
      volumeClaimTemplate:
        spec:
          storageClassName: **gp3**
          accessModes: ["ReadWriteOnce"]
          resources:
            requests:
              storage: 30Gi

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
      **alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'**

**grafana**:
  defaultDashboardsTimezone: Asia/Seoul
  adminPassword: prom-operator

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
      **alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'**

  **persistence**:
    enabled: true
    type: sts
    storageClassName: "gp3"
    accessModes:
      - ReadWriteOnce
    size: 20Gi

**defaultRules:
  create: false**
**kubeControllerManager:
  enabled: false
kubeEtcd:
  enabled: false
kubeScheduler:
  enabled: false**
**alertmanager:
  enabled: false**
EOT
cat monitor-values.yaml | yh

# 배포
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version **57.1.0** \
--**set** prometheus.prometheusSpec.scrapeInterval='15s' --**set** prometheus.prometheusSpec.evaluationInterval='15s' \
-f **monitor-values.yaml** --namespace monitoring

# 확인
~~## alertmanager-0 : 사전에 정의한 정책 기반(예: 노드 다운, 파드 Pending 등)으로 시스템 경고 메시지를 생성 후 경보 채널(슬랙 등)로 전송~~
## grafana : 프로메테우스는 메트릭 정보를 저장하는 용도로 사용하며, 그라파나로 시각화 처리
## prometheus-0 : 모니터링 대상이 되는 파드는 ‘exporter’라는 별도의 사이드카 형식의 파드에서 모니터링 메트릭을 노출, pull 방식으로 가져와 내부의 시계열 데이터베이스에 저장
## node-exporter : 노드익스포터는 물리 노드에 대한 자원 사용량(네트워크, 스토리지 등 전체) 정보를 메트릭 형태로 변경하여 노출
## operator : 시스템 경고 메시지 정책(prometheus rule), 애플리케이션 모니터링 대상 추가 등의 작업을 편리하게 할수 있게 CRD 지원
## kube-state-metrics : 쿠버네티스의 클러스터의 상태(kube-state)를 메트릭으로 변환하는 파드
helm list -n monitoring
kubectl get pod,svc,ingress,pvc -n monitoring
kubectl get-all -n monitoring
**kubectl get prometheus,servicemonitors -n monitoring**
~~~~**kubectl get crd | grep monitoring
kubectl df-pv**

```

![구성](/Images/eks/eks_o37.png)
![구성](/Images/eks/eks_o38.png)

- AWS ELB(ALB) 갯수 확인 → Rule 확인(어떻게 여러 도메인 처리를 하는 걸까?) ⇒ HTTP(80) 인입 시 어떻게 처리하나요?
![구성](/Images/eks/eks_o48.png)


- 삭제 명령어

```bash

# helm 삭제
**helm uninstall -n monitoring kube-prometheus-stack**

# crd 삭제
kubectl delete crd alertmanagerconfigs.monitoring.coreos.com
kubectl delete crd alertmanagers.monitoring.coreos.com
kubectl delete crd podmonitors.monitoring.coreos.com
kubectl delete crd probes.monitoring.coreos.com
kubectl delete crd prometheuses.monitoring.coreos.com
kubectl delete crd prometheusrules.monitoring.coreos.com
kubectl delete crd servicemonitors.monitoring.coreos.com
kubectl delete crd thanosrulers.monitoring.coreos.com

```


</details>





<details><summary>[Amazon EKS] AWS CNI Metrics 수집을 위한 사전 설정  </summary>
- [링크](https://grafana.com/grafana/dashboards/16032-aws-cni-metrics/) 


```bash

# PodMonitor 배포
cat <<EOF | kubectl create -f -
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata:
  name: aws-cni-metrics
  namespace: kube-system
spec:
  jobLabel: k8s-app
  namespaceSelector:
    matchNames:
    - kube-system
  podMetricsEndpoints:
  - interval: 30s
    path: /metrics
    port: metrics
  selector:
    matchLabels:
      k8s-app: aws-node
EOF

# PodMonitor 확인
kubectl get podmonitor -n kube-system
**kubectl get podmonitor -n kube-system aws-cni-metrics -o yaml | kubectl neat | yh**
apiVersion: monitoring.coreos.com/v1
kind: PodMonitor
metadata: 
  name: aws-cni-metrics
  namespace: kube-system
spec: 
  jobLabel: **k8s-app**
  **namespaceSelector**: 
    matchNames: 
    - **kube-system**
  **podMetricsEndpoints**: 
  - interval: 30s
    path: /metrics
    port: metrics
  **selector**: 
    matchLabels: 
      **k8s-app: aws-node**
          
# metrics url 접속 확인
**curl -s $N1:61678/metrics | grep '^awscni'**
awscni_add_ip_req_count 10
awscni_assigned_ip_addresses 8
awscni_assigned_ip_per_cidr{cidr="192.168.1.117/32"} 1
awscni_assigned_ip_per_cidr{cidr="192.168.1.131/32"} 1
awscni_assigned_ip_per_cidr{cidr="192.168.1.184/32"} 1
awscni_assigned_ip_per_cidr{cidr="192.168.1.210/32"} 0
awscni_assigned_ip_per_cidr{cidr="192.168.1.243/32"} 1
awscni_assigned_ip_per_cidr{cidr="192.168.1.247/32"} 1
awscni_assigned_ip_per_cidr{cidr="192.168.1.38/32"} 1
...

```

![구성](/Images/eks/eks_o39.png)

- 프로메테우스 Target , job (aws-cni 검색)

![구성](/Images/eks/eks_o42.png)

<aside>
❓ **ServiceMonitor** vs **PodMonitor** 은 어떤 차이가 있을까?

</aside>

https://github.com/prometheus-operator/prometheus-operator/issues/3119


</details>



<details><summary>프로메테우스 기본 사용 : 모니터링 그래프</summary>

- 모니터링 대상이 되는 서비스는 일반적으로 자체 웹 서버의 /metrics 엔드포인트 경로에 다양한 메트릭 정보를 노출
- 이후 프로메테우스는 해당 경로에 http get 방식으로 메트릭 정보를 가져와 TSDB 형식으로 저장


```bash

# 아래 처럼 프로메테우스가 각 서비스의 9100 접속하여 메트릭 정보를 수집
kubectl get node -owide
kubectl get svc,ep -n monitoring kube-prometheus-stack-prometheus-node-exporter

# 노드의 9100번의 /metrics 접속 시 다양한 메트릭 정보를 확인할수 있음 : 마스터 이외에 워커노드도 확인 가능
ssh ec2-user@$N1 curl -s localhost:**9100**/metrics

```
- 프로메테우스 ingress 도메인으로 웹 접속

```bash

# ingress 확인
kubectl get ingress -n monitoring kube-prometheus-stack-prometheus
kubectl describe ingress -n monitoring kube-prometheus-stack-prometheus

# 프로메테우스 ingress 도메인으로 웹 접속

echo -e "Prometheus Web URL = https://prometheus.$MyDomain"

# 웹 상단 주요 메뉴 설명
1. 경고(Alert) : 사전에 정의한 시스템 경고 정책(Prometheus Rules)에 대한 상황
2. 그래프(Graph) : 프로메테우스 자체 검색 언어 PromQL을 이용하여 메트릭 정보를 조회 -> 단순한 그래프 형태 조회
3. 상태(Status) : 경고 메시지 정책(Rules), 모니터링 대상(Targets) 등 다양한 프로메테우스 설정 내역을 확인 > 버전(2.42.0)
4. 도움말(Help)

```

![구성](/Images/eks/eks_o41.png)



- 쿼리 입력 옵션
    - Use local time : 출력 시간을 로컬 타임으로 변경
    - Enable query history : PromQL 쿼리 히스토리 활성화
    - Enable autocomplete : 자동 완성 기능 활성화
    - Enable highlighting : 하이라이팅 기능 활성화
    - Enable linter : ?
- 프로메테우스 설정(Configuration) 확인 : Status → Runtime & Build Information 클릭
    - **Storage retention** : 5d or 10GiB → 메트릭 저장 기간이 5일 경과 혹은 10GiB 이상 시 오래된 것부터 삭제 ⇒ helm 파라미터에서 수정 가능
- 프로메테우스 설정(Configuration) 확인 : Status → Command-Line Flags 클릭
    - -log.level : info
    - -storage.tsdb.retention.size : 10GiB
    - -storage.tsdb.retention.time : 5d
- 프로메테우스 설정(Configuration) 확인 : Status → Configuration ⇒ “node-exporter” 검색
    - **job name** 을 기준으로 scraping
    
    ```bash
    **global**:
      scrape_interval: 15s     # 메트릭 가져오는(scrape) 주기
      scrape_timeout: 10s      # 메트릭 가져오는(scrape) 타임아웃
      evaluation_interval: 15s # alert 보낼지 말지 판단하는 주기
    ...
    - **job_name**: serviceMonitor/monitoring/**kube-prometheus-stack-prometheus-node-exporter**/0
      scrape_interval: 30s
      scrape_timeout: 10s
      **metrics_path**: /metrics
      **scheme**: http
    ...
    **kubernetes_sd_configs**:    # 서비스 디스커버리(SD) 방식을 이용하고, 파드의 엔드포인트 List 자동 반영
      - role: **endpoints**
        kubeconfig_file: ""
        follow_redirects: true
        enable_http2: true
        namespaces:
          own_namespace: false
          names:
          - monitoring        # 서비스 엔드포인트가 속한 네임 스페이스 이름을 지정, 서비스 네임스페이스가 속한 포트 번호를 구분하여 메트릭 정보를 가져옴
    ```



![구성](/Images/eks/eks_o43.png)

![구성](/Images/eks/eks_o44.png)
![구성](/Images/eks/eks_o45.png)
![구성](/Images/eks/eks_o46.png)



- 전체 메트릭 대상(Targets) 확인 : Status → Targets
    - 해당 스택은 ‘노드-익스포터’, cAdvisor, 쿠버네티스 전반적인 현황 이외에 다양한 메트릭을 포함
    - 현재 각 Target 클릭 시 메트릭 정보 확인 : 아래 예시
        
        ```bash

        # serviceMonitor/monitoring/kube-prometheus-stack-kube-proxy/0 (3/3 up) 중 노드1에 Endpoint 접속 확인 (접속 주소는 실습 환경에 따라 다름)
        **curl -s http://192.168.1.216:10249/metrics | tail -n 5**
        rest_client_response_size_bytes_bucket{host="006fc3f3f0730a7fb3fdb3181f546281.gr7.ap-northeast-2.eks.amazonaws.com",verb="POST",le="4.194304e+06"} 1
        rest_client_response_size_bytes_bucket{host="006fc3f3f0730a7fb3fdb3181f546281.gr7.ap-northeast-2.eks.amazonaws.com",verb="POST",le="1.6777216e+07"} 1
        rest_client_response_size_bytes_bucket{host="006fc3f3f0730a7fb3fdb3181f546281.gr7.ap-northeast-2.eks.amazonaws.com",verb="POST",le="+Inf"} 1
        rest_client_response_size_bytes_sum{host="006fc3f3f0730a7fb3fdb3181f546281.gr7.ap-northeast-2.eks.amazonaws.com",verb="POST"} 626
        rest_client_response_size_bytes_count{host="006fc3f3f0730a7fb3fdb3181f546281.gr7.ap-northeast-2.eks.amazonaws.com",verb="POST"} 1
        
        ****# serviceMonitor/monitoring/kube-prometheus-stack-api-server/0 (2/2 up) 중 Endpoint 접속 확인 (접속 주소는 실습 환경에 따라 다름) 
        **>> 해당 IP주소는 어디인가요?, 왜 apiserver endpoint는 2개뿐인가요? , 아래 메트릭 수집이 되게 하기 위해서는 어떻게 하면 될까요?
        curl -s https://192.168.1.53/metrics | tail -n 5
        ...**
        
        # 그외 다른 타켓의 Endpoint 로 접속 확인 가능 : 예시) 아래는 coredns 의 Endpoint 주소 (접속 주소는 실습 환경에 따라 다름)
        **curl -s http://192.168.1.75:9153/metrics | tail -n 5**
        # TYPE process_virtual_memory_bytes gauge
        process_virtual_memory_bytes 7.79350016e+08
        # HELP process_virtual_memory_max_bytes Maximum amount of virtual memory available in bytes.
        # TYPE process_virtual_memory_max_bytes gauge
        process_virtual_memory_max_bytes 1.8446744073709552e+19

        ```
        
![구성](/Images/eks/eks_o42.png)


- 프로메테우스 설정(Configuration) 확인 : Status → Service Discovery : 모든 endpoint 로 도달 가능 시 **자동 발견**!, 도달 규칙은 설정Configuration 파일에 정의
    - 예) serviceMonitor/monitoring/kube-prometheus-stack-apiserver/0 경우 해당 __**address**__="*192.168.1.53*:443" **도달 가능 시 자동 발견됨**

- 메트릭을 그래프(Graph)로 조회 : Graph - 아래 PromQL 쿼리(전체 클러스터 노드의 CPU 사용량 합계)입력 후 조회 → Graph 확인
    - 혹은 지구 아이콘(Metrics Explorer) 클릭 시 전체 메트릭 출력되며, 해당 메트릭 클릭해서 확인
    
    ```bash
    1- avg(rate(node_cpu_seconds_total{mode="idle"}[1m]))
    ```
    

    ```bash
    # 노드 메트릭
    node 입력 후 자동 출력되는 메트릭 확인 후 선택
    node_boot_time_seconds
    
    # kube 메트릭
    kube 입력 후 자동 출력되는 메트릭 확인 후 선택
    ```
![구성](/Images/eks/eks_o54.png)    
![구성](/Images/eks/eks_o46.png)
![구성](/Images/eks/eks_o47.png)
![구성](/Images/eks/eks_o48.png)
![구성](/Images/eks/eks_o49.png)
![구성](/Images/eks/eks_o50.png)
![구성](/Images/eks/eks_o51.png)
![구성](/Images/eks/eks_o52.png)
![구성](/Images/eks/eks_o53.png)


</details>



<details><summary>쿼리</summary>
-  애플리케이션 - NGINX 웹서버 애플리케이션 모니터링 설정 및 접속
- 서비스모니터 동작
![구성](/Images/eks/eks_o100.png)
> https://containerjournal.com/topics/container-management/cluster-monitoring-with-prometheus-operator/

- nginx 를 helm 설치 시 프로메테우스 익스포터 Exporter 옵션 설정 시 자동으로 nginx 를 프로메테우스 모니터링에 등록 가능!
    - 프로메테우스 설정에서 nginx 모니터링 관련 내용을 서비스 모니터 CRD로 추가 가능!
- 기존 애플리케이션 파드에 프로메테우스 모니터링을 추가하려면 사이드카 방식을 사용하며 exporter 컨테이너를 추가!
- nginx 웹 서버(with helm)에 metrics 수집 설정 추가 - [Helm](https://artifacthub.io/packages/helm/bitnami/nginx)

```bash

# 모니터링
**watch -d "kubectl get pod; echo; kubectl get servicemonitors -n monitoring"**

# 파라미터 파일 생성 : 서비스 모니터 방식으로 nginx 모니터링 대상을 등록하고, export 는 9113 포트 사용
cat <<EOT > ~/nginx_metric-values.yaml
**metrics**:
  enabled: true

  service:
    port: 9113

  **serviceMonitor**:
    enabled: true
    namespace: monitoring
    interval: 10s
EOT

# 배포
helm **upgrade** nginx bitnami/nginx **--reuse-values** -f nginx_metric-values.yaml

# 확인
kubectl get pod,svc,ep
kubectl get servicemonitor -n monitoring nginx
kubectl get servicemonitor -n monitoring nginx -o json | jq

# 메트릭 확인 >> 프로메테우스에서 Target 확인
NGINXIP=$(kubectl get pod -l app.kubernetes.io/instance=nginx -o jsonpath={.items[0].status.podIP})
curl -s http://$NGINXIP:9113/metrics # nginx_connections_active Y 값 확인해보기
curl -s http://$NGINXIP:9113/metrics | grep ^nginx_connections_active

# nginx 파드내에 컨테이너 갯수 확인
kubectl get pod -l app.kubernetes.io/instance=nginx
kubectl describe pod -l app.kubernetes.io/instance=nginx

# 접속 주소 확인 및 접속
echo -e "Nginx WebServer URL = https://nginx.$MyDomain"
curl -s https://nginx.$MyDomain
kubectl logs deploy/nginx -f

# 반복 접속
while true; do curl -s https://nginx.$MyDomain -I | head -n 1; date; sleep 1; done

```

- 서비스 모니터링 생성 후 **3분** 정도 후에 **프로메테우스 웹서버**에서 State → Targets 에 nginx 서비스 모니터 추가 확인

![구성](/Images/eks/eks_o56.png)
![구성](/Images/eks/eks_o57.png)
![구성](/Images/eks/eks_o58.png)



- 설정이 자동으로 반영되는 원리 : 주요 config 적용 필요 시 reloader 동작!

```bash
#
**kubectl describe pod -n monitoring prometheus-kube-prometheus-stack-prometheus-0**
...
  **config-reloader**:
    Container ID:  containerd://55ef5f8170f20afd38c01f136d3e5674115b8593ce4c0c30c2f7557e702ee852
    Image:         quay.io/prometheus-operator/prometheus-config-reloader:v0.72.0
    Image ID:      quay.io/prometheus-operator/prometheus-config-reloader@sha256:89a6c7d3fd614ee1ed556f515f5ecf2dba50eec9af418ac8cd129d5fcd2f5c18
    Port:          8080/TCP
    Host Port:     0/TCP
    Command:
      /bin/prometheus-config-reloader
    Args:
      --listen-address=:8080
      --reload-url=http://127.0.0.1:9090/-/reload
      --config-file=/etc/prometheus/config/prometheus.yaml.gz
      --config-envsubst-file=/etc/prometheus/config_out/prometheus.env.yaml
      --watched-dir=/etc/prometheus/rules/prometheus-kube-prometheus-stack-prometheus-rulefiles-0
...
```

- 쿼리 : 애플리케이션, Graph → nginx_ 입력 시 다양한 메트릭 추가 확인 : nginx_connections_active 등

```bash
# nginx scale out : Targets 확인
**kubectl scale deployment nginx --replicas 2**

# 쿼리 Table -> Graph
**nginx**_up
**nginx**_http_requests_total
**nginx**_connections_active

```

![구성](/Images/eks/eks_o54.png)
![구성](/Images/eks/eks_o55.png)
![구성](/Images/eks/eks_o56.png)
![구성](/Images/eks/eks_o57.png)
![구성](/Images/eks/eks_o58.png)
![구성](/Images/eks/eks_o59.png)
![구성](/Images/eks/eks_o60.png)
![구성](/Images/eks/eks_o61.png)
![구성](/Images/eks/eks_o62.png)



</details>



<details><summary>PromQL</summary>

- [중급] **PromQL**
- 프로메테우스 메트릭 종류 (4종) : Counter, Gauge, Histogram, Summary  - [Link](https://prometheus.io/docs/concepts/metric_types/) [Blog](https://gurumee92.tistory.com/241)
- **게이지** Gauge : 특정 시점의 값을 표현하기 위해서 사용하는 메트릭 타입, CPU 온도나 메모리 사용량에 대한 현재 시점 값
- **카운터** Counter : 누적된 값을 표현하기 위해 사용하는 메트릭 타입, 증가 시 구간 별로 변화(추세) 확인, 계속 증가 → 함수 등으로 활용
- **서머리** Summary : 구간 내에 있는 메트릭 값의 빈도, 중앙값 등 통계적 메트릭
- **히스토그램** Histogram : 사전에 미리 정의한 구간 내에 있는 메트릭 값의 빈도를 측정 → 함수로 측정 포맷을 변경
- PromQL Query - [Docs](https://prometheus.io/docs/prometheus/latest/querying/basics/) [Operator](https://prometheus.io/docs/prometheus/latest/querying/operators/) [Example](https://prometheus.io/docs/prometheus/latest/querying/examples/)
        - Label Matchers : = , ! = , =~ 정규표현식
        
```bash
        # 예시
        node_memory_Active_bytes
        node_memory_Active_bytes{instance="192.168.1.188:9100"}
        node_memory_Active_bytes{instance**!=**"192.168.1.188:9100"}
        
        # 정규표현식
        node_memory_Active_bytes{instance=~"192.168.+"}
        node_memory_Active_bytes{instance=~"192.168.1.+"}
        
        # 다수 대상
        node_memory_Active_bytes{instance=~"192.168.1.188:9100|192.168.2.170:9100"}
        node_memory_Active_bytes{instance!~"192.168.1.188:9100|192.168.2.170:9100"}
        
        # 여러 조건 AND
        kube_deployment_status_replicas_available{namespace="kube-system"}
        kube_deployment_status_replicas_available{namespace="kube-system", deployment="coredns"}
```
        
- Binary Operators 이진 연산자 - [Link](https://prometheus.io/docs/prometheus/latest/querying/operators/#binary-operators)
- 산술 이진 연산자 : + - * / * ^
- 비교 이진 연산자 : = =  ! = > < > = < =
- 논리/집합 이진 연산자 : and 교집합 , or 합집합 , unless 차집합
        
```bash
        # 산술 이진 연산자 : + - * / * ^
        node_memory_Active_bytes
        node_memory_Active_bytes**/1024**
        node_memory_Active_bytes**/1024/1024**
        
        # 비교 이진 연산자 : = =  ! = > < > = < =
        nginx_http_requests_total
        nginx_http_requests_total > 100
        nginx_http_requests_total > 10000
        
        # 논리/집합 이진 연산자 : and 교집합 , or 합집합 , unless 차집합
        kube_pod_status_ready
        kube_pod_container_resource_requests
        
        kube_pod_status_ready == 1
        kube_pod_container_resource_requests > 1
        
        kube_pod_status_ready == 1 or kube_pod_container_resource_requests > 1
        kube_pod_status_ready == 1 and kube_pod_container_resource_requests > 1
```
**Aggregation Operators** 집계 연산자 - [Link](https://prometheus.io/docs/prometheus/latest/querying/operators/#aggregation-operators)
  - `sum` (calculate sum over dimensions) : 조회된 값들을 모두 더함
  - `min` (select minimum over dimensions) : 조회된 값에서 가장 작은 값을 선택
  - `max` (select maximum over dimensions) : 조회된 값에서 가장 큰 값을 선택
  - `avg` (calculate the average over dimensions) : 조회된 값들의 평균 값을 계산
  - `group` (all values in the resulting vector are 1) : 조회된 값을 모두 ‘1’로 바꿔서 출력
  - `stddev` (calculate population standard deviation over dimensions) : 조회된 값들의 모 표준 편차를 계산
  - `stdvar` (calculate population standard variance over dimensions) : 조회된 값들의 모 표준 분산을 계산
  - `count` (count number of elements in the vector) : 조회된 값들의 갯수를 출력 / 인스턴스 벡터에서만 사용 가능
  - `count_values` (count number of elements with the same value) : 같은 값을 가지는 요소의 갯수를 출력
  - `bottomk` (smallest k elements by sample value) : 조회된 값들 중에 가장 작은 값들 k 개 출력
  - `topk` (largest k elements by sample value) : 조회된 값들 중에 가장 큰 값들 k 개 출력
  - `quantile` (calculate φ-quantile (0 ≤ φ ≤ 1) over dimensions) : 조회된 값들을 사분위로 나눠서 (0 < $ < 1)로 구성하고, $에 해당 하는 요소들을 출력

```bash
        #
        node_memory_Active_bytes
        
        # 출력 값 중 Top 3
        topk(3, node_memory_Active_bytes)
        
        # 출력 값 중 하위 3
        bottomk(3, node_memory_Active_bytes)
        bottomk(3, node_memory_Active_bytes>0)
        
        # node 그룹별: **by**
        node_cpu_seconds_total
        node_cpu_seconds_total{mode="user"}
        node_cpu_seconds_total{mode="system"}
        
        avg(node_cpu_seconds_total)
        avg(node_cpu_seconds_total) by (instance)
        avg(node_cpu_seconds_total{mode="user"}) by (instance)
        avg(node_cpu_seconds_total{mode="system"}) by (instance)
        
        #
        nginx_http_requests_total
        sum(nginx_http_requests_total)
        sum(nginx_http_requests_total) by (instance)
        
        # 특정 내용 제외하고 출력 : **without**
        nginx_http_requests_total
        sum(nginx_http_requests_total) without (instance)
        sum(nginx_http_requests_total) without (instance,container,endpoint,job,namespace)
```
        
        - Time series selectors : Instant/Range vector selectors, Time Durations, Offset modifier, @ modifier - [Link](https://prometheus.io/docs/prometheus/latest/querying/basics/#time-series-selectors)
            - **인스턴스 벡터** Instant Vector : **시점**에 대한 메트릭 값만을 가지는 데이터 타입
            - **레인지 벡터** Range Vector : **시간의 구간**을 가지는 데이터 타입
            - 시간 단위 : ms, s, **m(주로 분 사용)**, h, d, w, y
        
```bash
        # 시점 데이터
        node_cpu_seconds_total
        
        # 15초 마다 수집하니 아래는 지난 4회차/8회차의 값 출력
        node_cpu_seconds_total[**1m**]
        node_cpu_seconds_total[**2m**]
```
        
- 활용
        
```bash
        # 서비스 정보 >> 네임스페이스별 >> cluster_ip 별
        kube_service_info
        count(kube_service_info)
        count(kube_service_info) by (namespace)
        count(kube_service_info) by (cluster_ip)
        
        # 컨테이너가 사용 메모리 -> 파드별
        container_memory_working_set_bytes
        sum(container_memory_working_set_bytes)
        **sum(container_memory_working_set_bytes) by (pod)**
        **topk(5**,sum(container_memory_working_set_bytes) by (pod))
        **topk(5**,sum(container_memory_working_set_bytes) by (pod))/1024/1024

```



</details>




## 그라파나

- **[Grafana open source software](https://grafana.com/oss/)** enables you to query, visualize, alert on, and explore your metrics, logs, and traces wherever they are stored.
    - Grafana OSS provides you with tools to turn your time-series database (TSDB) data into insightful graphs and visualizations.
- 그라파나는 **시각화 솔루**션으로 데이터 자체를 저장하지 않음 → 현재 실습 환경에서는 **데이터 소스**는 **프로메테우스**를 사용
- 접속 정보 확인 및 로그인 : 기본 계정 - **admin / prom-operator**

```bash
# 그라파나 버전 확인
kubectl exec -it -n monitoring deploy/kube-prometheus-stack-grafana -- **grafana-cli --version**
*grafana cli version **10.4.0***

# ingress 확인
kubectl get ingress -n monitoring kube-prometheus-stack-grafana
kubectl describe ingress -n monitoring kube-prometheus-stack-grafana

# ingress 도메인으로 웹 접속 : 기본 계정 - **admin / prom-operator**
echo -e "Grafana Web URL = https://grafana.$MyDomain"
```

- 우측 상단  : admin 사용자의 개인 설정

![구성](/Images/eks/eks_o63.png)

1. Search dashboards : 대시보드 검색
2. Starred : 즐겨찾기 대시보드
3. Dashboards : 대시보드 전체 목록 확인
4. Explore : 쿼리 언어 PromQL를 이용해 메트릭 정보를 그래프 형태로 탐색
5. Alerting : 경고, 에러 발생 시 사용자에게 경고를 전달
6. Connections : 설정, 예) 데이터 소스 설정 등
7. Administartor : 사용자, 조직, 플러그인 등 설정

- Connections → Your connections : 스택의 경우 자동으로 프로메테우스를 데이터 소스로 추가해둠 ← 서비스 주소 확인
    
![구성](/Images/eks/eks_o64.png)
    

    
```bash

    # 서비스 주소 확인
    **kubectl get svc,ep -n monitoring kube-prometheus-stack-prometheus**
    NAME                                       TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)    AGE
    service/kube-prometheus-stack-prometheus   ClusterIP   10.100.143.5   <none>        9090/TCP   21m
    
    NAME                                         ENDPOINTS           AGE
    endpoints/kube-prometheus-stack-prometheus   192.168.2.93:9090   21m
```
    
- 해당 데이터 소스 접속 확인
    
```bash

    # 테스트용 파드 배포
    cat <<EOF | kubectl create -f -
    apiVersion: v1
    kind: Pod
    metadata:
      name: netshoot-pod
    spec:
      containers:
      - name: netshoot-pod
        image: nicolaka/netshoot
        command: ["tail"]
        args: ["-f", "/dev/null"]
      terminationGracePeriodSeconds: 0
    EOF
    kubectl get pod netshoot-pod
    
    # 접속 확인
    **kubectl exec -it netshoot-pod -- nslookup kube-prometheus-stack-prometheus.monitoring**
    kubectl exec -it netshoot-pod -- curl -s kube-prometheus-stack-prometheus.monitoring:9090/graph -v ; echo
    
    # 삭제
    **kubectl delete pod** netshoot-pod

```

<details><summary>대시보드 사용하기</summary>

`기본 대시보드`

- 스택을 통해서 설치된 기본 대시보드 확인 : Dashboards → Browse
- (대략) 분류 : 자원 사용량 - Cluster/POD Resources, 노드 자원 사용량 - Node Exporter, 주요 애플리케이션 - CoreDNS 등
    - 확인해보자 - K8S / CR / **Cluster**, Node Exporter / Use Method / **Cluster**

`공식 대시보드 가져오기` - [링크](https://grafana.com/grafana/dashboards/?pg=docs-grafana-latest-dashboards) [추천](https://grafana.com/orgs/imrtfm/dashboards)

- [**Kubernetes / Views / Global**] Dashboard → New → Import → **15757** 력입력 후 Load ⇒ 데이터소스(Prometheus 선택) 후 **Import** 클릭

- **[1 Kubernetes All-in-one Cluster Monitoring KR]** Dashboard → New → Import → **17900** 입력 후 Load ⇒ 데이터소스(Prometheus 선택) 후 **Import** 클릭


![구성](/Images/eks/eks_o66.png)
![구성](/Images/eks/eks_o68.png)
![구성](/Images/eks/eks_o67.png)

- 해당 대시보드에서 값이 안 나오는 문제 해결하기 
1.  Edit 창 열기
![구성](/Images/eks/eks_o70.png)
2. 쿼리의 메인 문을 복사
![구성](/Images/eks/eks_o72.png)
3. Promethus에서 검색 해보기
![구성](/Images/eks/eks_o73.png)
4. 원인 파악 (aws 는  "Instance"로 표시됨 이 부분을 수정 **Node** -> **instance**)
![구성](/Images/eks/eks_o74.png)
5. 값 수정 후 저장
![구성](/Images/eks/eks_o75.png)
6. 저장
![구성](/Images/eks/eks_o75.png)

- 해당 패널에서 Edit → 아래 **수정** 쿼리 입력 후 **Run queries** 클릭 → 상단 **Save** 후 **Apply**
    
```bash

    sum by (node) (irate(node_cpu_seconds_total{mode!~"guest.*|idle|iowait", node="$node"}[5m]))

```
    
```bash

    node_cpu_seconds_total
    node_cpu_seconds_total{mode!~"guest.*|idle|iowait"}
    avg(node_cpu_seconds_total{mode!~"guest.*|idle|iowait"}) by (**node**)
    avg(node_cpu_seconds_total{mode!~"guest.*|idle|iowait"}) by (**instance**)
    
    # 수정
    sum by (instance) (irate(node_cpu_seconds_total{mode!~"guest.*|idle|iowait", **instance**="$**instance**"}[5m]))

```
    
```bash

    # 수정 : 메모리 점유율
    (node_memory_MemTotal_bytes{instance="$instance"}-node_memory_MemAvailable_bytes{instance="$instance"})/node_memory_MemTotal_bytes{instance="$instance"}
    
    # 수정 : 디스크 사용률
    sum(node_filesystem_size_bytes{instance="$instance"} - node_filesystem_avail_bytes{instance="$instance"}) by (node) / sum(node_filesystem_size_bytes{instance="$instance"}) by (node)

```


- [**Node Exporter Full**] Dashboard → New → Import → **1860** 입력 후 Load ⇒ 데이터소스(Prometheus 선택) 후 **Import** 클릭
- [**Node Exporter for Prometheus Dashboard based on 11074] 15172**
- kube-state-metrics-v2 가져와보자 : **Dashboard ID copied!** (13332) 클릭 - [링크](https://grafana.com/grafana/dashboards/13332-kube-state-metrics-v2/)
    - [**kube-state-metrics-v2**] Dashboard → New → Import → **13332** 입력 후 Load ⇒ 데이터소스(Prometheus 선택) 후 **Import** 클릭
- [Amazon EKS] **AWS CNI Metrics 16032** - [링크](https://grafana.com/grafana/dashboards/16032-aws-cni-metrics/)
    
    ```bash
    # PodMonitor 배포
    cat <<EOF | kubectl create -f -
    apiVersion: monitoring.coreos.com/v1
    kind: **PodMonitor**
    metadata:
      name: aws-cni-metrics
      namespace: kube-system
    spec:
      jobLabel: k8s-app
      namespaceSelector:
        matchNames:
        - kube-system
      podMetricsEndpoints:
      - interval: 30s
        path: /metrics
        port: metrics
      selector:
        matchLabels:
          k8s-app: aws-node
    EOF
    
    # PodMonitor 확인
    kubectl get podmonitor -n kube-system
    ```
  
- NGINX 애플리케이션 모니터링 **대시보드 추가**
    - 그라파나에 **12708** 대시보드 추가 

</details>


<details><summary>직접 패널 만들기</summary>
https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/

- Graphs & charts
    - [Time series](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/time-series/) is the default and main Graph visualization.
    - [State timeline](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/state-timeline/) for state changes over time.
    - [Status history](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/status-history/) for periodic state over time.
    - [Bar chart](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-chart/) shows any categorical data.
    - [Histogram](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/histogram/) calculates and shows value distribution in a bar chart.
    - [Heatmap](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/heatmap/) visualizes data in two dimensions, used typically for the magnitude of a phenomenon.
    - [Pie chart](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/pie-chart/) is typically used where proportionality is important.
    - [Candlestick](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/candlestick/) is typically for financial data where the focus is price/data movement.
    - [Gauge](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/gauge/) is the traditional rounded visual showing how far a single metric is from a threshold.
- Stats & numbers
    - [Stat](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/stat/) for big stats and optional sparkline.
    - [Bar gauge](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-gauge/) is a horizontal or vertical bar gauge.
- Misc
    - [Table](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/table/) is the main and only table visualization.
    - [Logs](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/logs/) is the main visualization for logs.
    - [Node graph](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/node-graph/) for directed graphs or networks.
    - [Traces](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/traces/) is the main visualization for traces.
    - [Flame graph](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/flame-graph/) is the main visualization for profiling.
    - [Canvas](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/canvas/) allows you to explicitly place elements within static and dynamic layouts.
    - [Geomap](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/geomap/) helps you visualize geospatial data.
- Widgets
    - [Dashboard list](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/dashboard-list/) can list dashboards.
    - [Alert list](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/alert-list/) can list alerts.
    - [Text](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/text/) can show markdown and html.
    - [News](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/news/) can show RSS feeds.
- 실습 준비 : 신규 대시보스 생성 → 패널 생성(Code 로 변경) → 쿼리 입력 후 Run queries 클릭 후 오른쪽 상단 Apply 클릭 → 대시보드 상단 저장
1. [Time series](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/time-series/) : 아래 쿼리 입력 후 오른쪽 입력 → Title(**노드별 5분간 CPU 사용 변화율**)
    
```bash
    node_cpu_seconds_total
    **rate**(node_cpu_seconds_total[**5m**])
    **sum**(rate(node_cpu_seconds_total[5m]))
    sum(rate(node_cpu_seconds_total[5m])) **by (instance)**
```
    

![구성](/Images/eks/eks_o77.png)
![구성](/Images/eks/eks_o78.png)
- **Time Series 선택**
![구성](/Images/eks/eks_o76.png)
- 위 쿼리값 입력
![구성](/Images/eks/eks_o79.png)
- 저장
![구성](/Images/eks/eks_o80.png)
![구성](/Images/eks/eks_o82.png)

2. [Bar chart](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/bar-chart/) : Add → Visualization 오른쪽**(Bar chart**) ⇒ 쿼리 Options : Format(Table), Type(Instance) → Title(네임스페이스 별 디플로이먼트 갯수)
    
```bash
    kube_deployment_status_replicas_available
    **count**(kube_deployment_status_replicas_available) **by (namespace)**
```
    
![구성](/Images/eks/eks_o85.png)
![구성](/Images/eks/eks_o86.png)
![구성](/Images/eks/eks_o87.png)
![구성](/Images/eks/eks_o88.png)



3. [Stat](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/stat/) : Add → Visualization 오른쪽(**Stat**) → Title(nginx 파드 수)
    
```bash
    kube_deployment_spec_replicas
    kube_deployment_spec_replicas{deployment="nginx"}
    
    # scale out
    kubectl scale deployment nginx --replicas 6
```


![구성](/Images/eks/eks_o88.png)




4. [Gauge](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/gauge/) : Add → Visualization 오른쪽(**Gauge**) → Title(노드 별 1분간 CPU 사용률)
    
```bash
    node_cpu_seconds_total{mode!~"guest.*|idle|iowait"}[1m]
    
    node_cpu_seconds_total
    node_cpu_seconds_total{mode="idle"}
    node_cpu_seconds_total{mode="idle"}[1m]
    rate(node_cpu_seconds_total{mode="idle"}[1m])
    avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) by (instance)
    1 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) by (instance))
```
    

![구성](/Images/eks/eks_o89.png)


5. [Table](https://grafana.com/docs/grafana/latest/panels-visualizations/visualizations/table/) : Add → Visualization 오른쪽(**Table**) ⇒ 쿼리 Options : Format(Table), Type(Instance) → Title(노드 OS 정보)
    
```bash
    node_os_info
```
    
- Transform data → Organize fields by name : id_like, instance, name, pretty_name



![구성](/Images/eks/eks_o90.png)
- 원하는 퀄럼만 출력
![구성](/Images/eks/eks_o91.png)


</details>

## 그라파나 얼럿 Alert

💡 **그라파나 9.4 버전**이 2월 28일 출시 - [링크](https://grafana.com/blog/2023/02/28/grafana-9.4-release/) ⇒ **Alerting** 기능이 강화되었고, **이미지 알람** 기능도 제공 - [링크](https://grafana.com/docs/grafana/latest/alerting/manage-notifications/images-in-notifications/)
**그라파나 9.5 버전**이 Alerting 기능 업데이트 - [링크](https://grafana.com/blog/2023/04/26/grafana-9.5-release/)


<details><summary>실습</summary>

1. 그라파나 → Alerting → Alert ruels → Create alert rule : nginx 웹 요청 1분 동안 누적 60 이상 시 Alert 설정

![구성](/Images/eks/eks_o92.png)
![구성](/Images/eks/eks_o93.png)
![구성](/Images/eks/eks_o94.png)
- 아래 Folder 과 Evaluation group(1m), Pending period(1m) 은 +Add new 클릭 후 신규로 만들어 주자
- 오른쪽 상단 `Save and exit` 클릭

![구성](/Images/eks/eks_o95.png)





2. Contact points → Add contact point 클릭
- Integration : 슬랙
- Webhook URL : 아래 주소 입력
    
    ```bash
    **https://hooks.slack.com/services/T03G23CRBNZ/B06HS19UDK2/dZj9QCVJZvraFHwPWcaI~!!@!~~**
    ```
    
- Optional Slack settings → Username : 메시지 구분을 위해서 각자 자신의 닉네임 입력
- 오른쪽 상단 : Test 해보고 저장

![구성](/Images/eks/eks_o96.png)
![구성](/Images/eks/eks_o97.png)

3. Notification policies : 기본 정책 수정 Edit - Default contact point(slack)

![구성](/Images/eks/eks_o98.png)
![구성](/Images/eks/eks_o99.png)



</details>


## 로깅 
 Grafana Loki 실습 정리 - [Link](https://grafana.com/docs/loki/latest/?pg=oss-loki&plcmt=quick-links)

<details><summary>참조내용</summary>

Grafana with Loki 에서 로그 데이터로 알람 발생하기

[How to create alerts with log data | Grafana Labs](https://grafana.com/tutorials/create-alerts-with-logs/)

https://jennifersoft.com/ko/blog/tech/2024-01-17-kubernetes-17/

https://kschoi728.tistory.com/74

https://whchoi98.gitbook.io/k8s/observability/loki

https://velog.io/@alli-eunbi/cgpfiy6q

</details>


##  Tracing
[Tracing - OpenTelemetry + Tempo](https://jerryljh.tistory.com/113)


## kubecost

<details><summary>설명</summary>

- `소개` : **OpenCost** [링크](https://www.opencost.io/)를 기반으로 구축되었으며 AWS에서 적극 지원, 쿠버네티스 리소스별 비용 분류 가시화 제공
    - Pricing - [링크](https://www.kubecost.com/pricing) : Free(메트릭 15일 보존, Business(메트릭 30일 보존, …), Enterprise(.)
    - Amazon EKS cost monitoring with **Kubecost architecture** - [링크](https://docs.kubecost.com/install-and-configure/install/provider-installations/aws-eks-cost-monitoring)
    

    
    - 수집 - [링크](https://aws.amazon.com/ko/blogs/containers/aws-and-kubecost-collaborate-to-deliver-cost-monitoring-for-eks-customers/)
    
   
    
    [Kubernetes 비용이 고민이라면? Kubecost](https://devocean.sk.com/blog/techBoardDetail.do?ID=164699&boardType=techBlog&searchData=&page=&subIndex=최신+기술+블로그)
    
- 설치 및 웹 접속 - [링크](https://docs.kubecost.com/install-and-configure/install/provider-installations/aws-eks-cost-monitoring) [Chart](https://github.com/kubecost/cost-analyzer-helm-chart/blob/develop/cost-analyzer/values-eks-cost-monitoring.yaml) [Gallery](https://gallery.ecr.aws/kubecost/cost-analyzer) ⇒ ingress 연동 설정 업데이트 작성하자 - [링크](https://bs-yang.com/290/)
    - ingress, service(nlb) 통한 접속은 왜인지 실패… 멤버분들 테스트 해보세요! [링크](https://docs.kubecost.com/install-and-configure/install/ingress-examples) [링크2](https://catalog.workshops.aws/eks-immersionday/en-US/kubecost/configure-ingress) → bastion ec2를 통한 ssh port forwarding 통한 접속 방식으로 우회
    
```bash
    # 
    cat <<EOT > cost-values.yaml
    global:
      grafana:
        enabled: true
        proxy: false
    
    priority:
      enabled: false
    networkPolicy:
      enabled: false
    podSecurityPolicy:
      enabled: false
    
    persistentVolume:
        storageClass: "gp3"
    
    prometheus:
      kube-state-metrics:
        disabled: false
      nodeExporter:
        enabled: true
    
    reporting:
      productAnalytics: true
    EOT
    
    **# kubecost chart 에 프로메테우스가 포함되어 있으니, 기존 프로메테우스-스택은 삭제하자 : node-export 포트 충돌 발생**
    **helm uninstall -n monitoring kube-prometheus-stack**
    
    # 배포
    kubectl create ns kubecost
    helm install kubecost oci://public.ecr.aws/kubecost/cost-analyzer --version **1.103.2** --namespace kubecost -f cost-values.yaml
    
    # Ingress 설정
    cat <<EOT > kubecost-ingress.yaml
    apiVersion: networking.k8s.io/v1
    kind: Ingress
    metadata:
      name: kubecost-ingress
      annotations:
        alb.ingress.kubernetes.io/certificate-arn: $CERT_ARN
        alb.ingress.kubernetes.io/group.name: study
        alb.ingress.kubernetes.io/listen-ports: '[{"HTTPS":443}, {"HTTP":80}]'
        alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
        alb.ingress.kubernetes.io/scheme: internet-facing
        alb.ingress.kubernetes.io/ssl-redirect: "443"
        alb.ingress.kubernetes.io/success-codes: 200-399
        alb.ingress.kubernetes.io/target-type: ip
    spec:
      ingressClassName: alb
      rules:
      - host: kubecost.$MyDomain
        http:
          paths:
          - backend:
              service:
                name: kubecost-cost-analyzer
                port:
                  number: 9090
            path: /
            pathType: Prefix
    EOT
    kubectl apply -f kubecost-ingress.yaml -n kubecost
    
    # 배포 확인
    kubectl get-all -n kubecost
    kubectl get all -n kubecost
    
    # kubecost-cost-analyzer 접속 정보 확인
    echo -e "Kubecost Web https://kubecost.$MyDomain"
```
   
    
- 사용법 - [링크1](https://www.eksworkshop.com/docs/observability/kubecost/costallocation) [링크2](https://aws.amazon.com/ko/blogs/containers/aws-and-kubecost-collaborate-to-deliver-cost-monitoring-for-eks-customers/)
        
        [AEWS) EKS Observability - Log on Me](https://logonme.net/tech/k8s/aews_w4/#6_Kubecost)
        
- 삭제:  `helm uninstall -n kubecost kubecost && kubectl delete -f kubecost-ingress.yaml -n kubecost`



</details>




##  AWS 관리형 서비스 AMP & AMG

- 참고 블로그
> [EKS 스터디 - 4주차 3편 - AMP에 EKS메트릭 저장](https://malwareanalysis.tistory.com/602)

> [[AEWS] 4주차 - AWS Managed Prometheus](https://blog.naver.com/qwerty_1234s/223107362723)

> [[AEWS] 4주차 - AMP, Prometheus, Node Exporter](https://blog.naver.com/qwerty_1234s/223107393655)

> [[AEWS] 4주차 - AMP, Prometheus 추가설정](https://blog.naver.com/qwerty_1234s/223107484931)

> [[AEWS] 4주차 - AMP, Grafana-Agent](https://blog.naver.com/qwerty_1234s/223107521565)



##  OpenTelemetry(OTel)

- EKS Add-on ADOT 사용해보기

> [[Study][Amazon EKS] EKS Add-On ADOT 사용해보기](https://ersia.tistory.com/30)

- ADOT, AMP 및 AMG를 사용한 모니터링

> [[4주차] EKS Observability - ADOT, AMP 및 AMG를 사용한 모니터링](https://kschoi728.tistory.com/97)


### (실습 완료 후) 자원  삭제

**삭제**

```bash

**eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME**

```

- ***AWS EC2 → 볼륨 : 남아 있는 볼륨 삭제하자!***

**(옵션) 로깅 삭제** : 위에서 삭제 안 했을 경우 삭제

```bash

# EKS Control Plane 로깅(CloudWatch Logs) 비활성화
eksctl utils **update-cluster-logging** --cluster $CLUSTER_NAME --region $AWS_DEFAULT_REGION **--disable-types all** --approve
# 로그 그룹 삭제 : 컨트롤 플레인
aws logs **delete-log-group** --log-group-name /aws/eks/$CLUSTER_NAME/cluster

---
# 로그 그룹 삭제 : 데이터 플레인
aws logs **delete-log-group** --log-group-name /aws/containerinsights/$CLUSTER_NAME/application
aws logs **delete-log-group** --log-group-name /aws/containerinsights/$CLUSTER_NAME/dataplane
aws logs **delete-log-group** --log-group-name /aws/containerinsights/$CLUSTER_NAME/host
aws logs **delete-log-group** --log-group-name /aws/containerinsights/$CLUSTER_NAME/performance

```

<details><summary>도전과제</summary>

- `[도전과제1]` (EKS Workshop) Observability with OpenSearch 실습 정리 - [Link](https://www.eksworkshop.com/docs/observability/opensearch/)
- `[도전과제2]` (EKS Workshop) EKS open source observability 실습 정리 - [Link](https://www.eksworkshop.com/docs/observability/open-source-metrics/)
- `[도전과제3]` (EKS Workshop) Enabling Container Insights Using AWS Distro for OpenTelemetry 실습 정리 - [Link](https://www.eksworkshop.com/docs/observability/container-insights/collect-metrics-adot-ci)
- `[도전과제4]` (EKS Workshop) Cost visibility with Kubecost 실습 정리 - [Link](https://www.eksworkshop.com/docs/observability/kubecost/)
- `[도전과제5]` Grafana Loki 실습 정리 - [Link](https://grafana.com/docs/loki/latest/?pg=oss-loki&plcmt=quick-links)
- `[도전과제6]` Empowering Kubernetes Observability with eBPF on Amazon EKS - [Link](https://aws.amazon.com/blogs/containers/empowering-kubernetes-observability-with-ebpf-on-amazon-eks/)
- `[도전과제7]` Enhance Kubernetes Operational Visibility with AWS Chatbot - [Link](https://aws.amazon.com/ko/blogs/mt/enhance-kubernetes-operational-visibility-with-aws-chatbot/)
    
    
- `[도전과제8]` Using Open Source Grafana Operator on your Kubernetes cluster to manage Amazon Managed Grafana - [링크](https://aws.amazon.com/blogs/mt/using-open-source-grafana-operator-on-your-kubernetes-cluster-to-manage-amazon-managed-grafana/)
- `[도전과제9]` Monitoring CoreDNS for DNS throttling issues using AWS Open source monitoring services - [링크](https://aws.amazon.com/blogs/mt/monitoring-coredns-for-dns-throttling-issues-using-aws-open-source-monitoring-services/)
- `[도전과제10]` Adding metrics and traces to your application on Amazon EKS with AWS Distro for OpenTelemetry, AWS X-Ray and Amazon CloudWatch - [링크](https://aws.amazon.com/blogs/mt/adding-metrics-and-traces-to-your-application-on-amazon-eks-with-aws-distro-for-opentelemetry-aws-x-ray-and-amazon-cloudwatch/)
- `[도전과제11]` Enhance Operational Insight by Converting the Output of any AWS SDK Commands to Prometheus Metrics - [링크](https://aws.amazon.com/blogs/mt/enhance-operational-insight-by-converting-the-output-of-any-aws-sdk-commands-to-prometheus-metrics/)
- `[도전과제12]` Integrating Kubecost with Amazon Managed Service for Prometheus - [링크](https://aws.amazon.com/blogs/mt/integrating-kubecost-with-amazon-managed-service-for-prometheus/)
- `[도전과제13]` Announcing AWS Observability Accelerator to configure comprehensive observability for Amazon EKS - [링크](https://aws.amazon.com/blogs/mt/announcing-aws-observability-accelerator-to-configure-comprehensive-observability-for-amazon-eks/)
- `[도전과제14]` Visualizing metrics across Amazon Managed Service for Prometheus workspaces using Amazon Managed Grafana - [링크](https://aws.amazon.com/blogs/mt/visualizing-metrics-across-amazon-managed-service-for-prometheus-workspaces-using-amazon-managed-grafana/)
- `[도전과제15]` Proactive autoscaling of Kubernetes workloads with KEDA and Amazon CloudWatch - [링크](https://aws.amazon.com/blogs/mt/proactive-autoscaling-of-kubernetes-workloads-with-keda-using-metrics-ingested-into-amazon-cloudwatch/)

<details>