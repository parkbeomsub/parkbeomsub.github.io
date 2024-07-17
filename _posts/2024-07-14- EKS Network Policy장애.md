---
layout: single
title: "EKS   Network Policy 버그 현상"
categories:  EKS
tags: [ DevOps , Kubernetes , EKS , Network, NetworkPolicy]
toc: true
---


## 버그 현상 (Network Policy)

pod(ns: default)  -x-> pod (ns:nginx)
pod(ns: default -x->  nginx service (Cluster IP)(ns: nginx)  -> nginx pod



### Network Policy
~~~bash
kubectl get networkpolicy [name] -n [namespace]  -o yaml |k neat
# k neat : yaml 값에 필요없는 값을 삭제해줌 

#  잔부 전상으로 등록되어 있었음
...


ingress:
 - from:
   - namespaceSeletor:
      matchLabels:
        kubernetes.io/metadata.name: 



egress:
 - to:
   - namespaceSeletor:
      matchLabels:
        kubernetes.io/metadata.name: 

....

~~~




### Policy Endpoint

> EKS에서  networkpolicy를 조회하고 정책 설정을 확인하는 방법

~~~bash

kubectl get policyendpoints.networking.k8s.aws
# kubectl get policyendpoints.networking.k8s.aws 조회된 내용을 yaml로 뽑아내면
# 연결이 되는 아이피 리스트들이 나옴 


~~~

### 문제확인

> NetworkPolicy 정책은 정상이나 통신이 되지 않고 있음 OS쪽에서 통신을 하는 로직이 동작하지 않고 있다.




### 해결방법

1. 임시 해결방법 : Netowkr Policy 재생성 
 - 문제점 생성- ... -삭제  시간에 인입되는 문제가 발생
  
2. 영구 해결방법 : Network Policy Agent 업그레이드
   - 위치는  namespace : kube-system   , Daemonset : aws-node , container : aws-network-policy-agent 
   - 문제 이미지 :v1.0.7 

### 버그 재현 :

- pod replica수를 늘렸다 줄였다한다.
~~~bash


#!/bin/bash
while true:do
    echo "scale down"
    kubectl scale deploy nginx --replicas=6 -n nginx
    sleep 20


    echo "scale up"
    kubectl scale deploy nginx --replicas=6 -n nginx
    sleep 20
done

~~~

### Network Policy 관련 OS 에서 확인하기

> contrack 관련 정보
 
~~~bash
# eks 노드에서 디버깅 : 설정된 정보조회
/opt/cni/bin/aws-eks-na-cli ebpf loaded-ebpfdata

~~~



참고:
https://github.com/choisungwook/terraform_practice/tree/main/network_policy_error
https://www.youtube.com/watch?v=Qac3r5WjY7Y
