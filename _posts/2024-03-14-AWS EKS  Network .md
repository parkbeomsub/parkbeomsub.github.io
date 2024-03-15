---
layout: single
title: "AWS EKS Network 실습"
categories: AWS
tags: [AWS, Container, Kubernetes , EKS , DevOps ,Network ,CNI ]
toc: true
---


# AWS EKS  Network
[**실습구성 링크**](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)



## AWS VPC CNI 소개
 - [사전학습](https://malwareanalysis.tistory.com/555)
  
    요약: pod 대역과 work node 대역은 동일하다.

    할당하는 과정은 tail -f /var/log/aws-routed-eni/ipamd.log 에서 확인 가능하고 
    ~~~
    # 네임스페이스 분석(워커노드에서)
    ssh ubuntu@{workernode IP}
    sudo lsns -o PID,COMMAND -t net
    ##최근 PID입력
    sudo nsenter -t {PID} -n ip -c addr
    ~~~

    **AWS CNI** :   Container Network Interface 는 k8s 네트워크 환경을 구성해준다 [링크1](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
    [링크2](https://kubernetes.io/docs/concepts/cluster-administration/addons/#networking-and-network-policy)

    - supports native VPC networking with the Amazon VPC Container Network Interface (CNI) plugin for Kubernetes.
    - **VPC 와 통합** : VPC Flow logs , VPC 라우팅 정책, 보안 그룹(Security group) 을 사용 가능함
    - This plugin assigns an IP address from your VPC to each pod.
    - VPC ENI 에 미리 할당된 IP(=Local-IPAM Warm IP Pool)를 파드에서 사용할 수 있음
  
      ![구성](/Images/eks/eks_s1.png)

      Calico CNI는 오버레이(VXLAN,IP-IP)통신을 하고 AWC CNI는 동일 대역으로 직접 통신한다. -> 속도나 부하면에서 AWS가 유리하다.

      <details><summary>워커 노드에 생성 가능한 최대 파트 갯수</summary>

      ![구성](/Images/eks/eks_s2.png)

      위 그림에서 secondry IPv4 할당 : t3.medium은  NIC이 3이고 닉당 5개의 pod를 15개 토탈 생성할 수 있다.

      IPv4 Prefix 위임  : 아이피 할당은 nic에 서브넷 안의 대역으로 넣을 수 가 있다. 해당 방법을 통해서  최대 배치가능 수를 늘릴 수 있다.
    
      </details>
    

<details><summary>실습</summary>

-  네트워크 기본 정보 확인
~~~
# CNI 정보 확인
kubectl describe daemonset aws-node --namespace kube-system | grep Image | cut -d "/" -f 2

# kube-proxy config 확인 : 모드 iptables 사용 >> ipvs 모드 사용하지 않는 이유???
kubectl describe cm -n kube-system kube-proxy-config
...
mode: "iptables"
...

# 노드 IP 확인
aws ec2 describe-instances --query "Reservations[*].Instances[*].{PublicIPAdd:PublicIpAddress,PrivateIPAdd:PrivateIpAddress,InstanceName:Tags[?Key=='Name']|[0].Value,Status:State.Name}" --filters Name=instance-state-name,Values=running --output table

# 파드 IP 확인
kubectl get pod -n kube-system -o=custom-columns=NAME:.metadata.name,IP:.status.podIP,STATUS:.status.phase

# 파드 이름 확인
kubectl get pod -A -o name

# 파드 갯수 확인
kubectl get pod -A -o name | wc -l
~~~
![구성](/Images/eks/eks_n21.png)

- 노드에 네트워크 정보 확인
~~~

# CNI 정보 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i tree /var/log/aws-routed-eni; echo; done
ssh ec2-user@$N1 sudo cat /var/log/aws-routed-eni/plugin.log | jq
ssh ec2-user@$N1 sudo cat /var/log/aws-routed-eni/ipamd.log | jq
ssh ec2-user@$N1 sudo cat /var/log/aws-routed-eni/egress-v6-plugin.log | jq
ssh ec2-user@$N1 sudo cat /var/log/aws-routed-eni/ebpf-sdk.log | jq
ssh ec2-user@$N1 sudo cat /var/log/aws-routed-eni/network-policy-agent.log | jq

# 네트워크 정보 확인 : eniY는 pod network 네임스페이스와 veth pair
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo ip -br -c addr; echo; done
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo ip -c addr; echo; done
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo ip -c route; echo; done
ssh ec2-user@$N1 sudo iptables -t nat -S
ssh ec2-user@$N1 sudo iptables -t nat -L -n -v

~~~



![구성](/Images/eks/eks_n22.png)
![구성](/Images/eks/eksn_23.png)

</details>

## 노드에서 기본 네트워크 정보 확인

![구성](/Images/eks/eksn_25.png)
- t3.medium 의 경우 ENI 마다 최대 6개의 IP를 가질 수 있다
- ENI0, ENI1 으로 2개의 ENI는 자신의 IP 이외에 추가적으로 5개의 보조 프라이빗 IP를 가질수 있다
- coredns 파드는 veth 으로 호스트에는 eniY@ifN 인터페이스와 파드에 eth0 과 연결되어 있다


**인스턴스의 네트워크 정보 확인 : 프라이빗 IP와 보조 프라이빗 IP 확인**

![구성](/Images/eks/eksn_26.png)
- 네트워크인터페이스(ENI)에 설명 내용 확인해보자 : 주ENI와 추가ENI의 설명 차이점 확인

<details><summary>실습</summary>

- 보조 IPv4 주소를 파드가 사용하는지 확인
~~~

kubectl get pod -n kube-system -l k8s-app=kube-dns -owide
NAME                       READY   STATUS    RESTARTS   AGE   IP              NODE                                               NOMINATED NODE   READINESS GATES
coredns-6777fcd775-57k77   1/1     Running   0          70m   192.168.1.142   ip-192-168-1-251.ap-northeast-2.compute.internal   <none>           <none>
coredns-6777fcd775-cvqsb   1/1     Running   0          70m   192.168.2.75    ip-192-168-2-34.ap-northeast-2.compute.internal    <none>           <none>

# 노드의 라우팅 정보 확인 >> EC2 네트워크 정보의 '보조 프라이빗 IPv4 주소'와 비교해보자
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo ip -c route; echo; done
~~~

![구성](/Images/eks/eksn_24.png)

- [실습] 테스트용 파드 생성 - (nicolaka/netshoot)[https://github.com/nicolaka/netshoot]

~~~

# [터미널1~3] 노드 모니터링
ssh ec2-user@$N1
watch -d "ip link | egrep 'eth|eni' ;echo;echo "[ROUTE TABLE]"; route -n | grep eni"

ssh ec2-user@$N2
watch -d "ip link | egrep 'eth|eni' ;echo;echo "[ROUTE TABLE]"; route -n | grep eni"

ssh ec2-user@$N3
watch -d "ip link | egrep 'eth|eni' ;echo;echo "[ROUTE TABLE]"; route -n | grep eni"

# 테스트용 파드 netshoot-pod 생성
cat <<EOF | kubectl create -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: netshoot-pod
spec:
  replicas: 3
  selector:
    matchLabels:
      app: netshoot-pod
  template:
    metadata:
      labels:
        app: netshoot-pod
    spec:
      containers:
      - name: netshoot-pod
        image: nicolaka/netshoot
        command: ["tail"]
        args: ["-f", "/dev/null"]
      terminationGracePeriodSeconds: 0
EOF

# 파드 이름 변수 지정
PODNAME1=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[0].metadata.name})
PODNAME2=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[1].metadata.name})
PODNAME3=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[2].metadata.name})

# 파드 확인
kubectl get pod -o wide
kubectl get pod -o=custom-columns=NAME:.metadata.name,IP:.status.podIP

# 노드에 라우팅 정보 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo ip -c route; echo; done

~~~



![구성](/Images/eks/eksn_27.png)

![구성](/Images/eks/eksn_28.png)

![구성](/Images/eks/eksn_29.png)


- 파드가 생성되면, **워커 노드**에 **eniY@ifN** **추가**되고 라우팅 테이블에도 정보가 추가된다

- 테스트용 파드 **eniY 정보 확인** - 워커 노드 EC2

~~~

# 노드3에서 네트워크 인터페이스 정보 확인
ssh ec2-user@$N3
----------------
ip -br -c addr show
ip -c link
ip -c addr
ip route # 혹은 route -n

# 마지막 생성된 네임스페이스 정보 출력 -t net(네트워크 타입)
sudo lsns -o PID,COMMAND -t net | awk 'NR>2 {print $1}' | tail -n 1

# 마지막 생성된 네임스페이스 net PID 정보 출력 -t net(네트워크 타입)를 변수 지정
MyPID=$(sudo lsns -o PID,COMMAND -t net | awk 'NR>2 {print $1}' | tail -n 1)

# PID 정보로 파드 정보 확인
sudo nsenter -t $MyPID -n ip -c addr
sudo nsenter -t $MyPID -n ip -c route

exit
----------------

~~~

![구성](/Images/eks/eksn_30.png)

![구성](/Images/eks/eksn_31.png)

-  테스트용 파드 접속(exec) 후 확인
  
~~~

# 테스트용 파드 접속(exec) 후 Shell 실행
kubectl exec -it $PODNAME1 -- zsh

# 아래부터는 pod-1 Shell 에서 실행 : 네트워크 정보 확인
----------------------------
ip -c addr
ip -c route
route -n
ping -c 1 <pod-2 IP>
ps
cat /etc/resolv.conf
exit
----------------------------

# 파드2 Shell 실행
kubectl exec -it $PODNAME2 -- ip -c addr

# 파드3 Shell 실행
kubectl exec -it $PODNAME3 -- ip -br -c addr

~~~



![구성](/Images/eks/eksn_32.png)

![구성](/Images/eks/eksn_33.png)

</details>

## 노드 간 파드 통신



## 파드에서 외부 통신



## 노드에 파드 생성 갯수 제한



## Service & AWS LoadBalancer Controller






## Ingress




## ExternalDNS




## Istio




## CoreDNS





##  Gatewaty API



##  파드 간 속도 측정



##  kube-ops-view



##  CNI-Metrics-helper



##  Network Policies with VPC CNI



##  How to rapidly scale your application with ALB on EKS (without losing 
traffic)



##  IPv6 with EKS


---
**삭제**
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~





<details><summary>실습</summary>
</details>