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

## 노드에서 기본 네트워크 정보 확인

##  노드 간 파드 통신


## 파드에서 외부 통신

## 노드에 파드 생성 갯수 제한

## Service & AWS LoadBalancer Controller

## Ingress

## ExternalDNS

## Istio

## CoreDNS


## 11. Gatewaty API
## 12. 파드 간 속도 측정
## 13. kube-ops-view
## 15. CNI-Metrics-helper
## 16. Network Policies with VPC CNI
## 17. How to rapidly scale your application with ALB on EKS (without losing traffic)
## 18. IPv6 with EKS


---
**삭제**
~~~
eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME
~~~



