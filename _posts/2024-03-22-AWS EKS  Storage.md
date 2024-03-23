---
layout: single
title: "AWS EKS Network 실습"
categories: AWS
tags: [AWS, Container, Kubernetes , EKS , DevOps ,Network ,CNI ]
toc: true
---


# AWS EKS  Storage
 > 첨부링크 : https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick2.yaml
 
 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)



![구성](/Images/eks/eks_s1.png)

![구성](/Images/eks/eks_s2.png)



## 기본 설정

<details><summary>설정 확인 및 실습 변수 설정</summary>
```bash

# default 네임스페이스 적용
**kubectl ns default**

# EFS 확인 : AWS 관리콘솔 EFS 확인해보자
echo $EfsFsId
mount -t efs -o tls $EfsFsId:/ /mnt/myefs
**df -hT --type nfs4**

**echo "efs file test" > /mnt/myefs/memo.txt**
cat /mnt/myefs/memo.txt
rm -f /mnt/myefs/memo.txt

# 스토리지클래스 및 CSI 노드 확인
kubectl get sc
kubectl get sc gp2 -o yaml | yh
kubectl get csinodes

# 노드 정보 확인
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone
****eksctl get iamidentitymapping --cluster myeks
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

 AWS LB/ExternalDNS, kube-ops-view 설치

```bash
# AWS LB Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

# ExternalDNS
MyDomain=<자신의 도메인>
**MyDomain=gasida.link**
MyDnzHostedZoneId=$(aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text)
echo $MyDomain, $MyDnzHostedZoneId

curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/**externaldns.yaml**
sed -i "s/0.13.4/0.14.0/g" externaldns.yaml
MyDomain=$MyDomain MyDnzHostedZoneId=$MyDnzHostedZoneId **envsubst** < **externaldns.yaml** | kubectl apply -f -

# kube-ops-view
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set env.TZ="Asia/Seoul" --namespace kube-system
kubectl patch svc -n kube-system kube-ops-view -p '{"spec":{"type":"LoadBalancer"}}'
kubectl **annotate** service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=**kubeopsview**.$MyDomain"
echo -e "Kube Ops View URL = http://**kubeopsview**.$MyDomain:8080/#scale=1.5"

```


![구성](/Images/eks/eks_s3.png)
![구성](/Images/eks/eks_s4.png)


</details>










## 스토리지 설명 및 이번 내용
<details><summary>설명</summary>

> Pod는 삭제되거나 재생성되면 Volume이 없으면 기존에 있는 데이터들이 삭제된다.
> 삭제되지 말아야하는 데이터들을 유지하는 방법이 필요한데, 그 기술이 PV, PVC 객체를 사용하여 생성하는 방법이다.
> Worker Node에 Volume을 연결하면 해당 노드에서만 생성되어야하는 조건들이 있고, 이를 해결하는 방법과 다양한  AWS Instance 타입으로 극복하는 방법들을 알려드릴고합니다.
> 기본은 PV 생성 > PVC를 생성하여 Pod와 연동을 시키는데  PVC를 생성할 때 Storage Class을 넣게되면 PV까지 생성하게 되는데 이를 동적 프로비저닝이라 한다.

![구성](/Images/eks/eks_s14.png)

출처:  https://aws.amazon.com/ko/blogs/tech/persistent-storage-for-kubernetes/





</details>


## Kubernetes 스토지리 이해
<details><summary> 소개 </summary>
- 종류 :  emptyDir, hostPath, PV/PVC
     - emptyDir : pod 의 생명주기 (생성될 때 만들어지고 삭제될제 삭제됨 )
     - hostPath : node마다  Mount path을 걸어줘서 특정 노드에서만 동작(경로가 있어야함)
     -  PV/PVC : 마운트를 별도 오브젝트로 만들어서 관리

![구성](/Images/eks/eks_s15.png)

- 다양한 종류
    K8S 자체 제공(hostPath, local), 온프렘 솔루션(ceph 등), NFS, 클라우드 스토리지(AWS EBS 등)

    
![구성](/Images/eks/eks_s16.png)


- `동적 프로비저닝` & 볼륨 상태 , `ReclaimPolicy`

    
![구성](/Images/eks/eks_s17.png)


</details>





<details><summary></summary>


</details>