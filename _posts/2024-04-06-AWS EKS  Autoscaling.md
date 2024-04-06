---
layout: single
title: "AWS EKS  Autoscaling"
categories:  Devops
tags: [linux, container, kubernetes , AWS , EKS, Monitoring ]
toc: true
---








## 실습 환경 구성

 > 첨부링크 :  https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick4.ya

 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)


<details><summary>펼치기</summary>

```bash

# YAML 파일 다운로드
curl -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick4.yaml

# CloudFormation 스택 배포
예시) aws cloudformation deploy --template-file eks-oneclick4.yaml --stack-name myeks --parameter-overrides KeyName=kp-gasida SgIngressSshCidr=$(curl -s ipinfo.io/ip)/32  MyIamUserAccessKeyID=AKIA5... MyIamUserSecretAccessKey='CVNa2...' ClusterBaseName=myeks --region ap-northeast-2

# CloudFormation 스택 배포 완료 후 작업용 EC2 IP 출력
aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[0].OutputValue' --output text

# 작업용 EC2 SSH 접속
ssh -i ~/.ssh/kp-gasida.pem ec2-user@$(aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[0].OutputValue' --output text)
or
ssh -i ~/.ssh/kp-gasida.pem root@$(aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[0].OutputValue' --output text)
~ password: qwe123

```


- 기본설정

```bash
# default 네임스페이스 적용
**kubectl ns default**

# 노드 정보 확인 : t3.medium
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone
****
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
kubectl annotate service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=kubeopsview.$MyDomain"
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080/#scale=1.5"

# AWS LB Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

# gp3 스토리지 클래스 생성
kubectl apply -f https://raw.githubusercontent.com/gasida/PKOS/main/aews/gp3-sc.yaml

# 노드 보안그룹 ID 확인
NGSGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text)
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr 192.168.1.100/32

```

-   프로메테우스 & 그라파나(admin / prom-operator) 설치 : 대시보드 추천 15757 17900 15172


```bash
# 사용 리전의 인증서 ARN 확인
CERT_ARN=`aws acm list-certificates --query 'CertificateSummaryList[].CertificateArn[]' --output text`
echo $CERT_ARN

# repo 추가
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts

# 파라미터 파일 생성 : PV/PVC(AWS EBS) 삭제에 불편하니, 4주차 실습과 다르게 PV/PVC 미사용
cat <<EOT > monitor-values.yaml
**prometheus**:
  prometheusSpec:
    podMonitorSelectorNilUsesHelmValues: false
    serviceMonitorSelectorNilUsesHelmValues: false
    retention: 5d
    retentionSize: "10GiB"

  verticalPodAutoscaler:
    enabled: true

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
      alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'

**grafana**:
  defaultDashboardsTimezone: Asia/Seoul
  adminPassword: prom-operator
  **defaultDashboardsEnabled: false**

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
      alb.ingress.kubernetes.io/load-balancer-name: myeks-ingress-alb
      alb.ingress.kubernetes.io/group.name: study
      alb.ingress.kubernetes.io/ssl-redirect: '443'

**kube-state-metrics:**
  rbac:
    extraRules:
      - apiGroups: ["autoscaling.k8s.io"]
        resources: ["verticalpodautoscalers"]
        verbs: ["list", "watch"]
  prometheus:
    monitor:
      enabled: true
  **customResourceState**:
    enabled: true
    config:
      kind: CustomResourceStateMetrics
      spec:
        resources:
          - groupVersionKind:
              group: autoscaling.k8s.io
              kind: "VerticalPodAutoscaler"
              version: "v1"
            labelsFromPath:
              verticalpodautoscaler: [metadata, name]
              namespace: [metadata, namespace]
              target_api_version: [apiVersion]
              target_kind: [spec, targetRef, kind]
              target_name: [spec, targetRef, name]
            metrics:
              - name: "vpa_containerrecommendations_target"
                help: "VPA container recommendations for memory."
                each:
                  type: Gauge
                  gauge:
                    path: [status, recommendation, containerRecommendations]
                    valueFrom: [target, memory]
                    labelsFromPath:
                      container: [containerName]
                commonLabels:
                  resource: "memory"
                  unit: "byte"
              - name: "vpa_containerrecommendations_target"
                help: "VPA container recommendations for cpu."
                each:
                  type: Gauge
                  gauge:
                    path: [status, recommendation, containerRecommendations]
                    valueFrom: [target, cpu]
                    labelsFromPath:
                      container: [containerName]
                commonLabels:
                  resource: "cpu"
                  unit: "core"
  selfMonitor:
    enabled: true

alertmanager:
  enabled: false
EOT
cat monitor-values.yaml | yh

# 배포
**kubectl create ns monitoring**
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack --version **57.2.0** \
--**set** prometheus.prometheusSpec.scrapeInterval='15s' --**set** prometheus.prometheusSpec.evaluationInterval='15s' \
-f **monitor-values.yaml** --namespace monitoring

# Metrics-server 배포
**kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml**

# 프로메테우스 ingress 도메인으로 웹 접속
echo -e "Prometheus Web URL = https://prometheus.$MyDomain"

# 그라파나 웹 접속 : 기본 계정 - **admin / prom-operator**
echo -e "Grafana Web URL = https://grafana.$MyDomain"

```


-  EKS Node Viewer 설치 : 노드 할당 가능 용량과 요청 request 리소스 표시, 실제 파드 리소스 사용량 X - 링크
```bash
# go 설치
**wget https://go.dev/dl/go1.22.1.linux-amd64.tar.gz
tar -C /usr/local -xzf go1.22.1.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
go version**
go version go1.22.1 linux/amd64

# EKS Node Viewer 설치 : 약 2분 이상 소요
**go install github.com/awslabs/eks-node-viewer/cmd/eks-node-viewer@latest**

# [신규 터미널] EKS Node Viewer 접속
**cd ~/go/bin && ./eks-node-viewer**
혹은
**cd ~/go/bin && ./eks-node-viewer --resources cpu,memory**

**명령 샘플**
# Standard usage
**./eks-node-viewer**

# Display both CPU and Memory Usage
**./eks-node-viewer --resources cpu,memory**

# Karenter nodes only
**./eks-node-viewer --node-selector "karpenter.sh/provisioner-name"**

# Display extra labels, i.e. AZ
**./eks-node-viewer --extra-labels topology.kubernetes.io/zone**

# Specify a particular AWS profile and region
AWS_PROFILE=myprofile AWS_REGION=us-west-2

**기본 옵션**
# select only Karpenter managed nodes
node-selector=karpenter.sh/provisioner-name

# display both CPU and memory
resources=cpu,memory
```

</details>


## 쿠버네티스에 오토스케일 종류


![구성](/Images/eks/eks_a01.png)

#### - HPA : pod 수를 늘린다.
#### - VPA : pod 스펙을 늘린다.
#### - CAS : 클러스터 노드수를 늘린다.
#### - Karpenter : CAS보다 빠르게 늘린다. 

### - 참고자료
[[EKS Study 5주차] EKS AutoScaling - HPA](https://kimalarm.tistory.com/60)
[[EKS Study 5주차] EKS AutoScaling - VPA](https://kimalarm.tistory.com/62)
[[EKS Study 5주차] EKS AutoScaling - CA](https://kimalarm.tistory.com/63)
[[EKS Study 5주차] EKS AutoScaling - Karpenter](https://kimalarm.tistory.com/64)





##  HPA - Horizontal Pod Autoscaler
테스트에 도움되는 grafana 대시보드 :17125
<details><summary>php-apache pod</summary>

~~~bash

# Run and expose php-apache server
curl -s -O https://raw.githubusercontent.com/kubernetes/website/main/content/en/examples/application/php-apache.yaml
cat php-apache.yaml | yh
kubectl apply -f php-apache.yaml

# 확인
kubectl exec -it deploy/php-apache -- cat /var/www/html/index.php
...

# 모니터링 : 터미널2개 사용
watch -d 'kubectl get hpa,pod;echo;kubectl top pod;echo;kubectl top node'
kubectl exec -it deploy/php-apache -- top

# 접속
PODIP=$(kubectl get pod -l run=php-apache -o jsonpath={.items[0].status.podIP})
curl -s $PODIP; echo

~~~

</details>

<details><summary>실습</summary>


```bash
# Create the HorizontalPodAutoscaler : requests.cpu=200m - [알고리즘](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/#algorithm-details)
# Since each pod requests **200 milli-cores** by kubectl run, this means an average CPU usage of **100 milli-cores**.
kubectl **autoscale** deployment php-apache **--cpu-percent=50** --min=1 --max=10
**kubectl describe hpa**
...
Metrics:                                               ( current / target )
  resource cpu on pods  (as a percentage of request):  0% (1m) / 50%
Min replicas:                                          1
Max replicas:                                          10
Deployment pods:                                       1 current / 1 desired
...

# HPA 설정 확인
**kubectl get hpa php-apache -o yaml | kubectl neat | yh**
spec: 
  minReplicas: 1               # [4] 또는 최소 1개까지 줄어들 수도 있습니다
  maxReplicas: 10              # [3] 포드를 최대 5개까지 늘립니다
  **scaleTargetRef**: 
    apiVersion: apps/v1
    kind: **Deployment**
    name: **php-apache**           # [1] php-apache 의 자원 사용량에서
  **metrics**: 
  - type: **Resource**
    resource: 
      name: **cpu**
      target: 
        type: **Utilization**
        **averageUtilization**: 50  # [2] CPU 활용률이 50% 이상인 경우

# 반복 접속 1 (**파드1** IP로 접속) >> 증가 확인 후 중지
while true;do curl -s $PODIP; sleep 0.5; done

# 반복 접속 2 (서비스명 도메인으로 **파드들 분산** 접속) >> 증가 확인(몇개까지 증가되는가? 그 이유는?) 후 중지 >> **중지 5분 후** 파드 갯수 감소 확인
# Run this in a separate terminal
# so that the load generation continues and you can carry on with the rest of the steps
kubectl run -i --tty load-generator --rm --image=**busybox**:1.28 --restart=Never -- /bin/sh -c "while sleep 0.01; do wget -q -O- http://php-apache; done"

```

- 삭제

~~~bash

- 오브젝트 삭제: `kubectl delete deploy,svc,hpa,pod --all`

~~~


</details>

![https://cafe.naver.com/kubeops](/Images/eks/eks_a07.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a08.png)


## KEDA - Kubernetes based Event Driven Autoscaler

> 설명:
기존의 **HPA**(Horizontal Pod Autoscaler)는 리소스(CPU, Memory) 메트릭을 기반으로 스케일 여부를 결정하게 됩니다.
반면에 **KEDA**는 **특정 이벤트를 기반으로 스케일 여부를 결정**할 수 있습니다.
예를 들어 airflow는 metadb를 통해 현재 실행 중이거나 대기 중인 task가 얼마나 존재하는지 알 수 있습니다.
이러한 이벤트를 활용하여 worker의 scale을 결정한다면 queue에 task가 많이 추가되는 시점에 더 빠르게 확장할 수 있습니다.

![구성](/Images/eks/eks_a02.png)



<details><summary>실습</summary>

#### 그라파나 대시보드

```json
{
  "annotations": {
    "list": [
      {
        "builtIn": 1,
        "datasource": {
          "type": "grafana",
          "uid": "-- Grafana --"
        },
        "enable": true,
        "hide": true,
        "iconColor": "rgba(0, 211, 255, 1)",
        "name": "Annotations & Alerts",
        "target": {
          "limit": 100,
          "matchAny": false,
          "tags": [],
          "type": "dashboard"
        },
        "type": "dashboard"
      }
    ]
  },
  "description": "Visualize metrics provided by KEDA",
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": 1653,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 0
      },
      "id": 8,
      "panels": [],
      "title": "Metric Server",
      "type": "row"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "The total number of errors encountered for all scalers.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 25,
            "gradientMode": "opacity",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": true,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "Errors/sec"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "http-demo"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "scaledObject"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "keda-system/keda-operator-metrics-apiserver"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 9,
        "w": 8,
        "x": 0,
        "y": 1
      },
      "id": 4,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "expr": "sum by(job) (rate(keda_scaler_errors{}[5m]))",
          "legendFormat": "{{ job }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Scaler Total Errors",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "The number of errors that have occurred for each scaler.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 25,
            "gradientMode": "opacity",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": true,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "Errors/sec"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "http-demo"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "scaler"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          },
          {
            "matcher": {
              "id": "byName",
              "options": "prometheusScaler"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 9,
        "w": 8,
        "x": 8,
        "y": 1
      },
      "id": 3,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "expr": "sum by(scaler) (rate(keda_scaler_errors{exported_namespace=~\"$namespace\", scaledObject=~\"$scaledObject\", scaler=~\"$scaler\"}[5m]))",
          "legendFormat": "{{ scaler }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Scaler Errors",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "The number of errors that have occurred for each scaled object.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 25,
            "gradientMode": "opacity",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": true,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "Errors/sec"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "http-demo"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "red",
                  "mode": "fixed"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 9,
        "w": 8,
        "x": 16,
        "y": 1
      },
      "id": 2,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "expr": "sum by(scaledObject) (rate(keda_scaled_object_errors{exported_namespace=~\"$namespace\", scaledObject=~\"$scaledObject\"}[5m]))",
          "legendFormat": "{{ scaledObject }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Scaled Object Errors",
      "type": "timeseries"
    },
    {
      "collapsed": false,
      "gridPos": {
        "h": 1,
        "w": 24,
        "x": 0,
        "y": 10
      },
      "id": 10,
      "panels": [],
      "title": "Scale Target",
      "type": "row"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "The current value for each scaler’s metric that would be used by the HPA in computing the target average.",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 25,
            "gradientMode": "opacity",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": true,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "none"
        },
        "overrides": [
          {
            "matcher": {
              "id": "byName",
              "options": "http-demo"
            },
            "properties": [
              {
                "id": "color",
                "value": {
                  "fixedColor": "blue",
                  "mode": "fixed"
                }
              }
            ]
          }
        ]
      },
      "gridPos": {
        "h": 9,
        "w": 24,
        "x": 0,
        "y": 11
      },
      "id": 5,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "expr": "sum by(metric) (keda_scaler_metrics_value{exported_namespace=~\"$namespace\", metric=~\"$metric\", scaledObject=\"$scaledObject\"})",
          "legendFormat": "{{ metric }}",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Scaler Metric Value",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "shows current replicas against max ones based on time difference",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 21,
            "gradientMode": "opacity",
            "hideFrom": {
              "legend": false,
              "tooltip": false,
              "viz": false
            },
            "lineInterpolation": "linear",
            "lineStyle": {
              "fill": "solid"
            },
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 24,
        "x": 0,
        "y": 20
      },
      "id": 13,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "kube_horizontalpodautoscaler_status_current_replicas{namespace=\"$namespace\",horizontalpodautoscaler=\"keda-hpa-$scaledObject\"}",
          "format": "time_series",
          "instant": false,
          "interval": "",
          "legendFormat": "current_replicas",
          "range": true,
          "refId": "A"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "kube_horizontalpodautoscaler_spec_max_replicas{namespace=\"$namespace\",horizontalpodautoscaler=\"keda-hpa-$scaledObject\"}",
          "format": "time_series",
          "hide": false,
          "instant": false,
          "legendFormat": "max_replicas",
          "range": true,
          "refId": "B"
        }
      ],
      "title": "Current/max replicas (time based)",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "shows current replicas against max ones based on time difference",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "continuous-GrYlRd"
          },
          "custom": {
            "fillOpacity": 70,
            "lineWidth": 0,
            "spanNulls": false
          },
          "mappings": [
            {
              "options": {
                "0": {
                  "color": "green",
                  "index": 0,
                  "text": "No scaling"
                }
              },
              "type": "value"
            },
            {
              "options": {
                "from": -200,
                "result": {
                  "color": "light-red",
                  "index": 1,
                  "text": "Scaling down"
                },
                "to": 0
              },
              "type": "range"
            },
            {
              "options": {
                "from": 0,
                "result": {
                  "color": "semi-dark-red",
                  "index": 2,
                  "text": "Scaling up"
                },
                "to": 200
              },
              "type": "range"
            }
          ],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "none"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 24,
        "x": 0,
        "y": 28
      },
      "id": 16,
      "options": {
        "alignValue": "left",
        "legend": {
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": false,
          "width": 0
        },
        "mergeValues": true,
        "rowHeight": 1,
        "showValue": "never",
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "delta(kube_horizontalpodautoscaler_status_current_replicas{namespace=\"$namespace\",horizontalpodautoscaler=\"keda-hpa-$scaledObject\"}[1m])",
          "format": "time_series",
          "instant": false,
          "interval": "",
          "legendFormat": ".",
          "range": true,
          "refId": "A"
        }
      ],
      "title": "Changes in replicas",
      "type": "state-timeline"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "${datasource}"
      },
      "description": "shows current replicas against max ones",
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "min": 0,
          "thresholds": {
            "mode": "percentage",
            "steps": [
              {
                "color": "green"
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 36
      },
      "id": 15,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "calcs": [
            "lastNotNull"
          ],
          "fields": "/^current_replicas$/",
          "values": false
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "pluginVersion": "9.5.2",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "kube_horizontalpodautoscaler_status_current_replicas{namespace=\"$namespace\",horizontalpodautoscaler=\"keda-hpa-$scaledObject\"}",
          "instant": true,
          "legendFormat": "current_replicas",
          "range": false,
          "refId": "A"
        },
        {
          "datasource": {
            "type": "prometheus",
            "uid": "${datasource}"
          },
          "editorMode": "code",
          "exemplar": false,
          "expr": "kube_horizontalpodautoscaler_spec_max_replicas{namespace=\"$namespace\",horizontalpodautoscaler=\"keda-hpa-$scaledObject\"}",
          "hide": false,
          "instant": true,
          "legendFormat": "max_replicas",
          "range": false,
          "refId": "B"
        }
      ],
      "title": "Current/max replicas",
      "type": "gauge"
    }
  ],
  "refresh": "1m",
  "schemaVersion": 38,
  "style": "dark",
  "tags": [],
  "templating": {
    "list": [
      {
        "current": {
          "selected": false,
          "text": "Prometheus",
          "value": "Prometheus"
        },
        "hide": 0,
        "includeAll": false,
        "multi": false,
        "name": "datasource",
        "options": [],
        "query": "prometheus",
        "queryValue": "",
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "type": "datasource"
      },
      {
        "current": {
          "selected": false,
          "text": "bhe-test",
          "value": "bhe-test"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "${datasource}"
        },
        "definition": "label_values(keda_scaler_active,exported_namespace)",
        "hide": 0,
        "includeAll": false,
        "multi": false,
        "name": "namespace",
        "options": [],
        "query": {
          "query": "label_values(keda_scaler_active,exported_namespace)",
          "refId": "PrometheusVariableQueryEditor-VariableQuery"
        },
        "refresh": 1,
        "regex": "",
        "skipUrlSync": false,
        "sort": 1,
        "type": "query"
      },
      {
        "current": {
          "selected": false,
          "text": "All",
          "value": "$__all"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "${datasource}"
        },
        "definition": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},scaledObject)",
        "hide": 0,
        "includeAll": true,
        "multi": true,
        "name": "scaledObject",
        "options": [],
        "query": {
          "query": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},scaledObject)",
          "refId": "PrometheusVariableQueryEditor-VariableQuery"
        },
        "refresh": 2,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      },
      {
        "current": {
          "selected": false,
          "text": "cronScaler",
          "value": "cronScaler"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "${datasource}"
        },
        "definition": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},scaler)",
        "hide": 0,
        "includeAll": false,
        "multi": false,
        "name": "scaler",
        "options": [],
        "query": {
          "query": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},scaler)",
          "refId": "PrometheusVariableQueryEditor-VariableQuery"
        },
        "refresh": 2,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      },
      {
        "current": {
          "selected": false,
          "text": "s0-cron-Etc-UTC-40xxxx-55xxxx",
          "value": "s0-cron-Etc-UTC-40xxxx-55xxxx"
        },
        "datasource": {
          "type": "prometheus",
          "uid": "${datasource}"
        },
        "definition": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},metric)",
        "hide": 0,
        "includeAll": false,
        "multi": false,
        "name": "metric",
        "options": [],
        "query": {
          "query": "label_values(keda_scaler_active{exported_namespace=\"$namespace\"},metric)",
          "refId": "PrometheusVariableQueryEditor-VariableQuery"
        },
        "refresh": 2,
        "regex": "",
        "skipUrlSync": false,
        "sort": 0,
        "type": "query"
      }
    ]
  },
  "time": {
    "from": "now-24h",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "KEDA",
  "uid": "asdasd8rvmMxdVk",
  "version": 8,
  "weekStart": ""
}
```

#### -실습

```bash

# KEDA 설치
cat <<EOT > keda-values.yaml
**metricsServer**:
  useHostNetwork: true

**prometheus**:
  metricServer:
    enabled: true
    port: 9022
    portName: metrics
    path: /metrics
    serviceMonitor:
      # Enables ServiceMonitor creation for the Prometheus Operator
      enabled: true
    podMonitor:
      # Enables PodMonitor creation for the Prometheus Operator
      enabled: true
  operator:
    enabled: true
    port: 8080
    serviceMonitor:
      # Enables ServiceMonitor creation for the Prometheus Operator
      enabled: true
    podMonitor:
      # Enables PodMonitor creation for the Prometheus Operator
      enabled: true

  webhooks:
    enabled: true
    port: 8080
    serviceMonitor:
      # Enables ServiceMonitor creation for the Prometheus webhooks
      enabled: true
EOT

kubectl create namespace **keda**
helm repo add kedacore https://kedacore.github.io/charts
helm install **keda** kedacore/keda --version 2.13.0 --namespace **keda -f** keda-values.yaml

# KEDA 설치 확인
kubectl get **all** -n keda
kubectl get **validatingwebhookconfigurations** keda-admission
kubectl get **validatingwebhookconfigurations** keda-admission | kubectl neat | yh
**kubectl get crd | grep keda**

# keda 네임스페이스에 디플로이먼트 생성
**kubectl apply -f php-apache.yaml -n keda
kubectl get pod -n keda**

# ScaledObject ****정책 생성 : cron
cat <<EOT > keda-cron.yaml
apiVersion: keda.sh/v1alpha1
kind: **ScaledObject**
metadata:
  name: php-apache-cron-scaled
spec:
  minReplicaCount: 0
  maxReplicaCount: 2
  pollingInterval: 30
  cooldownPeriod: 300
  **scaleTargetRef**:
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  **triggers**:
  - type: **cron**
    metadata:
      timezone: Asia/Seoul
      **start**: 00,15,30,45 * * * *
      **end**: 05,20,35,50 * * * *
      **desiredReplicas**: "1"
EOT
**kubectl apply -f keda-cron.yaml -n keda**

# 그라파나 대시보드 추가
# 모니터링
watch -d 'kubectl get ScaledObject,hpa,pod -n keda'
kubectl get ScaledObject -w

# 확인
kubectl get ScaledObject,hpa,pod -n keda
**kubectl get hpa -o jsonpath={.items[0].spec} -n keda | jq**
...
"metrics": [
    {
      "**external**": {
        "metric": {
          "name": "s0-cron-Asia-Seoul-**00,15,30,45**xxxx-**05,20,35,50**xxxx",
          "selector": {
            "matchLabels": {
              "scaledobject.keda.sh/name": "php-apache-cron-scaled"
            }
          }
        },
        "**target**": {
          "**averageValue**": "1",
          "type": "AverageValue"
        }
      },
      "type": "**External**"
    }

# KEDA 및 deployment 등 삭제
kubectl delete -f keda-cron.yaml -n keda && kubectl delete deploy php-apache -n keda && helm uninstall keda -n keda
kubectl delete namespace keda

```
</details>


![https://cafe.naver.com/kubeops](/Images/eks/eks_a12.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a13.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a14.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a15.png)

##   VPA - Vertical Pod Autoscaler
[EKS 스터디 - 5주차 1편 - VPA](https://malwareanalysis.tistory.com/603)

- 그라파나 대시보드 - 링크 14588
- 프로메테우스 

~~~bash

kube_customresource_vpa_containerrecommendations_target{resource="cpu"}
kube_customresource_vpa_containerrecommendations_target{resource="memory"}

~~~

<details><summary>실습</summary>

```bash

# 코드 다운로드
git clone https://github.com/kubernetes/autoscaler.git
cd ~/autoscaler/vertical-pod-autoscaler/
tree hack

# openssl 버전 확인
**openssl version**
OpenSSL 1.0.2k-fips  26 Jan 2017

# openssl 1.1.1 이상 버전 확인
**yum install openssl11 -y
openssl11 version**
OpenSSL 1.1.1g FIPS  21 Apr 2020

# 스크립트파일내에 openssl11 수정
**sed -i 's/openssl/openssl11/g' ~/autoscaler/vertical-pod-autoscaler/pkg/admission-controller/gencerts.sh**

# Deploy the Vertical Pod Autoscaler to your cluster with the following command.
watch -d kubectl get pod -n kube-system
cat hack/vpa-up.sh
**./hack/vpa-up.sh**
kubectl get crd | grep **autoscaling**
kubectl get **mutatingwebhookconfigurations** vpa-webhook-config
kubectl get **mutatingwebhookconfigurations** vpa-webhook-config -o json | jq

```


-  공식 예제 : pod가 실행되면 약 2~3분 뒤에 pod resource.reqeust가 VPA에 의해 수정 - [링크](https://github.com/kubernetes/autoscaler/tree/master/vertical-pod-autoscaler/examples)
- vpa에 spec.**updatePolicy**.**updateMode**를 **Off** 로 변경 시 파드에 Spec을 자동으로 변경 재실행 하지 않습니다. 기본값(Auto)


```bash
# 모니터링
watch -d "kubectl top pod;echo "----------------------";kubectl describe pod | grep Requests: -A2"

# 공식 예제 배포
cd ~/autoscaler/vertical-pod-autoscaler/
cat examples/hamster.yaml | yh
**kubectl apply -f examples/hamster.yaml && kubectl get vpa -w**

# 파드 리소스 Requestes 확인
**kubectl describe pod | grep Requests: -A2**
    Requests:
      cpu:        100m
      memory:     50Mi
--
    Requests:
      cpu:        587m
      memory:     262144k
--
    Requests:
      cpu:        587m
      memory:     262144k

# VPA에 의해 기존 파드 삭제되고 신규 파드가 생성됨
**kubectl get events --sort-by=".metadata.creationTimestamp" | grep VPA**
2m16s       Normal    EvictedByVPA             pod/hamster-5bccbb88c6-s6jkp         Pod was evicted by VPA Updater to apply resource recommendation.
76s         Normal    EvictedByVPA             pod/hamster-5bccbb88c6-jc6gq         Pod was evicted by VPA Updater to apply resource recommendation.
```

- 삭제:  `kubectl delete -f examples/hamster.yaml && cd ~/autoscaler/vertical-pod-autoscaler/ && **./hack/vpa-down.sh**`



</details>

![https://cafe.naver.com/kubeops](/Images/eks/eks_a10.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a09.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a11.png)


<details><summary>참고</summary>


- `KRR` : Prometheus-based **K**ubernetes **R**esource **R**ecommendations - [링크](https://github.com/robusta-dev/krr#getting-started) & Youtube - [링크](https://www.youtube.com/live/uITOzpf82RY?feature=share)
    - Difference with Kubernetes VPA
    
    | Feature 🛠️ | Robusta KRR 🚀 | Kubernetes VPA 🌐 |
    | --- | --- | --- |
    | Resource Recommendations 💡 | ✅ CPU/Memory requests and limits | ✅ CPU/Memory requests and limits |
    | Installation Location 🌍 | ✅ Not required to be installed inside the cluster, can be used on your own device, connected to a cluster | ❌ Must be installed inside the cluster |
    | Workload Configuration 🔧 | ✅ No need to configure a VPA object for each workload | ❌ Requires VPA object configuration for each workload |
    | Immediate Results ⚡ | ✅ Gets results immediately (given Prometheus is running) | ❌ Requires time to gather data and provide recommendations |
    | Reporting 📊 | ✅ Detailed CLI Report, web UI in https://home.robusta.dev/ | ❌ Not supported |
    | Extensibility 🔧 | ✅ Add your own strategies with few lines of Python | ⚠️ Limited extensibility |
    | Custom Metrics 📏 | 🔄 Support in future versions | ❌ Not supported |
    | Custom Resources 🎛️ | 🔄 Support in future versions (e.g., GPU) | ❌ Not supported |
    | Explainability 📖 | 🔄 Support in future versions (Robusta will send you additional graphs) | ❌ Not supported |
    | Autoscaling 🔀 | 🔄 Support in future versions | ✅ Automatic application of recommendations |
    
    ![https://github.com/robusta-dev/krr#getting-started](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/55924909-de68-4d02-96d4-a68397a28374/Untitled.png)
    
    https://github.com/robusta-dev/krr#getting-started
    
- `[도전과제3]` k8s 1.27: In-place Resource Resize for Kubernetes Pods (**alpha**) **pod재실행안하면서 resource변경** - [Link1](https://kubernetes.io/blog/2023/05/12/in-place-pod-resize-alpha/) [Link2](https://kubernetes.io/docs/tasks/configure-pod-container/resize-container-resources/)
    - **김예준**님이 InPlacePodVerticalScaling 내용 정리를 해주셨습니다!
    
    [FeatureGate 와 Pod Resizing](https://montkim.com/podresizing)
    
```bash

    # This pod is classified as a Guaranteed QoS class requesting 700m CPU and 200Mi memory.
    kubectl create ns qos-example
    kubectl apply -f https://k8s.io/examples/pods/qos/qos-pod-5.yaml
    kubectl get pod qos-demo-5 --output=yaml --namespace=qos-example | yh
    kubectl get pod qos-demo-5 --output=yaml --namespace=qos-example | kubectl neat | yh
    ...

```


</details>




## CA - Cluster Autoscaler

![구성](/Images/eks/eks_a03.png)

- Cluster Autoscale 동작을 하기 위한 **cluster-autoscaler 파드**(디플로이먼트)를 배치합니다.
- **Cluster Autoscaler(CA)**는 **pending** 상태인 **파드**가 존재할 경우, **워커 노드**를 **스케일 아웃**합니다.
- 특정 시간을 간격으로 사용률을 확인하여 스케일 인/아웃을 수행합니다. 그리고 AWS에서는 **Auto Scaling Group**(**ASG**)을 사용하여 Cluster Autoscaler를 적용합니다.


<details><summary>설정 / 실습</summary>

- 설정 전 확인
```bash
**# EKS 노드에 이미 아래 tag가 들어가 있음**
# k8s.io/cluster-autoscaler/enabled : true
# k8s.io/cluster-autoscaler/myeks : owned
**aws ec2 describe-instances  --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node --query "Reservations[*].Instances[*].Tags[*]" --output yaml | yh**
...
- Key: k8s.io/cluster-autoscaler/myeks
      Value: owned
- Key: k8s.io/cluster-autoscaler/enabled
      Value: 'true'
...

```
![구성](/Images/eks/eks_a04.png)

```bash

# 현재 autoscaling(ASG) 정보 확인
# aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='**클러스터이름**']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" --output table
**aws autoscaling describe-auto-scaling-groups \
    --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" \
    --output table**
-----------------------------------------------------------------
|                   DescribeAutoScalingGroups                   |
+------------------------------------------------+----+----+----+
|  eks-ng1-44c41109-daa3-134c-df0e-0f28c823cb47  |  3 |  3 |  3 |
+------------------------------------------------+----+----+----+

# MaxSize 6개로 수정
**export ASG_NAME=$(aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].AutoScalingGroupName" --output text)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name ${ASG_NAME} --min-size 3 --desired-capacity 3 --max-size 6**

# 확인
**aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" --output table**
-----------------------------------------------------------------
|                   DescribeAutoScalingGroups                   |
+------------------------------------------------+----+----+----+
|  eks-ng1-c2c41e26-6213-a429-9a58-02374389d5c3  |  3 |  6 |  3 |
+------------------------------------------------+----+----+----+

# 배포 : Deploy the Cluster Autoscaler (CA)
curl -s -O https://raw.githubusercontent.com/kubernetes/autoscaler/master/cluster-autoscaler/cloudprovider/aws/examples/cluster-autoscaler-autodiscover.yaml
sed -i "s/<YOUR CLUSTER NAME>/$CLUSTER_NAME/g" cluster-autoscaler-autodiscover.yaml
**kubectl apply -f cluster-autoscaler-autodiscover.yaml**

# 확인
kubectl get pod -n kube-system | grep cluster-autoscaler
kubectl describe deployments.apps -n kube-system cluster-autoscaler
**kubectl describe deployments.apps -n kube-system cluster-autoscaler | grep node-group-auto-discovery**
      --node-group-auto-discovery=asg:tag=k8s.io/cluster-autoscaler/enabled,k8s.io/cluster-autoscaler/myeks

# (옵션) cluster-autoscaler 파드가 동작하는 워커 노드가 퇴출(evict) 되지 않게 설정
kubectl -n kube-system annotate deployment.apps/cluster-autoscaler cluster-autoscaler.kubernetes.io/safe-to-evict="false"

```

- **SCALE A CLUSTER WITH Cluster Autoscaler(CA)** - [링크](https://www.eksworkshop.com/beginner/080_scaling/test_ca/)

```bash
# 모니터링 
kubectl get nodes -w
while true; do kubectl get node; echo "------------------------------" ; date ; sleep 1; done
while true; do aws ec2 describe-instances --query "Reservations[*].Instances[*].{PrivateIPAdd:PrivateIpAddress,InstanceName:Tags[?Key=='Name']|[0].Value,Status:State.Name}" --filters Name=instance-state-name,Values=running --output text ; echo "------------------------------"; date; sleep 1; done

# Deploy a Sample App
# We will deploy an sample nginx application as a ReplicaSet of 1 Pod
cat <<EoF> nginx.yaml
apiVersion: apps/v1
kind: **Deployment**
metadata:
  name: nginx-to-scaleout
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        service: nginx
        app: nginx
    spec:
      containers:
      - image: nginx
        name: nginx-to-scaleout
        resources:
          limits:
            cpu: 500m
            memory: 512Mi
          **requests:
            cpu: 500m
            memory: 512Mi**
EoF

kubectl apply -f nginx.yaml
kubectl get deployment/nginx-to-scaleout

# Scale our ReplicaSet
# Let’s scale out the replicaset to 15
kubectl scale --replicas=15 deployment/nginx-to-scaleout && date

# 확인
kubectl get pods -l app=nginx -o wide --watch
**kubectl -n kube-system logs -f deployment/cluster-autoscaler**

# 노드 자동 증가 확인
kubectl get nodes
aws autoscaling describe-auto-scaling-groups \
    --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='**myeks**']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" \
    --output table

**./eks-node-viewer --resources cpu,memory**
혹은
**./eks-node-viewer**

# 디플로이먼트 삭제
kubectl delete -f nginx.yaml && date

# **노드 갯수 축소** : 기본은 10분 후 scale down 됨, 물론 아래 flag 로 시간 수정 가능 >> 그러니 **디플로이먼트 삭제 후 10분 기다리고 나서 보자!**
# By default, cluster autoscaler will wait 10 minutes between scale down operations, 
# you can adjust this using the --scale-down-delay-after-add, --scale-down-delay-after-delete, 
# and --scale-down-delay-after-failure flag. 
# E.g. --scale-down-delay-after-add=5m to decrease the scale down delay to 5 minutes after a node has been added.

# 터미널1
watch -d kubectl get node
```

- 리소스 삭제 

```bash

위 실습 중 디플로이먼트 삭제 후 10분 후 노드 갯수 축소되는 것을 확인 후 아래 삭제를 해보자! >> 만약 바로 아래 CA 삭제 시 워커 노드는 4개 상태가 되어서 수동으로 2대 변경 하자!
**kubectl delete -f nginx.yaml**

# size 수정 
aws autoscaling update-auto-scaling-group --auto-scaling-group-name ${ASG_NAME} --min-size 3 --desired-capacity 3 --max-size 3
aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" --output table

# Cluster Autoscaler 삭제
kubectl delete -f cluster-autoscaler-autodiscover.yaml

```

- `[도전과제3]` Cluster Over-Provisioning : 여유 노드를 미리 프로비저닝 - [Workshop](https://www.eksworkshop.com/docs/autoscaling/compute/cluster-autoscaler/overprovisioning/) [Blog1](https://freesunny.tistory.com/57) [Blog2](https://tommypagy.tistory.com/373) [Blog3](https://haereeroo.tistory.com/24)
</details>

<details><summary>CA 문제점</summary>

- **CA 문제점** : 하나의 자원에 대해 두군데 (AWS **ASG** vs AWS **EKS**)에서 각자의 방식으로 관리 ⇒ **관리 정보가 서로 동기화되지 않아** 다양한 문제 발생
    - CA 문제점 : ASG에만 의존하고 노드 생성/삭제 등에 직접 관여 안함
    - EKS에서 노드를 삭제 해도 인스턴스는 삭제 안됨
    - 노드 축소 될 때 특정 노드가 축소 되도록 하기 매우 어려움 : pod이 적은 노드 먼저 축소, 이미 드레인 된 노드 먼저 축소
    - 특정 노드를 삭제 하면서 동시에 노드 개수를 줄이기 어려움 : 줄일때 삭제 정책 옵션이 다양하지 않음
        - 정책 미지원 시 삭제 방식(예시) : 100대 중 미삭제 EC2 보호 설정 후 삭제 될 ec2의 파드를 이주 후 scaling 조절로 삭제 후 원복
    - 특정 노드를 삭제하면서 동시에 노드 개수를 줄이기 어려움
    - 폴링 방식이기에 너무 자주 확장 여유를 확인 하면 API 제한에 도달할 수 있음
    - **스케일링 속도가 매우 느림**
    
    ---
    
    - Cluster Autoscaler 는 쿠버네티스 클러스터 자체의 오토 스케일링을 의미하며, 수요에 따라 워커 노드를 자동으로 추가하는 기능
    - 언뜻 보기에 클러스터 전체나 각 노드의 부하 평균이 높아졌을 때 확장으로 보인다 → 함정! 🚧
    - Pending 상태의 파드가 생기는 타이밍에 처음으로 **Cluster Autoscaler 이 동작**한다
        - 즉, Request 와 Limits 를 적절하게 설정하지 않은 상태에서는 실제 노드의 **부하 평균이 낮은 상황**에서도 **스케일 아웃**이 되거나,
        **부하 평균이 높은** 상황임에도 **스케일 아웃이 되지 않는다!**
    - 기본적으로 리소스에 의한 스케줄링은 Requests(최소)를 기준으로 이루어진다. 다시 말해 Requests 를 초과하여 할당한 경우에는 최소 리소스 요청만으로 리소스가 꽉 차 버려서 신규 노드를 추가해야만 한다. 이때 실제 컨테이너 프로세스가 사용하는 리소스 사용량은 고려되지 않는다.
    - 반대로 Request 를 낮게 설정한 상태에서 Limit 차이가 나는 상황을 생각해보자. 각 컨테이너는 Limits 로 할당된 리소스를 최대로 사용한다. 그래서 실제 리소스 사용량이 높아졌더라도 Requests 합계로 보면 아직 스케줄링이 가능하기 때문에 클러스터가 스케일 아웃하지 않는 상황이 발생한다.
    - 여기서는 **CPU 리소스** 할당을 예로 설명했지만 **메모리의 경우도 마찬**가지다.



</details>



![https://cafe.naver.com/kubeops](/Images/eks/eks_a17.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a18.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a19.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a20.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a21.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a22.png)







## CPA - Cluster Proportional Autoscaler
- 소개 : 노드 수 증가에 비례하여 성능 처리가 필요한 애플리케이션(컨테이너/파드)를 수평으로 자동 확장 ex. coredns


![구성](/Images/eks/eks_a05.png)
[EKS 스터디 - 5주차 2편 - CPA](https://malwareanalysis.tistory.com/604)



<details><summary>실습</summary>

```bash
#
helm repo add cluster-proportional-autoscaler https://kubernetes-sigs.github.io/cluster-proportional-autoscaler

# CPA규칙을 설정하고 helm차트를 릴리즈 필요
helm upgrade --install cluster-proportional-autoscaler cluster-proportional-autoscaler/cluster-proportional-autoscaler

# nginx 디플로이먼트 배포
cat <<EOT > cpa-nginx.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nginx
  template:
    metadata:
      labels:
        app: nginx
    spec:
      containers:
      - name: nginx
        image: nginx:latest
        resources:
          limits:
            cpu: "100m"
            memory: "64Mi"
          requests:
            cpu: "100m"
            memory: "64Mi"
        ports:
        - containerPort: 80
EOT
kubectl apply -f cpa-nginx.yaml

# CPA 규칙 설정
cat <<EOF > cpa-values.yaml
config:
  ladder:
    **nodesToReplicas:
      - [1, 1]
      - [2, 2]
      - [3, 3]
      - [4, 3]
      - [5, 5]**
options:
  namespace: default
  target: "deployment/nginx-deployment"
EOF
kubectl describe cm cluster-proportional-autoscaler

# 모니터링
**watch -d kubectl get pod**

# helm 업그레이드
helm upgrade --install cluster-proportional-autoscaler -f cpa-values.yaml cluster-proportional-autoscaler/cluster-proportional-autoscaler

# 노드 5개로 증가
export ASG_NAME=$(aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].AutoScalingGroupName" --output text)
aws autoscaling update-auto-scaling-group --auto-scaling-group-name ${ASG_NAME} --min-size 5 --desired-capacity 5 --max-size 5
aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" --output table

# 노드 4개로 축소
aws autoscaling update-auto-scaling-group --auto-scaling-group-name ${ASG_NAME} --min-size 4 --desired-capacity 4 --max-size 4
aws autoscaling describe-auto-scaling-groups --query "AutoScalingGroups[? Tags[? (Key=='eks:cluster-name') && Value=='myeks']].[AutoScalingGroupName, MinSize, MaxSize,DesiredCapacity]" --output table
```


- 삭제:  `helm uninstall cluster-proportional-autoscaler && kubectl delete -f cpa-nginx.yaml`
- (참고) CPU/Memory 기반 정책 - [Blog](https://leehosu.tistory.com/entry/AEWS-5-2-Amazon-EKS-Autoscaling-CA-CPA#cpa-%EC%A0%95%EC%B1%85-%EB%B0%B0%ED%8F%AC)
    
    ```bash
     "coresToReplicas":
          [
            [ 1, 1 ],
            [ 64, 3 ],
            [ 512, 5 ],
            [ 1024, 7 ],
            [ 2048, 10 ],
            [ 4096, 15 ]
          ],
    ```

</details>


-----
## Karpenter 실습 환경 준비를 위해서 현재 EKS 실습 환경 전부 삭제
~~~bash

eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME

~~~

---

##  Karpenter : K8S Native AutoScaler

- 소개 : 오픈소스 노드 수명 주기 관리 솔루션, 몇 초 만에 컴퓨팅 리소스 제공 - https://ec2spotworkshops.com/karpenter.html

![구성](/Images/eks/eks_a06.png)

[**참고링크**](https://file.notion.so/f/f/a6af158e-5b0f-4e31-9d12-0d0b2805956a/dc43285b-5aed-4cf3-bfc2-509b2a67fbb4/CON405_How-to-monitor-and-reduce-your-compute-costs.pdf?id=80f38a76-10ae-4b7b-b54e-33d6fc0b17b8&table=block&spaceId=a6af158e-5b0f-4e31-9d12-0d0b2805956a&expirationTimestamp=1712534400000&signature=hSwzzUZxJHzQEpUbyPwL04CmtUs0Y7kFdKUAzoGWJoc&downloadName=CON405_How-to-monitor-and-reduce-your-compute-costs.pdf)


- **Karpenter graduates to beta - [Link](https://aws.amazon.com/ko/blogs/containers/karpenter-graduates-to-beta/)**
- **[악분님] karpenter 0.2x -> 0.3x 버전 업그레이드 주의사항 - [Link](https://malwareanalysis.tistory.com/712)**
- **[악분님]** `karpenter 0.33이상부터 drift라는 옵션이 디폴트로 활성`화되어 있습니다.
    - 운영환경에 적용할 때 주의해야되는 옵션일 것 같아요drift는 *NodePool, NodeClass* 설정을 변경하면 기존 karpenter가 생성한 노드에도 적용되는 옵션입니다. 기존 노드에 변경된 옵션이 적용되면, 노드가 교체되어 장애를 발생시킬 수 있습니다.
    - drift설명: https://techblog.gccompany.co.kr/karpenter-0-3x-36a0cb57b205
    - 공식문서: https://karpenter.sh/docs/reference/settings/#feature-gates
- **[악분님] Karpenter 정리 영상 모음**
    
  <iframe width="529" height="298" src="https://www.youtube.com/embed/FPlCVVrCD64" title="[데브옵스] 오픈 소스 Karpenter를 활용한 Amazon EKS 확장 운영 전략 | 신재현, 무신사" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

<details><summary>내용 정리</summary>
<iframe width="529" height="298" src="https://www.youtube.com/embed/FPlCVVrCD64" title="[데브옵스] 오픈 소스 Karpenter를 활용한 Amazon EKS 확장 운영 전략 | 신재현, 무신사" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

- **작동 방식**
    - 모니터링 → (스케줄링 안된 Pod 발견) → 스펙 평가 → 생성 ⇒ **Provisioning**
    - 모니터링 → (비어있는 노드 발견) → 제거 ⇒ **Deprovisioning**
- **Provisioner** CRD : **시작 템플릿이 필요 없습니다**! ← 시작 템플릿의 대부분의 설정 부분을 대신함
    - 필수 : 보안그룹, 서브넷
    - 리소스 찾는 방식 : 태그 기반 자동, 리소스 ID 직접 명시
    - 인스턴스 타입은 **가드레일** 방식으로 선언 가능! : 스팟(우선) vs 온디멘드, 다양한 인스턴스 type 가능
- Pod에 적합한 인스턴스 중 **가장 저렴한 인스턴스**로 **증설** 됩니다
- PV를 위해 단일 서브넷에 노드 그룹을 만들 필요가 없습니다 → 자동으로 **PV가 존재하는 서브넷**에 **노드**를 만듭니다
- 사용 안하는 노드를 자동으로 정리, 일정 기간이 지나면 노드를 자동으로 만료 시킬 수 있음
    - **ttlSecondsAfterEmpty** : 노드에 데몬셋을 제외한 모든 Pod이 존재하지 않을 경우 해당 값 이후에 자동으로 정리됨
    - **ttlSecondsUntilExpired** : 설정한 기간이 지난 노드는 자동으로 cordon, drain 처리가 되어 노드를 정리함
        - 이때 노드가 주기적으로 정리되면 자연스럽게 기존에 여유가 있는 노드에 재배치 되기 때문에 좀 더 효율적으로 리소스 사용 가능 + 최신 AMI 사용 환경에 도움
    - 노드가 제때 drain 되지 않는다면 비효율적으로 운영 될 수 있습니다
- 노드를 줄여도 다른 노드에 충분한 여유가 있다면 **자동으로 정리**해줌!
- 큰 노드 하나가 작은 노드 여러개 보다 비용이 저렴하다면 **자동으로 합쳐**줌!
    
    → 기존에 확장 속도가 느려서 보수적으로 운영 하던 부분을 해소
    
- **오버 프로비저닝 필요** : 카펜터를 쓰더라도 EC2가 뜨고 데몬셋이 모두 설치되는데 최소 1~2분이 소요 → **깡통 증설용 Pod**를 만들어서 여유 공간을 강제로 확보!
- 오버 프로비저닝 Pod x **KEDA** : 대규모 증설이 예상 되는 경우 미리 준비




</details>



#### 전부 삭제하여 모니터링 재설치

> https://grafana.com/grafana/dashboards/?search=karpenter

~~~bash

#
helm repo add grafana-charts https://grafana.github.io/helm-charts
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring

# 프로메테우스 설치
curl -fsSL https://raw.githubusercontent.com/aws/karpenter-provider-aws/v"${KARPENTER_VERSION}"/website/content/en/preview/getting-started/getting-started-with-karpenter/prometheus-values.yaml | envsubst | tee prometheus-values.yaml
helm install --namespace monitoring prometheus prometheus-community/prometheus --values prometheus-values.yaml

# 그라파나 설치
curl -fsSL https://raw.githubusercontent.com/aws/karpenter-provider-aws/v"${KARPENTER_VERSION}"/website/content/en/preview/getting-started/getting-started-with-karpenter/grafana-values.yaml | tee grafana-values.yaml
helm install --namespace monitoring grafana grafana-charts/grafana --values grafana-values.yaml
kubectl patch svc -n monitoring grafana -p '{"spec":{"type":"LoadBalancer"}}'

# admin 암호
kubectl get secret --namespace monitoring grafana -o jsonpath="{.data.admin-password}" | base64 --decode ; echo

# 그라파나 접속
kubectl annotate service grafana -n monitoring "external-dns.alpha.kubernetes.io/hostname=grafana.$MyDomain"
echo -e "grafana URL = http://grafana.$MyDomain"

~~~




<details><summary>실습</summary>

- 실습 환경 배포(2분 후 접속) : **myeks2**

```bash
# YAML 파일 다운로드
curl -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/**karpenter-preconfig.yaml**

# CloudFormation 스택 배포
예시) aws cloudformation deploy --template-file **karpenter-preconfig.yaml** --stack-name **myeks2** --parameter-overrides KeyName=**kp-gasida** SgIngressSshCidr=$(curl -s ipinfo.io/ip)/32  MyIamUserAccessKeyID=**AKIA5...** MyIamUserSecretAccessKey=**'CVNa2...'** ClusterBaseName=**myeks2** --region ap-northeast-2

# CloudFormation 스택 배포 완료 후 작업용 EC2 IP 출력
aws cloudformation describe-stacks --stack-name **myeks2** --query 'Stacks[*].**Outputs[0]**.OutputValue' --output text

# 작업용 EC2 SSH 접속
ssh -i **~/.ssh/kp-gasida.pem** ec2-user@$(aws cloudformation describe-stacks --stack-name **myeks2** --query 'Stacks[*].Outputs[0].OutputValue' --output text)
```

- 사전 확인 & eks-node-viewer 설치

```bash
# IP 주소 확인 : 172.30.0.0/16 VPC 대역에서 172.30.1.0/24 대역을 사용 중
ip -br -c addr

# EKS Node Viewer 설치 : 현재 ec2 spec에서는 **설치에 다소 시간이 소요됨** = **2분 이상**
**wget https://go.dev/dl/go1.22.1.linux-amd64.tar.gz
tar -C /usr/local -xzf go1.22.1.linux-amd64.tar.gz
export PATH=$PATH:/usr/local/go/bin
go install github.com/awslabs/eks-node-viewer/cmd/eks-node-viewer@latest**

# [터미널1] bin 확인
**cd ~/go/bin && ./eks-node-viewer -h**

# EKS 배포 완료 후 실행 하자
**cd ~/go/bin && ./eks-node-viewer --resources cpu,memory**
```

- EKS 배포 - [Link](https://karpenter.sh/docs/getting-started/getting-started-with-karpenter/)

```bash
# 변수 정보 확인
export | egrep 'ACCOUNT|AWS_' | egrep -v 'SECRET|KEY'

# 변수 설정
export KARPENTER_NAMESPACE="kube-system"
export K8S_VERSION="1.29"
export KARPENTER_VERSION="0.35.2"
export TEMPOUT=$(mktemp)
export ARM_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2-arm64/recommended/image_id --query Parameter.Value --output text)"
export AMD_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2/recommended/image_id --query Parameter.Value --output text)"
export GPU_AMI_ID="$(aws ssm get-parameter --name /aws/service/eks/optimized-ami/${K8S_VERSION}/amazon-linux-2-gpu/recommended/image_id --query Parameter.Value --output text)"
export AWS_PARTITION="aws"
export **CLUSTER_NAME**="**${USER}-karpenter-demo**"
echo "export CLUSTER_NAME=$CLUSTER_NAME" >> /etc/profile
**echo $KARPENTER_VERSION $CLUSTER_NAME $AWS_DEFAULT_REGION $AWS_ACCOUNT_ID $TEMPOUT** $ARM_AMI_ID $AMD_AMI_ID $GPU_AMI_ID

# CloudFormation 스택으로 IAM Policy, Role(KarpenterNodeRole-myeks2) 생성 : **3분 정도 소요**
curl -fsSL https://raw.githubusercontent.com/aws/karpenter-provider-aws/v"${KARPENTER_VERSION}"/website/content/en/preview/getting-started/getting-started-with-karpenter/cloudformation.yaml  > "${TEMPOUT}" \
&& aws cloudformation deploy \
  --stack-name "Karpenter-${CLUSTER_NAME}" \
  --template-file "${TEMPOUT}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides "ClusterName=${CLUSTER_NAME}"

# 클러스터 생성 : myeks2 EKS 클러스터 생성 **19분 정도** 소요
**eksctl create cluster -f -** <<EOF
---
apiVersion: eksctl.io/v1alpha5
kind: ClusterConfig
metadata:
  name: ${CLUSTER_NAME}
  region: ${AWS_DEFAULT_REGION}
  version: "${K8S_VERSION}"
  **tags:
    karpenter.sh/discovery: ${CLUSTER_NAME}**

**iam**:
  withOIDC: true
  **serviceAccounts**:
  - metadata:
      name: karpenter
      namespace: "${KARPENTER_NAMESPACE}"
    roleName: ${CLUSTER_NAME}-karpenter
    attachPolicyARNs:
    - arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:policy/**KarpenterControllerPolicy-${CLUSTER_NAME}**
    roleOnly: true

**iamIdentityMappings**:
- arn: "arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:role/**KarpenterNodeRole-${CLUSTER_NAME}**"
  username: system:node:{{EC2PrivateDNSName}}
  groups:
  - system:bootstrappers
  - system:nodes

**managedNodeGroups**:
- instanceType: **m5.large**
  amiFamily: **AmazonLinux2**
  name: **${CLUSTER_NAME}-ng**
  desiredCapacity: 2
  minSize: 1
  maxSize: 10
  iam:
    withAddonPolicies:
      externalDNS: true
EOF

**# eks 배포 확인**
eksctl get cluster
eksctl get nodegroup --cluster $CLUSTER_NAME
eksctl get **iamidentitymapping** --cluster $CLUSTER_NAME
eksctl get **iamserviceaccount** --cluster $CLUSTER_NAME
eksctl get addon --cluster $CLUSTER_NAME

# default 네임스페이스 적용
**kubectl ns default**

# 노드 정보 확인
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone
****
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
kubectl annotate service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=kubeopsview.$MyDomain"
echo -e "Kube Ops View URL = http://kubeopsview.$MyDomain:8080/#scale=1.5"

# [터미널1] eks-node-viewer
**cd ~/go/bin && ./eks-node-viewer --resources cpu,memory**

**# k8s 확인**
kubectl cluster-info
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone
kubectl get pod -n kube-system -owide
**kubectl describe cm -n kube-system aws-auth**

# Karpenter 설치를 위한 변수 설정 및 확인
export CLUSTER_ENDPOINT="$(aws eks describe-cluster --name "${CLUSTER_NAME}" --query "cluster.endpoint" --output text)"
export KARPENTER_IAM_ROLE_ARN="arn:${AWS_PARTITION}:iam::${AWS_ACCOUNT_ID}:role/${CLUSTER_NAME}-karpenter"
echo "${CLUSTER_ENDPOINT} ${KARPENTER_IAM_ROLE_ARN}"

# EC2 Spot Fleet의 service-linked-role 생성 확인 : 만들어있는것을 확인하는 거라 아래 에러 출력이 정상!
# If the role has already been successfully created, you will see:
# An error occurred (InvalidInput) when calling the CreateServiceLinkedRole operation: Service role name AWSServiceRoleForEC2Spot has been taken in this account, please try a different suffix.
aws iam create-service-linked-role --aws-service-name spot.amazonaws.com || true

# docker logout : Logout of docker to perform an unauthenticated pull against the public ECR
docker logout public.ecr.aws

# helm registry logout
helm registry logout public.ecr.aws

# karpenter 설치
helm install karpenter oci://public.ecr.aws/karpenter/karpenter --version "${KARPENTER_VERSION}" --namespace "${KARPENTER_NAMESPACE}" --create-namespace \
  --set "serviceAccount.annotations.eks\.amazonaws\.com/role-arn=${KARPENTER_IAM_ROLE_ARN}" \
  --set "settings.clusterName=${CLUSTER_NAME}" \
  --set "settings.interruptionQueue=${CLUSTER_NAME}" \
  --set controller.resources.requests.cpu=1 \
  --set controller.resources.requests.memory=1Gi \
  --set controller.resources.limits.cpu=1 \
  --set controller.resources.limits.memory=1Gi \
  --wait
 
# 확인
kubectl get-all -n $KARPENTER_NAMESPACE
kubectl get all -n $KARPENTER_NAMESPACE
kubectl get crd | grep karpenter

# APi 변경
v1alpha5/**Provisioner** → v1beta1/**NodePool**
v1alpha1/**AWSNodeTemplate** → v1beta1/**EC2NodeClass** 
v1alpha5/**Machine** → v1beta1/**NodeClaim**
```

- **Create NodePool**(구 Provisioner) - [Link](https://karpenter.sh/docs/getting-started/getting-started-with-karpenter/#5-create-nodepool) [Workshop](https://www.eksworkshop.com/docs/autoscaling/compute/karpenter/setup-provisioner)
    - 관리 리소스는 securityGroupSelector and subnetSelector로 찾음
    - consolidationPolicy : 미사용 노드 정리 정책, 데몬셋 제외

```bash
cat <<EOF | envsubst | kubectl apply -f -
apiVersion: karpenter.sh/v1beta1
kind: **NodePool**
metadata:
  name: default
**spec**:
  template:
    spec:
      **requirements**:
        - key: kubernetes.io/arch
          operator: In
          values: ["**amd64**"]
        - key: kubernetes.io/os
          operator: In
          values: ["**linux**"]
        - key: karpenter.sh/capacity-type
          operator: In
          values: ["**spot**"]
        - key: karpenter.k8s.aws/instance-category
          operator: In
          values: ["c", "m", "r"]
        - key: karpenter.k8s.aws/instance-generation
          operator: Gt
          values: ["2"]
      **nodeClassRef**:
        apiVersion: karpenter.k8s.aws/v1beta1
        kind: **EC2NodeClass**
        name: default
  limits:
    cpu: **1000**
  **disruption**:
    **consolidationPolicy**: WhenUnderutilized
    expireAfter: **720h** # 30 * 24h = 720h
---
apiVersion: karpenter.k8s.aws/v1beta1
kind: **EC2NodeClass**
metadata:
  name: default
**spec**:
  amiFamily: **AL2** # Amazon Linux 2
  role: "**KarpenterNodeRole**-${CLUSTER_NAME}" # replace with your cluster name
  **subnetSelectorTerms**:
    - tags:
        karpenter.sh/discovery: "${CLUSTER_NAME}" # replace with your cluster name
  **securityGroupSelectorTerms**:
    - tags:
        karpenter.sh/discovery: "${CLUSTER_NAME}" # replace with your cluster name
  **amiSelectorTerms**:
    - id: "${ARM_AMI_ID}"
    - id: "${AMD_AMI_ID}"
#   - id: "${GPU_AMI_ID}" # <- GPU Optimized AMD AMI 
#   - name: "amazon-eks-node-${K8S_VERSION}-*" # <- automatically upgrade when a new AL2 EKS Optimized AMI is released. This is unsafe for production workloads. Validate AMIs in lower environments before deploying them to production.
EOF

# 확인
kubectl get nodepool,ec2nodeclass
```

- Scale up deployment - [Link](https://karpenter.sh/docs/getting-started/getting-started-with-karpenter/#6-scale-up-deployment) [Workshop](https://www.eksworkshop.com/docs/autoscaling/compute/karpenter/node-provisioning)

```bash
# pause 파드 1개에 CPU 1개 최소 보장 할당
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: **Deployment**
metadata:
  name: **inflate**
spec:
  **replicas: 0**
  selector:
    matchLabels:
      app: inflate
  template:
    metadata:
      labels:
        app: inflate
    spec:
      **terminationGracePeriodSeconds**: 0
      containers:
        - name: inflate
          image: public.ecr.aws/eks-distro/kubernetes/**pause**:3.7
          resources:
            requests:
              **cpu: 1**
EOF

# Scale up
kubectl get pod
**kubectl scale deployment inflate --replicas 5**
kubectl logs -f -n "${KARPENTER_NAMESPACE}" -l app.kubernetes.io/name=karpenter -c controller
**kubectl logs -f -n "${KARPENTER_NAMESPACE}" -l app.kubernetes.io/name=karpenter -c controller | jq '.'**
```

- Scale down deployment

```bash
# Now, delete the deployment. After a short amount of time, Karpenter should terminate the empty nodes due to consolidation.
**kubectl delete deployment inflate && date
kubectl logs -f -n "${KARPENTER_NAMESPACE}" -l app.kubernetes.io/name=karpenter -c controller**
```

- 리소스 삭제

```bash
# Karpenter IAM Role 생성한 CloudFormation 삭제
aws cloudformation **delete-stack** --stack-name "Karpenter-${CLUSTER_NAME}"

# EC2 Launch Template 삭제
aws ec2 **describe-launch-templates** --filters "Name=tag:karpenter.k8s.aws/cluster,Values=${CLUSTER_NAME}" |
    jq -r ".LaunchTemplates[].LaunchTemplateName" |
    xargs -I{} **aws ec2 delete-launch-template** --launch-template-name {}

# 클러스터 삭제
**eksctl delete cluster --name "${CLUSTER_NAME}"**

# 위 삭제 완료 후 아래 삭제
aws cloudformation delete-stack --stack-name **myeks2**
```


</details>


![https://cafe.naver.com/kubeops](/Images/eks/eks_a23.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a24.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a25.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a26.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a27.png)

![https://cafe.naver.com/kubeops](/Images/eks/eks_a28.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a29.png)
![https://cafe.naver.com/kubeops](/Images/eks/eks_a30.png)










