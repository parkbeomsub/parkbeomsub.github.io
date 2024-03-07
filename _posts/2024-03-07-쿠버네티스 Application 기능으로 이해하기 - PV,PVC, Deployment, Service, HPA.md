---
layout: single
title: "2024-03-04-쿠버네티스 Application 기능으로 이해하기 - PV,PVC, Deployment, Service, HPA"
categories: linux
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , PV,PVC ,Deployment, HPA, Service  ]
toc: true
---



#  2024-03-04-쿠버네티스 Application 기능으로 이해하기 - PV,PVC, Deployment, Service, HPA!

## PVC ,PV - local

   .

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory25.png)
 - 컨테이너에 마운트를 하기 위한 오브젝트가 PV, PVC이다.
 - pod가 리부팅 되면 파일들이 사라지는데  휘발성 파일이 아닌 기존 파일들을 남겨 놓기 위한 오브젝트라 볼 수 있다.
 - PV를 생성 후 PVC를 생성한 뒤 PVC와 POD를 연결하게 된다.

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory26.png)
 
 - 위 사진을 참조 , resource , accessModes 는 필수 값이며 ,  pv,pvc내용이 같아야한다.
  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory27.png)
- nodeAffinity를 사용하여 pv를 특정 노드에 생성을 할 수 있게하고 죽더라도 master에 재생성하여 데이터를 유지할 수 있다.

  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory28.png)
  - hostpath를 사용할 수 있는데  pv,pvc를 사지용하지 않고 바로 사용하는 방법이 있다. 이 방법은 권장하지 않고 node에 노드 공간이 부족해지면 해당 노드의 Pod들에도 영향이 긴다.  만약 해당 기능은 노드 정보를 이용해야하는 app 모니터링 툴같은 경우 사용이 가능하다.


 - * NFS와 같이 nas를 사용하면  수동연결이 필요하고 자동화 운영 관점에 좋지 않음  -> nas 운영까지 신경써야하고 NAS가 고장나면 크리티컬해짐



## Deployment - update
  Deploy에 Template의 내용이 수정되면 업데이트가 진행된다. 

  새로운 이미지를 등록하면  ReplicaSet이 기존 replicas를 0으로 신규를 기존값으로 변경시켜주고 기존의 replicas에 pod는 삭제된다.
 ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory29.png)

  
  ### strategy(reCrerate , Rolling update)
   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory30.png)

   - ReCreate 방식은 업데이트가 진행되면  기존 모든 pod를 삭제시키고 변경되는 pod를 한번에 시작시킨다.
      > 속도는 빠를 수 있으나  기동 시간 만큼 서비스가 중단됨

  - Rolling Update
    > 서비스 중단이 없도록 하기 위한 방법 
    > 기존 1개를 삭제 >  신규 1개를 생성 > 기존 1개 삭제 > 신규 생성으로 교차하여 삭제, 생성을 한다. 
    > 자원 사용량이 증가  150프로 증가

    관련옵션에는 
    ~~~
    maxUnavailable:  %   //업데이트 동안 최대 몇개의 pod를 업데이트 상태로 유지할지
    maxSurge: %  // 신규 파드를 최대 몇개까지 동시에 만들지
    ~~~

    ### 예제
    
    maxUnavailable: 100 %   
    maxSurge: 100%    
    maxUnavailable 100이면 결국 서비스를 중지시킨다는 의미이고 maxSurge 100면 replicas의 값만큼 한번에 생성한다는 뜻


    maxUnavailable: 0%   
    maxSurge: 100%  
    maxUnavailable: 0 이면 업데이트동안  서비스 불가인 pod가 없도록 설정, 서비스 중인 pod2개르 유지
    maxSurge 100이라 동시에 replica만큼 생성됨  pod 기동시간이 다르기 때문에  신규 pod가 정상적으로 생성되면  기존의 파트가 순차적으로 삭제됨 -> 블루/그린 배포와 유사
    ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory31.png)

    maxUnavailable: 25%   
    maxSurge: 25%
    위와 같이 기본값으로 설정하면  서비스되는 pod의 숫자가 줄어들어 서비스에 문제가 발생할 수 있다.  



  - 블루/ 그린베포
   > 기존/ 신규 동시에  호출되지 않고 자원을 기존의 2배로 늘린다음 늘어난 자원에 신규배포를 한다. 200프로 자원이 필요, 배포가 빠르다.  reCreate와 같은 현상



## Service

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory32.png)
 - 우선 Pod와 Service 는  label과 selecter로 연결이 된다.
 - 타입은 (LoadBalaner ,NodePort , ClousterIP)있다.
   - **NodePort** 타입은 워커노드 아이피에 Port를 빌려 pod와 연결된다.
   - container에 Port는 Service에 targetPort를 가르키게 된다.

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory33.png)
    
   - 기본은 **ClusterIP** 해당 타입은 쿠버네티스 내부에 pod만 접근하는 용도로 사용된다.
   - 서비스 포트라는 필수 속성이 있는데  역할로 Service Discovery (내부 DNS를 이용해  서비스의 이름을 API로 호출할 수 있게 하는 기능) 

   ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory34.png)

   - 만약 네임스페이스가 있다면   [service_name].[namespace]:[port]
   - **팁** pod에 앱의 port가 변경되면  서비스의 TargetPort까지 신경써야한다. 해결방법은 pod내부에 ports (정보성 옵션)라는 설정값이 있고 Name , conateinerPort를 넣을 수 있다. 서비스의 targetPort에 pod의 ports의 이름을 넣으면 된다. -> pod의 port 변경 시 Service 변경 불 필요

    ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory35.png)

    - **서비스 레지스트리** 
      - pod가 제거되면 자동으로 연결을 끊어주고 신규 pod에 연결을 시켜주는 기능
    

## HPA
  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory36.png)
  
  - HPA에 Deploy 이름으로 지정을 하고  최대/최소 replica 수르 지정한다. 추가적으로 메크릭값의 수치를 정하면 생성 가능하다.

  - 위 사진을 보면  CPU가 60%이면  액션을 하도록 설정을 했는데 만약 1개의 파드만 70%이면 동작하지 않는다. 평균으로 움직이기 때문이다.
  - 공식은 변경 파드수  = 현재 pod 수 8(평균 CPU /HPA CPU)   -> 값에 올림 처리한다.
  - Memory는 내부 가비지 컬렉션의 동작으로 동적으로 변경되기 때문에 부하를 판단하기는 어렵다. -> 잘 사용을 하지 않는다.
  
  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory37.png)

    - 이상적인  스케일은  중단 없이 부하에 맞게 증량/증감되는 그래프
    - 현실적인 스케일은 pod가 모두 중단되어 Error로 변경되고 다시 시작되면 그 시간동안 재시작된다. 

  - **behavior**는 잦은 스케일링을 방지를 위한 옵션이다 / 120으로 설정하면 120분동안 임계치를 유지해야지 동작하는 옵션이다.

    ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory38.png)



 
 