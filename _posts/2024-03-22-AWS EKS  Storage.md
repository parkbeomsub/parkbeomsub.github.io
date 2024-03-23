---
layout: single
title: "AWS EKS Storage 실습"
categories: AWS
tags: [AWS, Container, Kubernetes , EKS , DevOps ,Network ,CNI ]
toc: true
---


# AWS EKS  Storage
 > 첨부링크 : https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick2.yaml
 
 > 방식은 아래와 동일하니 위 링크만 변경하여 진행한다.
  [ 실습구성 링크 ](https://parkbeomsub.github.io/aws/AWS-EKS-%EC%84%A4%EC%B9%98(addon-AWS-CNI,-Core-DNS,-kube-proxy)/)



![구성](/Images/eks/eks_s1.png)

![구성](/Images/eks/eks_s2.png)



## 기본 설정

<details><summary>설정 확인 및 실습 변수 설정</summary>
```bash

# default 네임스페이스 적용
**kubectl ns default**

# EFS 확인 : AWS 관리콘솔 EFS 확인해보자
echo $EfsFsId
mount -t efs -o tls $EfsFsId:/ /mnt/myefs
**df -hT --type nfs4**

**echo "efs file test" > /mnt/myefs/memo.txt**
cat /mnt/myefs/memo.txt
rm -f /mnt/myefs/memo.txt

# 스토리지클래스 및 CSI 노드 확인
kubectl get sc
kubectl get sc gp2 -o yaml | yh
kubectl get csinodes

# 노드 정보 확인
kubectl get node --label-columns=node.kubernetes.io/instance-type,eks.amazonaws.com/capacityType,topology.kubernetes.io/zone
****eksctl get iamidentitymapping --cluster myeks
****
# 노드 IP 확인 및 PrivateIP 변수 지정
N1=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2a -o jsonpath={.items[0].status.addresses[0].address})
N2=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2b -o jsonpath={.items[0].status.addresses[0].address})
N3=$(kubectl get node --label-columns=topology.kubernetes.io/zone --selector=topology.kubernetes.io/zone=ap-northeast-2c -o jsonpath={.items[0].status.addresses[0].address})
echo "export N1=$N1" >> /etc/profile
echo "export N2=$N2" >> /etc/profile
echo "export N3=$N3" >> /etc/profile
echo $N1, $N2, $N3

# 노드 보안그룹 ID 확인
NGSGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng1* --query "SecurityGroups[*].[GroupId]" --output text)
aws ec2 authorize-security-group-ingress --group-id $NGSGID --protocol '-1' --cidr 192.168.1.100/32

# 워커 노드 SSH 접속
for node in $N1 $N2 $N3; do ssh ec2-user@$node hostname; done
```

 AWS LB/ExternalDNS, kube-ops-view 설치

```bash
# AWS LB Controller
helm repo add eks https://aws.github.io/eks-charts
helm repo update
helm install aws-load-balancer-controller eks/aws-load-balancer-controller -n kube-system --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false --set serviceAccount.name=aws-load-balancer-controller

# ExternalDNS
MyDomain=<자신의 도메인>
**MyDomain=gasida.link**
MyDnzHostedZoneId=$(aws route53 list-hosted-zones-by-name --dns-name "${MyDomain}." --query "HostedZones[0].Id" --output text)
echo $MyDomain, $MyDnzHostedZoneId

curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/aews/**externaldns.yaml**
sed -i "s/0.13.4/0.14.0/g" externaldns.yaml
MyDomain=$MyDomain MyDnzHostedZoneId=$MyDnzHostedZoneId **envsubst** < **externaldns.yaml** | kubectl apply -f -

# kube-ops-view
helm repo add geek-cookbook https://geek-cookbook.github.io/charts/
helm install kube-ops-view geek-cookbook/kube-ops-view --version 1.2.2 --set env.TZ="Asia/Seoul" --namespace kube-system
kubectl patch svc -n kube-system kube-ops-view -p '{"spec":{"type":"LoadBalancer"}}'
kubectl **annotate** service kube-ops-view -n kube-system "external-dns.alpha.kubernetes.io/hostname=**kubeopsview**.$MyDomain"
echo -e "Kube Ops View URL = http://**kubeopsview**.$MyDomain:8080/#scale=1.5"

```


![구성](/Images/eks/eks_s3.png)
![구성](/Images/eks/eks_s4.png)


</details>










## 스토리지 설명 및 이번 내용
<details><summary>설명</summary>

> Pod는 삭제되거나 재생성되면 Volume이 없으면 기존에 있는 데이터들이 삭제된다.
> 삭제되지 말아야하는 데이터들을 유지하는 방법이 필요한데, 그 기술이 PV, PVC 객체를 사용하여 생성하는 방법이다.
> Worker Node에 Volume을 연결하면 해당 노드에서만 생성되어야하는 조건들이 있고, 이를 해결하는 방법과 다양한  AWS Instance 타입으로 극복하는 방법들을 알려드릴고합니다.
> 기본은 PV 생성 > PVC를 생성하여 Pod와 연동을 시키는데  PVC를 생성할 때 Storage Class을 넣게되면 PV까지 생성하게 되는데 이를 동적 프로비저닝이라 한다.

![구성](/Images/eks/eks_s14.png)

출처:  https://aws.amazon.com/ko/blogs/tech/persistent-storage-for-kubernetes/





</details>


## Kubernetes 스토지리 이해
<details><summary> 소개 </summary>
- 종류 :  emptyDir, hostPath, PV/PVC
     - emptyDir : pod 의 생명주기 (생성될 때 만들어지고 삭제될제 삭제됨 )
     - hostPath : node마다  Mount path을 걸어줘서 특정 노드에서만 동작(경로가 있어야함)
     -  PV/PVC : 마운트를 별도 오브젝트로 만들어서 관리

![구성](/Images/eks/eks_s15.png)

- 다양한 종류
    K8S 자체 제공(hostPath, local), 온프렘 솔루션(ceph 등), NFS, 클라우드 스토리지(AWS EBS 등)

    
![구성](/Images/eks/eks_s16.png)


- `동적 프로비저닝` & 볼륨 상태 , `ReclaimPolicy`

    
![구성](/Images/eks/eks_s17.png)



---

## 이번 강의에서는 AWS에서 제공하는 저장서비스들을 사용해본다.
> AWS에서 Kubernetes를 사용할때 연결할 수 있게 CSI를 제공하니 참고하여 자기 자신에게 맞는 타입을 사용하면 좋을 것 같다.


- **CSI Driver 배경** : Kubernetes source code 내부에 존재하는 AWS EBS provisioner는 당연히 Kubernetes release lifecycle을 따라서 배포되므로, provisioner 신규 기능을 사용하기 위해서는 Kubernetes version을 업그레이드해야 하는 제약 사항이 있습니다. 따라서, Kubernetes 개발자는 Kubernetes 내부에 내장된 provisioner (in-tree)를 모두 삭제하고, 별도의 controller Pod을 통해 동적 provisioning을 사용할 수 있도록 만들었습니다. 이것이 바로 CSI (Container Storage Interface) driver 입니다
- CSI 를 사용하면, K8S 의 공통화된 CSI 인터페이스를 통해 다양한 프로바이더를 사용할 수 있다.

![구성](/Images/eks/eks_s18.png)

</details>



<details><summary>AWS 관련 정보 및 생명주기 확인</summary>

- **Node-specific Volume Limits - [링크](https://kubernetes.io/docs/concepts/storage/storage-limits/)**
    - AWS EC2 Type에 따라 볼륨 최대 제한 : 25개 ~ 39개
    
    ```bash

    # 확인
    **kubectl describe node | grep Allocatable: -A1**
    Allocatable:
      **attachable-volumes-aws-ebs:  25**

    ```
    
    - `KUBE_MAX_PD_VOLS` 환경 변수의 값을 설정한 후, 스케줄러를 재시작하여 이러한 한도를 변경 가능
    
- 기본 컨테이너 환경의 **임시 파일시스템** 사용
    
    ```bash
    # 파드 배포
    # date 명령어로 현재 시간을 10초 간격으로 /home/pod-out.txt 파일에 저장
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/date-busybox-pod.yaml
    cat date-busybox-pod.yaml | yh
    **kubectl apply -f date-busybox-pod.yaml**
    
    # 파일 확인
    kubectl get pod
    **kubectl exec busybox -- tail -f /home/pod-out.txt**
    Sat Jan 28 15:33:11 UTC 2023
    Sat Jan 28 15:33:21 UTC 2023
    ...
    
    # 파드 삭제 후 다시 생성 후 파일 정보 확인 > 이전 기록이 보존되어 있는지?
    **kubectl delete pod busybox**
    **kubectl apply -f date-busybox-pod.yaml**
    **kubectl exec busybox -- tail -f /home/pod-out.txt**
    
    # 실습 완료 후 삭제
    **kubectl delete pod busybox**

    ```


    ![구성](/Images/eks/eks_s5.png)


    
    - 호스트 Path 를 사용하는 PV/PVC : **local-path-provisioner 스트리지 클래스** 배포 - [링크](https://github.com/rancher/local-path-provisioner)
    
    <aside>
    ❓ **hostPath** vs **Local Path Provisioner(StorageClass 제공)** 의 차이점과 장단점은?
    
    </aside>
    

    ```bash

    # 배포
    **curl -s -O https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml**
    ~~~~**kubectl apply -f local-path-storage.yaml**
    
    # 확인
    kubectl **get-all** -n local-path-storage
    kubectl get **pod** -n local-path-storage **-owide**
    kubectl describe cm -n local-path-storage local-path-config
    **kubectl get sc**
    **kubectl get sc local-path**
    NAME         PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION   AGE
    local-path   rancher.io/local-path   Delete          WaitForFirstConsumer   false                  34s

    ```
    
     ![구성](/Images/eks/eks_s6.png)
     ![구성](/Images/eks/eks_s7.png)


    - PV/PVC 를 사용하는 파드 생성
    
  ```bash

    # PVC 생성
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/localpath1.yaml
    cat localpath1.yaml | yh
    **kubectl apply -f localpath1.yaml**
    
    # PVC 확인
    kubectl get pvc
    kubectl describe pvc
    
    # 파드 생성
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/localpath2.yaml
    cat localpath2.yaml | yh
    **kubectl apply -f localpath2.yaml**
    
    # 파드 확인
    kubectl get pod,pv,pvc
    kubectl describe pv    # Node Affinity 확인
    **kubectl exec -it app -- tail -f /data/out.txt**
    Sun Jan 29 05:13:45 UTC 2023
    ... 
    ****
    # 워커노드 중 현재 파드가 배포되어 있다만, 아래 경로에 out.txt 파일 존재 확인
    for node in $N1 $N2 $N3; do ssh ec2-user@$node **tree /opt/local-path-provisioner**; done
    /opt/local-path-provisioner
    └── pvc-f1615862-e4cd-47d0-b89c-8d0e99270678_default_localpath-claim
        └── out.txt
    
    # 해당 워커노드 자체에서 out.txt 파일 확인 : 아래 굵은 부분은 각자 실습 환경에 따라 다름
    **ssh ec2-user@$N1** tail -f /opt/local-path-provisioner/pvc-f1615862-e4cd-47d0-b89c-8d0e99270678_default_localpath-claim/out.txt
    Sun Jan 29 05:13:45 UTC 2023
    ... 

  ```
    ![구성](/Images/eks/eks_s8.png)

    
    ![구성](/Images/eks/eks_s9.png)
    ![구성](/Images/eks/eks_s10.png)


    - 파드 삭제 후 파드 재생성해서 데이터 유지 되는지 확인
    
  ```bash

    # 파드 삭제 후 PV/PVC 확인
    **kubectl delete pod app**
    kubectl get pod,pv,pvc
    for node in $N1 $N2 $N3; do ssh ec2-user@$node **tree /opt/local-path-provisioner**; done
    
    # 파드 다시 실행
    **kubectl apply -f localpath2.yaml**
     
    # 확인
    **kubectl exec -it app -- head /data/out.txt
    kubectl exec -it app -- tail -f /data/out.txt**

  ```
    
    ![구성](/Images/eks/eks_s11.png)
    ![구성](/Images/eks/eks_s9.png)





    - 다음 실습을 위해서 파드와 PVC 삭제
    
  ```bash

    # 파드와 PVC 삭제 
    kubectl delete **pod** app
    kubectl get pv,pvc
    kubectl delete **pvc** localpath-claim
    
    # 확인
    kubectl get pv
    for node in $N1 $N2 $N3; do ssh ec2-user@$node **tree /opt/local-path-provisioner**; done

  ```
    
    - (참고) **Kubestr & sar 모니터링 및 성능 측정 확인 (NVMe SSD) - [링크](https://kubestr.io/) [Github](https://github.com/kastenhq/kubestr) [한글](https://flavono123.github.io/posts/kubestr-and-monitoring-tools/) [CloudStorage](https://www.cncf.io/blog/2021/04/05/kubernetes-storage-options-can-be-overwhelming-pick-the-right-one/)**

    - **Kubestr 이용한 성능 측정** - [링크](https://kubestr.io/) [Youtube](https://youtu.be/GJag6DwQDEA) [Blog](https://www.civo.com/learn/benchmarking-kubernetes-storage-using-kubestr) ⇒ local-path 와 NFS 등 스토리지 클래스의 **IOPS 차이**를 확인
    

  ![구성](/Images/eks/eks_s20.png)

    kubestr 측정 과정 : 그림출처 https://sogkyc.tistory.com/21




        
    
  ```bash

    # kubestr 툴 다운로드 - [Link](https://kubestr.io/)
    wget https://github.com/kastenhq/kubestr/releases/download/v0.4.41/kubestr_0.4.41_Linux_amd64.tar.gz
    tar xvfz kubestr_0.4.41_Linux_amd64.tar.gz && mv kubestr /usr/local/bin/ && chmod +x /usr/local/bin/**kubestr**
    
    # 스토리지클래스 점검
    **kubestr -h**
    **kubestr**
    
    # 모니터링
    **watch 'kubectl get pod -owide;echo;kubectl get pv,pvc'
    ssh ec2-user@$N1 iostat -xmdz 1
    ssh ec2-user@$N2 iostat -xmdz 1
    ssh ec2-user@$N3 iostat -xmdz 1**
    --------------------------------------------------------------
    # rrqm/s : 초당 드라이버 요청 대기열에 들어가 병합된 **읽기** 요청 횟수
    # wrqm/s : 초당 드라이버 요청 대기열에 들어가 병합된 **쓰기** 요청 횟수
    # r/s : 초당 디스크 장치에 요청한 **읽기** 요청 횟수
    # w/s : 초당 디스크 장치에 요청한 **쓰기** 요청 횟수
    # rMB/s : 초당 디스크 장치에서 **읽은** 메가바이트 수
    # wMB/s : 초당 디스크 장치에 **쓴** 메가바이트 수
    # await : 가장 중요한 지표, 평균 응답 시간. 드라이버 요청 대기열에서 기다린 시간과 장치의 I/O 응답시간을 모두 포함 (단위: ms)
    iostat -xmdz 1 -p xvdf
    Device:         rrqm/s   wrqm/s     **r/s**     w/s    **rMB/s**    wMB/s avgrq-sz avgqu-sz   **await** r_await w_await  svctm  **%util**
    xvdf              0.00     0.00 **2637.93**    0.00    **10.30**     0.00     8.00     6.01    **2.28**    2.28    0.00   0.33  86.21
    --------------------------------------------------------------
    
    # 측정 : Read
    **curl -s -O https://raw.githubusercontent.com/wikibook/kubepractice/main/ch10/fio-read.fio
    kubestr fio -f fio-read.fio -s local-path --size 10G**
    
    # [NVMe] 4k 디스크 블록 기준 Read 평균 IOPS는 **20309** >> 4분 정도 소요
    **kubestr fio -f fio-read.fio -s local-path --size 10G**
    PVC created kubestr-fio-pvc-ncx6p
    Pod created kubestr-fio-pod-w5cgr
    Running FIO test (fio-read.fio) on StorageClass (local-path) with a PVC of Size (10G)
    Elapsed time- 3m42.14412586s
    FIO test results:
    
    FIO version - fio-3.30
    Global options - ioengine=libaio verify= direct=1 gtod_reduce=
    
    JobName:
      blocksize= filesize= iodepth= rw=
    **read**:
      IOPS=20300.531250 BW(KiB/s)=81202
      iops: min=17304 max=71653 **avg=20309.919922**
      bw(KiB/s): min=69216 max=286612 avg=81239.710938
    
    Disk stats (read/write):
      nvme1n1: ios=2433523/10 merge=0/3 ticks=7649660/20 in_queue=7649680, util=99.958305%
      -  OK
    
    # 측정 : Write
    **curl -s -O https://raw.githubusercontent.com/wikibook/kubepractice/main/ch10/fio-write.fio**
    sed -i '/directory/d' **fio-write.fio**
    **kubestr fio -f fio-write.fio -s local-path --size 10G**
    
    # [NVMe] 4k 디스크 블록 기준 Write 평균 IOPS는 9082 >> 9분 정도 소요
    **kubestr fio -f fio-write.fio -s local-path --size 10G**
    PVC created kubestr-fio-pvc-58j52
    Pod created kubestr-fio-pod-rc9lj
    Running FIO test (fio-write.fio) on StorageClass (local-path) with a PVC of Size (10G)
    Elapsed time- 8m52.522138847s
    FIO test results:
    
    FIO version - fio-3.30
    Global options - ioengine=libaio verify= direct=1 gtod_reduce=
    
    JobName:
      blocksize= filesize= iodepth= rw=
    **write**:
      IOPS=9077.357422 BW(KiB/s)=36309
      iops: min=8292 max=14203 **avg=9082.347656**
      bw(KiB/s): min=33168 max=56822 avg=36329.429688
    
    Disk stats (read/write):
      nvme1n1: ios=0/1087555 merge=0/4 ticks=0/29941255 in_queue=29941255, util=99.965790%
      -  OK


  ```
    
  ![구성](/Images/eks/eks_s21.png)
  ![구성](/Images/eks/eks_s24.png)
  ![구성](/Images/eks/eks_s25.png)


  - AWS 스토리지 서비스 비교
    ![구성](/Images/eks/eks_s19.png)

  - **Choosing the right storage for cloud native CI/CD on Amazon Elastic Kubernetes Service**
    
    [Choosing the right storage for cloud native CI/CD on Amazon Elastic Kubernetes Service | Amazon Web Services](https://aws.amazon.com/blogs/storage/choosing-the-right-storage-for-cloud-native-ci-cd-on-amazon-elastic-kubernetes-service/)



</details>



##  AWS EBS Controller
[EKS 스터디 - 3주차 1편 - EKS가 AWS스토리지를 다루는 원리](https://malwareanalysis.tistory.com/598)

`Volume (ebs-csi-controller)` : EBS CSI driver 동작 : 볼륨 생성 및 파드에 볼륨 연결 - [링크](https://github.com/kubernetes-sigs/aws-ebs-csi-driver)

- persistentvolume, persistentvolumeclaim의 **accessModes는 ReadWriteOnce로 설정**해야 합니다 - **Why?**
- EBS스토리지 기본 설정이 **동일 AZ**에 있는 EC2 인스턴스(에 배포된 파드)에 연결해야 합니다 - Why? **파드 스케줄링 방안**은?

![구성](/Images/eks/eks_s22.png)
![https://malwareanalysis.tistory.com/598]()

https://malwareanalysis.tistory.com/598


![구성](/Images/eks/eks_s23.png)



- **설치** Amazon EBS CSI driver as an Amazon EKS add-on - [링크](https://docs.aws.amazon.com/eks/latest/userguide/managing-ebs-csi.html) [Parameters](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/blob/master/docs/parameters.md)


<details>
  <summary>펼치기</summary>
    
  ```bash

    # 아래는 **aws-ebs-csi-driver** 전체 버전 정보와 기본 설치 버전(True) 정보 확인
    **aws eks describe-addon-versions \
        --addon-name aws-ebs-csi-driver \
        --kubernetes-version 1.28 \
        --query "addons[].addonVersions[].[addonVersion, compatibilities[].defaultVersion]" \
        --output text**
    
    # ISRA 설정 : AWS관리형 정책 AmazonEBSCSIDriverPolicy 사용
    eksctl create **iamserviceaccount** \
      --name **ebs-csi-controller-sa** \
      --namespace kube-system \
      --cluster ${CLUSTER_NAME} \
      --attach-policy-arn arn:aws:iam::aws:policy/service-role/**AmazonEBSCSIDriverPolicy** \
      --approve \
      --role-only \
      --role-name **AmazonEKS_EBS_CSI_DriverRole**
    
    # ISRA 확인
    **eksctl get iamserviceaccount --cluster myeks**
    NAMESPACE	    NAME				            ROLE ARN
    kube-system 	ebs-csi-controller-sa		**arn:aws:iam::911283464785:role/AmazonEKS_EBS_CSI_DriverRole**
    ...
    
    # Amazon EBS CSI driver addon 추가
    **eksctl create addon --name aws-ebs-csi-driver --cluster ${CLUSTER_NAME} --service-account-role-arn arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole --force**
    kubectl get sa -n kube-system ebs-csi-controller-sa -o yaml | head -5
    
    # 확인
    **eksctl get addon --cluster ${CLUSTER_NAME}**
    kubectl get deploy,ds -l=app.kubernetes.io/name=aws-ebs-csi-driver -n kube-system
    kubectl get pod -n kube-system -l 'app in (ebs-csi-controller,ebs-csi-node)'
    kubectl get pod -n kube-system -l app.kubernetes.io/component=csi-driver
    
    # ebs-csi-controller 파드에 6개 컨테이너 확인
    **kubectl get pod -n kube-system -l app=ebs-csi-controller -o jsonpath='{.items[0].spec.containers[*].name}' ; echo**
    ebs-plugin csi-provisioner csi-attacher csi-snapshotter csi-resizer liveness-probe
    
    # csinodes 확인
    kubectl get csinodes
    
    # gp3 스토리지 클래스 생성 - [Link](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/blob/master/docs/parameters.md)
    kubectl get sc

    cat <<EOT > gp3-sc.yaml
    kind: **StorageClass**
    apiVersion: storage.k8s.io/v1
    metadata:
      name: gp3
    **allowVolumeExpansion: true**
    **provisioner: ebs.csi.aws.com**
    volumeBindingMode: WaitForFirstConsumer
    parameters:
      **type: gp3**
      ~~#iops: "5000"
      #throughput: "250"~~
      allowAutoIOPSPerGBIncrease: 'true'
      encrypted: 'true'
      **fsType**: **xfs** # 기본값이 ext4
    EOT
    **kubectl apply -f gp3-sc.yaml**
    kubectl get sc
    kubectl describe sc gp3 | grep Parameters
    
    **~~# 속도 테스트 >> iops, throughput 설정 시 뒤에 pvc,pod 생성이 되지 않음... 문제 해결 필요**
    kubestr fio -f fio-read.fio -s **gp3** --size 10G
    while true; do **aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true --query "Volumes[].{VolumeId: VolumeId, VolumeType: VolumeType, InstanceId: Attachments[0].InstanceId, State: Attachments[0].State}" --output text; date; sleep 1; done**~~

  ```

  ![구성](/Images/eks/eks_s26.png)
  ![구성](/Images/eks/eks_s27.png)


    - AWS EBS 스토리지 클래스 파라미터 - [링크](https://kubernetes.io/ko/docs/concepts/storage/storage-classes/#aws-ebs)


</details>

<details><summary>PVC .PV 테스트</summary>

```bash

# 워커노드의 EBS 볼륨 확인 : tag(키/값) 필터링 - [링크](https://docs.aws.amazon.com/ko_kr/cli/latest/userguide/cli-usage-filter.html)
**aws ec2 describe-volumes --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node --output table**
aws ec2 describe-volumes --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node --query "Volumes[*].Attachments" | jq
****aws ec2 describe-volumes --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node **--query "Volumes[*].{ID:VolumeId,Tag:Tags}" | jq**
aws ec2 describe-volumes --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node **--query "Volumes[].[VolumeId, VolumeType, Attachments[].[InstanceId, State][]][]" | jq**
aws ec2 describe-volumes --filters Name=tag:Name,Values=$CLUSTER_NAME-ng1-Node **--query "Volumes[].{VolumeId: VolumeId, VolumeType: VolumeType, InstanceId: Attachments[0].InstanceId, State: Attachments[0].State}" | jq**

# 워커노드에서 파드에 추가한 EBS 볼륨 확인
aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true --output table
aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true --query "Volumes[*].{ID:VolumeId,Tag:Tags}" | jq
aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true --query "Volumes[].{VolumeId: VolumeId, VolumeType: VolumeType, InstanceId: Attachments[0].InstanceId, State: Attachments[0].State}" | jq

# 워커노드에서 파드에 추가한 EBS 볼륨 모니터링
while true; do **aws ec2 describe-volumes --filters Name=tag:ebs.csi.aws.com/cluster,Values=true --query "Volumes[].{VolumeId: VolumeId, VolumeType: VolumeType, InstanceId: Attachments[0].InstanceId, State: Attachments[0].State}" --output text; date; sleep 1; done**

# PVC 생성
cat <<EOT > awsebs-pvc**.yaml**
apiVersion: v1
kind: **PersistentVolumeClaim**
metadata:
  name: **ebs-claim**
spec:
  accessModes:
    - **ReadWriteOnce**
  resources:
    requests:
      **storage: 4Gi**
  **storageClassName: gp3**
EOT
**kubectl apply -f** awsebs-pvc**.yaml**
kubectl get pvc,pv

# 파드 생성
cat <<EOT > awsebs-pod**.yaml**
apiVersion: v1
kind: Pod
metadata:
  name: **app**
spec:
  terminationGracePeriodSeconds: 3
  containers:
  - name: app
    image: centos
    command: ["/bin/sh"]
    args: ["-c", "while true; do echo **\**$(date -u) >> /data/out.txt; sleep 5; done"]
    volumeMounts:
    - name: persistent-storage
      mountPath: /data
  volumes:
  - name: persistent-storage
    **persistentVolumeClaim**:
      claimName: **ebs-claim**
EOT
**kubectl apply -f** awsebs-pod**.yaml**

# PVC, 파드 확인
kubectl get pvc,pv,pod
kubectl get **VolumeAttachment**

# 추가된 EBS 볼륨 상세 정보 확인 
aws ec2 describe-volumes --volume-ids $(kubectl get pv -o jsonpath="{.items[0].spec.csi.volumeHandle}") | jq

# PV 상세 확인 : nodeAffinity 내용의 의미는?
**kubectl get pv -o yaml | yh**
...
    **nodeAffinity**:
      required:
        nodeSelectorTerms:
        - **matchExpressions**:
          - key: topology.ebs.csi.aws.com/zone
            operator: In
            values:
            - ap-northeast-2b
...

kubectl get node --label-columns=**topology.ebs.csi.aws.com/zone**,topology.kubernetes.io/zone
kubectl describe node | more

# 파일 내용 추가 저장 확인
kubectl exec app -- tail -f /data/out.txt

# 아래 명령어는 확인까지 다소 시간이 소요됨
kubectl df-pv

## 파드 내에서 볼륨 정보 확인
kubectl exec -it app -- sh -c 'df -hT --type=overlay'
kubectl exec -it app -- sh -c 'df -hT --type=xfs'

```



  ![구성](/Images/eks/eks_s29.png)
  ![구성](/Images/eks/eks_s30.png)

- 볼륨 증가 
- [링크](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/tree/master/examples/kubernetes/resizing) ⇒ 늘릴수는 있어도 줄일수는 없단다! 
- [링크](https://kubernetes.io/blog/2018/07/12/resizing-persistent-volumes-using-kubernetes/)




```bash

# 현재 pv 의 이름을 기준하여 4G > 10G 로 증가 : .spec.resources.requests.storage의 4Gi 를 10Gi로 변경
kubectl get **pvc** ebs-claim -o jsonpath={.spec.resources.requests.storage} ; echo
kubectl get **pvc** ebs-claim -o jsonpath={.status.capacity.storage} ; echo
**kubectl patch pvc ebs-claim -p '{"spec":{"resources":{"requests":{"storage":"10Gi"}}}}'**
~~kubectl patch pvc ebs-claim -p '{"status":{"capacity":{"storage":"10Gi"}}}'~~ # status 는 바로 위 커멘드 적용 후 EBS 10Gi 확장 후 알아서 10Gi 반영됨

# 확인 : 볼륨 용량 수정 반영이 되어야 되니, 수치 반영이 조금 느릴수 있다
kubectl exec -it app -- sh -c 'df -hT --type=xfs'
**kubectl df-pv**
aws ec2 describe-volumes --volume-ids $(kubectl get pv -o jsonpath="{.items[0].spec.csi.volumeHandle}") | jq

```

  ![구성](/Images/eks/eks_s31.png)
  ![구성](/Images/eks/eks_s32.png)

- **IOPS 증가 - [Link](https://aws.amazon.com/ko/blogs/storage/simplifying-amazon-ebs-volume-migration-and-modification-using-the-ebs-csi-driver/) ← driver 버전 차이인지 현재 적용 안됨**

```bash

#
aws ec2 describe-volumes --volume-ids $(kubectl get pv -o jsonpath="{.items[0].spec.csi.volumeHandle}") | jq
kubectl annotate pvc ebs-claim ebs.csi.aws.com/iops=5000
...

#
kubectl get pvc ebs-claim -o yaml | kubectl neat | yh
aws ec2 describe-volumes --volume-ids $(kubectl get pv -o jsonpath="{.items[0].spec.csi.volumeHandle}") | jq

```

- 삭제

```bash

**kubectl delete pod app & kubectl delete pvc ebs-claim**

```


![구성](/Images/eks/eks_s34.png)
![구성](/Images/eks/eks_s35.png)
![구성](/Images/eks/eks_s36.png)

</details>






## AWS Volume SnapShots Controller

- Volumesnapshots 컨트롤러 설치 - [링크](https://github.com/kubernetes-csi/external-snapshotter) [VolumeSnapshot](https://kubernetes.io/docs/concepts/storage/volume-snapshots/) [example](https://github.com/kubernetes-sigs/aws-ebs-csi-driver/tree/master/examples/kubernetes/snapshot) [Blog](https://aws.amazon.com/blogs/containers/using-amazon-ebs-snapshots-for-persistent-storage-with-your-amazon-eks-cluster-by-leveraging-add-ons/)

<details><summary>설치/테스트/삭제</summary>



```bash

    # (참고) EBS CSI Driver에 snapshots 기능 포함 될 것으로 보임
    kubectl describe pod -n kube-system -l app=ebs-csi-controller
    
    # Install Snapshot CRDs
    curl -s -O https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshots.yaml
    curl -s -O https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshotclasses.yaml
    curl -s -O https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/client/config/crd/snapshot.storage.k8s.io_volumesnapshotcontents.yaml
    kubectl apply -f snapshot.storage.k8s.io_volumesnapshots.yaml,snapshot.storage.k8s.io_volumesnapshotclasses.yaml,snapshot.storage.k8s.io_volumesnapshotcontents.yaml
    kubectl get crd | grep snapshot
    kubectl api-resources  | grep snapshot
    
    # Install Common Snapshot Controller
    curl -s -O https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/deploy/kubernetes/snapshot-controller/rbac-snapshot-controller.yaml
    curl -s -O https://raw.githubusercontent.com/kubernetes-csi/external-snapshotter/master/deploy/kubernetes/snapshot-controller/setup-snapshot-controller.yaml
    kubectl apply -f rbac-snapshot-controller.yaml,setup-snapshot-controller.yaml
    kubectl get deploy -n kube-system snapshot-controller
    kubectl get pod -n kube-system -l app=snapshot-controller
    
    # Install Snapshotclass
    curl -s -O https://raw.githubusercontent.com/kubernetes-sigs/aws-ebs-csi-driver/master/examples/kubernetes/snapshot/manifests/classes/snapshotclass.yaml
    kubectl apply -f snapshotclass.yaml
    kubectl get vsclass # 혹은 volumesnapshotclasses

```

![구성](/Images/eks/eks_s33.png)
![구성](/Images/eks/eks_s37.png)
![구성](/Images/eks/eks_s38.png)


- 테스트 PVC/파드 생성

```bash

# PVC 생성
**kubectl apply -f** awsebs-pvc**.yaml**

# 파드 생성
**kubectl apply -f** awsebs-pod**.yaml**

# 파일 내용 추가 저장 확인
kubectl exec app -- tail -f /data/out.txt

# VolumeSnapshot 생성 : Create a VolumeSnapshot referencing the PersistentVolumeClaim name >> EBS 스냅샷 확인
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/ebs-volume-snapshot.yaml
cat ebs-volume-snapshot.yaml | yh
**kubectl apply -f ebs-volume-snapshot.yaml**

# VolumeSnapshot 확인
**kubectl get volumesnapshot**
**kubectl get volumesnapshot ebs-volume-snapshot -o jsonpath={.status.boundVolumeSnapshotContentName} ; echo**
kubectl describe volumesnapshot.snapshot.storage.k8s.io ebs-volume-snapshot
**kubectl get volumesnapshotcontents**

# VolumeSnapshot ID 확인 
**kubectl get volumesnapshotcontents -o jsonpath='{.items[*].status.snapshotHandle}' ; echo**

# AWS EBS 스냅샷 확인
aws ec2 describe-snapshots --owner-ids self | jq
aws ec2 describe-snapshots --owner-ids self --query 'Snapshots[]' --output table

# app & pvc 제거 : 강제로 장애 재현
**kubectl delete pod app && kubectl delete pvc ebs-claim**

```

![구성](/Images/eks/eks_s39.png)



- 스냅샷으로 복원

```bash

# 스냅샷에서 PVC 로 복원
kubectl get pvc,pv
cat <<EOT > ebs-snapshot-restored-claim.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ebs-snapshot-restored-claim
spec:
  **storageClassName: gp3**
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 4Gi
  **dataSource:**
    name: **ebs-volume-snapshot**
    kind: **VolumeSnapshot**
    apiGroup: snapshot.storage.k8s.io
EOT
cat ebs-snapshot-restored-claim.yaml | yh
**kubectl apply -f ebs-snapshot-restored-claim.yaml**

# 확인
kubectl get pvc,pv

# 파드 생성
curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/3/ebs-snapshot-restored-pod.yaml
cat ebs-snapshot-restored-pod.yaml | yh
**kubectl apply -f ebs-snapshot-restored-pod.yaml**

# 파일 내용 저장 확인 : 파드 삭제 전까지의 저장 기록이 남아 있다. 이후 파드 재생성 후 기록도 잘 저장되고 있다
**kubectl exec app -- cat /data/out.txt**
...
Sat Dec 24 15:12:24 UTC 2022
Sat Dec 24 15:12:24 UTC 2022
Sat Dec 24 15:24:23 UTC 2022
Sat Dec 24 15:24:23 UTC 2022
...

# 삭제
kubectl delete pod app && kubectl delete pvc ebs-snapshot-restored-claim && kubectl delete volumesnapshots ebs-volume-snapshot

```

- (참고) **볼륨 snapscheduler** (정기적인 반복 스냅샷 생성)에 대해서 정리해주셨습니다
    
    [EKS에서 볼륨 snapscheduler 설치하기](https://popappend.tistory.com/113)
    
    [Kube snapshot scheduler](https://jerryljh.tistory.com/42)
    
    [Documentation](https://backube.github.io/snapscheduler/)


</details>






##  AWS EFS Controller
> 현재는 Addon을 통해 설치가 가능하나 이번 실습은 수동으로 설치
> 현재는 EFS Addon 설치 가능 → https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html


- 현재는 EFS Addon 설치 가능 → https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html
![구성](/Images/eks/eks_s53.png)

- 구성 아키텍처
![구성](/Images/eks/eks_s54.png)


<details><summary>설치 확인</summary>

arn을 에 account_id를 적는데 ec2>보안에 값을 넣는다.

~~~bash

# EFS 정보 확인 
aws efs describe-file-systems --query "FileSystems[*].FileSystemId" --output text

# IAM 정책 생성
curl -s -O https://raw.githubusercontent.com/kubernetes-sigs/aws-efs-csi-driver/master/docs/iam-policy-example.json
aws iam create-policy --policy-name AmazonEKS_EFS_CSI_Driver_Policy --policy-document file://iam-policy-example.json

# ISRA 설정 : 고객관리형 정책 AmazonEKS_EFS_CSI_Driver_Policy 사용
eksctl create iamserviceaccount \
  --name efs-csi-controller-sa \
  --namespace kube-system \
  --cluster ${CLUSTER_NAME} \
  --attach-policy-arn arn:aws:iam::${ACCOUNT_ID}:policy/AmazonEKS_EFS_CSI_Driver_Policy \
  --approve

# ISRA 확인
kubectl get sa -n kube-system efs-csi-controller-sa -o yaml | head -5
eksctl get iamserviceaccount --cluster myeks

# EFS Controller 설치
helm repo add aws-efs-csi-driver https://kubernetes-sigs.github.io/aws-efs-csi-driver/
helm repo update
helm upgrade -i aws-efs-csi-driver aws-efs-csi-driver/aws-efs-csi-driver \
    --namespace kube-system \
    --set image.repository=602401143452.dkr.ecr.${AWS_DEFAULT_REGION}.amazonaws.com/eks/aws-efs-csi-driver \
    --set controller.serviceAccount.create=false \
    --set controller.serviceAccount.name=efs-csi-controller-sa

# 확인
helm list -n kube-system
kubectl get pod -n kube-system -l "app.kubernetes.io/name=aws-efs-csi-driver,app.kubernetes.io/instance=aws-efs-csi-driver"

~~~


### EFS 파일시스템을 다수의 파드가 사용하게 설정 : Add empty StorageClasses from static example - Workshop 링크


```bash

# 모니터링
watch 'kubectl get sc efs-sc; echo; kubectl get pv,pvc,pod'

# 실습 코드 clone
git clone https://github.com/kubernetes-sigs/aws-efs-csi-driver.git /root/efs-csi
cd /root/efs-csi/examples/kubernetes/multiple_pods/specs && tree

# EFS 스토리지클래스 생성 및 확인
cat storageclass.yaml | yh
kubectl apply -f storageclass.yaml
kubectl get sc efs-sc

# PV 생성 및 확인 : volumeHandle을 자신의 EFS 파일시스템ID로 변경
**EfsFsId=**$(aws efs describe-file-systems --query "FileSystems[*].FileSystemId" --output text)
sed -i "s/**fs-4af69aab**/**$EfsFsId**/g" pv.yaml

**cat pv.yaml | yh**
apiVersion: v1
kind: PersistentVolume
metadata:
  name: efs-pv
spec:
  capacity:
    **storage: 5Gi**
  volumeMode: **Filesystem**
  accessModes:
    - **ReadWriteMany**
  persistentVolumeReclaimPolicy: Retain
  storageClassName: **efs-sc**
  csi:
    driver: efs.csi.aws.com
    volumeHandle: **fs-05699d3c12ef609e2**

**kubectl apply -f pv.yaml**
kubectl get pv; kubectl describe pv

# PVC 생성 및 확인
cat claim.yaml | yh
**kubectl apply -f claim.yaml**
**kubectl get pvc**

# 파드 생성 및 연동 : 파드 내에 /data 데이터는 EFS를 사용
cat pod1.yaml pod2.yaml | yh
**kubectl apply -f pod1.yaml,pod2.yaml**
kubectl df-pv

# 파드 정보 확인 : **PV에 5Gi 와 파드 내에서 확인한 NFS4 볼륨 크리 8.0E의 차이는 무엇? 파드에 6Gi 이상 저장 가능한가?**
kubectl get pods
**kubectl exec -ti app1 -- sh -c "df -hT -t nfs4"**
**kubectl exec -ti app2 -- sh -c "df -hT -t nfs4"**
Filesystem           Type            Size      Used Available Use% Mounted on
**127.0.0.1:/          nfs4            8.0E         0      8.0E   0% /data**

# 공유 저장소 저장 동작 확인
**tree /mnt/myefs**              # 작업용EC2에서 확인
tail -f /mnt/myefs/out1.txt  # 작업용EC2에서 확인
**kubectl exec -ti app1 -- tail -f /data/out1.txt
kubectl exec -ti app2 -- tail -f /data/out2.txt**

```

- 실습 완료 후 삭제

```bash

# 쿠버네티스 리소스 삭제
kubectl delete pod app1 app2
kubectl delete pvc efs-claim && kubectl delete pv efs-pv && kubectl delete sc efs-sc

```

![구성](/Images/eks/eks_s40.png)
![구성](/Images/eks/eks_s41.png)


- 삭제 
~~~bash

# 쿠버네티스 리소스 삭제
kubectl delete -f pod.yaml
kubectl delete -f storageclass.yaml

~~~

</details>


## Mountpoint for Amazon S3 CSI driver
- 참조
  - https://docs.aws.amazon.com/eks/latest/userguide/s3-csi.html
  - https://github.com/awslabs/mountpoint-s3/blob/main/doc/CONFIGURATION.md
  - https://github.com/awslabs/mountpoint-s3-csi-driver/blob/main/examples/kubernetes/  - static_provisioning/README.md



## EKS Persistent Volumes for Instance Store & Add NodeGroup
- 신규 노드 그룹 ng2 생성 - [Blog](https://aws.amazon.com/ko/blogs/containers/eks-persistent-volumes-for-instance-store/) : **c5d.large** 의 EC2 **인스턴스** 스토어(**임시** 블록 스토리지) 설정 작업 - [링크](https://docs.aws.amazon.com/ko_kr/AWSEC2/latest/UserGuide/InstanceStorage.html) , NVMe SSD - [링크](https://docs.aws.amazon.com/ko_kr/AWSEC2/latest/UserGuide/ssd-instance-store.html)
    - **데이터 손실** : 기본 디스크 드라이브 오류, 인스턴스가 **중지**됨, 인스턴스가 **최대 절전 모드**로 전환됨, 인스턴스가 **종료**됨
    

    
    - 인스턴스 스토어는 EC2 스토리지(EBS) 정보에 출력되지는 않는다


<details><summary>실습/ 테스트/ 삭제</summary>

  ```bash

    # 인스턴스 스토어 볼륨이 있는 c5 모든 타입의 스토리지 크기
    **aws ec2 describe-instance-types \
     --filters "Name=instance-type,Values=c5*" "Name=instance-storage-supported,Values=true" \
     --query "InstanceTypes[].[InstanceType, InstanceStorageInfo.TotalSizeInGB]" \
     --output table**
    --------------------------
    |  DescribeInstanceTypes |
    +---------------+--------+
    |  **c5d.large**    |  **50**    |
    |  c5d.12xlarge |  1800  |
    ...
    
    # 신규 노드 그룹 생성
    eksctl create nodegroup --help
    eksctl create nodegroup -c $CLUSTER_NAME -r $AWS_DEFAULT_REGION --subnet-ids "$PubSubnet1","$PubSubnet2","$PubSubnet3" --ssh-access \
      -n ng2 -t c5d.large -N 1 -m 1 -M 1 --node-volume-size=30 --node-labels **disk=nvme** **--max-pods-per-node 100** --dry-run > myng2.yaml
    
    cat <<EOT > nvme.yaml
      **preBootstrapCommands**:
        - |
          # Install Tools
          yum install nvme-cli links tree jq tcpdump sysstat -y
    
          # Filesystem & Mount
          mkfs -t xfs /dev/nvme1n1
          mkdir /data
          mount /dev/nvme1n1 /data
    
          # Get disk UUID
          uuid=\$(blkid -o value -s UUID mount /dev/nvme1n1 /data) 
    
          # Mount the disk during a reboot
          echo /dev/nvme1n1 /data xfs defaults,noatime 0 2 >> /etc/fstab
    EOT
    sed -i -n -e '/volumeType/r nvme.yaml' -e '1,$p' myng2.yaml
    **eksctl create nodegroup -f myng2.yaml**
    
    # 노드 보안그룹 ID 확인
    NG2SGID=$(aws ec2 describe-security-groups --filters Name=group-name,Values=*ng2* --query "SecurityGroups[*].[GroupId]" --output text)
    aws ec2 authorize-security-group-ingress --group-id $NG2SGID --protocol '-1' --cidr 192.168.1.100/32
    
    # 워커 노드 SSH 접속
    N4=<각자 자신의 워커 노드4번 Private IP 지정>
    N4=192.168.3.160
    ssh ec2-user@$N4 hostname
    
    # 확인
    ssh ec2-user@$N4 sudo **nvme list**
    ssh ec2-user@$N4 sudo **lsblk -e 7 -d**
    ssh ec2-user@$N4 sudo df -hT -t xfs
    ssh ec2-user@$N4 sudo tree /data
    ssh ec2-user@$N4 sudo cat /etc/fstab
    
    # (옵션) max-pod 확인
    **kubectl describe node -l disk=nvme | grep Allocatable: -A7**
    Allocatable:
      attachable-volumes-aws-ebs:  25
      cpu:                         1930m
      ephemeral-storage:           27905944324
      hugepages-1Gi:               0
      hugepages-2Mi:               0
      memory:                      3097552Ki
      **pods:                        100**
    
    # (옵션) kubelet 데몬 파라미터 확인 : -~~-max-pods=29~~ **--max-pods=100**
    **ssh ec2-user@$N4 sudo ps -ef | grep kubelet**
    root      2972     1  0 16:03 ?        00:00:09 /usr/bin/kubelet --config /etc/kubernetes/kubelet/kubelet-config.json --kubeconfig /var/lib/kubelet/kubeconfig --container-runtime-endpoint unix:///run/containerd/containerd.sock --image-credential-provider-config /etc/eks/image-credential-provider/config.json --image-credential-provider-bin-dir /etc/eks/image-credential-provider --node-ip=192.168.3.131 --pod-infra-container-image=602401143452.dkr.ecr.ap-northeast-2.amazonaws.com/eks/pause:3.5 --v=2 --cloud-provider=aws --container-runtime=remote --node-labels=eks.amazonaws.com/sourceLaunchTemplateVersion=1,alpha.eksctl.io/cluster-name=myeks,alpha.eksctl.io/nodegroup-name=ng2,disk=nvme,eks.amazonaws.com/nodegroup-image=ami-0da378ed846e950a4,eks.amazonaws.com/capacityType=ON_DEMAND,eks.amazonaws.com/nodegroup=ng2,eks.amazonaws.com/sourceLaunchTemplateId=lt-030e6043923ce712b --max-pods=29 --max-pods=100

  ```
    
  - 스토리지 클래스 재생성
    
  ```bash

    # 기존 삭제
    #curl -s -O https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
    cd
    kubectl delete -f local-path-storage.yaml
    
    #
    sed -i 's/opt/data/g' local-path-storage.yaml
    kubectl apply -f local-path-storage.yaml
    
    # 모니터링
    **watch 'kubectl get pod -owide;echo;kubectl get pv,pvc'
    ssh ec2-user@$N4 iostat -xmdz 1 -p nvme1n1**
    
    # 측정 : Read
    #curl -s -O https://raw.githubusercontent.com/wikibook/kubepractice/main/ch10/fio-read.fio
    **kubestr fio -f fio-read.fio -s local-path --size 10G --nodeselector disk=nvme
    ...**

  ```
    
  - 삭제
    
  ```bash

    # 
    kubectl delete -f local-path-storage.yaml
    
    # 노드그룹 삭제
    **eksctl delete nodegroup -c $CLUSTER_NAME -n ng2**

  ```
![구성](/Images/eks/eks_s42.png)
![구성](/Images/eks/eks_s43.png)
![구성](/Images/eks/eks_s44.png)
![구성](/Images/eks/eks_s45.png)
![구성](/Images/eks/eks_s46.png)
![구성](/Images/eks/eks_s47.png)

</details>










## 노드 그룹

[1년 동안 Workload의 절반을 ARM64로 Migration하기](https://hyperconnect.github.io/2023/07/25/migrate-half-of-workload-in-a-year.html)


- **Graviton (ARM) Instance 노드그룹** - [Link](https://www.eksworkshop.com/docs/fundamentals/managed-node-groups/graviton/)
    
![구성](/Images/eks/eks_s55.png)






<details><summary>arm 실습</summary>
    

```bash

    #
    kubectl get nodes -L kubernetes.io/arch
    
    # 신규 노드 그룹 생성
    eksctl create nodegroup --help
    eksctl create nodegroup -c $CLUSTER_NAME -r $AWS_DEFAULT_REGION --subnet-ids "$PubSubnet1","$PubSubnet2","$PubSubnet3" --ssh-access \
      -n **ng3** -t t4g.medium -N 1 -m 1 -M 1 --node-volume-size=30 --node-labels family**=graviton** --dry-run > myng3.yaml
    **eksctl create nodegroup -f myng3.yaml**
    
    # 확인
    **kubectl get nodes --label-columns eks.amazonaws.com/nodegroup,kubernetes.io/arch**
    **kubectl describe nodes --selector family=graviton**
    aws eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name ng3 | jq .nodegroup.taints
    
    # taints 셋팅 -> 적용에 2~3분 정도 시간 소요
    aws eks update-nodegroup-config --cluster-name $CLUSTER_NAME --nodegroup-name **ng3** --taints "addOrUpdateTaints=[{key=frontend, value=true, effect=**NO_EXECUTE**}]"
    
    # 확인
    **kubectl describe nodes --selector family=graviton | grep Taints
    aws eks describe-nodegroup --cluster-name $CLUSTER_NAME --nodegroup-name ng3 | jq .nodegroup.taints**
    # NO_SCHEDULE - This corresponds to the Kubernetes NoSchedule taint effect. This configures the managed node group with a taint that repels all pods that don't have a matching toleration. All running pods are not evicted from the manage node group's nodes.
    # NO_EXECUTE - This corresponds to the Kubernetes NoExecute taint effect. Allows nodes configured with this taint to not only repel newly scheduled pods but also evicts any running pods without a matching toleration.
    # PREFER_NO_SCHEDULE - This corresponds to the Kubernetes PreferNoSchedule taint effect. If possible, EKS avoids scheduling Pods that do not tolerate this taint onto the node.

```
    
- Run pods on Graviton
    
```bash

    #
    cat << EOT > busybox.yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: busybox
    spec:
      terminationGracePeriodSeconds: 3
      containers:
      - name: busybox
        image: busybox
        command:
        - "/bin/sh"
        - "-c"
        - "while true; do date >> /home/pod-out.txt; cd /home; sync; sync; sleep 10; done"
      **tolerations:
        - effect: NoExecute
          key: frontend
          operator: Exists**
    EOT
    kubectl apply -f busybox.yaml
    
    # 파드가 배포된 노드 정보 확인
    kubectl get pod -owide
    
    # 삭제
    kubectl delete pod busybox
    **eksctl delete nodegroup -c $CLUSTER_NAME -n ng3**

```

![구성](/Images/eks/eks_s48.png)
![구성](/Images/eks/eks_s49.png)



[Workshop Studio](https://catalog.us-east-1.prod.workshops.aws/workshops/c4ab40ed-0299-4a4e-8987-35d90ba5085e/en-US/060-graviton)

</details>




<details><summary>Spot Instance 실습</summary>





- **Spot instances** 



- 자료

  [Link](https://www.eksworkshop.com/docs/fundamentals/managed-node-groups/spot/) [Blog](https://aws.amazon.com/ko/blogs/containers/amazon-eks-now-supports-provisioning-and-managing-ec2-spot-instances-in-managed-node-groups/)
    - **Instance type diversification** - [Link](https://github.com/aws/amazon-ec2-instance-selector)
    
    ```bash

    # ec2-instance-selector 설치
    curl -Lo ec2-instance-selector https://github.com/aws/amazon-ec2-instance-selector/releases/download/v2.4.1/ec2-instance-selector-`uname | tr '[:upper:]' '[:lower:]'`-amd64 && chmod +x ec2-instance-selector
    mv ec2-instance-selector /usr/local/bin/
    ec2-instance-selector --version
    
    # 사용
    **ec2-instance-selector --vcpus 2 --memory 4 --gpus 0 --current-generation -a x86_64 --deny-list 't.*' --output table-wide**
    Instance Type  VCPUs   Mem (GiB)  Hypervisor  Current Gen  Hibernation Support  CPU Arch  Network Performance  ENIs    GPUs    GPU Mem (GiB)  GPU Info  On-Demand Price/Hr  **Spot Price/Hr (30d avg)**  
    -------------  -----   ---------  ----------  -----------  -------------------  --------  -------------------  ----    ----    -------------  --------  ------------------  -----------------------  
    c5.large       2       4          nitro       true         true                 x86_64    Up to 10 Gigabit     3       0       0              none      $0.096              $0.04574                 
    c5a.large      2       4          nitro       true         false                x86_64    Up to 10 Gigabit     3       0       0              none      $0.086              $0.02859                 
    c5d.large      2       4          nitro       true         true                 x86_64    Up to 10 Gigabit     3       0       0              none      $0.11               $0.03266                 
    c6i.large      2       4          nitro       true         true                 x86_64    Up to 12.5 Gigabit   3       0       0              none      $0.096              $0.04011                 
    c6id.large     2       4          nitro       true         true                 x86_64    Up to 12.5 Gigabit   3       0       0              none      $0.1155             $0.02726                 
    c6in.large     2       4          nitro       true         false                x86_64    Up to 25 Gigabit     3       0       0              none      $0.1281             $0.0278                  
    c7i.large      2       4          nitro       true         true                 x86_64    Up to 12.5 Gigabit   3       0       0              none      $0.1008             $0.02677
    
    #Internally ec2-instance-selector is making calls to the **DescribeInstanceTypes** for the specific region and filtering the instances based on the criteria selected in the command line, in our case we filtered for instances that meet the following criteria:
    - Instances with no GPUs
    - of x86_64 Architecture (no ARM instances like A1 or m6g instances for example)
    - Instances that have 2 vCPUs and 4 GB of RAM
    - Instances of current generation (4th gen onwards)
    - Instances that don’t meet the regular expression t.* to filter out burstable instance types

    ```
    
    - **Create spot capacity** - [Link](https://www.eksworkshop.com/docs/fundamentals/managed-node-groups/spot/create-spot-capacity)
    
    ![구성](/Images/eks/eks_s56.png)

    ```bash
    
    #
    kubectl get nodes -l eks.amazonaws.com/capacityType=ON_DEMAND
    **kubectl get nodes -L eks.amazonaws.com/capacityType**
    NAME                                              STATUS   ROLES    AGE   VERSION               CAPACITYTYPE
    ip-192-168-1-65.ap-northeast-2.compute.internal   Ready    <none>   75m   v1.28.5-eks-5e0fdde   ON_DEMAND
    ip-192-168-2-89.ap-northeast-2.compute.internal   Ready    <none>   75m   v1.28.5-eks-5e0fdde   ON_DEMAND
    ip-192-168-3-39.ap-northeast-2.compute.internal   Ready    <none>   75m   v1.28.5-eks-5e0fdde   ON_DEMAND
    
    # 생성 : 아래 node-role 은 각자 자신의 노드롤 ARN을 입력하자
    # role AWSServiceRoleForAmazonEKSNodegroup 테스트해보자
    aws eks create-nodegroup \
      --cluster-name $CLUSTER_NAME \
      --nodegroup-name **managed-spot** \
      --subnets $PubSubnet1 $PubSubnet2 $PubSubnet3 \
      --node-role ***arn:aws:iam::911283464785:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-wvZ2FX2m79Vv*** \
      --instance-types c5.large c5d.large c5a.large \
      --capacity-type **SPOT** \
      --scaling-config minSize=2,maxSize=3,desiredSize=2 \
      --disk-size 20
    
    aws eks create-nodegroup \
      --cluster-name $CLUSTER_NAME \
      --nodegroup-name **managed-spot** \
      --subnets $PubSubnet1 $PubSubnet2 $PubSubnet3 \
      --node-role **arn:aws:iam::911283464785:role/eksctl-myeks-nodegroup-ng1-NodeInstanceRole-Bf5LiwkL64gF** \
      --instance-types c5.large c5d.large c5a.large \
      --capacity-type **SPOT** \
      --scaling-config minSize=2,maxSize=3,desiredSize=2 \
      --disk-size 20
    
    #
    aws eks wait nodegroup-active --cluster-name $CLUSTER_NAME --nodegroup-name managed-spot
    
    # 확인
    **kubectl get nodes -L eks.amazonaws.com/capacityType,eks.amazonaws.com/nodegroup**
    NAME                                               STATUS   ROLES    AGE   VERSION               CAPACITYTYPE   NODEGROUP
    ip-192-168-1-38.ap-northeast-2.compute.internal    Ready    <none>   37s   v1.28.5-eks-5e0fdde   SPOT           managed-spot
    ip-192-168-1-65.ap-northeast-2.compute.internal    Ready    <none>   93m   v1.28.5-eks-5e0fdde   ON_DEMAND      ng1
    ip-192-168-2-104.ap-northeast-2.compute.internal   Ready    <none>   37s   v1.28.5-eks-5e0fdde   SPOT           managed-spot
    ip-192-168-2-89.ap-northeast-2.compute.internal    Ready    <none>   93m   v1.28.5-eks-5e0fdde   ON_DEMAND      ng1
    ip-192-168-3-39.ap-northeast-2.compute.internal    Ready    <none>   93m   v1.28.5-eks-5e0fdde   ON_DEMAND      ng1
    ```
    
    - **Running a workload on Spot**
    
    ```bash
    #
    cat << EOT > busybox.yaml
    apiVersion: v1
    kind: Pod
    metadata:
      name: busybox
    spec:
      terminationGracePeriodSeconds: 3
      containers:
      - name: busybox
        image: busybox
        command:
        - "/bin/sh"
        - "-c"
        - "while true; do date >> /home/pod-out.txt; cd /home; sync; sync; sleep 10; done"
      **nodeSelector:
        eks.amazonaws.com/capacityType: SPOT**
    EOT
    kubectl apply -f busybox.yaml
    
    # 파드가 배포된 노드 정보 확인
    kubectl get pod -owide
    
    # 삭제
    kubectl delete pod busybox
    **eksctl delete nodegroup -c $CLUSTER_NAME -n managed-spot**
    ```
    

![구성](/Images/eks/eks_s50.png)
![구성](/Images/eks/eks_s51.png)





</details>


## Fargate 

- 설치 링크 :
  - https://www.eksworkshop.com/docs/fundamentals/fargate/
  - [https://velog.io/@jhyoo9727/EKS-Fargate-간단-설치](https://velog.io/@jhyoo9727/EKS-Fargate-%EA%B0%84%EB%8B%A8-%EC%84%A4%EC%B9%98)

   -  [[1주차] Amazon EKS 시작하기 - Nodes - Fargate](https://kschoi728.tistory.com/86)

  -   [AEWS) Amzaon EKS 설치 및 기본 사용 - Log on Me](https://logonme.net/tech/aews_w1/)

<details><summary>Fargate 관련 링크 및 설명</summary>

[**리눅서**]님 : EKS Nodeless 1편~8편 - [링크](https://linuxer.name/?s=nodeless)


[**xgro**]님 : Nodeless Concept - [링크](https://velog.io/@xgro/eksNodeless)
![image.gif](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/9ec6dbce-68ea-4258-aae1-d86ee1217361/image.gif)


- EKS(컨트롤 플레인) + Fargate(데이터 플레인)의 완전한 서버리스화(=AWS **관리형**)
    - Cluster Autoscaler 불필요, VM 수준의 격리 가능(VM isolation at Pod Level)

![구성](/Images/eks/eks_s57.png)

- 파게이트 프로파일(파드가 사용할 서브넷, 네임스페이스, 레이블 조건)을 생성하여 지정한 파드가 파게이트에서 동작하게 함

![구성](/Images/eks/eks_s58.png)

- EKS 는 스케줄러가 특정 조건을 기준으로 어느 노드에 파드를 동작시킬지 결정, 혹은 특정 설정으로 특정 노드에 파드가 동작하게 가능함

![구성](/Images/eks/eks_s59.png)

- Data Plane

![구성](/Images/eks/eks_s560.png)


</details>



###  Fargate 실습

- 프라이빗 서브넷에서 NATGW 생성 및 라우팅 정보를 CloudFormation 으로 추가한다
- Fargate profile 생성하여 파드를 생성 후 확인해보자!


<details>
<summary>실습</summary>

- **~~프라이빗 서브넷에서 NATGW 생성 및 라우팅 정보 추가 설정 → NATGW 는 자체 시간당 비용과 tx/rx 트래픽 비용 부과가 되니 실습 후 째빠르게 삭제하자!~~**
    
    ```bash
    # 변수 지정
    PrivateSubnetRouteTable=$(aws ec2 describe-route-tables --filters Name=tag:Name,Values=$CLUSTER_NAME-PrivateSubnetRouteTable --query 'RouteTables[0].RouteTableId' --output text)
    
    # NATGW 생성, Private 라우팅 정보 추가
    curl -s -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/natgw.yaml
    sed -i "s/<PublicSubnet1>/$PrivateSubnet1/g" natgw.yaml
    sed -i "s/<PrivateSubnetRouteTable>/$PrivateSubnetRouteTable/g" natgw.yaml
    cat natgw.yaml | yh
    aws cloudformation deploy --template-file natgw.yaml --stack-name $CLUSTER_NAME-natgw
    ```
    
    - 확인 : NATGW, PrivateSubnetRouteTable에 라우팅 추가 확인
    
- **~~Fargate profile 생성~~**
    - 클러스터에 Fargate로 pod를 배포하기 위해서는 pod가 실행될 때 사용하는 하나 이상의 fargate profile을 정의해야 합니다.
    - 즉, fargate profile이란 fargate로 pod를 생성하기 위한 **조건을 명시해놓은 프로파일**이라고 보시면 됩니다.
    - 파드가 동작한 **Private 서브넷**이 필요, Private 서브넷에서 **외부 통신을 위한 NAT GW** 배치 후 연결.
    
    ```bash
    #
    cat << EOT > fagatepolicy.json
    {
      "Version": "2012-10-17",
      "Statement": [
        {
          "Effect": "Allow",
          "Condition": {
             "ArnLike": {
                "aws:SourceArn": "arn:aws:eks:$AWS_DEFAULT_REGION:$ACCOUNT_ID:fargateprofile/$CLUSTER_NAME/*"
             }
          },
          "Principal": {
            "Service": "eks-fargate-pods.amazonaws.com"
          },
          "Action": "sts:AssumeRole"
        }
      ]
    }
    EOT
    
    # arn:aws:iam::911283464785:role/AmazonEKSFargatePodExecutionRole
    aws iam create-role --role-name AmazonEKSFargatePodExecutionRole --assume-role-policy-document file://"fagatepolicy.json"
    aws iam attach-role-policy --policy-arn arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy --role-name **AmazonEKSFargatePodExecutionRole**
    ```
    
    - **AWS EKS 관리 콘솔 → 컴퓨팅 → Fargate 프로파일 추가 : 웹 콘솔에서 생성**
        - 이름 : myfargate
        - 포드 실행 역할 : AmazonEKSFargatePodExecutionRole
        - 서브넷 : PrivateSubnet1~3 선택
        - 태그 : Name / myeks-fargate
        - 네임스페이스 : default(레이블 일치 fargate : yes) , kube-system
    
    ```bash
    # Get list of Fargate Profiles in a cluster
    eksctl get fargateprofile --cluster $CLUSTER_NAME
    eksctl get fargateprofile --cluster $CLUSTER_NAME -o json | jq
    
    #
    aws eks create-fargate-profile \
        --fargate-profile-name coredns \
        --cluster-name my-cluster \
        --pod-execution-role-arn arn:aws:iam::111122223333:role/AmazonEKSFargatePodExecutionRole \
        --selectors namespace=kube-system,labels={k8s-app=kube-dns} \
        --subnets subnet-0000000000000001 subnet-0000000000000002 subnet-0000000000000003
    
    #
    kubectl patch deployment coredns \
        -n kube-system \
        --type json \
        -p='[{"op": "remove", "path": "/spec/template/metadata/annotations/eks.amazonaws.com~1compute-type"}]'
    
    # eksctl-host 에서 파게이트에 생성된 파드들과 접속 가능하게 보안그룹 설정 룰(rule) 추가
    EKSSGID=$(aws eks describe-cluster --name $CLUSTER_NAME --query cluster.resourcesVpcConfig.clusterSecurityGroupId --output text)
    aws ec2 authorize-security-group-ingress --group-id $EKSSGID --protocol '-1' --cidr 192.168.1.100/32
    ```
    
- **~~Fargate로 샘플 pod 배포하기~~**
    
    ```bash
    # 모니터링
    watch -d kubectl get node,pod
    
    # 디플로이먼트 생성
    curl -s -O https://raw.githubusercontent.com/gasida/PKOS/main/2/nginx-dp.yaml
    vim nginx-dp.yaml
    ---
    template:
        metadata:
          labels:
            app: nginx
            **fargate: yes**
    ...
    ---
    **kubectl apply -f nginx-dp.yaml**
    
    # 샘플 nginx 디플로이먼트 배포
    # We will deploy an sample nginx application as a ReplicaSet of 1 Pod
    cat <<EoF> nginx.yaml
    apiVersion: apps/v1
    kind: Deployment
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
            **node: fargate**
        spec:
          containers:
          - image: nginx
            name: nginx-to-scaleout
            resources:
              limits:
                cpu: 500m
                memory: 512Mi
              requests:
                cpu: 500m
                memory: 512Mi
    EoF
    
    # 확인: 노드, 파드 상세 정보 화인 >> **아니? 파게이트 노드의 IP와 파드의 IP가 똑같다? 어떻게 이런일이?**
    kubectl apply -f nginx.yaml  # 파드 배포 실행 후 2~3분 정도 시간 소요
    kubectl get deployment
    kubectl get node
    kubectl get node -l eks.amazonaws.com/compute-type=fargate -o wide  # AWS 웹콘솔에서 - EC2 갯수 확인 시 추가된 EC2 인스턴스가 없다!
    kubectl get pod -owide
    FpPod1=$(kubectl get pod -oname | cut -d "/" -f 2)
    kubectl describe pod $FpPod1  # 파드 상세 정보 화인
    
    # (옵션) nginx 파드 Shell 접속 후 외부(인터넷) 통신 확인
    kubectl exec -it $FpPod1 -- curl ipinfo.io/ip  # 출력되는 IP는 어떤 리소스일까요? 맞추어보세요!
    kubectl exec -it $FpPod1 -- curl www.google.com
    
    # Scale our ReplicaSet
    # Let’s scale out the replicaset to 10
    # 파게이트 사용 시 데이터 플레인 용량 관리에서 해방되므로 Cloud AutoScaler 를 고려하지 않아도 된다!
    kubectl scale --replicas=10 deployment/nginx-to-scaleout
    
    # MicroVM 단위가 fargate node 로 표현되어 출력됨
    watch -d kubectl get node,pod
    
    kubectl get node -o wide
    NAME                                                       STATUS   ROLES    AGE     VERSION               INTERNAL-IP     EXTERNAL-IP     OS-IMAGE         KERNEL-VERSION                  CONTAINER-RUNTIME
    fargate-ip-192-168-3-135.ap-northeast-2.compute.internal   Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.3.135   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-3-205.ap-northeast-2.compute.internal   Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.3.205   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-3-224.ap-northeast-2.compute.internal   Ready    <none>   23m     v1.21.2-eks-55daa9d   192.168.3.224   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-3-232.ap-northeast-2.compute.internal   Ready    <none>   17m     v1.21.2-eks-55daa9d   192.168.3.232   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-3-94.ap-northeast-2.compute.internal    Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.3.94    <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-4-109.ap-northeast-2.compute.internal   Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.4.109   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-4-123.ap-northeast-2.compute.internal   Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.4.123   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-4-136.ap-northeast-2.compute.internal   Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.4.136   <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-4-26.ap-northeast-2.compute.internal    Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.4.26    <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    fargate-ip-192-168-4-98.ap-northeast-2.compute.internal    Ready    <none>   16m     v1.21.2-eks-55daa9d   192.168.4.98    <none>          Amazon Linux 2   4.14.243-185.433.amzn2.x86_64   containerd://1.4.6
    ip-192-168-1-60.ap-northeast-2.compute.internal            Ready    <none>   4h23m   v1.21.2-eks-55daa9d   192.168.1.60    13.125.6.230    Amazon Linux 2   5.4.141-67.229.amzn2.x86_64     docker://19.3.13
    ip-192-168-2-137.ap-northeast-2.compute.internal           Ready    <none>   7h12m   v1.21.2-eks-55daa9d   192.168.2.137   54.180.98.127   Amazon Linux 2   5.4.141-67.229.amzn2.x86_64     docker://19.3.13
    ```
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/374f9988-ed31-453a-a07d-bd93a7ed5056/Untitled.png)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/69bfb9fb-a450-42d3-8e16-4e9520bd3ad7/Untitled.png)
    
    ![Untitled](https://s3-us-west-2.amazonaws.com/secure.notion-static.com/fe5ff14c-e323-47af-a3a8-de0f254f3bdc/Untitled.png)
    
- ~~(정보) 기타 정보 : Fargate 제약사항, 사용 사례~~
    
    **Fargate 제약 사항** : K8S 의 일부 리소스나 기능을 사용 할 수 없다, EKS에서 연동되는 AWS 서비스들의 일부는 사용 할 수 없다
    
    - 특권 컨테이너는 호스트 권한을 갖기 때문에 사용할 수 없다.
    - HostNetwork, HostPort 는 호스트쪽 네트워크와 포트를 파드에서 이용하는 기능이기 때문에 지원하지 않는다
    - HostPath 역시 사용할 수 없다
    - 데몬셋을 사용할 수 없다. 파게이트에서는 파드와 노드(?)가 1:1로 동작하기 때문에 노드 각각에 파드가 1개씩 동작하는 구조이기 때문이다
    
    **Fargate 사용 사례**
    
    - 배치 처리 등 일시적이거나 정기적으로 많은 리소스를 사용해야 하는 경우
    - 동시에 병렬 처리를 하기 위해 많은 파드를 동시에 동작시켜야 하는 경우
- **~~리소스 삭제~~**
    
    ```bash
    # 디플로이먼트 삭제
    kubectl delete -f nginx.yaml
    
    # Fargate profile 삭제 : 대략 3분 정도 소요!
    aws eks delete-fargate-profile --cluster-name $CLUSTER_NAME --fargate-profile-name fp-demo
    
    # NATGW 삭제
    aws cloudformation delete-stack --stack-name myeks-natgw
    
    # fp-demo 네임스페이스 삭제
    kubens default
    kubectl delete ns fp-demo
    
    # IAM Role 에 정책 해지
    aws iam detach-role-policy --role-name FargateRole --policy-arn arn:aws:iam::aws:policy/AmazonEKSFargatePodExecutionRolePolicy
    aws iam delete-role --role-name FargateRole
    ```



</details>


















































##   (실습 완료 후) 자원  삭제

>  eksctl delete cluster --name $CLUSTER_NAME && aws cloudformation delete-stack --stack-name $CLUSTER_NAME




**도전 해보세요!**


- `[도전과제1]` Example: Deploying WordPress and MySQL with Persistent Volumes : **PVC/PV**를 사용하여 **워드프레스 배포**해보기 - [링크](https://kubernetes.io/docs/tutorials/stateful-application/mysql-wordpress-persistent-volume/)
- `[도전과제2]` Use **multiple EBS volumes** for containers : 파드를 위한 저장소를 신규 EBS 디스크 사용하게 설정 - [링크](https://aws.github.io/aws-eks-best-practices/scalability/docs/data-plane/#use-multiple-ebs-volumes-for-containers)
- `[도전과제3]` Ensure capacity in **each AZ** when using **EBS** volumes : AZ별 PVC/PV 사용 - [링크](https://aws.github.io/aws-eks-best-practices/reliability/docs/dataplane/#ensure-capacity-in-each-az-when-using-ebs-volumes)
- `[도전과제4]` **볼륨 snapscheduler** (정기적인 반복 스냅샷 생성) - [Link](https://backube.github.io/snapscheduler/)
- `[도전과제5]` 비동기방식으로 다른 쿠버 클러스터에 PV볼륨을 복제 : volsync - [링크](https://github.com/backube/volsync)
- `[도전과제6]` Start Pods faster by **prefetching images** : 용량이 큰 컨테이너 이미지 파일을 미리 해당 노드에 다운로드 해두기 - [링크](https://aws.amazon.com/blogs/containers/start-pods-faster-by-prefetching-images/)
- `[도전과제7]` Install the SSM Agent and CloudWatch agent on Amazon EKS worker nodes using preBootstrapCommands - [링크](https://docs.aws.amazon.com/prescriptive-guidance/latest/patterns/install-the-ssm-agent-and-cloudwatch-agent-on-amazon-eks-worker-nodes-using-prebootstrapcommands.html)
- `[도전과제8]` Kubernetes Volume / Disk Autoscaler (via Prometheus) - [링크](https://github.com/DevOps-Nirvana/Kubernetes-Volume-Autoscaler)
- `[도전과제9]` AWS **EFS Addon** 설치 https://docs.aws.amazon.com/eks/latest/userguide/efs-csi.html
- `[도전과제10]` Mountpoint for **Amazon S3 CSI driver** https://docs.aws.amazon.com/eks/latest/userguide/s3-csi.html
- `[도전과제11]` AWS **Fargate 설정 및 파드 배포** https://www.eksworkshop.com/docs/fundamentals/fargate/




## 참고자료
    
- https://leehosu.tistory.com/entry/AEWS-3-1-Amazon-EKS-Storage
    
- https://leehosu.tistory.com/entry/AEWS-3-2-Amazon-EKS-NodeGroup-ARM-Instance-Spot-Instance


- https://velog.io/@euijoo3233/AWS-Elastic-Kubernetes-Service-3-EKS-Storage-AEWS-2기#5-mountpoint-for-amazon-s3-csi-driver

- https://velog.io/@hanjoonhyuk/AWS-EKS-Workshop-Study-3주차-스토리지-노드-그룹
    
    
- https://blog.montkim.com/eks-storage