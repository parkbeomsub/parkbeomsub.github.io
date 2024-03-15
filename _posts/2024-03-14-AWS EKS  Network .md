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
- **목표** : 파드간 통신 시 tcpdump 내용을 확인하고 통신 과정을 알아본다
- **파드간 통신 흐름** : AWS VPC CNI 경우 별도의 오버레이(Overlay) 통신 기술 없이, VPC Native 하게 파드간 직접 통신이 가능하다
  
![구성](/Images/eks/eksn_34.png)

 출처 : https://github.com/aws/amazon-vpc-cni-k8s/blob/master/docs/cni-proposal.md


<details><summary>실습</summary>

- 파드간 통신 테스트 및 확인 : 별도의 NAT 동작 없이 통신 가능!
~~~

# 파드 IP 변수 지정
PODIP1=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[0].status.podIP})
PODIP2=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[1].status.podIP})
PODIP3=$(kubectl get pod -l app=netshoot-pod -o jsonpath={.items[2].status.podIP})

# 파드1 Shell 에서 파드2로 ping 테스트
kubectl exec -it $PODNAME1 -- ping -c 2 $PODIP2

# 파드2 Shell 에서 파드3로 ping 테스트
kubectl exec -it $PODNAME2 -- ping -c 2 $PODIP3

# 파드3 Shell 에서 파드1로 ping 테스트
kubectl exec -it $PODNAME3 -- ping -c 2 $PODIP1

# 워커 노드 EC2 : TCPDUMP 확인
sudo tcpdump -i any -nn icmp
sudo tcpdump -i eth1 -nn icmp
sudo tcpdump -i eth0 -nn icmp
sudo tcpdump -i eniYYYYYYYY -nn icmp

[워커 노드1]
# routing policy database management 확인
ip rule

# routing table management 확인
ip route show table local

# 디폴트 네트워크 정보를 eth0 을 통해서 빠져나간다
ip route show table main
default via 192.168.1.1 dev eth0

~~~

![구성](/Images/eks/eksn_43.png)

![구성](/Images/eks/eksn_35.png)

![구성](/Images/eks/eksn_36.png)






</details>






## 파드에서 외부 통신

- **파드에서 외부 통신 흐름** : iptable 에 SNAT 을 통하여 노드의 eth0 IP로 변경되어서 외부와 통신됨

![구성](/Images/eks/eksn_37.png)


- VPC CNI 의 External source network address translation (SNAT) 설정에 따라, 외부(인터넷) 통신 시 SNAT 하거나 혹은 SNAT 없이 통신을 할 수 있다  [링크](https://docs.aws.amazon.com/eks/latest/userguide/external-snat.html)



<details><summary>실습</summary>

- **파드에서 외부 통신** 테스트 및 확인
- 파드 shell 실행 후 외부로 ping 테스트 & 워커 노드에서 tcpdump 및 iptables 정보 확인
~~~


**# 작업용 EC2 :** pod-1 Shell 에서 외부로 ping
kubectl exec -it $PODNAME1 -- ping -c 1 www.google.com
kubectl exec -it $PODNAME1 -- ping -i 0.1 www.google.com

**# 워커 노드 EC2** : TCPDUMP 확인
sudo tcpdump -i any -nn icmp
sudo tcpdump -i eth0 -nn icmp

**# 워커 노드 EC2** : 퍼블릭IP 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i curl -s ipinfo.io/ip; echo; echo; done

**# 작업용 EC2 :** pod-1 Shell 에서 외부 접속 확인 - 공인IP는 어떤 주소인가?
## The right way to check the weather - [링크](https://github.com/chubin/wttr.in)
for i in $PODNAME1 $PODNAME2 $PODNAME3; do echo ">> Pod : $i <<"; kubectl exec -it $i -- curl -s ipinfo.io/ip; echo; echo; done
kubectl exec -it $PODNAME1 -- curl -s **wttr.in**/seoul
kubectl exec -it $PODNAME1 -- curl -s wttr.in/seoul?format=3
kubectl exec -it $PODNAME1 -- curl -s wttr.in/Moon
kubectl exec -it $PODNAME1 -- curl -s wttr.in/:help

**# 워커 노드 EC2**
## 출력된 결과를 보고 어떻게 빠져나가는지 고민해보자!
ip rule
ip route show table main
sudo **iptables -L -n -v -t nat
sudo iptables -t nat -S**

# 파드가 외부와 통신시에는 아래 처럼 'AWS-SNAT-CHAIN-0' 룰(rule)에 의해서 SNAT 되어서 외부와 통신!
# 참고로 뒤 IP는 eth0(ENI 첫번째)의 IP 주소이다
# --random-fully 동작 - [링크1](https://ssup2.github.io/issue/Linux_TCP_SYN_Packet_Drop_SNAT_Port_Race_Condition/)  [링크2](https://ssup2.github.io/issue/Kubernetes_TCP_Connection_Delay_VXLAN_CNI_Plugin/)
sudo iptables -t nat -S | grep 'A AWS-SNAT-CHAIN'
-A AWS-SNAT-CHAIN-0 ! -d **192.168.0.0/16** -m comment --comment "AWS SNAT CHAIN" -j RETURN
-A AWS-SNAT-CHAIN-0 ! -o vlan+ -m comment --comment "AWS, SNAT" -m addrtype ! --dst-type LOCAL -j SNAT --to-source **192.168.1.251** --random-fully

## 아래 'mark 0x4000/0x4000' 매칭되지 않아서 RETURN 됨!
-A KUBE-POSTROUTING -m mark ! --mark 0x4000/0x4000 -j RETURN
-A KUBE-POSTROUTING -j MARK --set-xmark 0x4000/0x0
-A KUBE-POSTROUTING -m comment --comment "kubernetes service traffic requiring SNAT" -j MASQUERADE --random-fully
...

# 카운트 확인 시 AWS-SNAT-CHAIN-0에 매칭되어, 목적지가 **192.168.0.0/16** 아니고 외부 빠져나갈때 SNAT **192.168.1.251(EC2 노드1 IP)** 변경되어 나간다!
sudo iptables -t filter --zero; sudo iptables -t nat --zero; sudo iptables -t mangle --zero; sudo iptables -t raw --zero
watch -d 'sudo iptables -v --numeric --table nat --list AWS-SNAT-CHAIN-0; echo ; sudo iptables -v --numeric --table nat --list KUBE-POSTROUTING; echo ; sudo iptables -v --numeric --table nat --list POSTROUTING'

# conntrack 확인
**for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo conntrack -L -n |grep -v '169.254.169'; echo; done**
conntrack v1.4.5 (conntrack-tools): 
icmp     1 28 src=172.30.66.58 dst=8.8.8.8 type=8 code=0 id=34392 src=8.8.8.8 dst=172.30.85.242 type=0 code=0 id=50705 mark=128 use=1
tcp      6 23 TIME_WAIT src=172.30.66.58 dst=34.117.59.81 sport=58144 dport=80 src=34.117.59.81 dst=172.30.85.242 sport=80 dport=44768 [ASSURED] mark=128 use=1


~~~


![구성](/Images/eks/eksn_38.png)

![구성](/Images/eks/eksn_39.png)

![구성](/Images/eks/eksn_40.png)

![구성](/Images/eks/eksn_41.png)

![구성](/Images/eks/eksn_42.png)







* 다음 실습을 위해서 파드 삭제: 
  >  kubectl delete deploy netshoot-pod





</details>




## 노드에 파드 생성 갯수 제한


사전 준비 : kube-ops-view 설치
<details><summary>설치</summary>


~~~


# kube-ops-view
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set env.TZ="Asia/Seoul" --namespace kube-system
kubectl patch svc -n kube-system kube-ops-view -p '{"spec":{"type":"LoadBalancer"}}'

# kube-ops-view 접속 URL 확인 (1.5 배율)
kubectl get svc -n kube-system kube-ops-view -o jsonpath={.status.loadBalancer.ingress[0].hostname} | awk '{ print "KUBE-OPS-VIEW URL = http://"$1":8080/#scale=1.5"}'

~~~

</details>

- Secondary IPv4 addresses (기본값) : 인스턴스 유형에 최대 ENI 갯수와 할당 가능 IP 수를 조합하여 선정

- **워커 노드의 인스턴스 타입 별 파드 생성 갯수 제한**
    - **인스턴스 타입** 별 ENI 최대 갯수와 할당 가능한 최대 IP 갯수에 따라서 파드 배치 갯수가 결정됨
    - 단, aws-node 와 kube-proxy 파드는 호스트의 IP를 사용함으로 최대 갯수에서 제외함

    ![구성](/Images/eks/eksn_44.png)





<details><summary>워커 노드의 인스턴스 정보 확인 : t3.medium 사용 시</summary>


```bash
# t3 타입의 정보(필터) 확인
aws ec2 describe-instance-types --filters Name=instance-type,Values=**t3.*** \
 --query "InstanceTypes[].{**Type**: InstanceType, **MaxENI**: NetworkInfo.MaximumNetworkInterfaces, **IPv4addr**: NetworkInfo.Ipv4AddressesPerInterface}" \
 --output table
--------------------------------------
|        DescribeInstanceTypes       |
+----------+----------+--------------+
| IPv4addr | MaxENI   |    Type      |
+----------+----------+--------------+
|  15      |  4       |  t3.2xlarge  |
|  **6**       |  **3**       |  **t3.medium**   |
|  **12**      |  **3**       |  **t3.large**    |
|  15      |  4       |  t3.xlarge   |
|  2       |  2       |  t3.micro    |
|  2       |  2       |  t3.nano     |
|  4       |  3       |  t3.small    |
+----------+----------+--------------+

# c5 타입의 정보(필터) 확인
aws ec2 describe-instance-types --filters Name=instance-type,Values=**c5*.*** \
 --query "InstanceTypes[].{**Type**: InstanceType, **MaxENI**: NetworkInfo.MaximumNetworkInterfaces, **IPv4addr**: NetworkInfo.Ipv4AddressesPerInterface}" \
 --output table

# 파드 사용 가능 계산 예시 : aws-node 와 kube-proxy 파드는 host-networking 사용으로 IP 2개 남음
((MaxENI * (IPv4addr-1)) + 2)
**t3.medium** 경우 : ((3 * (6 - 1) + **2** ) = **17개 >>** aws-node 와 kube-proxy 2개 제외하면 **15개**

# 워커노드 상세 정보 확인 : 노드 상세 정보의 Allocatable 에 pods 에 17개 정보 확인
**kubectl describe node | grep Allocatable: -A6**
Allocatable:
  cpu:                         1930m
  ephemeral-storage:           27905944324
  hugepages-1Gi:               0
  hugepages-2Mi:               0
  memory:                      3388360Ki
  **pods:                        17**
```

</details>



<details><summary>최대 파드 생성 및 확인</summary>

~~~bash

# 워커 노드 EC2 - 모니터링
while true; do ip -br -c addr show && echo "--------------" ; date "+%Y-%m-%d %H:%M:%S" ; sleep 1; done

# 작업용 EC2 - 터미널1
watch -d 'kubectl get pods -o wide'

# 작업용 EC2 - 터미널2
# 디플로이먼트 생성
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/2/nginx-dp.yaml
**kubectl apply -f nginx-dp.yaml**

# 파드 확인
kubectl get pod -o wide
kubectl get pod -o=custom-columns=NAME:.metadata.name,IP:.status.podIP

# 파드 증가 테스트 >> 파드 정상 생성 확인, 워커 노드에서 eth, eni 갯수 확인
kubectl scale deployment nginx-deployment --replicas=8

# 파드 증가 테스트 >> 파드 정상 생성 확인, 워커 노드에서 eth, eni 갯수 확인 >> 어떤일이 벌어졌는가?
kubectl scale deployment nginx-deployment --replicas=15

# 파드 증가 테스트 >> 파드 정상 생성 확인, 워커 노드에서 eth, eni 갯수 확인 >> 어떤일이 벌어졌는가?
kubectl scale deployment nginx-deployment --replicas=30

# 파드 증가 테스트 >> 파드 정상 생성 확인, 워커 노드에서 eth, eni 갯수 확인 >> 어떤일이 벌어졌는가?
**kubectl scale deployment nginx-deployment --replicas=50**

# 파드 생성 실패!
kubectl get pods | grep Pending
nginx-deployment-7fb7fd49b4-d4bk9   0/1     Pending   0          3m37s
nginx-deployment-7fb7fd49b4-qpqbm   0/1     Pending   0          3m37s
...

kubectl describe pod <Pending 파드> | grep Events: -A5
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  45s   default-scheduler  0/3 nodes are available: 1 node(s) had untolerated taint {node-role.kubernetes.io/control-plane: }, 2 **Too many pods**. preemption: 0/3 nodes are available: 1 Preemption is not helpful for scheduling, 2 No preemption victims found for incoming pod.

# 디플로이먼트 삭제
**kubectl delete deploy nginx-deployment**

~~~



![구성](/Images/eks/eksn_45.png)


![구성](/Images/eks/eksn_46.png)


![구성](/Images/eks/eksn_47.png)


![구성](/Images/eks/eksn_48.png)


![구성](/Images/eks/eksn_49.png)


![구성](/Images/eks/eksn_50.png)

![구성](/Images/eks/eksn_51.png)

![구성](/Images/eks/eksn_52.png)









</details>




**해결방안** : [해결 방안 : Prefix Delegation, WARM & MIN IP/Prefix Targets, Custom Network](https://docs.google.com/spreadsheets/d/1yhkuBJBY2iO2Ax5FcbDMdWD5QLTVO6Y_kYt_VumnEtI/edit#gid=1994017257)


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



##  How to rapidly scale your application with ALB on EKS (without losing traffic)



##  IPv6 with EKS


---
**삭제**
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~





<details><summary>실습</summary>
</details>