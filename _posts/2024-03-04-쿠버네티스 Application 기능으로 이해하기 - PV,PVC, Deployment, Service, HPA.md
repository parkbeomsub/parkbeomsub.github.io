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


 - * NFS와 같이 nas를 사용하면  수동연결이 필요하고 자동화 운영 관점에 좋지 않음 

 


