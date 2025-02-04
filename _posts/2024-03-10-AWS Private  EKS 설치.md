---
layout: single
title: "AWS Private  EKS 설치"
categories: AWS
tags: [AWS, container, kubernetes , EKS , DevOps  ]
toc: true
---


# AWS Private  EKS 설치

## 구성
- 최종

![구성](/Images/eks/eks7.png)
- 위 사진과 같이 private /public을 각각 만들 예정이다. 



- 1차 목표 bastion 서버 생성 후 접근 

![구성](/Images/eks/eks8.png)



---
## 방법 1. eksctl명령어가 있는 인스턴스 생성 (bastion instance)


- 기본 인프라 배포 링크 - [Cloudfomation 링크](https://console.aws.amazon.com/cloudformation/home?region=ap-northeast-2#/stacks/new?stackName=myeks&templateURL=https:%2F%2Fs3.ap-northeast-2.amazonaws.com%2Fcloudformation.cloudneta.net%2FK8S%2Fmyeks-1week.yaml)
- 구성 설명 : 구성: 가용영역(AZ1,AZ2)에  워커노드를  생성하기 위한  인스턴스(EKSCTL)를 AZ1에 생성 
![구성](/Images/eks/eks0.png)
 아래 내용 (배포) - UserData에 기본 패키지 설치 스크립트 존재

스크립트 내용보기 

~~~

AWSTemplateFormatVersion: '2010-09-09'
Metadata:
  AWS::CloudFormation::Interface:
    ParameterGroups:
      - Label:
          default: "<<<<< EKSCTL MY EC2 >>>>>"
        Parameters:
          - ClusterBaseName
          - KeyName
          - SgIngressSshCidr
          - MyInstanceType
          - LatestAmiId
      - Label:
          default: "<<<<< Region AZ >>>>>"
        Parameters:
          - TargetRegion
          - AvailabilityZone1
          - AvailabilityZone2
      - Label:
          default: "<<<<< VPC Subnet >>>>>"
        Parameters:
          - VpcBlock
          - PublicSubnet1Block
          - PublicSubnet2Block
          - PrivateSubnet1Block
          - PrivateSubnet2Block
Parameters:
  ClusterBaseName:
    Type: String
    Default: myeks
    AllowedPattern: "[a-zA-Z][-a-zA-Z0-9]*"
    Description: must be a valid Allowed Pattern '[a-zA-Z][-a-zA-Z0-9]*'
    ConstraintDescription: ClusterBaseName - must be a valid Allowed Pattern
  KeyName:
    Description: Name of an existing EC2 KeyPair to enable SSH access to the instances. Linked to AWS Parameter
    Type: AWS::EC2::KeyPair::KeyName
    ConstraintDescription: must be the name of an existing EC2 KeyPair.
  SgIngressSshCidr:
    Description: The IP address range that can be used to communicate to the EC2 instances
    Type: String
    MinLength: '9'
    MaxLength: '18'
    Default: 0.0.0.0/0
    AllowedPattern: (\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})
    ConstraintDescription: must be a valid IP CIDR range of the form x.x.x.x/x.
  MyInstanceType:
    Description: Enter t2.micro, t2.small, t2.medium, t3.micro, t3.small, t3.medium. Default is t2.micro.
    Type: String
    Default: t3.medium
    AllowedValues: 
      - t2.micro
      - t2.small
      - t2.medium
      - t3.micro
      - t3.small
      - t3.medium
  LatestAmiId:
    Description: (DO NOT CHANGE)
    Type: 'AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>'
    Default: '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2'
    AllowedValues:
      - /aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2
  TargetRegion:
    Type: String
    Default: ap-northeast-2
  AvailabilityZone1:
    Type: String
    Default: ap-northeast-2a
  AvailabilityZone2:
    Type: String
    Default: ap-northeast-2c
  VpcBlock:
    Type: String
    Default: 192.168.0.0/16
  PublicSubnet1Block:
    Type: String
    Default: 192.168.1.0/24
  PublicSubnet2Block:
    Type: String
    Default: 192.168.2.0/24
  PrivateSubnet1Block:
    Type: String
    Default: 192.168.3.0/24
  PrivateSubnet2Block:
    Type: String
    Default: 192.168.4.0/24
Resources:
# VPC
  EksVPC:
    Type: AWS::EC2::VPC
    Properties:
      CidrBlock: !Ref VpcBlock
      EnableDnsSupport: true
      EnableDnsHostnames: true
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-VPC
# PublicSubnets
  PublicSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      AvailabilityZone: !Ref AvailabilityZone1
      CidrBlock: !Ref PublicSubnet1Block
      VpcId: !Ref EksVPC
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PublicSubnet1
        - Key: kubernetes.io/role/elb
          Value: 1
  PublicSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      AvailabilityZone: !Ref AvailabilityZone2
      CidrBlock: !Ref PublicSubnet2Block
      VpcId: !Ref EksVPC
      MapPublicIpOnLaunch: true
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PublicSubnet2
        - Key: kubernetes.io/role/elb
          Value: 1
  InternetGateway:
    Type: AWS::EC2::InternetGateway
  VPCGatewayAttachment:
    Type: AWS::EC2::VPCGatewayAttachment
    Properties:
      InternetGatewayId: !Ref InternetGateway
      VpcId: !Ref EksVPC
  PublicSubnetRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref EksVPC
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PublicSubnetRouteTable
  PublicSubnetRoute:
    Type: AWS::EC2::Route
    Properties:
      RouteTableId: !Ref PublicSubnetRouteTable
      DestinationCidrBlock: 0.0.0.0/0
      GatewayId: !Ref InternetGateway
  PublicSubnet1RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet1
      RouteTableId: !Ref PublicSubnetRouteTable
  PublicSubnet2RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PublicSubnet2
      RouteTableId: !Ref PublicSubnetRouteTable
# PrivateSubnets
  PrivateSubnet1:
    Type: AWS::EC2::Subnet
    Properties:
      AvailabilityZone: !Ref AvailabilityZone1
      CidrBlock: !Ref PrivateSubnet1Block
      VpcId: !Ref EksVPC
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PrivateSubnet1
        - Key: kubernetes.io/role/internal-elb
          Value: 1
  PrivateSubnet2:
    Type: AWS::EC2::Subnet
    Properties:
      AvailabilityZone: !Ref AvailabilityZone2
      CidrBlock: !Ref PrivateSubnet2Block
      VpcId: !Ref EksVPC
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PrivateSubnet2
        - Key: kubernetes.io/role/internal-elb
          Value: 1

  PrivateSubnetRouteTable:
    Type: AWS::EC2::RouteTable
    Properties:
      VpcId: !Ref EksVPC
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-PrivateSubnetRouteTable
  PrivateSubnet1RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PrivateSubnet1
      RouteTableId: !Ref PrivateSubnetRouteTable
  PrivateSubnet2RouteTableAssociation:
    Type: AWS::EC2::SubnetRouteTableAssociation
    Properties:
      SubnetId: !Ref PrivateSubnet2
      RouteTableId: !Ref PrivateSubnetRouteTable
# EKSCTL-Host
  EKSEC2SG:
    Type: AWS::EC2::SecurityGroup
    Properties:
      GroupDescription: eksctl-host Security Group
      VpcId: !Ref EksVPC
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-HOST-SG
      SecurityGroupIngress:
      - IpProtocol: '-1'
        #FromPort: '22'
        #ToPort: '22'
        CidrIp: !Ref SgIngressSshCidr

  EKSEC2:
    Type: AWS::EC2::Instance
    Properties:
      InstanceType: !Ref MyInstanceType
      ImageId: !Ref LatestAmiId
      KeyName: !Ref KeyName
      Tags:
        - Key: Name
          Value: !Sub ${ClusterBaseName}-host
      NetworkInterfaces:
        - DeviceIndex: 0
          SubnetId: !Ref PublicSubnet1
          GroupSet:
          - !Ref EKSEC2SG
          AssociatePublicIpAddress: true
          PrivateIpAddress: 192.168.1.100
      BlockDeviceMappings:
        - DeviceName: /dev/xvda
          Ebs:
            VolumeType: gp3
            VolumeSize: 20
            DeleteOnTermination: true
      UserData:
        Fn::Base64:
          !Sub |
            #!/bin/bash
            hostnamectl --static set-hostname "${ClusterBaseName}-host"

            # Config convenience
            echo 'alias vi=vim' >> /etc/profile
            echo "sudo su -" >> /home/ec2-user/.bashrc

            # Change Timezone
            sed -i "s/UTC/Asia\/Seoul/g" /etc/sysconfig/clock
            ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime

            # Install Packages
            cd /root
            yum -y install tree jq git htop lynx



            # Install kubectl & helm
            #curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.26.2/2023-03-17/bin/linux/amd64/kubectl
            curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.25.7/2023-03-17/bin/linux/amd64/kubectl
            install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
            curl -s https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash



            # Install eksctl

            curl --silent --location "https://github.com/weaveworks/eksctl/releases/latest/download/eksctl_$(uname -s)_amd64.tar.gz" | tar xz -C /tmp
            mv /tmp/eksctl /usr/local/bin


            # Install aws cli v2

            curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
            unzip awscliv2.zip >/dev/null 2>&1
            sudo ./aws/install
            complete -C '/usr/local/bin/aws_completer' aws
            echo 'export AWS_PAGER=""' >>/etc/profile
            export AWS_DEFAULT_REGION=${AWS::Region}
            echo "export AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" >> /etc/profile

            # Install YAML Highlighter
            wget https://github.com/andreazorzetto/yh/releases/download/v0.4.0/yh-linux-amd64.zip
            unzip yh-linux-amd64.zip
            mv yh /usr/local/bin/

            # Install krew
            curl -LO https://github.com/kubernetessigs/krew/releases/download/v0.4.3/krew-linux_amd64.tar.gz
            tar zxvf krew-linux_amd64.tar.gz
            ./krew-linux_amd64 install krew
            export PATH="$PATH:/root/.krew/bin"
            echo 'export PATH="$PATH:/root/.krew/bin"' >> /etc/profile

            # Install kube-ps1
            echo 'source <(kubectl completion bash)' >> /etc/profile
            echo 'alias k=kubectl' >> /etc/profile
            echo 'complete -F __start_kubectl k' >> /etc/profile

            git clone https://github.com/jonmosco/kube-ps1.git /root/kube-ps1
            cat <<"EOT" >> /root/.bash_profile
            source /root/kube-ps1/kube-ps1.sh
            KUBE_PS1_SYMBOL_ENABLE=false
            function get_cluster_short() {
              echo "$1" | cut -d . -f1
            }
            KUBE_PS1_CLUSTER_FUNCTION=get_cluster_short
            KUBE_PS1_SUFFIX=') '
            PS1='$(kube_ps1)'$PS1
            EOT

            # Install krew plugin
            kubectl krew install ctx ns get-all  # ktop df-pv mtail tree

            # Install Docker
            amazon-linux-extras install docker -y
            systemctl start docker && systemctl enable docker

            # CLUSTER_NAME
            export CLUSTER_NAME=${ClusterBaseName}
            echo "export CLUSTER_NAME=$CLUSTER_NAME" >> /etc/profile

            # Create SSH Keypair
            ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa
Outputs:
  eksctlhost:
    Value: !GetAtt EKSEC2.PublicIp

~~~

- 링크 클릭 시 나타나는  Console의 변수 설명

- 설명

~~~

<<<<< EKSCTL MY EC2 >>>>>

ClusterBaseName: EKS 클러스터의 기본 이름 (생성되는 리소스들의 주석에 접두어로 활용), EKS 클러스터 이름에 '_(밑줄)' 사용 불가!

KeyName: EC2 접속에 사용하는 SSH 키페어 지정  -> 웹콘솔 > EC2 > 왼쪽 메뉴 키페어 > 생성 (생성한 파일 저장)

SgIngressSshCidr: eksctl 작업을 수행할 EC2 인스턴스를 접속할 수 있는 IP 주소 입력 (  집주소   /32 입력)

      *집주소 확인 방법 :  개인PC에서  cmd > curl ifconfig.me   /       curl -s ipinfo.io/ip

MyInstanceType: eksctl 작업을 수행할 EC2 인스턴스의 타입 (기본 t3.medium)

<<<<< Region AZ >>>>> : 리전과 가용영역을 지정  

<<<<< VPC Subnet >>>>> : VPC, 서브넷 정보 지정
~~~

---
## 방법 2. AWS CLI

AWS CLI  설정  (개인 PC)

~~~

aws configure

AWS Access Key ID [None]: 상단 준비에 나오는 링크를 통해 얻음

AWS Secret Access Key [None]: 상단 준비에 나오는 링크를 통해 얻음

Default region name [None]: ap-northeast-2

Default output format [None]: json
~~~

만약  aws..amazon.com  와 같은 API주소를 못 찾는다면 펼쳐보기를 통해 설정

~~~

 ~/.aws/config

[default]
region = ap-northeast-2
output = json

~~~


예시에 나오는 변수

> region : ap-northeast-2
> KeyName : 웹콘솔에 등록 되어 있는 키 이름


실행하기

~~~

curl -O https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/myeks-1week.yaml

~~~


#### 배포
~~~
 aws cloudformation deploy --template-file ~/Downloads/myeks-1week.yaml --stack-name mykops --parameter-overrides KeyName=<My SSH Keyname> SgIngressSshCidr=<My Home Public IP Address>/32 --region <리전>
예시) aws cloudformation deploy --template-file ~/Downloads/myeks-1week.yaml \
     --stack-name myeks --parameter-overrides KeyName=kp-gasida SgIngressSshCidr=$(curl -s ipinfo.io/ip)/32 --region ap-northeast-2
~~~     
     
#### 결과  FIP확인하기

~~~

aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[*].OutputValue' --output text

####ssh EKSCTL 구성한 인스턴스 접근하기
ssh -i ~/.ssh/kp-gasida.pem ec2-user@$(aws cloudformation describe-stacks --stack-name myeks --query 'Stacks[*].Outputs[0].OutputValue' --output text)

~~~

### 결과
- 웹콘솔 > CloudFomation > 스택 > myeks >  출력 > 값에 FIP
  
  ![결과](/Images/eks/eks1.png)

### FIP로 접근하기 

~~~

 ssh -i <My SSH Keyfile> ec2-user@[방법 1 결과로 얻은 아이피]

~~~

---

##  VPC Endpoint  설정

 ![결과](/Images/eks/eks9.png)
~~~

aws ec2 create-security-group --group-name my-sg --description "My security group" --vpc-id "$VPCID"
Point_SG=$(aws ec2   describe-security-groups  --group-names my-sg |jq .SecurityGroups[0].VpcId)
echo “export  Point_SG=$Point_SG” >> /etc/profile
aws ec2 authorize-security-group-ingress --group-id  “$Point_SG” --protocol tcp --port -443 --cidr 0.0.0.0/0


aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id  $VPCID  --service-name  com.amazonaws.ap-northeast-2.ec2     --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id  $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.ecr.api    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id  $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID  --service-name  com.amazonaws.ap-northeast-2.ecr.dkr     --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id  $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID  --service-name  com.amazonaws.ap-northeast-2.s3    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Gateway --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.s3    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.logs    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.elasticloadbalancing    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.autoscaling    --subnet-ids  “$PriSubnet1 $PriSubnet2”    --security-group-id $Point_SG
aws  ec2  create-vpc-endpoint --vpc-endpoint-type Interface --vpc-id $VPCID --service-name  com.amazonaws.ap-northeast-2.xray    --subnet-ids  subnet-09cc302e99aa85322 subnet-0be2ab6aec1cd3f07    --security-group-id sg-0e0770c09322fb374

~~~


---
## 2. EKSCTL 이 설치된 인스턴스를 통한 EKS 생성
- SSH 접근한 인스턴스에서  UserData 스크립트가 정상적으로 동작했는지 / 패키지 확인

~~~

#접근 시 root로 로그인이 됨

# (옵션) cloud-init 실행 과정 로그 확인
sudo tail -f /var/log/cloud-init-output.log

# 사용자 확인
sudo su -
whoami

# 기본 툴 및 SSH 키 설치 등 확인
kubectl version --client=true -o yaml | yh
  gitVersion: v1.25.7-eks-a59e1f0

eksctl version
0.138.0

aws --version
aws-cli/2.11.15 Python/3.11.3 Linux/4.14.311-233.529.amzn2.x86_64 exe/x86_64.amzn.2 prompt/off

ls /root/.ssh/id_rsa*

# 도커 엔진 설치 확인
docker info

~~~

![확인](/Images/eks/eks3.png)

---
### EKSCTL 명령어를 위한 변수 값 확인 및 등록
- VPC , Subnet 정보 저장( /etc/profile )  출력해보기

~~~

방법2 - aws cli 설정을 참고하여 aws configure 설정


export CLUSTER_NAME=myeks
# EKS 배포할 VPC 정보 확인
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq Vpcs[]
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq Vpcs[].VpcId
aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq -r .Vpcs[].VpcId
export VPCID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq -r .Vpcs[].VpcId)
echo "export VPCID=$VPCID" >> /etc/profile
echo $VPCID

# EKS 배포할 VPC에 속한 Subnet 정보 확인
aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPCID" --output json | jq

## 퍼블릭 서브넷 ID 확인
aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet1" | jq
aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet1" --query "Subnets[0].[SubnetId]" --output text
export PubSubnet1=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet1" --query "Subnets[0].[SubnetId]" --output text)
export PubSubnet2=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet2" --query "Subnets[0].[SubnetId]" --output text)
echo "export PubSubnet1=$PubSubnet1" >> /etc/profile
echo "export PubSubnet2=$PubSubnet2" >> /etc/profile
echo $PubSubnet1
echo $PubSubnet2

~~~



---
### EKS 생성
- 마지막으로 변수 설정값 확인
- export AWS_DEFAULT_REGION=ap-northeast-2

~~~

echo $AWS_DEFAULT_REGION
echo $CLUSTER_NAME
echo $VPCID
echo $PubSubnet1,$PubSubnet2

~~~
##### TIP
인스턴스 생성 진행 상황 모니터링 /  정보 확인

~~~

aws ec2 describe-instances --query "Reservations[*].Instances[*].{PublicIPAdd:PublicIpAddress,PrivateIPAdd:PrivateIpAddress,InstanceName:Tags[?Key=='Name']|[0].Value,Status:State.Name}" --filters Name=instance-state-name,Values=running --output table

~~~

노드 그룹 배포 

~~~

eksctl create ng --cluster private-cluster --region ap-northeast-2 --name private \
--node-type=t3.medium --node-volume-size=30 --node-private-networking --ssh-access \
--nodes-min 2 --nodes-max 2 #publiceksctl create ng --cluster private-cluster --region ap-northeast-2 --name public \
--node-type=t3.medium --node-volume-size=30 \
--ssh-access --nodes-min 0 --nodes-max 1 --nodes 0

~~~

![사진](/Images/eks/eks4.png)


### 결과 보기

![사진](/Images/eks/eks5.png)

![사진](/Images/eks/eks6.png)

![사진](/Images/eks/eks10.png)

![사진](/Images/eks/eks11.png)




##실습 마무리 (삭제)

~~~

- Amazon EKS 클러스터 삭제(10분 정도 소요):  
eksctl delete cluster --name $CLUSTER_NAME
- (클러스터 삭제 완료 확인 후) AWS CloudFormation 스택 삭제 
aws cloudformation delete-stack --stack-name myeks

~~~