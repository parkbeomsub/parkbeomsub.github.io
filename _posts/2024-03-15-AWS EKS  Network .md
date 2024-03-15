---
layout: single
title: "AWS EKS Network 실습"
categories: AWS
tags: [AWS, Container, Kubernetes , EKS , DevOps ,Network ,CNI ]
toc: true
---


# AWS EKS  Network
[ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)



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

     AWS CNI  :   Container Network Interface 는 k8s 네트워크 환경을 구성해준다 [링크1](https://kubernetes.io/docs/concepts/cluster-administration/networking/)
    [링크2](https://kubernetes.io/docs/concepts/cluster-administration/addons/#networking-and-network-policy)

    - supports native VPC networking with the Amazon VPC Container Network Interface (CNI) plugin for Kubernetes.
    -  VPC 와 통합  : VPC Flow logs , VPC 라우팅 정책, 보안 그룹(Security group) 을 사용 가능함
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


 인스턴스의 네트워크 정보 확인 : 프라이빗 IP와 보조 프라이빗 IP 확인 

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

- [실습] 테스트용 파드 생성 - [nicolaka/netshoot](https://github.com/nicolaka/netshoot)

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


- 파드가 생성되면,  워커 노드 에  eniY@ifN   추가 되고 라우팅 테이블에도 정보가 추가된다

- 테스트용 파드  eniY 정보 확인  - 워커 노드 EC2

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
-  목표  : 파드간 통신 시 tcpdump 내용을 확인하고 통신 과정을 알아본다
-  파드간 통신 흐름  : AWS VPC CNI 경우 별도의 오버레이(Overlay) 통신 기술 없이, VPC Native 하게 파드간 직접 통신이 가능하다
  
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

-  파드에서 외부 통신 흐름  : iptable 에 SNAT 을 통하여 노드의 eth0 IP로 변경되어서 외부와 통신됨

![구성](/Images/eks/eksn_37.png)


- VPC CNI 의 External source network address translation (SNAT) 설정에 따라, 외부(인터넷) 통신 시 SNAT 하거나 혹은 SNAT 없이 통신을 할 수 있다  [링크](https://docs.aws.amazon.com/eks/latest/userguide/external-snat.html)



<details><summary>실습</summary>

-  파드에서 외부 통신  테스트 및 확인
- 파드 shell 실행 후 외부로 ping 테스트 & 워커 노드에서 tcpdump 및 iptables 정보 확인
~~~


 # 작업용 EC2 :  pod-1 Shell 에서 외부로 ping
kubectl exec -it $PODNAME1 -- ping -c 1 www.google.com
kubectl exec -it $PODNAME1 -- ping -i 0.1 www.google.com

 # 워커 노드 EC2  : TCPDUMP 확인
sudo tcpdump -i any -nn icmp
sudo tcpdump -i eth0 -nn icmp

 # 워커 노드 EC2  : 퍼블릭IP 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i curl -s ipinfo.io/ip; echo; echo; done

 # 작업용 EC2 :  pod-1 Shell 에서 외부 접속 확인 - 공인IP는 어떤 주소인가?
## The right way to check the weather - [링크](https://github.com/chubin/wttr.in)
for i in $PODNAME1 $PODNAME2 $PODNAME3; do echo ">> Pod : $i <<"; kubectl exec -it $i -- curl -s ipinfo.io/ip; echo; echo; done
kubectl exec -it $PODNAME1 -- curl -s  wttr.in /seoul
kubectl exec -it $PODNAME1 -- curl -s wttr.in/seoul?format=3
kubectl exec -it $PODNAME1 -- curl -s wttr.in/Moon
kubectl exec -it $PODNAME1 -- curl -s wttr.in/:help

 # 워커 노드 EC2 
## 출력된 결과를 보고 어떻게 빠져나가는지 고민해보자!
ip rule
ip route show table main
sudo  iptables -L -n -v -t nat
sudo iptables -t nat -S 

# 파드가 외부와 통신시에는 아래 처럼 'AWS-SNAT-CHAIN-0' 룰(rule)에 의해서 SNAT 되어서 외부와 통신!
# 참고로 뒤 IP는 eth0(ENI 첫번째)의 IP 주소이다
# --random-fully 동작 - [링크1](https://ssup2.github.io/issue/Linux_TCP_SYN_Packet_Drop_SNAT_Port_Race_Condition/)  [링크2](https://ssup2.github.io/issue/Kubernetes_TCP_Connection_Delay_VXLAN_CNI_Plugin/)
sudo iptables -t nat -S | grep 'A AWS-SNAT-CHAIN'
-A AWS-SNAT-CHAIN-0 ! -d  192.168.0.0/16  -m comment --comment "AWS SNAT CHAIN" -j RETURN
-A AWS-SNAT-CHAIN-0 ! -o vlan+ -m comment --comment "AWS, SNAT" -m addrtype ! --dst-type LOCAL -j SNAT --to-source  192.168.1.251  --random-fully

## 아래 'mark 0x4000/0x4000' 매칭되지 않아서 RETURN 됨!
-A KUBE-POSTROUTING -m mark ! --mark 0x4000/0x4000 -j RETURN
-A KUBE-POSTROUTING -j MARK --set-xmark 0x4000/0x0
-A KUBE-POSTROUTING -m comment --comment "kubernetes service traffic requiring SNAT" -j MASQUERADE --random-fully
...

# 카운트 확인 시 AWS-SNAT-CHAIN-0에 매칭되어, 목적지가  192.168.0.0/16  아니고 외부 빠져나갈때 SNAT  192.168.1.251(EC2 노드1 IP)  변경되어 나간다!
sudo iptables -t filter --zero; sudo iptables -t nat --zero; sudo iptables -t mangle --zero; sudo iptables -t raw --zero
watch -d 'sudo iptables -v --numeric --table nat --list AWS-SNAT-CHAIN-0; echo ; sudo iptables -v --numeric --table nat --list KUBE-POSTROUTING; echo ; sudo iptables -v --numeric --table nat --list POSTROUTING'

# conntrack 확인
 for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo conntrack -L -n |grep -v '169.254.169'; echo; done 
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

-  워커 노드의 인스턴스 타입 별 파드 생성 갯수 제한 
    -  인스턴스 타입  별 ENI 최대 갯수와 할당 가능한 최대 IP 갯수에 따라서 파드 배치 갯수가 결정됨
    - 단, aws-node 와 kube-proxy 파드는 호스트의 IP를 사용함으로 최대 갯수에서 제외함

    ![구성](/Images/eks/eksn_44.png)





<details><summary>워커 노드의 인스턴스 정보 확인 : t3.medium 사용 시</summary>


```bash
# t3 타입의 정보(필터) 확인
aws ec2 describe-instance-types --filters Name=instance-type,Values= t3. * \
 --query "InstanceTypes[].{ Type : InstanceType,  MaxENI : NetworkInfo.MaximumNetworkInterfaces,  IPv4addr : NetworkInfo.Ipv4AddressesPerInterface}" \
 --output table
--------------------------------------
|        DescribeInstanceTypes       |
+----------+----------+--------------+
| IPv4addr | MaxENI   |    Type      |
+----------+----------+--------------+
|  15      |  4       |  t3.2xlarge  |
|   6        |   3        |   t3.medium    |
|   12       |   3        |   t3.large     |
|  15      |  4       |  t3.xlarge   |
|  2       |  2       |  t3.micro    |
|  2       |  2       |  t3.nano     |
|  4       |  3       |  t3.small    |
+----------+----------+--------------+

# c5 타입의 정보(필터) 확인
aws ec2 describe-instance-types --filters Name=instance-type,Values= c5*. * \
 --query "InstanceTypes[].{ Type : InstanceType,  MaxENI : NetworkInfo.MaximumNetworkInterfaces,  IPv4addr : NetworkInfo.Ipv4AddressesPerInterface}" \
 --output table

# 파드 사용 가능 계산 예시 : aws-node 와 kube-proxy 파드는 host-networking 사용으로 IP 2개 남음
((MaxENI * (IPv4addr-1)) + 2)
 t3.medium  경우 : ((3 * (6 - 1) +  2  ) =  17개 >>  aws-node 와 kube-proxy 2개 제외하면  15개 

# 워커노드 상세 정보 확인 : 노드 상세 정보의 Allocatable 에 pods 에 17개 정보 확인
 kubectl describe node | grep Allocatable: -A6 
Allocatable:
  cpu:                         1930m
  ephemeral-storage:           27905944324
  hugepages-1Gi:               0
  hugepages-2Mi:               0
  memory:                      3388360Ki
   pods:                        17 
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
 kubectl apply -f nginx-dp.yaml 

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
 kubectl scale deployment nginx-deployment --replicas=50 

# 파드 생성 실패!
kubectl get pods | grep Pending
nginx-deployment-7fb7fd49b4-d4bk9   0/1     Pending   0          3m37s
nginx-deployment-7fb7fd49b4-qpqbm   0/1     Pending   0          3m37s
...

kubectl describe pod <Pending 파드> | grep Events: -A5
Events:
  Type     Reason            Age   From               Message
  ----     ------            ----  ----               -------
  Warning  FailedScheduling  45s   default-scheduler  0/3 nodes are available: 1 node(s) had untolerated taint {node-role.kubernetes.io/control-plane: }, 2  Too many pods . preemption: 0/3 nodes are available: 1 Preemption is not helpful for scheduling, 2 No preemption victims found for incoming pod.

# 디플로이먼트 삭제
 kubectl delete deploy nginx-deployment 

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




 해결방안  : [해결 방안 : Prefix Delegation, WARM & MIN IP/Prefix Targets, Custom Network](https://docs.google.com/spreadsheets/d/1yhkuBJBY2iO2Ax5FcbDMdWD5QLTVO6Y_kYt_VumnEtI/edit#gid=1994017257)


## Service & AWS LoadBalancer Controller
 - K8S의 서비스 타입은 3가지인데 
![구성](/Images/eks/eksn_78.png)

> K8S의 모든 서비스는  워커노드의 Iptables에 따라가서 여러홉을 거친다.
반면에  LoadBalancer Controller에 의한 LB타입은 컨트롤러가 대상 아이피를 전부 저장해 놓고 있기 때문에 다이렉트로 pod로 전해진다.

`NLB 모드 전체 정리`

1.  인스턴스 유형 
    1. `externalTrafficPolicy` : ClusterIP ⇒ 2번 분산 및 SNAT으로 Client IP 확인 불가능 ← `LoadBalancer` 타입 (기본 모드) 동작
    2. `externalTrafficPolicy` : Local ⇒ 1번 분산 및 ClientIP 유지, 워커 노드의 iptables 사용함
    - 상세 설명
        
         통신 흐름 
        
         요약  : 외부 클라이언트가 '로드밸런서' 접속 시 부하분산 되어 노드 도달 후 iptables 룰로 목적지 파드와 통신됨
        
        !https://s3-us-west-2.amazonaws.com/secure.notion-static.com/154fbeb0-5b37-42b9-93f8-90c76d1ad200/Untitled.png
        
        !https://s3-us-west-2.amazonaws.com/secure.notion-static.com/f864bcc0-3c5d-4f95-8332-2ce9abf1fa83/Untitled.png
        
        - 노드는 외부에 공개되지 않고 로드밸런서만 외부에 공개되어, 외부 클라이언트는 로드밸랜서에 접속을 할 뿐 내부 노드의 정보를 알 수 없다
        - 로드밸런서가 부하분산하여 파드가 존재하는 노드들에게 전달한다, iptables 룰에서는 자신의 노드에 있는 파드만 연결한다 (`externalTrafficPolicy: local`)
        - DNAT 2번 동작 : 첫번째(로드밸런서 접속 후 빠져 나갈때), 두번째(노드의 iptables 룰에서 파드IP 전달 시)
        - 외부 클라이언트 IP 보존(유지) : AWS NLB 는  타켓 이  인스턴스 일 경우 클라이언트 IP를 유지, iptables 룰 경우도 `externalTrafficPolicy` 로 클라이언트 IP를 보존
        
         부하분산 최적화  : 노드에 파드가 없을 경우 '로드밸런서'에서 노드에 헬스 체크(상태 검사)가 실패하여 해당 노드로는 외부 요청 트래픽을 전달하지 않는다
        
        !https://s3-us-west-2.amazonaws.com/secure.notion-static.com/5c640a55-2f67-4b4d-b4b0-27b565ea0d73/Untitled.png
        
        ![3번째 인스턴스(Node3)은 상태 확인 실패로 외부 요청 트래픽 전달하지 않는다](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/3bb7b833-c811-454e-a01d-cf5f4b28863a/Untitled.png)
        
        3번째 인스턴스(Node3)은 상태 확인 실패로 외부 요청 트래픽 전달하지 않는다
        [AWS NLB - Client IP 확인 & Proxy protocol](https://www.notion.so/AWS-NLB-Client-IP-Proxy-protocol-57827e2c83fc474992b37e65db81f669?pvs=21)

        
         IP 유형 ⇒ 반드시 AWS LoadBalancer 컨트롤러 파드 및 정책 설정이 필요함! 
        1. `Proxy Protocol v2 비활성화` ⇒ NLB에서 바로 파드로 인입, 단 ClientIP가 NLB로 SNAT 되어 Client IP 확인 불가능
        2. `Proxy Protocol v2 활성화` ⇒ NLB에서 바로 파드로 인입 및 ClientIP 확인 가능(→ 단 PPv2 를 애플리케이션이 인지할 수 있게 설정 필요)

AWS LoadBalancer Controller 배포 with IRSA - 링크

<details><summary>설치</summary>

~~~

# OIDC 확인
aws eks describe-cluster --name $CLUSTER_NAME --query "cluster.identity.oidc.issuer" --output text
aws iam list-open-id-connect-providers | jq

# IAM Policy (AWSLoadBalancerControllerIAMPolicy) 생성
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.5.4/docs/install/iam_policy.json
aws iam create-policy --policy-name AWSLoadBalancerControllerIAMPolicy --policy-document file://iam_policy.json

# 혹시 이미 IAM 정책이 있지만 예전 정책일 경우 아래 처럼 최신 업데이트 할 것
# aws iam update-policy ~~~

# 생성된 IAM Policy Arn 확인
aws iam list-policies --scope Local | jq
aws iam get-policy --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy | jq
aws iam get-policy --policy-arn arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy --query 'Policy.Arn'

# AWS Load Balancer Controller를 위한 ServiceAccount를 생성 >> 자동으로 매칭되는 IAM Role 을 CloudFormation 으로 생성됨!
# IAM 역할 생성. AWS Load Balancer Controller의 kube-system 네임스페이스에 aws-load-balancer-controller라는 Kubernetes 서비스 계정을 생성하고 IAM 역할의 이름으로 Kubernetes 서비스 계정에 주석을 답니다
eksctl create iamserviceaccount --cluster=$CLUSTER_NAME --namespace=kube-system --name=aws-load-balancer-controller --role-name AmazonEKSLoadBalancerControllerRole \
--attach-policy-arn=arn:aws:iam::$ACCOUNT_ID:policy/AWSLoadBalancerControllerIAMPolicy --override-existing-serviceaccounts --approve

## IRSA 정보 확인
eksctl get iamserviceaccount --cluster $CLUSTER_NAME

## 서비스 어카운트 확인
kubectl get serviceaccounts -n kube-system aws-load-balancer-controller -o yaml | yh

# Helm Chart 설치
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

## 설치 확인 : aws-load-balancer-controller:v2.7.1
kubectl get crd
kubectl get deployment -n kube-system aws-load-balancer-controller
kubectl describe deploy -n kube-system aws-load-balancer-controller
kubectl describe deploy -n kube-system aws-load-balancer-controller | grep 'Service Account'
  Service Account:  aws-load-balancer-controller
 
# 클러스터롤, 롤 확인
kubectl describe clusterrolebindings.rbac.authorization.k8s.io aws-load-balancer-controller-rolebinding
kubectl describe clusterroles.rbac.authorization.k8s.io aws-load-balancer-controller-role
...
PolicyRule:
  Resources                                     Non-Resource URLs  Resource Names  Verbs
  ---------                                     -----------------  --------------  -----
  targetgroupbindings.elbv2.k8s.aws             []                 []              [create delete get list patch update watch]
  events                                        []                 []              [create patch]
  ingresses                                     []                 []              [get list patch update watch]
  services                                      []                 []              [get list patch update watch]
  ingresses.extensions                          []                 []              [get list patch update watch]
  services.extensions                           []                 []              [get list patch update watch]
  ingresses.networking.k8s.io                   []                 []              [get list patch update watch]
  services.networking.k8s.io                    []                 []              [get list patch update watch]
  endpoints                                     []                 []              [get list watch]
  namespaces                                    []                 []              [get list watch]
  nodes                                         []                 []              [get list watch]
  pods                                          []                 []              [get list watch]
  endpointslices.discovery.k8s.io               []                 []              [get list watch]
  ingressclassparams.elbv2.k8s.aws              []                 []              [get list watch]
  ingressclasses.networking.k8s.io              []                 []              [get list watch]
  ingresses/status                              []                 []              [update patch]
  pods/status                                   []                 []              [update patch]
  services/status                               []                 []              [update patch]
  targetgroupbindings/status                    []                 []              [update patch]
  ingresses.elbv2.k8s.aws/status                []                 []              [update patch]
  pods.elbv2.k8s.aws/status                     []                 []              [update patch]
  services.elbv2.k8s.aws/status                 []                 []              [update patch]
  targetgroupbindings.elbv2.k8s.aws/status      []                 []              [update patch]
  ingresses.extensions/status                   []                 []              [update patch]
  pods.extensions/status                        []                 []              [update patch]
  services.extensions/status                    []                 []              [update patch]
  targetgroupbindings.extensions/status         []                 []              [update patch]
  ingresses.networking.k8s.io/status            []                 []              [update patch]
  pods.networking.k8s.io/status                 []                 []              [update patch]
  services.networking.k8s.io/status             []                 []              [update patch]
  targetgroupbindings.networking.k8s.io/status  []                 []              [update patch]

~~~

![구성](/Images/eks/eksn_53.png)
![구성](/Images/eks/eksn_54.png)
![구성](/Images/eks/eksn_55.png)
![구성](/Images/eks/eksn_56.png)
![구성](/Images/eks/eksn_57.png)
![구성](/Images/eks/eksn_58.png)
![구성](/Images/eks/eksn_59.png)
![구성](/Images/eks/eksn_60.png)
![구성](/Images/eks/eksn_61.png)





</details>

---


<details><summary>테스트</summary>

~~~

# 모니터링
watch -d kubectl get pod,svc,ep

# 작업용 EC2 - 디플로이먼트 & 서비스 생성
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/2/echo-service-nlb.yaml
cat echo-service-nlb.yaml | yh
kubectl apply -f echo-service-nlb.yaml

# 확인
kubectl get deploy,pod
kubectl get svc,ep,ingressclassparams,targetgroupbindings
kubectl get targetgroupbindings -o json | jq

# (옵션) 빠른 실습을 위해서 등록 취소 지연(드레이닝 간격) 수정 : 기본값 300초
vi echo-service-nlb.yaml
..
apiVersion: v1
kind: Service
metadata:
  name: svc-nlb-ip-type
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    service.beta.kubernetes.io/aws-load-balancer-healthcheck-port: "8080"
    service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
    service.beta.kubernetes.io/aws-load-balancer-target-group-attributes: deregistration_delay.timeout_seconds=60
...
:wq!
kubectl apply -f echo-service-nlb.yaml

# AWS ELB(NLB) 정보 확인
aws elbv2 describe-load-balancers | jq
aws elbv2 describe-load-balancers --query 'LoadBalancers[*].State.Code' --output text
ALB_ARN=$(aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `k8s-default-svcnlbip`) == `true`].LoadBalancerArn' | jq -r '.[0]')
aws elbv2 describe-target-groups --load-balancer-arn $ALB_ARN | jq
TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --load-balancer-arn $ALB_ARN | jq -r '.TargetGroups[0].TargetGroupArn')
aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN | jq
{
  "TargetHealthDescriptions": [
    {
      "Target": {
        "Id": "192.168.2.153",
        "Port": 8080,
        "AvailabilityZone": "ap-northeast-2b"
      },
      "HealthCheckPort": "8080",
      "TargetHealth": {
        "State": "initial",
        "Reason": "Elb.RegistrationInProgress",
        "Description": "Target registration is in progress"
      }
    },
...

# 웹 접속 주소 확인
kubectl get svc svc-nlb-ip-type -o jsonpath={.status.loadBalancer.ingress[0].hostname} | awk '{ print "Pod Web URL = http://"$1 }'

# 파드 로깅 모니터링
kubectl logs -l app=deploy-websrv -f

# 분산 접속 확인
NLB=$(kubectl get svc svc-nlb-ip-type -o jsonpath={.status.loadBalancer.ingress[0].hostname})
curl -s $NLB
for i in {1..100}; do curl -s $NLB | grep Hostname ; done | sort | uniq -c | sort -nr
  52 Hostname: deploy-echo-55456fc798-2w65p
  48 Hostname: deploy-echo-55456fc798-cxl7z

# 지속적인 접속 시도 : 아래 상세 동작 확인 시 유용(패킷 덤프 등)
while true; do curl -s --connect-timeout 1 $NLB | egrep 'Hostname|client_address'; echo "----------" ; date "+%Y-%m-%d %H:%M:%S" ; sleep 1; done

~~~


- AWS NLB의 대상 그룹 확인 : IP를 확인해보자
- 파드 2개 → 1개 → 3개 설정 시 동작 : auto discovery ← 어떻게 동작?

~~~


# (신규 터미널) 모니터링
while true; do aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN --output text; echo; done

# 작업용 EC2 - 파드 1개 설정 
kubectl scale deployment deploy-echo --replicas=1

# 확인
kubectl get deploy,pod,svc,ep
curl -s $NLB
for i in {1..100}; do curl -s --connect-timeout 1 $NLB | grep Hostname ; done | sort | uniq -c | sort -nr

# 작업용 EC2 - 파드 3개 설정 
kubectl scale deployment deploy-echo --replicas=3

# 확인 : NLB 대상 타켓이 아직 initial 일 때 100번 반복 접속 시 어떻게 되는지 확인해보자!
kubectl get deploy,pod,svc,ep
curl -s $NLB
for i in {1..100}; do curl -s --connect-timeout 1 $NLB | grep Hostname ; done | sort | uniq -c | sort -nr

# 
kubectl describe deploy -n kube-system aws-load-balancer-controller | grep -i 'Service Account'
  Service Account:  aws-load-balancer-controller

# [AWS LB Ctrl] 클러스터 롤 바인딩 정보 확인
kubectl describe clusterrolebindings.rbac.authorization.k8s.io aws-load-balancer-controller-rolebinding

# [AWS LB Ctrl] 클러스터롤 확인 
kubectl describe clusterroles.rbac.authorization.k8s.io aws-load-balancer-controller-role


~~~

> 실습 리소스 삭제:  kubectl delete deploy deploy-echo; kubectl delete svc svc-nlb-ip-type


![구성](/Images/eks/eksn_63.png)

![구성](/Images/eks/eksn_64.png)




</details>


<details><summary>심화 -도전 </summary>


-  (심화) Pod readiness gate  : ALB/NLB 대상(ip mode)이 ALB/NLB의 헬스체크에 의해 정상일 경우 해당 파드로 전달할 수 있는 기능 - [Link](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.7/deploy/pod_readiness_gate/) [K8S](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/#pod-readiness-gate)
    - 사전 준비
    
    ```bash
    # 바로 위에서 실습 리소스 삭제했다면, 다시 생성 : deregistration_delay.timeout_seconds=60 확인
     kubectl apply -f echo-service-nlb.yaml 
    kubectl scale deployment deploy-echo --replicas=1
    
    #
     kubectl get pod -owide 
    NAME                           READY   STATUS    RESTARTS   AGE   IP              NODE                                               NOMINATED NODE   READINESS GATES
    deploy-echo-7f579ff9d7-gqdf5   1/1     Running   0          20m   192.168.2.153   ip-192-168-2-108.ap-northeast-2.compute.internal   <none>           <none>
    
    # mutatingwebhookconfigurations 확인 : mutating 대상(네임스페이스에 아래 매칭 시)
    kubectl get mutatingwebhookconfigurations
     kubectl get mutatingwebhookconfigurations aws-load-balancer-webhook -o yaml | kubectl neat | yh 
    ...
      name: mpod.elbv2.k8s.aws
       namespaceSelector : 
        matchExpressions: 
        - key:  elbv2.k8s.aws/pod-readiness-gate-inject 
          operator: In
          values: 
          - enabled
      objectSelector: 
        matchExpressions: 
        - key: app.kubernetes.io/name
          operator: NotIn
          values: 
          - aws-load-balancer-controller
    ...
    
    # 현재 확인
     kubectl get ns --show-labels 
    NAME              STATUS   AGE   LABELS
    default           Active   75m   kubernetes.io/metadata.name=default
    kube-node-lease   Active   75m   kubernetes.io/metadata.name=kube-node-lease
    kube-public       Active   75m   kubernetes.io/metadata.name=kube-public
    kube-system       Active   75m   kubernetes.io/metadata.name=kube-system
    ```
    
    - 설정 및 확인
    
    ```bash
    # (터미널 각각 2개) 모니터링
    watch -d kubectl get pod,svc,ep -owide
    while true; do aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN --output text; echo; done
    
    #
     kubectl label namespace default elbv2.k8s.aws/pod-readiness-gate-inject=enabled 
    kubectl get ns --show-labels
    
    # READINESS GATES 항목 추가 확인
    kubectl describe pod
     kubectl get pod -owide 
    NAME                           READY   STATUS    RESTARTS   AGE   IP              NODE                                               NOMINATED NODE    READINESS GATES 
    deploy-echo-7f579ff9d7-gqdf5   1/1     Running   0          25m   192.168.2.153   ip-192-168-2-108.ap-northeast-2.compute.internal   <none>           <none>
    
    #
     kubectl delete pod --all 
     kubectl get pod -owide 
    NAME                           READY   STATUS    RESTARTS   AGE     IP              NODE                                               NOMINATED NODE    READINESS GATES 
    deploy-echo-6959b47ddf-h9vhc   1/1     Running   0          3m21s   192.168.1.127   ip-192-168-1-113.ap-northeast-2.compute.internal   <none>           1/1
    
     kubectl describe pod 
    ...
    Readiness Gates:
      Type                                                          Status
      target-health.elbv2.k8s.aws/k8s-default-svcnlbip-5eff23b37f   True 
    Conditions:
      Type                                                          Status
      target-health.elbv2.k8s.aws/k8s-default-svcnlbip-5eff23b37f   True 
      Initialized                                                   True 
      Ready                                                         True 
      ContainersReady                                               True 
      PodScheduled                                                  True 
    ...
    
     kubectl get pod -o yaml | yh 
    ...
        readinessGates: 
        - conditionType: target-health.elbv2.k8s.aws/k8s-default-svcnlbip-5eff23b37f
    ...
      status: 
        conditions: 
        - lastProbeTime: null
          lastTransitionTime: "2024-03-10T02:00:50Z"
          status: "True"
          type:  target-health.elbv2.k8s.aws/k8s-default-svcnlbip-5eff23b37f 
    ...
    
    # 분산 접속 확인
    NLB=$(kubectl get svc svc-nlb-ip-type -o jsonpath={.status.loadBalancer.ingress[0].hostname})
    curl -s $NLB
    for i in {1..100}; do curl -s $NLB | grep Hostname ; done | sort | uniq -c | sort -nr
    ```
    
    - 실습 리소스 삭제:  `kubectl delete deploy deploy-echo; kubectl delete svc svc-nlb-ip-type`
    
- NLB 대상 타켓을  Instance mode  로 설정해보기
- NLB IP Target &  Proxy Protocol v2  활성화 : NLB에서 바로 파드로 인입 및 ClientIP 확인 설정 - [링크](https://www.notion.so/AWS-NLB-Client-IP-Proxy-protocol-57827e2c83fc474992b37e65db81f669?pvs=21) [image](https://hub.docker.com/r/gasida/httpd/tags) [참고](https://canaryrelease.tistory.com/42)



</details>

## Ingress

- 인그레스 소개 : 클러스터 내부의 서비스(ClusterIP, NodePort, Loadbalancer)를 외부로 노출(HTTP/HTTPS) - Web Proxy 역할
![구성](/Images/eks/eksn_79.png)
- AWS LB타입으로 인해 다이렉트로 파드로 인입되는 장점을 활용, Ingress를 통해 http/https  ALB의 동작을 수행한다.



<details><summary>베포 / 설치</summary>


~~~
# 게임 파드와 Service, Ingress 배포
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/ingress1.yaml
cat ingress1.yaml | yh
kubectl apply -f ingress1.yaml

# 모니터링
watch -d kubectl get pod,ingress,svc,ep -n game-2048

# 생성 확인
kubectl get-all -n game-2048
kubectl get ingress,svc,ep,pod -n game-2048
kubectl get targetgroupbindings -n game-2048
NAME                               SERVICE-NAME   SERVICE-PORT   TARGET-TYPE   AGE
k8s-game2048-service2-e48050abac   service-2048   80             ip            87s

# ALB 생성 확인
aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `k8s-game2048`) == `true`]' | jq
ALB_ARN=$(aws elbv2 describe-load-balancers --query 'LoadBalancers[?contains(LoadBalancerName, `k8s-game2048`) == `true`].LoadBalancerArn' | jq -r '.[0]')
aws elbv2 describe-target-groups --load-balancer-arn $ALB_ARN
TARGET_GROUP_ARN=$(aws elbv2 describe-target-groups --load-balancer-arn $ALB_ARN | jq -r '.TargetGroups[0].TargetGroupArn')
aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN | jq

# Ingress 확인
kubectl describe ingress -n game-2048 ingress-2048
kubectl get ingress -n game-2048 ingress-2048 -o jsonpath="{.status.loadBalancer.ingress[*].hostname}{'\n'}"

# 게임 접속 : ALB 주소로 웹 접속
kubectl get ingress -n game-2048 ingress-2048 -o jsonpath={.status.loadBalancer.ingress[0].hostname} | awk '{ print "Game URL = http://"$1 }'

# 파드 IP 확인
kubectl get pod -n game-2048 -owide

~~~

![구성](/Images/eks/eksn_65.png)

![구성](/Images/eks/eksn_66.png)

![구성](/Images/eks/eksn_67.png)

![구성](/Images/eks/eksn_68.png)

![구성](/Images/eks/eksn_69.png)


</details>

<details><summary>테스트 시나리오</summary>


- 파드 3개로 증가

~~~

# 터미널1
watch kubectl get pod -n game-2048
while true; do aws elbv2 describe-target-health --target-group-arn $TARGET_GROUP_ARN --output text; echo; done

# 터미널2 : 파드 3개로 증가
kubectl scale deployment -n game-2048 deployment-2048 --replicas 3

~~~

- 파드 1개로 감소

~~~

# 터미널2 : 파드 1개로 감소
kubectl scale deployment -n game-2048 deployment-2048 --replicas 1

~~~

> 실습 리소스  삭제

~~~

kubectl delete ingress ingress-2048 -n game-2048
kubectl delete svc service-2048 -n game-2048 && kubectl delete deploy deployment-2048 -n game-2048 && kubectl delete ns game-2048

~~~

</details>

심화 링크

Exposing Kubernetes Applications, Part 1: Service and Ingress Resources - [링크](https://aws.amazon.com/ko/blogs/containers/exposing-kubernetes-applications-part-1-service-and-ingress-resources/)

## ExternalDNS
- AWS에서는  K8S 서비스/인그레스 생성 시 도메인을 설정하면, AWS(Route 53), Azure(DNS), GCP(Cloud DNS) 에 A 레코드(TXT 레코드)로 자동 생성/삭제 가능

![구성](/Images/eks/eksn_80.png)

- 권한을 주는 방법이 다양한데 ( Node IAM Role, Static credentials, IRSA )


해당 실습을 위해 도메인이 필요합니다./ 없으시면 참고 부탁드리며 저 개인 도메인은  base-on.com 입니다.

<details><summary>실습 </summary>


-  Route53 정보 확인 및 변수 지정~

    ~~~

    # 자신의 도메인 변수 지정 : 소유하고 있는 자신의 도메인을 입력하시면 됩니다
    MyDomain=<자신의 도메인>
    MyDomain=base-on.com
    echo "export MyDomain=gasida.link" >> /etc/profile

    # 자신의 Route 53 도메인 ID 조회 및 변수 지정
    aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." | jq
    aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Name"
    aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text
    MyDnzHostedZoneId=`aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text`
    echo $MyDnzHostedZoneId

    # (옵션) NS 레코드 타입 첫번째 조회
    aws route53 list-resource-record-sets --output json --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'NS']" | jq -r '.[0].ResourceRecords[].Value'
    # (옵션) A 레코드 타입 모두 조회
    aws route53 list-resource-record-sets --output json --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A']"

    # A 레코드 타입 조회
    aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A']" | jq
    aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A'].Name" | jq
    aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A'].Name" --output text

    # A 레코드 값 반복 조회
    while true; do aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A']" | jq ; date ; echo ; sleep 1; done

    ~~~


    - Exteral DNS 설치 [참조](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md)

    ~~~

    # EKS 배포 시 Node IAM Role 설정되어 있음
    # eksctl create cluster ... --external-dns-access ...

    # 
    MyDomain=<자신의 도메인>
    MyDomain=gasida.link

    # 자신의 Route 53 도메인 ID 조회 및 변수 지정
    MyDnzHostedZoneId=$(aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text)

    # 변수 확인
    echo $MyDomain, $MyDnzHostedZoneId

    # ExternalDNS 배포
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/externaldns.yaml
    sed -i "s/0.13.4/0.14.0/g" externaldns.yaml
    cat externaldns.yaml | yh
    MyDomain=$MyDomain MyDnzHostedZoneId=$MyDnzHostedZoneId envsubst < externaldns.yaml | kubectl apply -f -

    # 확인 및 로그 모니터링
    kubectl get pod -l app.kubernetes.io/name=external-dns -n kube-system
    kubectl logs deploy/external-dns -n kube-system -f

    ~~~

    - (참고) 기존에 ExternalDNS를 통해 사용한 A/TXT 레코드가 있는 존의 경우에 policy 정책을 upsert-only 로 설정 후 사용 하자 - [Link](https://github.com/kubernetes-sigs/external-dns/blob/master/docs/tutorials/aws.md#deploy-externaldns)
    - 해당 옵션은 삭제하면 등록되어 있는 레코드를 남기는 옵션 -> 이번 실습에서는 빠른 실습을 위해 삭제

    ~~~
     --policy=upsert-only # would prevent ExternalDNS from deleting any records, omit to enable full synchronization

    ~~~

    Service(NLB) + 도메인 연동(ExternalDNS) - [도메인체크](https://www.whatsmydns.net/)

    ~~~

    # 터미널1 (모니터링)
    watch -d 'kubectl get pod,svc'
    kubectl logs deploy/external-dns -n kube-system -f

    # 테트리스 디플로이먼트 배포
    cat <<EOF | kubectl create -f -
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: tetris
      labels:
        app: tetris
    spec:
      replicas: 1
      selector:
        matchLabels:
          app: tetris
      template:
        metadata:
          labels:
            app: tetris
        spec:
          containers:
          - name: tetris
            image: bsord/tetris
    ---
    apiVersion: v1
    kind: Service
    metadata:
      name: tetris
      annotations:
        service.beta.kubernetes.io/aws-load-balancer-nlb-target-type: ip
        service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
        service.beta.kubernetes.io/aws-load-balancer-cross-zone-load-balancing-enabled: "true"
        service.beta.kubernetes.io/aws-load-balancer-backend-protocol: "http"
        #service.beta.kubernetes.io/aws-load-balancer-healthcheck-port: "80"
    spec:
      selector:
        app: tetris
      ports:
      - port: 80
        protocol: TCP
        targetPort: 80
      type: LoadBalancer
      loadBalancerClass: service.k8s.aws/nlb
    EOF

    # 배포 확인
    kubectl get deploy,svc,ep tetris

    # NLB에 ExternanDNS 로 도메인 연결
    kubectl annotate service tetris "external-dns.alpha.kubernetes.io/hostname=tetris.$MyDomain"
    while true; do aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A']" | jq ; date ; echo ; sleep 1; done

    # Route53에 A레코드 확인
    aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A']" | jq
    aws route53 list-resource-record-sets --hosted-zone-id "${MyDnzHostedZoneId}" --query "ResourceRecordSets[?Type == 'A'].Name" | jq .[]

    # 확인
    dig +short tetris.$MyDomain @8.8.8.8
    dig +short tetris.$MyDomain

    # 도메인 체크
    echo -e "My Domain Checker = https://www.whatsmydns.net/#A/tetris.$MyDomain"

    # 웹 접속 주소 확인 및 접속
    echo -e "Tetris Game URL = http://tetris.$MyDomain"

    ~~~


(/Images/eks/eksn_71.png)
(/Images/eks/eksn_72.png)
(/Images/eks/eksn_73.png)
(/Images/eks/eksn_74.png)
(/Images/eks/eksn_75.png)
(/Images/eks/eksn_76.png)
(/Images/eks/eksn_77.png)



> 리소스 삭제 : kubectl delete deploy,svc tetris ← 삭제 시 externaldns 에 의해서 A레코드도 같이 삭제됨





</details>




## Istio


- Getting Started with Istio on Amazon EKS - [Link](https://aws.amazon.com/ko/blogs/opensource/getting-started-with-istio-on-amazon-eks/)
- Using Istio Traffic Management on Amazon EKS to Enhance User Experience - [Link](https://aws.amazon.com/ko/blogs/opensource/using-istio-traffic-management-to-enhance-user-experience/)

`추천 영상` : [토스 SLASH 22](https://youtu.be/ftFHZwyUN38)

<details><summary>서비스 매시(Service Mesh)</summary>

    -  등장 배경  : 마이크로서비스 아키텍처 환경의 시스템 전체 모니터링의 어려움, 운영 시 시스템 문제 발생할 때 원인과 병목 구간 찾기 어려움
    -  개념  : 마이크로서비스 간에 매시 형태의  통신 이나 그  경로 를  제어  - 예) 이스티오(Istio), 링커드(Linkerd), AWS App Mesh - [링크](https://layer5.io/service-mesh-landscape)
    -  기본 동작  : 파드 간 통신 경로에 프록시를 놓고  트래픽 모니터링 이나  트래픽 컨트롤  → 기존 애플리케이션  코드에 수정 없이  구성 가능!
    -  트래픽 모니터링  : 요청의 '에러율, 레이턴시, 커넥션 개수, 요청 개수' 등 메트릭 모니터링, 특정 서비스간 혹은 특정 요청 경로로 필터링 → 원인 파악 용이!
    -  트래픽 컨트롤  : 트래픽 시프팅(Traffic shifting), 서킷 브레이커(Circuit Breaker), 폴트 인젝션(Fault Injection), 속도 제한(Rate Limit)
        - 트래픽 시프팅(Traffic shifting) : 예시) 99% 기존앱 + 1% 신규앱 , 특정 단말/사용자는 신규앱에 전달하여 단계적으로 적용하는 카니리 배포 가능
        - 서킷 브레이커(Circuit Breaker) : 목적지 마이크로서비스에 문제가 있을 시 접속을 차단하고 출발지 마이크로서비스에 요청 에러를 반환 (연쇄 장애, 시스템 전제 장애 예방)
        - 폴트 인젝션(Fault Injection) : 의도적으로 요청을 지연 혹은 실패를 구현
        - 속도 제한(Rate Limit) : 요청 개수를 제한

</details>
<details><summary>이스티오 소개</summary>

- '구글 IBM 리프트(Lyft)'가 중심이 되어 개발하고 있는 오픈 소스 소프트웨어이며, C++ 로 만들어진 엔보이(Envoy)를 사용하여 서비스 매시를 구성
    
    ![https://istio.io/latest/docs/ops/deployment/architecture/](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/ce82b997-7c6e-4aaa-9d2c-0d49854a4b1c/istio-arch.svg)
    
    https://istio.io/latest/docs/ops/deployment/architecture/
    
    -  Istio 구성요소와 envoy  : 컨트롤 플레인( istiod ) ,  데이터 플레인 (istio-proxy >  envoy )
        -  istiod  :  Pilot (데이터 플레인과 통신하면서 라우팅 규칙을 동기화, ADS),  Gally (Istio 와 K8S 연동, Endpoint 갱신 등),  Citadel (연결 암호화, 인증서관리 등)
            
            ![https://istio.io/latest/docs/concepts/security/](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/d2ed8eb7-3cc7-4470-86d7-ba855467a567/arch-sec.svg)
            
            https://istio.io/latest/docs/concepts/security/
            
        - Envoy proxy : C++ 구현된 고성능 프록시, 네트워크의 투명성을 목표, 다양한  필터체인  지원(L3/L4, HTTP L7), 동적 configuration API 제공 - [링크](https://www.envoyproxy.io/docs/envoy/latest/intro/what_is_envoy)
    - 이스티오는 각  파드  안에  사이드카 로  엔보이 프록시 가 들어가 있는 형태
    - 모든 마이크로서비스간 통신은 엔보이를 통과하여,  메트릭을 수집 하거나  트래픽 컨트롤 을 할 수 있음
    - 트래픽 컨트롤을 하기위해 엔보이 프록시에  전송 룰 을 설정 →  컨트롤 플레인 의  이스티오 가 정의된 정보를 기반으로  엔보이 설정 을 하게 함
    - 마이크로서비스 간의 통신을 mutual TLS 인증( mTLS )으로 서로 TLS 인증으로 암호화 할 수 있음
    - 각 애플리케이션은  파드  내의 엔보이 프록시에 접속하기 위해  localhost 에 TCP 접속 을 함

</details>


<details><summary>Envoy 소개</summary>

-    L7 Proxy  , Istio 의 Sidecar proxy 로 사용 - [링크](https://www.envoyproxy.io/docs/envoy/latest/intro/life_of_a_request) [주요 용어](https://www.envoyproxy.io/docs/envoy/latest/intro/arch_overview/intro/terminology)
    -  Istio 구성요소와 envoy  : 컨트롤 플레인(istiod) - ADS 를 이용한 Configuration 동기화 - 데이터 플레인(istio-proxy > envoy)
    
    ![https://blog.naver.com/alice_k106/222000680202](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/832f0d89-1e5c-4f32-a612-4125acbf1902/Untitled.png)
    
    https://blog.naver.com/alice_k106/222000680202
    
    ![https://www.envoyproxy.io/docs/envoy/latest/intro/life_of_a_request](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/edd537ec-6ec0-4fc5-b209-f4e0683daa1d/lor-architecture.svg)
    
    https://www.envoyproxy.io/docs/envoy/latest/intro/life_of_a_request
    
    -  Cluster  : envoy 가 트래픽을 포워드할 수 있는 논리적인 서비스 (엔드포인트 세트), 실제 요청이 처리되는 IP 또는 엔드포인트의 묶음을 의미.
    -  Endpoint  : IP 주소, 네트워크 노드로 클러스터로 그룹핑됨, 실제 접근이 가능한 엔드포인트를 의미. 엔드포인트가 모여서 하나의 Cluster 가 된다.
    -  Listener  : 무엇을 받을지 그리고 어떻게 처리할지 IP/Port 를 바인딩하고, 요청 처리 측면에서 다운스트림을 조정하는 역할.
    -  Route  : Listener 로 들어온 요청을 어디로 라우팅할 것인지를 정의. 라우팅 대상은 일반적으로 Cluster 라는 것에 대해 이뤄지게 된다.
    -  Filter  : Listener 로부터 서비스에 트래픽을 전달하기까지 요청 처리 파이프라인
    - UpStream : envoy 요청을 포워딩해서 연결하는 백엔드 네트워크 노드 - 사이드카일때 application app, 아닐때 원격 백엔드
    - DownStream : An entity connecting to envoy, In non-sidecar models this is a remote client

</details>



<details><summary>작업용 EC2에 Envoy 설치</summary>

- [링크](https://www.envoyproxy.io/docs/envoy/latest/start/install)
    
    ```bash
    #
    sudo rpm --import 'https://rpm.dl.getenvoy.io/public/gpg.CF716AF503183491.key'
    curl -sL 'https://rpm.dl.getenvoy.io/public/config.rpm.txt?distro=el&codename=7' > /tmp/tetrate-getenvoy-rpm-stable.repo
    sudo yum-config-manager --add-repo '/tmp/tetrate-getenvoy-rpm-stable.repo'
    sudo yum makecache --disablerepo='*' --enablerepo='tetrate-getenvoy-rpm-stable' -y
    sudo yum install getenvoy-envoy -y
    
    # 확인
    envoy --version
    envoy  version: d362e791eb9e4efa8d87f6d878740e72dc8330ac/1.18.2/clean-getenvoy-76c310e-envoy/RELEASE/BoringSSL
    
    # 도움말
    envoy --help
    ```
    
</details>



<details><summary>Envoy proxy 실습 </summary>



-  Envoy proxy 실습 
    - envoy-demo.yaml
        
        ```yaml
         static _resources:
        
           listeners :
          - name: listener_0
            address:
               socket_address :
                address:  0.0.0.0 
                port_value:  10000 
            filter_chains:
            - filters:
              - name: envoy.filters.network.http_connection_manager
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                  stat_prefix: ingress_http
                  access_log:
                  - name: envoy.access_loggers.stdout
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
                  http_filters:
                  - name: envoy.filters.http.router
                   route_config :
                    name: local_route
                    virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      routes:
                      - match:
                          prefix: "/"
                        route:
                          host_rewrite_literal: www.envoyproxy.io
                           cluster : service_envoyproxy_io
        
           clusters :
          - name: service_envoyproxy_io
            type: LOGICAL_DNS
            # Comment out the following line to test on v6 networks
            dns_lookup_family: V4_ONLY
             connect_timeout: 5s 
            load_assignment:
              cluster_name: service_envoyproxy_io
              endpoints:
              - lb_endpoints:
                -  endpoint :
                    address:
                      socket_address:
                        address: www.envoyproxy.io
                        port_value: 443
            transport_socket:
              name: envoy.transport_sockets.tls
              typed_config:
                "@type": type.googleapis.com/envoy.extensions.transport_sockets.tls.v3.UpstreamTlsContext
                sni: www.envoyproxy.io
        ```
        
    
    ```bash
    # 데모 config 적용하여 실행
    curl -O https://www.envoyproxy.io/docs/envoy/latest/_downloads/92dcb9714fb6bc288d042029b34c0de4/envoy-demo.yaml
    envoy -c envoy-demo.yaml
    
    # 에러 출력되면서 실행 실패
    error initializing configuration 'envoy-demo.yaml': Field ' connect_timeout ' is missing in: name: "service_envoyproxy_io"
    
    # (터미널1) connect_timeout 추가 후 다시 실행
    sed -i'' -r -e "/dns_lookup_family/a\    connect_timeout: 5s" envoy-demo.yaml
    envoy -c envoy-demo.yaml
    ## 출력 로그
    [2021-12-13T12:20:25.981Z] "GET / HTTP/1.1" 200 - 0 4472 1140 1080 "-" "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.93 Safari/537.36" "a6999dc1-5e5e-4029-89b7-331b081fca27" "www.envoyproxy.io" "52.220.193.16:443"
    [2021-12-13T12:22:21.634Z] "GET / HTTP/1.1" 200 - 0 17228 247 121  "-" "curl/7.74.0" "39b7b07d-3f79-4e61-81b4-2944bd041535" "www.envoyproxy.io" "167.99.78.230:443"
    
    # (터미널2) 정보 확인
    ss -tnlp
    State    Recv-Q  Send-Q    Local Address:Port   Peer Address:Port    Process
    LISTEN   0       4096      0.0.0.0:10000        0.0.0.0:*            users:(("envoy",pid=8007,fd=18),("envoy",pid=8007,fd=16))
    
    # 접속 테스트
    curl -s http://127.0.0.1:10000 | grep -o "<title>.*</title>"
    <title>Envoy Proxy - Home</title>
    
    # 자신의PC(웹브라우저)에서 작업용EC2 접속 확인 >> 어느 사이트로 접속이 되는가?
    echo -e "Envoy Proxy Demo = http://$(curl -s ipinfo.io/ip):10000"
    
    # 연결 정보 확인
     ss -tnp 
    
    # (터미널1) envoy 실행 취소(CTRL+C) 후 (관리자페이지) 설정 덮어쓰기 - [링크](https://www.envoyproxy.io/docs/envoy/latest/start/quick-start/run-envoy#override-the-default-configuration)
    cat <<EOT> envoy-override.yaml
     admin :
      address:
        socket_address:
          address:  0.0.0.0 
          port_value:  9902 
    EOT
    envoy -c envoy-demo.yaml --config-yaml "$(cat envoy-override.yaml)"
    
    #  웹브라우저 에서  http://192.168.10.254:9902  접속 확인!
    # 자신의PC(웹브라우저)에서 작업용EC2 접속 확인 >> 어느 사이트로 접속이 되는가?
    echo -e "Envoy Proxy Demo = http://$(curl -s ipinfo.io/ip): 9902 "
    ```
    
    ![clusters 클릭 확인endpoint) , listeners 클릭 확인](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/598c68aa-9465-48ee-9a90-1a5a6e0a5340/Untitled.png)
    
    clusters 클릭 확인endpoint) , listeners 클릭 확인
    
    - myhome.yaml ← 파일 생성
        
        ```yaml
        cat <<EOT> myhome.yaml
         admin :
          address:
            socket_address:
              address:  0.0.0.0 
              port_value:  9902 
        
         static _resources:
        
           listeners :
          - name: listener_1
            address:
              socket_address:
                address: 0.0.0.0
                port_value:  20000 
            filter_chains:
            - filters:
              - name: envoy.filters.network.http_connection_manager
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                  stat_prefix: ingress_http
                  access_log:
                  - name: envoy.access_loggers.stdout
                    typed_config:
                      "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
                  http_filters:
                  - name: envoy.filters.http.router
                   route_config :
                    name: local_route
                    virtual_hosts:
                    - name: local_service
                      domains: ["*"]
                      routes:
                      - match:
                          prefix: "/"
                        route:
                           cluster : myhome
        
           clusters :
          - name: myhome
            type: STATIC
            dns_lookup_family: V4_ONLY
             connect_timeout: 5s 
            lb_policy: ROUND_ROBIN
            load_assignment:
              cluster_name: myhome
              endpoints:
              - lb_endpoints:
                -  endpoint :
                    address:
                      socket_address:
                        address:  127.0.0.1 
                        port_value:  80 
        EOT
        ```
        
    
    ```bash
    # 작업용EC2에 웹서버 설치
    yum -y install httpd
    systemctl start httpd
    echo "myweb server test" > /var/www/html/index.html
    curl localhost
    
    # (터미널1) envoy 실행
    cat myhome.yaml | yh
    envoy -c myhome.yaml
    
    # (터미널2) 정보 확인
    curl -s http://127.0.0.1:20000
    
    # 자신의PC(웹브라우저)에서 작업용EC2 접속 확인 >> 어느 사이트로 접속이 되는가?
      echo -e "Envoy Proxy Demo = http://$(curl -s ipinfo.io/ip): 20000 "
    ```

</details>



` ingressgateway 인입 구성 방안 ` : NLB → istio-ingressgateway , ALB → istio-ingressgateway - [링크](https://www.clud.me/11354dd3-48f3-454d-917f-eca8d975e034) [링크2](https://nyyang.tistory.com/158) [링크3](https://devocean.sk.com/blog/techBoardDetail.do?ID=163656) [링크4](https://kingofbackend.tistory.com/m/244)

1.  NLB (IP mode) → istio-ingressgateway : 파드 IP로 직접 연결, Client IP 수집 시 PPv2 활성화 및 envoy 옵션 수정 필요 - [링크](https://istio.io/latest/blog/2020/show-source-ip/)
2.  *ALB(Instance mode)  → (NodePort) istio-ingressgateway : 노드의 NodePort로 연결(약간 비효율적인 연결 가능), Client IP는 XFF로 수집
3.  ALB(IP mode)  → istio-ingressgateway : 가능 할 것으로 보임, 테스트 해 볼 것
-  아래 Istio 실습 전 사전 준비 사항  : AWS LoadBalancer Controller, ExternanDNS




<details><summary>설치</summary>

-  설치  : k8s 1.23~1.26은  istio 1.17  지원됨 - [버전](https://istio.io/latest/docs/releases/supported-releases/#support-status-of-istio-releases) [설치](https://istio.io/latest/docs/setup/getting-started/) [Operator](https://istio.io/latest/docs/setup/install/operator/) [Workshop](https://archive.eksworkshop.com/advanced/310_servicemesh_with_istio/)
    
    ```bash
     # istioctl 설치 
     ISTIOV=1.17.2
    curl -s -L https://istio.io/downloadIstio | ISTIO_VERSION=$ISTIOV TARGET_ARCH=x86_64 sh - 
    tree istio-$ISTIOV -L 2
     cp istio-$ISTIOV/bin/istioctl /usr/local/bin/istioctl 
    istioctl version --remote=false
    
    # (default 프로파일) 컨트롤 플레인 배포 - [링크](https://istio.io/latest/docs/setup/additional-setup/config-profiles/) [Customizing](https://istio.io/latest/docs/setup/additional-setup/customize-installation/)
    istioctl profile list
    istioctl profile dump  default  | yh
    istioctl profile dump --config-path components.ingressGateways
    istioctl profile dump --config-path values.gateways.istio-ingressgateway
    istioctl install --set profile= default  -y
    
    # 설치 확인
    kubectl get-all -n istio-system
    kubectl get all -n istio-system
     kubectl get crd  | grep istio.io | sort 
    authorizationpolicies.security.istio.io      2023-05-02T12:22:17Z
    destinationrules.networking.istio.io         2023-05-02T12:22:17Z
    envoyfilters.networking.istio.io             2023-05-02T12:22:17Z
    gateways.networking.istio.io                 2023-05-02T12:22:17Z
    istiooperators.install.istio.io              2023-05-02T12:22:17Z
    peerauthentications.security.istio.io        2023-05-02T12:22:17Z
    proxyconfigs.networking.istio.io             2023-05-02T12:22:17Z
    requestauthentications.security.istio.io     2023-05-02T12:22:17Z
    serviceentries.networking.istio.io           2023-05-02T12:22:17Z
    sidecars.networking.istio.io                 2023-05-02T12:22:17Z
    telemetries.telemetry.istio.io               2023-05-02T12:22:17Z
    virtualservices.networking.istio.io          2023-05-02T12:22:17Z
    wasmplugins.extensions.istio.io              2023-05-02T12:22:17Z
    workloadentries.networking.istio.io          2023-05-02T12:22:17Z
    workloadgroups.networking.istio.io           2023-05-02T12:22:17Z
    
    # NodePort로 변경
    kubectl patch  svc  -n istio-system  istio-ingressgateway  -p '{"spec":{"type":"NodePort"}}'
    
    # 확인
     kubectl get svc,ep -n istio-system istio-ingressgateway 
    NAME                   TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)                                      AGE
    istio-ingressgateway   NodePort   10.100.247.44   <none>         15021:32609 /TCP,80:30479/TCP,443:31783/TCP   92m
    
    NAME                             ENDPOINTS                                                AGE
    endpoints/istio-ingressgateway   192.168.2.15:15021,192.168.2.15:8080,192.168.2.15:8443   99m
    
    # istio-ingressgateway 의 envoy 버전 확인
    kubectl exec -it deploy/istio-ingressgateway -n istio-system -c istio-proxy --  envoy --version 
    envoy  version: d799381810ae54f1cccb2a9ae79d9c6191ca2c83/ 1.25.4 -dev/Clean/RELEASE/BoringSSL
    
     kubectl get svc -n istio-system istio-ingressgateway -o jsonpath={.spec.ports[*]} | jq 
    {
      "name": " status-port ",
      "nodePort":  32609 ,
      "port":  15021 ,
      "protocol": "TCP",
      "targetPort":  15021 
    }
    {
      "name": "http2",
      "nodePort": 30479,
      "port": 80,
      "protocol": "TCP",
      "targetPort": 8080
    }
    {
      "name": "https",
      "nodePort": 31783,
      "port": 443,
      "protocol": "TCP",
      "targetPort": 8443
    }
    
     kubectl get deploy/istio-ingressgateway -n istio-system -o jsonpath={.spec.template.spec.containers[0].ports[*]} | jq 
    {
      "containerPort":  15021 ,
      "protocol": "TCP"
    }
    {
      "containerPort": 8080,
      "protocol": "TCP"
    }
    {
      "containerPort": 8443,
      "protocol": "TCP"
    }
    {
      "containerPort": 15090,
      "name": "http-envoy-prom",
      "protocol": "TCP"
    }
    
     kubectl get deploy/istio-ingressgateway -n istio-system -o jsonpath={.spec.template.spec.containers[0].readinessProbe} | jq 
    {
      "failureThreshold": 30,
      "httpGet": {
        "path": " /healthz/ready ",
        "port":  15021 ,
        "scheme": "HTTP"
      },
      "initialDelaySeconds": 1,
      "periodSeconds": 2,
      "successThreshold": 1,
      "timeoutSeconds": 1
    }
    
    #
    HPORT=$(kubectl get service istio-ingressgateway -n istio-system -o jsonpath='{.spec.ports[?(@.name=="status-port")].nodePort}')
    
    # 사용 리전의 인증서 ARN 확인
    aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text
    CERT_ARN=$(aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text)
    echo $CERT_ARN
    
    # 배포
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/ istioingress .yaml
    MyDomain=$MyDomain HPORT=$HPORT CERT_ARN=$CERT_ARN envsubst <  istioingress .yaml | kubectl apply -f -
    
    # 확인
     kubectl get pod,svc,ingress -n istio-system 
    
    # istioingress 접속 시도
    echo "https://istio.${MyDomain}"
    
      # Auto Injection with namespace label : 해당 네임스페이스에 생성되는 모든 파드들은 istio 사이드카가 자동으로 winjection 됨
    # mutating Webhook admisstion controller 사용
    kubectl label namespace default istio-injection=enabled
    kubectl get ns -L istio-injection
    NAME              STATUS   AGE     ISTIO-INJECTION
    default           Active   58m     enabled
    ...
    ```

</details>

<details><summary>배포</summary>

-  샘플 애플리케이션 배포  - [링크](https://istio.io/latest/docs/examples/bookinfo/)  [실수연발](http://www.webegt.com./cgi-bin/egt/read.cgi?board=Shakespeare&y_number=7&nnew=2) (셰익스피어) [Wikipedia](https://en.wikipedia.org/wiki/The_Comedy_of_Errors)
    
    [bookinfo + kiali를 이용한 Istio 모니터링](https://tisdev.tistory.com/2)
    
    - 4개의 마이크로서비스로 구성 : Productpage, reviews, ratings, details
        - ProductPage 페이지에서 요청을 받으면, 도서 리뷰를 보여주는 Reviews 서비스와 도서 상세 정보를 보여주는 Details 서비스에 접속하고,
        - ProductPage 는 Reviews 와 Details 결과를 사용자에게 응답한다.
        - Reviews 서비스는 v1, v2, v3 세 개의 버전이 있고 v2, v3 버전의 경우 Ratings 서비스에 접소갛여 도서에 대한 5단계 평가를 가져옴.
        - Reviews 서비스의 차이는, v1은 Rating 이 없고, v2는 검은색 별로 Ratings 가 표시되며, v3는 색깔이 있는 별로 Ratings 가 표시됨.
    
    ![https://istio.io/latest/docs/examples/bookinfo/](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/1fbd0a99-6bf3-41c4-bb31-c131cc511a8b/Untitled.png)
    
    https://istio.io/latest/docs/examples/bookinfo/
    
    ```bash
    # 설치
    tree istio-$ISTIOV/samples/bookinfo/platform/kube/
    cat istio-$ISTIOV/samples/bookinfo/platform/kube/bookinfo.yaml | yh
     kubectl apply -f istio-$ISTIOV/samples/bookinfo/platform/kube/bookinfo.yaml 
    
    # 설치 확인
    kubectl get pod,svc
    
    # ratings 파드에서 exec(curl)로 productpage 접속하여 정상 동작 확인
    # kubectl get pod -l app=ratings -o jsonpath='{.items[0].metadata.name}'
    kubectl exec "$(kubectl get pod -l app=ratings -o jsonpath='{.items[0].metadata.name}')" -c ratings -- curl -sS productpage:9080/productpage | grep -o "<title>.*</title>"
    
    # 실제 요청을 받기 위해 Gateway, VirtualService 생성
    # Istio Gateway(=gw)/VirtualService(=vs) 설정 정보를 확인
    # virtual service 는 다른 네임스페이스의 서비스(ex. svc-nn.<ns>)도 참조할 수 있다
    cat istio-$ISTIOV/samples/bookinfo/networking/bookinfo-gateway.yaml | yh
     kubectl apply -f istio-$ISTIOV/samples/bookinfo/networking/bookinfo-gateway.yaml 
    kubectl get gateway,virtualservices
    
    # 외부 접속 주소 확인
    echo "https://istio.${MyDomain}/productpage"
    
    # 접속 확인 >> 웹 브라우저 접속 후 새로고침으로 별점 부분 확인!
    curl -I https://istio.${MyDomain}/productpage
    curl -s https://istio.${MyDomain}/productpage | grep -o "<title>.*</title>"
    <title>Simple Bookstore App</title>
    
    # productpage 파드의 istio-proxy 로그 확인 : Access log 가 나오지 않는다!
    kubectl logs -l app=productpage -c istio-proxy -f
    
    # Using Telemetry API : envoy 에 access log 활성화
    kubectl apply -f - <<EOF
    apiVersion: telemetry.istio.io/v1alpha1
    kind: Telemetry
    metadata:
      name: mesh-default
      namespace: istio-system
    spec:
      accessLogging:
        - providers:
          - name:  envoy 
    EOF
    
    # 확인
    kubectl get telemetries -n istio-system
    
    # productpage 파드의 istio-proxy 로그 확인 : Access log 가 출력된다! : Default access log format - [링크](https://istio.io/latest/docs/tasks/observability/logs/access-log/#default-access-log-format)
    kubectl logs -l app=productpage -c istio-proxy -f
    [2022-02-16T17:56:20.030Z] "GET /reviews/0 HTTP/1.1" 200 - via_upstream - "-" 0 375 11 11 "-" "curl/7.68.0" "c1921f78-c8de-4445-a026-360b5dd6f51d" "reviews:9080" "172.16.184.6:9080" outbound|9080||reviews.default.svc.cluster.local 172.16.158.7:55410 10.101.97.213:9080 172.16.158.7:34590 - default
    [2022-02-16T17:56:20.020Z] "GET /productpage HTTP/1.1" 200 - via_upstream - "-" 0 5179 23 23 "192.168.10.254" "curl/7.68.0" "c1921f78-c8de-4445-a026-360b5dd6f51d" "www.gasida.dev:30858" "172.16.158.7:9080" inbound|9080|| 127.0.0.6:55471 172.16.158.7:9080 192.168.10.254:0 outbound_.9080_._.productpage.default.svc.cluster.local default
    
    ```
    
    - 클라이언트 PC → ALB → Istio ingressgateway 파드 → (Gateway, VirtualService, Service 는 Bypass) → Endpoint(파드 : 사이드카 - Nginx)
    -  Gateway  : 지정한 인그레스 게이트웨이로부터 트래픽이 인입, 프로토콜 및 포트, HOSTS, Proxy 등 설정 가능
    -  VirtualService  : 인입 처리할 hosts 설정, L7 PATH 별 라우팅, 목적지에 대한 정책 설정 가능 (envoy route config)
    
    ![[출처] https://tisdev.tistory.com/2](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/e35e2881-ac92-48aa-bed2-abdc9fabb499/Untitled.png)
    
    [출처] https://tisdev.tistory.com/2
    
    ![새로고침으로  Reviews  와  Ratings   변경  확인! 별점 부분 변경 확인!](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/e1fc55ca-157a-4a84-9337-f50478a950e5/Untitled.png)
    
    새로고침으로  Reviews  와  Ratings   변경  확인! 별점 부분 변경 확인!

</details>


<details><summary>키알리 소개</summary>


-  Kiali (키알리) 소개  : 주 데이터 소스(Prometheus ,  Jaeger)- [링크](https://istio.io/latest/docs/ops/integrations/kiali/) [링크2](https://kiali.io/docs/configuration/istio/#monitoring-port-of-the-istiod-pod) [링크3](https://kiali.io/docs/configuration/p8s-jaeger-grafana/)
    - [Kiali](https://kiali.io/) is an  observability  console for  Istio  with service mesh configuration and validation capabilities. 
    Kiali provides  detailed metrics  and a  basic [Grafana](https://istio.io/latest/docs/ops/integrations/grafana) integration , which can be used for advanced queries. 
     Distributed tracing  is provided by  integration with [Jaeger](https://istio.io/latest/docs/ops/integrations/jaeger). 
        - Jaeger 와 연동을 통해서 분산 트레이싱을 제공할 수 있다
    -  Monitoring port of the IstioD pod  :  Kiali  connects  directly  to the  IstioD   pod  (not the Service) to check for its  health .
    By default, the connection is done to  port   15014  which is the default monitoring port of the IstioD pod.
        - 파드의 헬스체크는 Kiali 가 직접 IstioD 파드에 TCP Port 15014 를 통해서 체크한다
    -  Prometheus, Jaeger and Grafana  - [링크](https://kiali.io/docs/configuration/p8s-jaeger-grafana/)
     Prometheus  and  Jaeger  are  primary data sources  for  Kiali .
    This page describes how to configure Kiali to communicate with these dependencies.
    A minimalistic  Grafana  integration is also available.
        - 주 데이터 소스는 Prometheus and Jaeger 이며, 최소 수준의 Grafana 와 연동할 수 있다
    
-  대시보드 : kiali(키알리)  - [링크](https://kiali.io/docs/) [Docs](https://istio.io/latest/docs/tasks/observability/kiali/)
    -  Kiali (키알리) 대시보드  along with  Prometheus ,  Grafana , and  Jaeger  - [링크](https://istio.io/latest/docs/setup/getting-started/#dashboard)
    
    ```bash
    # 배포 (디렉터리에 있는 모든 yaml 자원을 생성)
    tree istio-$ISTIOV/samples/addons
    istio-1.17.2/samples/addons
    ├── extras
    │   ├── prometheus-operator.yaml
    │   ├── prometheus_vm_tls.yaml
    │   ├── prometheus_vm.yaml
    │   ├── skywalking.yaml
    │   └── zipkin.yaml
    ├── grafana.yaml
    ├── jaeger.yaml
    ├── kiali.yaml
    ├── prometheus.yaml
    └── README.md
    
    # 설치
    kubectl apply -f istio-$ISTIOV/samples/addons
    
    # 서비스 확인
    kubectl get svc -n istio-system
    
    # 모니터링 서비스 타입을 LoadBalancer 로 변경 (외부 접속 가능하게!) : CLB 각각 생성
    kubectl patch svc -n istio-system kiali -p '{"spec":{"type":"LoadBalancer"}}'
    kubectl patch svc -n istio-system grafana -p '{"spec":{"type":"LoadBalancer"}}'
    kubectl get svc -n istio-system
    
    # CLB에 ExternanDNS 로 도메인 연결
    kubectl annotate service kiali -n istio-system "external-dns.alpha.kubernetes.io/hostname=kiali.$MyDomain"
    kubectl annotate service grafana -n istio-system "external-dns.alpha.kubernetes.io/hostname=grafana.$MyDomain"
    kubectl logs -l app.kubernetes.io/name=external-dns -n kube-system -f
    
    # 확인
    dig +short kiali.$MyDomain @8.8.8.8
    dig +short kiali.$MyDomain @1.1.1.1
    dig +short kiali.$MyDomain
    dig +short grafana.$MyDomain @8.8.8.8
    dig +short grafana.$MyDomain @1.1.1.1
    dig +short grafana.$MyDomain
    
    # 웹 접속 주소 확인 및 접속 : 그라파나는 정상 접속까지 다소 시간 소요됨
    echo -e "Kiali Web URL = http://kiali.$MyDomain:20001"
    echo -e "Grafana Web URL = http://grafana.$MyDomain:3000"
    
    # 트래픽 발생
    for i in $(seq 1 100);  do curl -s -k -o /dev/null "https://istio.${MyDomain}/productpage"; done
    for i in $(seq 1 1000); do curl -s -k -o /dev/null "https://istio.${MyDomain}/productpage"; done
    
    # 지속적인 접속 시도 : 바로 아래 접속 커맨드를 실행해놓고 그 다음 실습들을 진행하자!
    while true; do curl -s -k "https://istio.${MyDomain}/productpage" | grep -o "<title>.*</title>"; date "+%Y-%m-%d %H:%M:%S" ; sleep 1; done
    
    # (참고) 1초에 10번 접속을 지속적으로 시도
    while true; do curl -s -k "https://istio.${MyDomain}/productpage" | grep -o "<title>.*</title>"; sleep 0.1; done
    ```
    
    -  Kiali (키알리) 대시보드 둘러보기  - [링크](https://istio.io/latest/docs/tasks/observability/kiali/)
        -  Namespace  를  default  로 선택 후  Graph  (Traffic, Versioned app graph) 에서  Display  옵션 중 ‘ Traffic Distribution ’ 과 ‘ Traffic Animation ’ 활성화! , ~~Last 1~5m~~
        -  Applications  과  Services  측면에서의 정보를 확인해보자
        -  Workloads  에서  Logs (istio-proxy, app) 를 확인할 수 있고,  Envoy  관련 설정 정보(Clusters, Listeners, Routes, Config 등)를 편리하게 볼 수 있다
        
        ![스크린샷 2021-12-17 오후 4.47.49.png](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/ee38ade1-36e7-4f42-9e62-a0e14a62c8e4/스크린샷_2021-12-17_오후_4.47.49.png)
        
        -  Istio Config  에서 Istio 관련 설정을 볼 수 있고, Action 으로 Istio 관련 오브젝트를 설정/삭제 할 수 있다
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/95babbf3-62ac-4167-b6f3-06adb1ab2443/Untitled.png)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/b59edd95-6239-42ef-a717-a9e68add5acf/Untitled.png)


</details>

## CoreDNS


쿠버네티스  DNS 쿼리 Flow  - [링크](https://www.nslookup.io/learning/the-life-of-a-dns-query-in-kubernetes/)

![https://www.nslookup.io/learning/the-life-of-a-dns-query-in-kubernetes/](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/fdc45e0d-e11e-4f18-947b-1942d744d179/Untitled.png)

https://www.nslookup.io/learning/the-life-of-a-dns-query-in-kubernetes/

-  (심화) Recent changes to the CoreDNS add-on  - [Link](https://aws.amazon.com/ko/blogs/containers/recent-changes-to-the-coredns-add-on/)


##  Gatewaty API

[Amazon VPC Lattice - Part 9: AWS Gateway API Controller](https://zigispace.net/1233)

https://aws.amazon.com/ko/blogs/containers/introducing-aws-gateway-api-controller-for-amazon-vpc-lattice-an-implementation-of-kubernetes-gateway-api/

##  파드 간 속도 측정


 참고 링크  : [iperf3](https://iperf.fr/iperf-download.php) [docker](https://hub.docker.com/r/networkstatic/iperf3) [github](https://github.com/nerdalert/iperf3) [dockerfile](https://github.com/nerdalert/iperf3/blob/master/Dockerfile)

`iperf3` :  서버  모드로 동작하는 단말과  클라이언트  모드로 동작하는 단말로 구성해서  최대 네트워크 대역폭  측정 - TCP, UDP, SCTP 지원

- (참고) macOS에서  간략 테스트 

<details><summary>펼치기</summary>


        ```bash
        # iperf3 설치 
        brew install iperf3

        # iperf3 테스트 1 : TCP 5201, 측정시간 10초
        iperf3 -s # 서버모드 실행
        iperf3 -c 127.0.0.1 # 클라이언트모드 실행

        # iperf3 테스트 2 : TCP 80, 측정시간 5초
        iperf3 -s -p 80
        iperf3 -c 127.0.0.1 -p 80 -t 5

        # iperf3 테스트 3 : UDP 사용, 역방향 모드(-R)
        iperf3 -s 
        iperf3 -c 127.0.0.1 -u -b 100G

        # iperf3 테스트 4 : 역방향 모드(-R)
        iperf3 -s 
        iperf3 -c 127.0.0.1 -R

        # iperf3 테스트 5 : 쌍방향 모드(-R)
        iperf3 -s 
        iperf3 -c 127.0.0.1 --bidir

        # iperf3 테스트 6 : TCP 다중 스트림(30개), -P(number of parallel client streams to run)
        iperf3 -s 
        iperf3 -c 127.0.0.1 -P 2 -t 30
        ```
    
-  [실습] 쿠버네티스 환경에서 속도 측정 테스트 
    - 배포 및 확인
        
        ```bash
        # 배포
        curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/k8s-iperf3.yaml
        cat k8s-iperf3.yaml | yh
         kubectl apply -f k8s-iperf3.yaml 
        
        # 확인 : 서버와 클라이언트가 다른 워커노드에 배포되었는지 확인
        kubectl get deploy,svc,pod -owide
        
        # 서버 파드 로그 확인 : 기본 5201 포트 Listen
         kubectl logs -l app=iperf3-server -f 
        ```
        
    1. TCP 5201, 측정시간 5초
        
        ```bash
        # 클라이언트 파드에서 아래 명령 실행
        kubectl exec -it deploy/ iperf3-client  --  iperf3 -c iperf3-server -t 5 
        
        # 서버 파드 로그 확인 : 기본 5201 포트 Listen
        kubectl logs -l  app=iperf3-server  -f
        ```
        
    2. UDP 사용, 역방향 모드(-R)
        
        ```bash
        # 클라이언트 파드에서 아래 명령 실행
        kubectl exec -it deploy/ iperf3-client  --  iperf3 -c iperf3-server -u -b 20G 
        
        # 서버 파드 로그 확인 : 기본 5201 포트 Listen
        kubectl logs -l  app=iperf3-server  -f
        ```
        
    3. TCP, 쌍방향 모드(-R)
        
        ```bash
        # 클라이언트 파드에서 아래 명령 실행
        kubectl exec -it deploy/ iperf3-client  --  iperf3 -c iperf3-server -t 5 --bidir 
        
        # 서버 파드 로그 확인 : 기본 5201 포트 Listen
        kubectl logs -l  app=iperf3-server  -f
        ```
        
    4. TCP 다중 스트림(30개), -P(number of parallel client streams to run)
        
        ```bash
        # 클라이언트 파드에서 아래 명령 실행
        kubectl exec -it deploy/ iperf3-client  --  iperf3 -c iperf3-server -t 10 -P 2 
        
        # 서버 파드 로그 확인 : 기본 5201 포트 Listen
        kubectl logs -l  app=iperf3-server  -f
        ```
        
    
    - 삭제:   `kubectl delete -f k8s-iperf3.yaml` 


- 샘플 애플리케이션 배포 및 네트워크 정책 적용 실습 2 - [Link](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/cni-network-policy.html#network-policy-stars-demo) ← 직접 실습 해보세요!
    - 네트워크 정책 로그를 Amazon CloudWatch Logs로 전송 - [Link](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/cni-network-policy.html#network-policies-troubleshooting)

</details>

##  kube-ops-view

kube-ops-view : 노드의 파드 상태 정보를 웹 페이지에서 실시간으로 출력 - [링크](https://artifacthub.io/packages/helm/geek-cookbook/kube-ops-view)

<details><summary>실습</summary>


# 설치
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set env.TZ="Asia/Seoul" --namespace kube-system
kubectl patch svc -n kube-system kube-ops-view -p '{"spec":{"type":"LoadBalancer"}}'
kubectl annotate service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=kubeopsview.$MyDomain"

# 접속 주소 확인 : 각각 1배, 1.5배, 3배 크기
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080"
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080/#scale=1.5"
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080/#scale=3.0"

# nginx 파드 배포
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/2/nginx-dp.yaml
kubectl apply -f nginx-dp.yaml
kubectl scale deployment nginx-deployment --replicas 15
kubectl scale deployment nginx-deployment --replicas 40
kubectl delete -f nginx-dp.yaml


</details>

![구성](/Images/eks/eksn_65.png)








## Topology Aware Hint




[Amazon EKS에서 Topology Aware Hint 기능을 활용하여 Cross-AZ 통신 비용 절감하기 | Amazon Web Services](https://aws.amazon.com/ko/blogs/tech/amazon-eks-reduce-cross-az-traffic-costs-with-topology-aware-hints/)

[Exploring the effect of Topology Aware Hints on network traffic in Amazon Elastic Kubernetes Service | Amazon Web Services](https://aws.amazon.com/blogs/containers/exploring-the-effect-of-topology-aware-hints-on-network-traffic-in-amazon-elastic-kubernetes-service/)

- 테스트를 위한 디플로이먼트와 서비스 배포


<details><summary>펼치기</summary>

    ```bash
    # 현재 노드 AZ 배포 확인
     kubectl get node --label-columns=topology.kubernetes.io/zone 
    NAME                                               STATUS   ROLES    AGE   VERSION                 ZONE 
    ip-192-168-1-225.ap-northeast-2.compute.internal   Ready    <none>   70m   v1.24.11-eks-a59e1f0   ap-northeast-2a
    ip-192-168-2-248.ap-northeast-2.compute.internal   Ready    <none>   70m   v1.24.11-eks-a59e1f0   ap-northeast-2b
    ip-192-168-3-228.ap-northeast-2.compute.internal   Ready    <none>   70m   v1.24.11-eks-a59e1f0   ap-northeast-2c
    
    # 테스트를 위한 디플로이먼트와 서비스 배포
    cat <<EOF | kubectl create -f -
    apiVersion: apps/v1
    kind:  Deployment 
    metadata:
      name: deploy-echo
    spec:
      replicas: 3
      selector:
        matchLabels:
          app: deploy-websrv
      template:
        metadata:
          labels:
            app: deploy-websrv
        spec:
          terminationGracePeriodSeconds: 0
          containers:
          - name: websrv
            image:  registry.k8s.io/echoserver:1.5 
            ports:
            -  containerPort: 8080 
    ---
    apiVersion: v1
    kind:  Service 
    metadata:
      name: svc-clusterip
    spec:
      ports:
        - name: svc-webport
           port: 8080
          targetPort: 80 
      selector:
        app: deploy-websrv
      type:  ClusterIP 
    EOF
    
    # 확인
    kubectl get deploy,svc,ep,endpointslices
    kubectl get pod -owide
    kubectl get svc,ep svc-clusterip
    kubectl get endpointslices -l kubernetes.io/service-name=svc-clusterip
    kubectl get endpointslices -l kubernetes.io/service-name=svc-clusterip -o yaml | yh
    
    # 접속 테스트를 수행할 클라이언트 파드 배포
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
    
    # 확인
    kubectl get pod -owide
    ```
    
- 테스트 파드(netshoot-pod)에서 ClusterIP 접속 시 부하분산 확인 :   AZ(zone) 상관없이 랜덤 확률 부하분산 동작
    
    ```bash

    # 디플로이먼트 파드가 배포된 AZ(zone) 확인
     kubectl get pod -l app=deploy-websrv -owide 
    
    # 테스트 파드(netshoot-pod)에서 ClusterIP 접속 시 부하분산 확인
    kubectl exec -it  netshoot-pod  -- curl  svc-clusterip  | grep Hostname
    Hostname: deploy-echo-7f67d598dc-h9vst
    
    kubectl exec -it  netshoot-pod  -- curl  svc-clusterip  | grep Hostname
    Hostname: deploy-echo-7f67d598dc-45trg
    
    # 100번 반복 접속 : 3개의 파드로 AZ(zone) 상관없이 랜덤 확률 부하분산 동작
    kubectl exec -it netshoot-pod -- zsh -c "for i in { 1..100 }; do curl -s  svc-clusterip  | grep Hostname; done | sort | uniq -c | sort -nr"
      35 Hostname: deploy-echo-7f67d598dc-45trg
      33 Hostname: deploy-echo-7f67d598dc-hg995
      32 Hostname: deploy-echo-7f67d598dc-h9vst

    ```
    
    - (심화) IPTables 정책 확인 : ClusterIP는 KUBE-SVC-Y → KUBE-SEP-Z… (3곳) ⇒ 즉, 3개의 파드로 랜덤 확률 부하분산 동작
    
    ```bash
    
    ssh ec2-user@$N1 sudo  iptables -t nat -nvL 
    ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list  PREROUTING 
    ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list  KUBE-SERVICES 
      305 18300  KUBE-SVC-KBDEBIL6IU6WL7RF   tcp  --  *      *       0.0.0.0/0            10.100.155.216       /* default/svc-clusterip:svc-webport cluster IP */ tcp dpt:80
      ...
    
      # 노드1에서 SVC 정책 확인 : SEP(Endpoint) 파드 3개 확인 >> 즉, 3개의 파드로 랜덤 확률 부하분산 동작
      ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list  KUBE-SVC-KBDEBIL6IU6WL7RF 
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
      108  6480 KUBE-SEP- WC4ARU3RZJKCUD7M   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport -> 192.168.1.240:8080 */ statistic mode random probability 0.33333333349
      115  6900 KUBE-SEP- 3HFAJH523NG6SBCX   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport -> 192.168.2.36:8080 */ statistic mode random probability 0.50000000000
       82  4920 KUBE-SEP- H37XIVQWZO52OMNP   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport -> 192.168.3.13:8080 */
    
    # 노드2에서 동일한 SVC 이름 정책 확인 : 상동
    ssh ec2-user@$N2 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF
    (상동)
    
    # 노드3에서 동일한 SVC 이름 정책 확인 : 상동
    ssh ec2-user@$N3 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF
    (상동)
    
      # 3개의 SEP는 각각 개별 파드 접속 정보
      ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list KUBE-SEP- WC4ARU3RZJKCUD7M 
    Chain KUBE-SEP-WC4ARU3RZJKCUD7M (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-MARK-MASQ  all  --  *      *       192.168.1.240        0.0.0.0/0            /* default/svc-clusterip:svc-webport */
      108  6480 DNAT       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport */ tcp to: 192.168.1.240:8080 
    
    ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list KUBE-SEP- 3HFAJH523NG6SBCX 
    Chain KUBE-SEP-3HFAJH523NG6SBCX (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-MARK-MASQ  all  --  *      *       192.168.2.36         0.0.0.0/0            /* default/svc-clusterip:svc-webport */
      115  6900 DNAT       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport */ tcp to: 192.168.2.36:8080 
    
    ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list KUBE-SEP- H37XIVQWZO52OMNP 
    Chain KUBE-SEP-H37XIVQWZO52OMNP (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-MARK-MASQ  all  --  *      *       192.168.3.13         0.0.0.0/0            /* default/svc-clusterip:svc-webport */
       82  4920 DNAT       tcp  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport */ tcp to: 192.168.3.13:8080 

    ```
    
-  Topology Aware Hint  설정 후 테스트 파드(netshoot-pod)에서 ClusterIP 접속 시 부하분산 확인 :  같은 AZ(zone)의 목적지 파드로만 접속 
    
    ```bash

    # Topology Aware Hint 설정 : 서비스에 annotate에 아래처럼 추가
    kubectl annotate service svc-clusterip " service.kubernetes.io/topology-aware-hints=auto "
    
    # 100번 반복 접속 : 테스트 파드(netshoot-pod)와 같은 AZ(zone)의 목적지 파드로만 접속
    kubectl exec -it netshoot-pod -- zsh -c "for i in { 1..100 }; do curl -s  svc-clusterip  | grep Hostname; done | sort | uniq -c | sort -nr"
      100 Hostname: deploy-echo-7f67d598dc-45trg
    
    # endpointslices 확인 시, 기존에 없던 hints 가 추가되어 있음 >> 참고로 describe로는 hints 정보가 출력되지 않음
     kubectl get endpointslices -l kubernetes.io/service-name=svc-clusterip -o yaml | yh 
    apiVersion: v1
    items:
    - addressType: IPv4
      apiVersion: discovery.k8s.io/v1
      endpoints:
       - addresses: 
        - 192.168.3.13
        conditions:
          ready: true
          serving: true
          terminating: false
         hints:
          forZones:
          - name: ap-northeast-2c 
         nodeName :  ip-192-168-3-228 .ap-northeast-2.compute.internal
        targetRef:
          kind: Pod
          name: deploy-echo-7f67d598dc-hg995
          namespace: default
          uid: c1ce0e9c-14e7-417d-a1b9-2dfd54da8d4a
        zone: ap-northeast-2c
       - addresses: 
        - 192.168.2.65
        conditions:
          ready: true
          serving: true
          terminating: false
         hints:
          forZones:
          - name: ap-northeast-2b 
         nodeName: ip-192-168-2-248 .ap-northeast-2.compute.internal
        targetRef:
          kind: Pod
          name: deploy-echo-7f67d598dc-h9vst
          namespace: default
          uid: 77af6a1b-c600-456c-96f3-e1af621be2af
        zone: ap-northeast-2b
       - addresses: 
        - 192.168.1.240
        conditions:
          ready: true
          serving: true
          terminating: false
         hints:
          forZones:
          - name: ap-northeast-2a 
         nodeName: ip-192-168-1-225 .ap-northeast-2.compute.internal
        targetRef:
          kind: Pod
          name: deploy-echo-7f67d598dc-45trg
          namespace: default
          uid: 53ca3ac7-b9fb-4d98-a3f5-c312e60b1e67
        zone: ap-northeast-2a
      kind: EndpointSlice
    
    ```
    
    - (심화) IPTables 정책 확인 : ClusterIP는 KUBE-SVC-Y → KUBE-SEP-Z… (1곳, 해당 노드와 같은 AZ에 배포된 파드만 출력) ⇒ 동일 AZ간 접속
    
    ```bash
    # 노드1에서 SVC 정책 확인 : SEP(Endpoint) 파드 1개 확인(해당 노드와 같은 AZ에 배포된 파드만 출력) >> 동일 AZ간 접속
    ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-SEP- WC4ARU3RZJKCUD7M   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.1.240:8080  */
    
    # 노드2에서 SVC 정책 확인 : SEP(Endpoint) 파드 1개 확인(해당 노드와 같은 AZ에 배포된 파드만 출력) >> 동일 AZ간 접속
    ssh ec2-user@$N2 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-SEP- 3HFAJH523NG6SBCX   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.2.36:8080  */
    
    # 노드3에서 SVC 정책 확인 : SEP(Endpoint) 파드 1개 확인(해당 노드와 같은 AZ에 배포된 파드만 출력) >> 동일 AZ간 접속
    ssh ec2-user@$N3 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-SEP- H37XIVQWZO52OMNP   all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.3.13:8080  */
    ```
    
    - (추가 테스트) 만약 파드 갯수를 1개로 줄여서 같은 AZ에 목적지 파드가 없을 경우?
    
    ```bash
    # 파드 갯수를 1개로 줄이기
    kubectl scale deployment deploy-echo --replicas 1
    
    # 파드 AZ 확인 : 아래 처럼 현재 다른 AZ에 배포
     kubectl get pod -owide 
    NAME                           READY   STATUS    RESTARTS   AGE   IP              NODE                                               NOMINATED NODE   READINESS GATES
     deploy-echo -7f67d598dc-h9vst   1/1     Running   0          18m    192.168.2 .65    ip-192-168-2-248.ap-northeast-2.compute.internal   <none>           <none>
     netshoot-pod                    1/1     Running   0          66m    192.168.1. 137   ip-192-168-1-225.ap-northeast-2.compute.internal   <none>           <none>
    
    # 100번 반복 접속 : 다른 AZ이지만 목적지파드로 접속됨!
    kubectl exec -it netshoot-pod -- zsh -c "for i in { 1..100 }; do curl -s  svc-clusterip  | grep Hostname; done | sort | uniq -c | sort -nr"
      100 Hostname:  deploy-echo -7f67d598dc-h9vst
    
    # 아래 3개 노드 모두 SVC에 1개의 SEP 정책 존재
     ssh ec2-user@$N1 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF 
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
      100  6000 KUBE-SEP-XFCOE5ZRIDUONHHN  all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.2.65:8080  */
    
     ssh ec2-user@$N2 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF 
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-SEP-XFCOE5ZRIDUONHHN  all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.2.65:8080  */
    
     ssh ec2-user@$N3 sudo iptables -v --numeric --table nat --list KUBE-SVC-KBDEBIL6IU6WL7RF 
    Chain KUBE-SVC-KBDEBIL6IU6WL7RF (1 references)
     pkts bytes target     prot opt in     out     source               destination
        0     0 KUBE-SEP-XFCOE5ZRIDUONHHN  all  --  *      *       0.0.0.0/0            0.0.0.0/0            /* default/svc-clusterip:svc-webport ->  192.168.2.65:8080  */
    
    # endpointslices 확인 : hint 정보 없음
     kubectl get endpointslices -l kubernetes.io/service-name=svc-clusterip -o yaml | yh 
    ```
    
    - (참고) Topology Aware Hint 설정 제거
    
    ```bash
    kubectl annotate service svc-clusterip "service.kubernetes.io/topology-aware-hints - "
    ```
    
    - 실습 리소스 삭제:  `kubectl delete deploy deploy-echo; kubectl delete svc svc-clusterip`
    
- (추가) 파드 토폴로지 분배  topologySpreadConstraints  - [Docs](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
    
    ```bash
    # 디플로이먼트 배포
    cat <<EOF | kubectl create -f -
    apiVersion: apps/v1
    kind: Deployment
    metadata:
      name: deploy-echo
    spec:
       replicas: 6 
      selector:
        matchLabels:
          app: deploy-websrv
      template:
        metadata:
          labels:
            app: deploy-websrv
        spec:
          terminationGracePeriodSeconds: 0
          containers:
          - name: websrv
            image: registry.k8s.io/echoserver:1.5
            ports:
            - containerPort: 8080
           topologySpreadConstraints :
          - maxSkew: 1
            topologyKey: " topology.kubernetes.io/zone "
            whenUnsatisfiable:  DoNotSchedule 
            labelSelector:
              matchLabels:
                app: deploy-websrv
    EOF
    
    # 파드 토폴로지 분배 확인 : AZ별 2개씩 파드 배포 확인
     kubectl get pod -owide 
    NAME                           READY   STATUS    RESTARTS   AGE    IP              NODE                                               NOMINATED NODE   READINESS GATES
    deploy-echo-79c4fcbc44-27tr5   1/1     Running   0          108s   192.168.1.240   ip-192-168-1-225.ap-northeast-2.compute.internal   <none>           <none>
    deploy-echo-79c4fcbc44-2bgcr   1/1     Running   0          108s   192.168.1.177   ip-192-168-1-225.ap-northeast-2.compute.internal   <none>           <none>
    deploy-echo-79c4fcbc44-4gf8n   1/1     Running   0          108s   192.168.3.13    ip-192-168-3-228.ap-northeast-2.compute.internal   <none>           <none>
    deploy-echo-79c4fcbc44-5dqt8   1/1     Running   0          108s   192.168.2.65    ip-192-168-2-248.ap-northeast-2.compute.internal   <none>           <none>
    deploy-echo-79c4fcbc44-6d99q   1/1     Running   0          108s   192.168.2.180   ip-192-168-2-248.ap-northeast-2.compute.internal   <none>           <none>
    deploy-echo-79c4fcbc44-m2qvh   1/1     Running   0          108s   192.168.3.66    ip-192-168-3-228.ap-northeast-2.compute.internal   <none>           <none>
    ```
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/76aa791d-2f21-44b5-8332-3333ce186629/Untitled.png)
    
    - 갯수를 5개 → 4개 → 3개로 줄여보면서 확인 해보자 ⇒ 이후 4개 → 5개 → 6개 → 7개 → 8개 → 9개로 늘려 보면서 배치를 확인해보자
    
    ```bash
    kubectl scale deployment deploy-echo --replicas 5
    kubectl scale deployment deploy-echo --replicas 4
    kubectl scale deployment deploy-echo --replicas 3
    ```
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/85c55478-e702-4ab3-bb9c-a9b9ac679c45/Untitled.png)
    
    - 실습 리소스 삭제:  `kubectl delete deploy deploy-echo`

</details>

## CNI-Metrics-helper

https://blog.naver.com/qwerty_1234s/223101405443

##  Network Policies with VPC CNI


`참고 링크` : [Link1](https://aws.amazon.com/ko/blogs/containers/amazon-vpc-cni-now-supports-kubernetes-network-policies/) [Link2](https://github.com/aws-samples/eks-network-policy-examples) [Link3](https://docs.aws.amazon.com/ko_kr/eks/latest/userguide/cni-network-policy.html)

- AWS EKS fully supports the  upstream Kubernetes Network Policy API , ensuring compatibility and adherence to Kubernetes standards.

`동작` :  eBPF 로 패킷 필터링 동작 - Network Policy Controller, Node Agent, eBPF SDK

- 사전 조건 : EKS 1.25 버전 이상, AWS VPC CNI 1.14 이상, OS 커널 5.10 이상 EKS 최적화 AMI(AL2, Bottlerocket, Ubuntu)
- Network Policy Controller : v1.25 EKS 버전 이상 자동 설치, 통제 정책 모니터링 후 eBPF 프로그램을 생성 및 업데이트하도록 Node Agent에 지시
- Node Agent : AWS VPC CNI 번들로 ipamd 플러그인과 함께 설치됨(aws-node 데몬셋). eBPF 프래그램을 관리
- eBPF SDK : AWS VPC CNI에는 노드에서 eBPF 프로그램과 상호 작용할 수 있는 SDK 포함, eBPF 실행의 런타임 검사, 추적 및 분석 가능


<details><summary>설치</summary>

~~~

# Network Policy 기본 비활성화되어 있어, 활성화 필요 : 실습 환경은 미리 활성화 설정 추가되어 있음
tail -n 11 myeks.yaml | yh
addons: 
- name: vpc-cni # no version is specified so it deploys the default version
  version: latest # auto discovers the latest available
  attachPolicyARNs: 
    - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
  configurationValues: |-
    enableNetworkPolicy: "true"

# Node Agent 확인 : AWS VPC CNI 1.14 이상 버전 정보 확인
kubectl get ds aws-node -n kube-system -o yaml | k neat | yh
...
    - args: 
      - --enable-ipv6=false
      - --enable-network-policy=true
...
    volumeMounts: 
    - mountPath: /host/opt/cni/bin
      name: cni-bin-dir
    - mountPath: /sys/fs/bpf
      name: bpf-pin-path
    - mountPath: /var/log/aws-routed-eni
      name: log-dir
    - mountPath: /var/run/aws-node
      name: run-dir
...


kubectl get ds aws-node -n kube-system -o yaml | grep -i image:
kubectl get pod -n kube-system -l k8s-app=aws-node
kubectl get ds -n kube-system aws-node -o jsonpath='{.spec.template.spec.containers[*].name}{"\n"}'
aws-node aws-eks-nodeagent

# EKS 1.25 버전 이상 확인
kubectl get node

# OS 커널 5.10 이상 확인
ssh ec2-user@$N1 uname -r
5.10.210-201.852.amzn2.x86_64

# 실행 중인 eBPF 프로그램 확인
ssh ec2-user@$N1 sudo /opt/cni/bin/aws-eks-na-cli ebpf progs
Programs currently loaded : 
Type : 26 ID : 6 Associated maps count : 1
========================================================================================
Type : 26 ID : 8 Associated maps count : 1
========================================================================================

# 각 노드에 BPF 파일 시스템을 탑재 확인
ssh ec2-user@$N1 mount | grep -i bpf
none on /sys/fs/bpf type bpf (rw,nosuid,nodev,noexec,relatime,mode=700)

ssh ec2-user@$N1 df -a | grep -i bpf
none                   0       0         0    - /sys/fs/bpf

~~~

```bash
#
git clone https://github.com/aws-samples/eks-network-policy-examples.git
cd eks-network-policy-examples
tree advanced/manifests/
kubectl apply -f advanced/manifests/

# 확인
kubectl get pod,svc
kubectl get pod,svc -n another-ns

# 통신 확인
kubectl exec -it client-one -- curl demo-app
kubectl exec -it client-two -- curl demo-app
kubectl exec -it another-client-one -n another-ns -- curl  demo-app 
kubectl exec -it another-client-one -n another-ns -- curl demo-app. default 
kubectl exec -it another-client-two -n another-ns -- curl demo-app.default.svc
```

- 모든 트래픽 거부

```bash
# 모니터링
# kubectl exec -it client-one -- curl demo-app
while true; do kubectl exec -it client-one -- curl --connect-timeout 1 demo-app ; date; sleep 1; done

# 정책 적용
cat advanced/policies/01-deny-all-ingress.yaml | yh
kubectl apply -f advanced/policies/01-deny-all-ingress.yaml
 kubectl get networkpolicy 

# 정책 다시 삭제
kubectl delete -f advanced/policies/01-deny-all-ingress.yaml

# 다시 적용
kubectl apply -f advanced/policies/01-deny-all-ingress.yaml
```

- 동일 네임스페이스 + 클라이언트1 로부터의 수신 허용

```bash
#
cat advanced/policies/03-allow-ingress-from-samens-client-one.yaml | yh
kubectl apply -f advanced/policies/03-allow-ingress-from-samens-client-one.yaml
kubectl get networkpolicy

# 클라이언트2 수신 확인
kubectl exec -it client-two -- curl --connect-timeout 1 demo-app
```

- another-ns 네임스페이스로부터의 수신 허용

```bash
# 모니터링
# kubectl exec -it another-client-one -n another-ns -- curl --connect-timeout 1 demo-app.default
while true; do kubectl exec -it another-client-one -n another-ns -- curl --connect-timeout 1 demo-app.default ; date; sleep 1; done

#
cat advanced/policies/04-allow-ingress-from-xns.yaml | yh
kubectl apply -f advanced/policies/04-allow-ingress-from-xns.yaml
kubectl get networkpolicy

#
kubectl exec -it another-client-two -n another-ns -- curl --connect-timeout 1 demo-app.default
```

- eBPF 관련 정보 확인

```bash
# 실행 중인 eBPF 프로그램 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i  sudo /opt/cni/bin/aws-eks-na-cli ebpf progs ; echo; done

# eBPF 로그 확인
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo cat /var/log/aws-routed-eni/ebpf-sdk.log; echo; done
for i in $N1 $N2 $N3; do echo ">> node $i <<"; ssh ec2-user@$i sudo cat /var/log/aws-routed-eni/ network-policy-agent ; echo; done
```

- 송신 트래픽 거부 : 기본 네임스페이스의 클라이언트-1 포드에서 모든 송신 격리를 적용

```bash
# 모니터링
while true; do kubectl exec -it client-one -- curl --connect-timeout 1 google.com ; date; sleep 1; done

#
cat advanced/policies/06-deny-egress-from-client-one.yaml | yh
kubectl apply -f advanced/policies/06-deny-egress-from-client-one.yaml
kubectl get networkpolicy

#
kubectl exec -it client-one -- nslookup demo-app
```

- 송신 트래픽 허용 : DNS 트래픽을 포함하여 여러 포트 및 네임스페이스에서의 송신을 허용

```bash
# 모니터링
while true; do kubectl exec -it client-one -- curl --connect-timeout 1 demo-app ; date; sleep 1; done

#
cat advanced/policies/08-allow-egress-to-demo-app.yaml | yh
kubectl apply -f advanced/policies/08-allow-egress-to-demo-app.yaml
kubectl get networkpolicy
```

- 실습 후 리소스 삭제

```bash
kubectl delete networkpolicy --all
kubectl delete -f advanced/manifests/
```


</details>



##  How to rapidly scale your application with ALB on EKS (without losing traffic)

https://aws.amazon.com/ko/blogs/containers/how-to-rapidly-scale-your-application-with-alb-on-eks-without-losing-traffic/

https://github.com/aws-samples/app-health-with-aws-load-balancer-controller/tree/main

https://aws.github.io/aws-eks-best-practices/networking/loadbalancing/loadbalancing/

##  IPv6 with EKS

The Journey to IPv6 on Amazon EKS: Foundation (Part 1) - [Link](https://aws.amazon.com/blogs/containers/the-journey-to-ipv6-on-amazon-eks-foundation-part-1/)

The Journey to IPv6 on Amazon EKS: Foundation (Part 2) - [Link](https://aws.amazon.com/blogs/containers/the-journey-to-ipv6-on-amazon-eks-implementation-patterns-part-2/)

The Journey to IPv6 on Amazon EKS: Foundation (Part 3) - [Link](https://aws.amazon.com/blogs/containers/the-journey-to-ipv6-on-amazon-eks-interoperability-scenarios-part-3/)



---
 삭제 
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~



----
같이 해보면 좋은 과제들 
- `[도전과제1]` EKS Max pod 개수 증가 - Prefix Delegation + WARM & MIN IP/Prefix Targets : EKS에 직접 설정 후 파드 150대 생성해보기 - [링크](https://aws.github.io/aws-eks-best-practices/networking/prefix-mode/) [Workshop](https://www.eksworkshop.com/docs/networking/prefix/)
    
    [Prefix Delegation | EKS Workshop](https://www.eksworkshop.com/docs/networking/prefix/)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/4fcccbd6-c493-44e7-9844-6311e620670d/Untitled.png)
    
- `[도전과제2]` EKS Max pod 개수 증가 - Custom Network : EKS에 직접 설정 후 파드 150대 생성해보기 - [링크](https://aws.github.io/aws-eks-best-practices/networking/custom-networking/) [Workshop](https://www.eksworkshop.com/docs/networking/custom-networking/)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/a4203f92-1986-4765-97ff-5f3220c971a9/Untitled.png)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/a83d3da4-3ffb-4956-8fd2-25748699388d/Untitled.png)
    
- `[도전과제3]` Security Group for Pod : 파드별 보안그룹 적용해보기 - [링크](https://aws.github.io/aws-eks-best-practices/networking/sgpp/) [Workshop](https://www.eksworkshop.com/docs/networking/security-groups-for-pods/)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/221f40b5-cefd-453a-8e01-b1f30e99bd3c/Untitled.png)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/4d7ac0d5-3b48-44fb-bdcb-83748754a41b/Untitled.png)
    
- `[도전과제4]` 게임서버의 트래픽(UDP)를 서비스(NLB)를 통해 인입 설정 - [링크](https://aws.amazon.com/ko/blogs/containers/how-to-route-udp-traffic-into-kubernetes/)
- `[도전과제5]` Multiple Ingress pattern : 여러 Ingress 를 하나의 ALB에서 처리 할 수 있게 설정 - [링크](https://www.eksworkshop.com/docs/fundamentals/exposing/ingress/multiple-ingress)
- `[도전과제6]` How to rapidly scale your application with ALB on EKS (without losing traffic) - [링크](https://aws.amazon.com/blogs/containers/how-to-rapidly-scale-your-application-with-alb-on-eks-without-losing-traffic/)
    - [AWS][EKS] Zero downtime deployment(RollingUpdate) when using AWS Load Balancer Controller on Amazon EKS - [링크](https://easoncao.com/zero-downtime-deployment-when-using-alb-ingress-controller-on-amazon-eks-and-prevent-502-error/)
    - pod graceful shutdown - [링크](https://linuxer.name/2023/03/pod-graceful-shutdown/)
- `[도전과제7]` Expose Amazon EKS pods through cross-account load balancer - [링크](https://aws.amazon.com/blogs/containers/expose-amazon-eks-pods-through-cross-account-load-balancer/)
- `[도전과제8]` Exposing Kubernetes Applications, Part 2: AWS Load Balancer Controller - [링크](https://aws.amazon.com/blogs/containers/exposing-kubernetes-applications-part-2-aws-load-balancer-controller/)
    1. EKS 생성 시 IRSA 설정 참고
        <details><summary>설치</summary>

        ```bash
        apiVersion: eksctl.io/v1alpha5
        kind: ClusterConfig
        metadata:
          name: aws-load-balancer-controller-walkthrough
          region: ${AWS_REGION}
          version: '1.23'
         iam:
          withOIDC: true
          serviceAccounts:
            - metadata:
                name: aws-load-balancer-controller
                namespace: kube-system
              attachPolicyARNs:
                - arn:aws:iam::${AWS_ACCOUNT}:policy/AWSLoadBalancerControllerIAMPolicy 
        ...
        ```

        </details>
        
    2. AWS LB Ctrl Helm Chart 설치
    3. ~
- `[도전과제9]` Exposing Kubernetes Applications, Part 3: NGINX Ingress Controller - [링크](https://aws.amazon.com/blogs/containers/exposing-kubernetes-applications-part-3-nginx-ingress-controller/) [Rewrite](https://nauco.tistory.com/94)
- `[도전과제10]` EC2 ENA의 [linklocal_allowance_exceeded](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/metrics-collected-by-CloudWatch-agent.html#linux-metrics-enabled-by-CloudWatch-agent) 메트릭을 프로메테우스로 수집 - [링크](https://aws.amazon.com/ko/blogs/mt/monitoring-coredns-for-dns-throttling-issues-using-aws-open-source-monitoring-services/)
- `[도전과제11]` Leveraging CNI custom networking alongside security groups for pods in Amazon EKS - [링크](https://aws.amazon.com/blogs/containers/leveraging-cni-custom-networking-alongside-security-groups-for-pods-in-amazon-eks/)
- `[도전과제12]` Using AWS Load Balancer Controller for blue/green deployment, canary deployment and A/B testing - [링크](https://aws.amazon.com/blogs/containers/using-aws-load-balancer-controller-for-blue-green-deployment-canary-deployment-and-a-b-testing/)
- `[도전과제13]` How to use Application Load Balancer and Amazon Cognito to authenticate users for your Kubernetes web apps - [링크](https://aws.amazon.com/blogs/containers/how-to-use-application-load-balancer-and-amazon-cognito-to-authenticate-users-for-your-kubernetes-web-apps/)
- `[도전과제14]` EKS에 NodeLocal DNS Cache 설정으로 클러스터의 DNS 성능 향상 - [Docs](https://kubernetes.io/docs/tasks/administer-cluster/nodelocaldns/) [블로깅](https://kim-dragon.tistory.com/281)
- `[도전과제15]` Addressing latency and data transfer costs on EKS using Istio - [링크](https://aws.amazon.com/blogs/containers/addressing-latency-and-data-transfer-costs-on-eks-using-istio/)
- `[도전과제16]` Deploy a gRPC-based application on an Amazon EKS cluster and access it with an Application Load Balancer - [링크](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/deploy-a-grpc-based-application-on-an-amazon-eks-cluster-and-access-it-with-an-application-load-balancer.html)
- `[도전과제17]` Optimize webSocket applications scaling with API Gateway on Amazon EKS - [Link](https://aws.amazon.com/ko/blogs/containers/optimize-websocket-applications-scaling-with-api-gateway-on-amazon-eks/)
- `[도전과제18]` Use shared VPC subnets in Amazon EKS - [Link](https://aws.amazon.com/ko/blogs/containers/use-shared-vpcs-in-amazon-eks/)
- `[도전과제19]` Recent changes to the CoreDNS add-on - [Link](https://aws.amazon.com/ko/blogs/containers/recent-changes-to-the-coredns-add-on/)
- `[도전과제20]` Automating custom networking to solve IPv4 exhaustion in Amazon EKS - [Link](https://aws.amazon.com/ko/blogs/containers/automating-custom-networking-to-solve-ipv4-exhaustion-in-amazon-eks/)
- `[도전과제21]` A deeper look at Ingress Sharing and Target Group Binding in AWS Load Balancer Controller - [Link](https://aws.amazon.com/ko/blogs/containers/a-deeper-look-at-ingress-sharing-and-target-group-binding-in-aws-load-balancer-controller/)
- `[도전과제22]` Using Istio Traffic Management on Amazon EKS to Enhance User Experience - [Link](https://aws.amazon.com/ko/blogs/opensource/using-istio-traffic-management-to-enhance-user-experience/)
- `[도전과제23]` Getting Started with Istio on Amazon EKS - [Link](https://aws.amazon.com/ko/blogs/opensource/getting-started-with-istio-on-amazon-eks/)
- `[도전과제24]` Avoiding Errors & Timeouts with Kubernetes Applications and AWS Load Balancers - [Link](https://aws.github.io/aws-eks-best-practices/networking/loadbalancing/loadbalancing/)
- `[도전과제25]` ALB 경우 인증서 ARN 지정 없이, 자동 발견 가능 : 방안1(ingress tls), 방안2(ingress rule host) - [Link](https://kubernetes-sigs.github.io/aws-load-balancer-controller/v2.7/guide/ingress/cert_discovery/)
- `EKS Workshop`
    -  Prefix Delegation :  https://www.eksworkshop.com/docs/networking/vpc-cni/prefix/
    -  Custom Networking :  https://www.eksworkshop.com/docs/networking/vpc-cni/custom-networking/
    -  Security Groups for Pods :  https://www.eksworkshop.com/docs/networking/vpc-cni/security-groups-for-pods/
    -  Network Policies :  https://www.eksworkshop.com/docs/networking/vpc-cni/network-policies/
    -  Amazon VPC Lattice :  https://www.eksworkshop.com/docs/networking/vpc-lattice/
