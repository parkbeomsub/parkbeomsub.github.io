---
layout: single
title: "Jenkins  Docker Image  잦은 배포 방법 / 이미지 관리 방법"
categories:  Devops
tags: [linux, container, kubernetes , 인강-일프로, 쿠버네티스 어나더 클래스 (지상편) - Sprint 1 2 , DevOps ,jenkins ,CI/DC ,Jenkens  ]
toc: true
---


#  Jenkins 파일에서 environment에 변수 선언을 날짜로 설정한다.

> BUILD_DATE = sh(script: "echo `date +%y%m%d.%d%H%M`", returnStdout: true).trim()

~~~bash

environment {
  APP_VERSION = '1.0.1'
  BUILD_DATE = sh(script: "echo `date +%y%m%d.%d%H%M`", returnStdout: true).trim()
  TAG = "${APP_VERSION}-" + "${BUILD_DATA}"

stage('컨테이너 빌드 및 업로드') {
  steps {
	script{
	  // 도커 빌드
      sh "docker build ./2224/build/docker -t 1pro/api-tester:${TAG}"
      sh "docker push 1pro/api-tester:${TAG}"

stage('헬름 배포') {
  steps {
    withCredentials([file(credentialsId: 'k8s_master_config', variable: 'KUBECONFIG')]) {
      sh "helm upgrade api-tester-2224 ./2224/deploy/helm/api-tester -f ./2224/deploy/helm/api-tester/values-dev.yaml" +
         ...
         " --set image.tag=${TAG}"   // Deployment의 Image에 태그 값 주입



~~~


##  docker tag 변경 명령 (to latest)

~~~bash

docker tag 1pro/api-tester:1.0.1-231220.171834 1pro/api-tester:latest
docker push 1pro/api-tester:latest

~~~

## 업로드 후 CI/CD Server에 만들어진 이미지 삭제 - Jenkinsfile 내용 


~~~bash

stage('컨테이너 빌드 및 업로드') {
  steps {
	script{
	  // 도커 빌드
      sh "docker build ./${CLASS_NUM}/build/docker -t ${DOCKERHUB_USERNAME}/api-tester:${TAG}"
      sh "docker push ${DOCKERHUB_USERNAME}/api-tester:${TAG}"
      sh "docker rmi ${DOCKERHUB_USERNAME}/api-tester:${TAG}"   // 이미지 삭제

~~~

