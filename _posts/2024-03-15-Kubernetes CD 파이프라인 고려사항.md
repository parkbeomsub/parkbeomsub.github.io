---
layout: single
title: "쿠버네티스 CI/CD 파이프라인을 구성할 때 고려해야 하는 요소"
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins ,CI/DC , 1pro ]
toc: true
---



[이전 글](https://parkbeomsub.github.io/devops/%EC%BF%A0%EB%B2%84%EB%84%A4%ED%8B%B0%EC%8A%A4-Devops-Jenkins-%EC%86%8C%EC%8A%A4-%EB%B9%8C%EB%93%9C%ED%95%98%EA%B8%B0/)

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory81.png)

 - 이전글에서  CICD 환경을 구축했고 위 사진과 같이 1,2,3 을 나눠 소스 빌드/이미지 빌드/ 배포 를 진행했다.
 - 이번 포스팅에서는  Jenkins Pipeline을 구성할 때 고려해야하는 요소가 무엇이 있는지 보도록하자. 
 - Jenkins Pipeline 을 통해 1,2,3 번의 액션을 한 번에 할 수 있는데 실무에서 일을 하다 보면 기능적인 구분보다 담당하는 사람에 따라서 구성을 분리하는 게 좋을 때도 많습니다  -> 각각 역할을 담당하는 사람이 다를 수 있어서
 - 데이버 보안 /레퍼런스 / 유지보수 업체 고려사항
  
  


---

![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory81.png)
   - 위 사진과 같이 빌드에 소스빌드/컨테이너 빌드를 두고 배포를 argocd를 둬서 인프라 환경을  구분하여 배포할 수 있다.
---
![출처:https://cafe.naver.com/kubeops](/Images/인강/linuxhistory83.png)

- 배포를  agrocd 위치에 어디에 두냐에 따라  장단점이 발생
  1.  사진의 배포를 CICD환경에 두는 경우  하나만 관리하는 장점 , 장애시 영향도가 높다.
  2.  인프라 환경에 argocd를 두면 이중관리가 필요하지만  장애시 영향도가 없다.
  

   ||CICD 도구||
   |-----|-----|-----|
   |온라인| Github Actions|  
   |오프라인|jenkins  jenkinsX  tekton|
   
   ||CI Tool||
   |----|----|----|
   |온라인|Travis CI   Circle CI|
   |오프라인|GitLab|

   ||CD Tool||
   |----|-----|----|
   |온라인|-|
   |오프라인|ArgoCD Spinnaker|

 - 온라인 경우 CICD 서버를 구성하지 않아도 되지만 git에 올라가는 데이터가  중요한 것이라면  사용하면 안 된다.
 - 컨테이너 툴비교하면 ArgoCD가 가장 많이 사용
 - 모든 툴 비교하면 GitAction > Jenkins > ArgoCD
 - 국내는 Jenkins  > GitHubAction > Argo 
  
---
**Docker 대체**  
Docker는 도커데몬이 항상 띄어져있어라 컨태이너가 동작하고, 백그라운드서비스

도커가 죽으면 컨테이너가 모두 다운되는 현상도 문제가 됨 -> CI/CD에는 큰 문제가 되지 않음

- 대체자
   이미지 빌드는  buildah
   이미지 push는 skopeo
 