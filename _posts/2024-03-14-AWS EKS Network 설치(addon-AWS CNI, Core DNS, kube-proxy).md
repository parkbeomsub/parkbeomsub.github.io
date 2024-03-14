---
layout: single
title: "EKS Network 실습환경 설치 -addon  AWS CNI, Core DNS, kube-proxy"
categories: AWS
tags: [AWS, Container, Kubernetes , EKS , DevOps  ]
toc: true
---


# AWS EKS  Network 실습 환경 구성
## 구성 환경
- **사전 준비** : AWS 계정, SSH 키 페어, IAM 계정 생성 후 키

#### 구성도
  ![구성](/Images/eks/eks_n0.png)

> 설명  
- CloudFormation 스택 실행 시 **파라미터**를 기입하면, 해당 정보가 반영되어 배포됩니다.
- 실습 환경을 위한 **VPC** 1개가 생성되고, **퍼블릭** 서브넷 3개와 **프라이빗** 서브넷 3개가 생성됩니다.
- CloudFormation 에 EC2의 **UserData** 부분(**Script** 실행)으로 Amazon EKS **설치(with OIDC, Endpoint Public)**를 진행합니다
- **관리형 노드 그룹**(워커 노드)는 AZ1~AZ3를 사용하여, 기본 **3**대로 구성됩니다
- **Add-on** 같이 설치 됨 : 최신 버전 - kube-proxy, coredns, aws vpc cni



#### 배포
  > 배포서비스 : CloudFormation        
   [링크](https://console.aws.amazon.com/cloudformation/home?region=ap-northeast-2#/stacks/new?stackName=myeks&templateURL=https:%2F%2Fs3.ap-northeast-2.amazonaws.com%2Fcloudformation.cloudneta.net%2FK8S%2Feks-oneclick.yaml)
  



**Deploy EC2** 

    1. **KeyName** : 작업용 bastion ec2에 SSH 접속을 위한 **SSH 키페어** 선택 *← 미리 SSH 키 생성 해두자!*

    2. **MyIamUserAccessKeyID** : **관리자** 수준의 권한을 가진 IAM User의 액세스 키ID 입력

    3. **MyIamUserSecretAccessKey** : **관리자** 수준의 권한을 가진 IAM User의 **시크릿 키ID** 입력 **← 노출되지 않게 보안 주의**

    4. **SgIngressSshCidr** : 작업용 bastion ec2에 **SSH 접속 가능한 IP** 입력 (**집 공인IP**/32 입력), 보안그룹 인바운드 규칙에 반영됨

    5. MyInstanceType: 작업용 bastion EC2 인스턴스의 타입 (기본 **t3.medium**) ⇒ 변경 가능

    6. LatestAmiId : 작업용 bastion EC2에 사용할 AMI는 아마존리눅스2 최신 버전 사용

 **EKS Config** 

    1. **ClusterBaseName** : EKS **클러스터 이름**이며, **myeks** 기본값 사용을 권장 → 이유: 실습 리소스 태그명과 실습 커멘드에서 사용

    2. **KubernetesVersion** : EKS 호환, 쿠버네티스 버전 (기본 v1.29, 실습은 **1.28** 버전 사용) ⇒ 변경 가능

    3. **WorkerNodeInstanceType**: 워커 노드 EC2 인스턴스의 타입 (기본 **t3.medium**) ⇒ 변경 가능

    4. **WorkerNodeCount** : 워커노드의 갯수를 입력 (기본 3대) ⇒ 변경 가능

    5. **WorkerNodeVolumesize** : 워커노드의 EBS 볼륨 크기 (기본 80GiB) ⇒ 변경 가능

  **Region AZ** 
 
  리전과 가용영역을 지정, 기본값 그대로 사용

  

![구성](/Images/eks/eks_n1-1.png)
> https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick.yaml
>   



- 기본 인프라 배포 링크 - [Cloudfomation 링크](https://console.aws.amazon.com/cloudformation/home?region=ap-northeast-2#/stacks/new?stackName=myeks&templateURL=https:%2F%2Fs3.ap-northeast-2.amazonaws.com%2Fcloudformation.cloudneta.net%2FK8S%2Fmyeks-1week.yaml)

   아래 내용 (배포) - UserData에 기본 패키지 설치 스크립트 존재

   위 링크를 통해 yaml 확인해보면 아래와 같은 특이사항이 있다.

- 특이사항
  eksctl ~~ --dry-run 명령어로 yaml로 만든 후 add-on 을 아래와 같이 추가

  ~~~
  cat <<EOT >> myeks.yaml
  addons:
  - name: vpc-cni # no version is specified so it deploys the default version
    version: latest # auto discovers the latest available
    attachPolicyARNs:
      - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
    configurationValues: |-
      enableNetworkPolicy: "true"
  - name: kube-proxy
    version: latest
  - name: coredns
    version: latest
  EOT
  ~~~


  **약 20 분 소요**

  #### 완료 상태포기 

  ~~~

  ssh -i ~/.ssh/kp-gasida.pem ec2-user@$(aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[0].OutputValue' --output  text)

  # cloud-init 실행 과정 로그 확인  
  tail -f /var/log/cloud-init-output.log  

  # cloud-init 정상 완료 후 eksctl 실행 과정 로그 확인  
  tail -f /root/create-eks.log  

  # default 네임스페이스 적용 
  kubectl ns default  

  # 설치 확인 
  kubectl cluster-info  
  eksctl get cluster  
  eksctl get nodegroup --cluster $CLUSTER_NAME  

  # 환경변수 정보 확인  
  export | egrep 'ACCOUNT|AWS_|CLUSTER|KUBERNETES|VPC|Subnet' 
  export | egrep 'ACCOUNT|AWS_|CLUSTER|KUBERNETES|VPC|Subnet' | egrep -v 'SECRET|KEY' 

  # 인증 정보 확인  
  cat /root/.kube/config | yh 
  kubectl config view | yh  
  kubectl ctx 

  # 노드 정보 확인  
  kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone  
  eksctl get iamidentitymapping --cluster myeks 

  # krew 플러그인 확인
  kubectl krew list

  # 모든 네임스페이스에서 모든 리소스 확인
  kubectl get-all

  ~~~
![구성](/Images/eks/eks_n2.png)

![구성](/Images/eks/eks_n3.png)

![구성](/Images/eks/eks_n4.png)

![구성](/Images/eks/eks_n5.png)

![구성](/Images/eks/eks_n6.png)

![구성](/Images/eks/eks_n7.png)


## 노드 정보 및 ssh 접속

  ~~~

  # 노드 IP 확인 및 PrivateIP 변수 지정
  aws ec2 describe-instances --query "Reservations[*].Instances[*].{PublicIPAdd:PublicIpAddress,PrivateIPAdd:PrivateIpAddress,InstanceName:Tags[?Key=='Name']|[0].Value,Status:State.Name}" --filters Name=instance-state-name,Values=running --output table
  N1=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2a -o jsonpath={.items[0].status.addresses[0].address})
  N2=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2b -o jsonpath={.items[0].status.addresses[0].address})
  N3=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2c -o jsonpath={.items[0].status.addresses[0].address})
  echo "export N1=$N1" >> /etc/profile
  echo "export N2=$N2" >> /etc/profile
  echo "export N3=$N3" >> /etc/profile
  echo $N1, $N2, $N3

  # 보안그룹 ID와 보안그룹 이름(Name아님을 주의!) 확인
  aws ec2 describe-security-groups --query 'SecurityGroups[*].[GroupId, GroupName]' --output text

  # 노드 보안그룹 ID 확인
  aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text
  NGSGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text)
  echo $NGSGID
  echo "export NGSGID=$NGSGID" >> /etc/profile

  # 노드 보안그룹에 eksctl-host 에서 노드(파드)에 접속 가능하게 룰(Rule) 추가 설정
  aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr 192.168.1.100/32

  # eksctl-host 에서 노드의IP나 coredns 파드IP로 ping 테스트
  ping -c 1 $N1
  ping -c 1 $N2
  ping -c 1 $N3

  # 워커 노드 SSH 접속 : '-i ~/.ssh/id_rsa' 생략 가능
  for node in $N1 $N2 $N3; do ssh -i ~/.ssh/id_rsa ec2-user@$node hostname; done
  ssh ec2-user@$N1
  exit
  ssh ec2-user@$N2
  exit
  ssh ec2-user@$N3
  exit

  ~~~
![구성](/Images/eks/eks_n8.png)


![구성](/Images/eks/eks_n9.png)

![구성](/Images/eks/eks_n10.png)

![구성](/Images/eks/eks_n11.png)

![구성](/Images/eks/eks_n12.png)

![구성](/Images/eks/eks_n14.png)


### 모든 파드의 컨테이너 이미지 정보 확인 : 기본설치 vs Add-on 으로 최신 버전 설치
<details>
<summary>펼치기</summary>

  ~~~
  
  # 모든 파드의 컨테이너 이미지 정보 확인
  kubectl get pods --all-namespaces -o jsonpath="{.items[*].spec.containers[*].image}" | tr -s '[[:space:]]' '\n' | sort | uniq -c
  
  # 위 버전은 Add-on 으로 최신 버전 설치
  kubectl get pods -A
  kubectl get pods --all-namespaces -o jsonpath="{.items[*].spec.containers[*].image}" | tr -s '[[:space:]]' '\n' | sort | uniq -c
        3 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon/aws-network-policy-agent:v1.0.8-eksbuild.1
        3 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon-k8s-cni:v1.16.4-eksbuild.2
        2 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/coredns:v1.10.1-eksbuild.7
        3 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/kube-proxy:v1.28.6-minimal-eksbuild.
        # 아래는 기본 설치 시 버전
        2 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/amazon-k8s-cni:v1.15.1-eksbuild.1
        2 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/coredns:v1.10.1-eksbuild.4
        2 602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/kube-proxy:v1.28.2-minimal-eksbuild.2
  
  # eksctl 설치/업데이트 addon 확인
  eksctl get addon --cluster $CLUSTER_NAME
  NAME            VERSION                 STATUS  ISSUES  IAMROLE                                                                      UPDATE AVAILABLE CONFIGURATION VALUES
  coredns         v1.10.1-eksbuild.7      ACTIVE  0
  kube-proxy      v1.28.6-eksbuild.2      ACTIVE  0
  vpc-cni         v1.16.4-eksbuild.2      ACTIVE  0       arn:aws:iam::911283464785:role/eksctl-myeks-addon-vpc-cni-Role1-tGXXZMjRWrW3                  enableNetworkPolicy: "true"
  
  # (참고) eks 설치 yaml 중 addon 내용
  tail -n11 myeks.yaml
  addons:
  - name: vpc-cni # no version is specified so it deploys the default version
    version: latest # auto discovers the latest available
    attachPolicyARNs:
      - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
    configurationValues: |-
      enableNetworkPolicy: "true"
  - name: kube-proxy
    version: latest
  - name: coredns
    version: latest
  
  ~~~

  ![구성](/Images/eks/eks_n15.png)
  ![구성](/Images/eks/eks_n16.png)
  ![구성](/Images/eks/eks_n17.png)



  **버전별 Add-on 지원 **
  ~~~
  # v1.29 지원 addon
  aws eks describe-addon-versions --kubernetes-version 1.29  --query 'addons[].{MarketplaceProductUrl: marketplaceInformation.productUrl, Name: addonName, Owner: owner Publisher: publisher, Type: type}' --output table
  eksctl utils describe-addon-versions --kubernetes-version 1.29 | grep AddonName
  
  # v1.28 지원 addon
  aws eks describe-addon-versions --kubernetes-version 1.28  --query 'addons[].{MarketplaceProductUrl: marketplaceInformation.productUrl, Name: addonName, Owner: owner Publisher: publisher, Type: type}' --output table
  eksctl utils describe-addon-versions --kubernetes-version 1.28 | grep AddonName
  
  # v1.27 지원 addon
  aws eks describe-addon-versions --kubernetes-version 1.27  --query 'addons[].{MarketplaceProductUrl: marketplaceInformation.productUrl, Name: addonName, Owner: owner Publisher: publisher, Type: type}' --output table
  eksctl utils describe-addon-versions --kubernetes-version 1.27 | grep AddonName
  
  # 지원 addon 비교
  eksctl utils describe-addon-versions --kubernetes-version 1.29 | grep AddonName | wc -l
  eksctl utils describe-addon-versions --kubernetes-version 1.28 | grep AddonName | wc -l
  eksctl utils describe-addon-versions --kubernetes-version 1.27 | grep AddonName | wc -l
  
  ~~~

  ![구성](/Images/eks/eks_n18.png)

  ![구성](/Images/eks/eks_n19.png)


  **Add-on 별 전체 버전 정보 확인**
  ~~~
  
  ADDON=<add-on 이름>
  ADDON=vpc-cni
  
  # 아래는 vpc-cni 전체 버전 정보와 기본 설치 버전(True) 정보 확인
  aws eks describe-addon-versions \
      --addon-name $ADDON \
      --kubernetes-version 1.28 \
      --query "addons[].addonVersions[].[addonVersion, compatibilities[].defaultVersion]" \
      --output text
  
  ~~~


  </details>


## 삭제하기
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~