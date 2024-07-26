---
layout: single
title: "쿠버네티스 각 리소스별 동작(Probe, Service, Secret, HPA)"
categories: linux
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , PV,PVC ,Deployment, HPA, Service, 1pro  ]
toc: true
---



#  쿠버네티스 각 리소스별 동작(Probe, Service, Secret, HPA)

## Probe

   - Probe 
     - 순서

        -> kube-apiserver 요청 인입 

        -> Etcd에 저장/조회  데이터베이스를 모니터링하고 있는 controller-Manager가 Deployment 조회 

        -> replicaset을 생성 요청을 API서버에 호출 

        -> controller_Manager가  pod를 생성 요청을 API서버에 호출 

        -> 데이터베이스에 저장 됨 

        -> kube-scheduler가  pod를 생성할 노스 스케줄링 

        -> 각 노드의 kubelet이 정보가 있는 pod를 모니터링 

        -> kubelet이 containerd에 컨테이너 생성 요청

        -> **Kubelet이  probe 설정에 따라 생성**

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory25.png)

## Service 
  - Service 생성 및 연결 순서 

    -> nodePort 타입으로 생성

    -> pod와 연결

    -> kubelet이 kubeproxy에 iptables내용에 룰 추가를 요청/ 생성

    -> iptables에서  트레픽 설정이 되고  트레픽 전달은  cni가 담당


## Secret
  - 컨테이너 내부의 파일들은  노드의 메모리 영역에 마운팅된다. 내용이 많아지면  메모리에 부하가 생김
  - 변경하면  5초 뒤 변경됨


## HPA
  - 자원사용량은 kubelet이 알고 있다. 10초마다 cpu/memeory를 조회 / hpa를 사용하기 위해선 metric server를 설치해야된다. 메트릭 서버가 있어야  kube controller가  임계 값 및 메트릭 확인 (15초)하고 스케일링을 1~85 초 반응하여 동작한다.




## 기타 컴포넌트 로그확인 



### Resource 확인

~~~

kubectl api-resources

~~~


### Cluster 주요 컴포넌트 로그 확인

~~~

// 주요 컴포넌트 로그 보기 (kube-system)
kubectl get pods -n kube-system
kubectl logs -n kube-system etcd-k8s-master
kubectl logs -n kube-system kube-scheduler-k8s-master
kubectl logs -n kube-system kube-apiserver-k8s-master

~~~
​

### Master Node 파일 위치

~~~
// 쿠버네티스 인증서 위치
cd /etc/kubernetes
ls /root/.kube/config

// Control Plane Component Pod 생성 yaml 파일 위치
ls /etc/kubernetes/manifests

// 전체 Pod 로그
/var/log/pods/<namespace_<pod-name>_<uid>/<number>.log
/var/log/containers/<pod-name>_<namespace>_<container-name>_<container-id>.log
​
~~~

### 트러블 슈팅

~~~

// kubelet 상태 확인
1) systemctl status kubelet       // systemctl (restart or start) kubelet
2) journalctl -u kubelet | tail -10

// 상태 확인 -> 상세 로그 확인 -> 10분 구글링 -> VM 재기동 -> Cluster 재설치 ->  답을 찾을 때 까지 구글링

// containerd 상태 확인
1) systemctl status containerd
2) journalctl -u containerd | tail -10

// 노드 상태 확인
1) kubectl get nodes -o wide
2) kubectl describe node k8s-master

// Pod 상태 확인
1) kubectl get pods -A -o wide
// Event 확인 (기본값: 1h)
2-1) kubectl get events -A
2-2) kubectl events -n anotherclass-123 --types=Warning  (or Normal)
// Log 확인
3-1) kubectl logs -n anotherclass-123 <pod-name> --tail 10    // 10줄 만 조회하기
3-2) kubectl logs -n anotherclass-123 <pod-name> -f           // 실시간으로 조회 걸어 놓기
3-3) kubectl logs -n anotherclass-123 <pod-name> --since=1m   // 1분 이내에 생성된 로그만 보기




2. Pod 생성 및 probe 동작


[지상편] 쿠버네티스 첫 오브젝트 잘 끼우기 > Component 동작으로 이해하기 > Pod 생성 및 probe 동작

​

​

3. Service 동작


[지상편] 쿠버네티스 첫 오브젝트 잘 끼우기 > Component 동작으로 이해하기 > Service 동작

​

iptables -t nat -L KUBE-NODEPORTS -n  | column -t
​

4. Secret 동작


[지상편] 쿠버네티스 첫 오브젝트 잘 끼우기 > Component 동작으로 이해하기 > Secret 동작

​

​

5. HPA 동작


[지상편] 쿠버네티스 첫 오브젝트 잘 끼우기 > Component 동작으로 이해하기 > HPA 동작

~~~
​


[추가 질문]
Q: worker node를 master node에 join 시킨 다는 게 무엇인지?

A: 마스터 노드는 쿠버네티스 주요 컴포넌트가 돌아가는 곳이고, 워커노드가 우리가 만든 App들이 올라가는 공간입니다. 이렇게 마스터 노드 + 워커 노드를 합쳐서 우리는 쿠버네티스 클러스터라고 말하고요. 현재 강의에서는 마스터 노드에 우리가 만든 App들이 올라가도록 강제로 설정을 해 놓았기 때문에, 마스터 노드만 으로도 동작이 가능한 겁니다.그래서 결국 마스터 노드(vm)를 먼저 만든 다음에 워커 노드(vm)를 만들어서 마스터 노드에 연결을 해야 되요. 그 과정을 join이라고 하고요. 자원이 부족할 때마다 워커노드를 계속 join 시키는 방식으로 클러스터 규모가 커지게 됩니다.


Q:  worker component와 worker node는 동일한 개념인지? worker component에 application을 올리기 위한 공간이라면, kubelet은 왜 worker component에 포함이 되지 않는지?

A:worker node는 vm과 같은 단위의 개념입니다. component는 application이고요. 그렇기 때문에 다른 개념이고, worker node 위에 worker 로써의 역할을 하기 위해 올라가는 모든 Application을 worker component라고 합니다. 그러면 엄말히 말해서 kubelet Worker Component라고 할 수 있기 한데, 제가 그림을 단계적으로 나눠서 Worker Component에 포함이 안되는 것처럼 보일 수는 있겠네요. kubelet도 worker component고요. 제 그림의 경우 VM 영역은 사용자가 직접 설치하는 영역, 파란색 Kubernetes Cluster는 쿠버네티스 셋업을 하면 자동으로 생성되는 영역으로 이해해 주시면 됩니다.

Q: Addon은 어디에 설치되는 것인지, 검색해보니 addon은 control plane component와 구분되는 개념인 것 같은데, 그림 상에서는 control plane component 내부에 있어서 관련되어 있는지?

A: 쿠버네티스 기본 컴포넌트들만으로는 제한 되는 기능들이 많습니다. Pod의 자원(cpu,memory) 사용량을 보려면 꼭 metrics-server를 별도 addon으로 설치해 줘야 되는거죠. 이 addon은 마스터나 워커노드 모두에 설치 될 수 있습니다. 어디에 설치되는지는 addon별로 기능마다 달라요. calico의 경우 각 워커노드마다 통신을 지원 해줘야하는 기능을 위해 각 워커노드 별로 Pod가 설치되는 기능도 있고, 그냥 마스터 위에서 설치되는 Pod도 있는거죠.




