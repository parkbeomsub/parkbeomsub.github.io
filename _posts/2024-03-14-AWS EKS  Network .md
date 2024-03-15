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
    # 네임스페이스 분석
    ssh ubuntu@{workernode IP}
    sudo lsns -o PID,COMMAND -t net
    ##최근 PID입력
    sudo nsenter -t {PID} -n ip -c addr
    ~~~

    

## 노드에서 기본 네트워크 정보 확인

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
##  How to rapidly scale your application with ALB on EKS (without losing traffic)
##  IPv6 with EKS


---
**삭제**
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~



