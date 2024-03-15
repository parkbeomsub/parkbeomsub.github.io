---
layout: single
title: "쿠버네티스  배포 전략을 세울 때 고려해야 하는 요소"
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins ,CI/DC  ]
toc: true
---




[이전 글1](https://parkbeomsub.github.io/devops/%EC%BF%A0%EB%B2%84%EB%84%A4%ED%8B%B0%EC%8A%A4-Devops-Jenkins-%EC%86%8C%EC%8A%A4-%EB%B9%8C%EB%93%9C%ED%95%98%EA%B8%B0/)
[이전글 2](https://parkbeomsub.github.io/devops/Kubernetes-CD-%ED%8C%8C%EC%9D%B4%ED%94%84%EB%9D%BC%EC%9D%B8-%EA%B3%A0%EB%A0%A4%EC%82%AC%ED%95%AD/)

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory84.png)



- Kubernetes의 기능으로 배포 전략이 다행해졌다.

- ReCreate
  - pod를 삭제하고  / 새로운 pod를 생성하는 방식
  - Down Time이 발생한다.
  - 방법은 Deploy 업데이트
  - 유즈케이스 : 데이터베이스 스키마 변경 작업( service 중지 > replicas 0 > DB 작업 > replicas 기존 값으로 변경  ) 
  - 특징 : 자동으로 배포 (정지 , 롤백 가능)  ,트래픽 제어 불가
  - 툴 : kubectl /helm / kustomize




- Rolling Update
  - 버전 1,버전2 를 교차하며 삭제 / 생성하는 방법 
  - DownTime 발생하지않음
  - 배포 작업 : Deploy update
  - 유즈케이스 : 데이터베이스 스키마 변경 작업( service 중지 > replicas 0 > DB 작업 > replicas 기존 값으로 변경  ) 
  - 특징 : 자동배포 , 트레픽 제어불가, 서비스 중단없음
  - 툴 : kubectl /helm / kustomize



- Blue/ Green
   - 서비스에 service selector에 라벨링을 가지고  v1 ->v2 로 트레픽을 전환하는  방법
   - 한번에 전환이 되고 리소스가 2배가 필요함
   - 특징 :수동 배포시 롤백이 빠름(라벨링만 다시 바꾸면 되니)   , script를 통한   자동배포         
   - 주의사항 : 전환 시 과도한 트래픽이 유입되면 메모리나 DB커넥션들을 최적화시키느라 CPU를 많이 사용한다. 그렇게 되면 서버가 재시작되는 상황이 발생하여 사전에 앱이 어느정도의 트래픽을 처리하는지 사전에 부하테스트를 하는게 필요 
   - 공공기관 /금융권에서 사용하는게 좋음  qa는 신규버전 서비스에 접근




- Canary
   - Ingress Controller를 통한 트레픽 분산 방법  트레픽 량을 조금씩 늘려  이동시키는 방법
   - 방법 : v2 deploy /ingress/ 서비스 생성  > v1/v2에 가중치 변경 > v1 삭제
   - 콜드 스타트 방지
   - 특정 헤더 값에 의해서 v2에 접근할 수 있음
   - 두 버전을 비교할 수 있음
   - 툴 : argo  + ngins / istio



출처:https://cafe.naver.com/kubeops