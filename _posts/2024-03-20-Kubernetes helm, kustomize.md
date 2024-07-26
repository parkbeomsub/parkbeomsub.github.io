---
layout: single
title: "Kubernetes helm, kustomize"
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins ,CI/DC ,Jenkens ,kustomize, helm , 1pro]
toc: true
---



# helm kustomize 비교

## Helm 
- 함수방식
- template 밑에 배포해야할 오브젝트들이 많은데  {} 의 변수처리를 한 것들이 있다.
  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory103.png)
- helm install 명령어를 통해 변수에 인자가 치환된다.
  ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory104.png)
  - API 서버에 해당 yaml 으로 실행요청
## kustomize 
- 오버레이방식
- -k 옵션은  kustomize 패키지를 배포한다는 옵션
    ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory105.png)
- 아래 그림의 파란색 부분의 yaml  targetport 옵션이 없어서 유효하지 않지만  base파일을 덮어서  사용하여 재구성
    ![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory106.png)


## 요약
  - 둘다 한번의 명령으로 여러 오프젝트를 생성할 수 있다.
  - 다만 방식의 차이가 위와 같이 있으며 , 만약 설치 오브젝트가 많아지는 경우 helm은  명령어의 파라미터가 늘어나고, kustomize는 파일의 수가 많아진다.
