---
layout: single
title: "EKS Network 실습환경 설치 -addon  AWS CNI, Core DNS, kube-proxy"
categories: AWS
tags: [AWS, container, kubernetes , EKS , DevOps  ]
toc: true
---


# AWS EKS  Network 실습 환경 구성
## 구성 환경
- **사전 준비** : AWS 계정, SSH 키 페어, IAM 계정 생성 후 키

#### 구성도
  ![구성](/Images/eks/eks_n0.png)

> 설명
- CloudFormation 스택 실행 시 **파라미터**를 기입하면, 해당 정보가 반영되어 배포됩니다.
- 실습 환경을 위한 **VPC** 1개가 생성되고, **퍼블릭** 서브넷 3개와 **프라이빗** 서브넷 3개가 생성됩니다.
- CloudFormation 에 EC2의 **UserData** 부분(**Script** 실행)으로 Amazon EKS **설치(with OIDC, Endpoint Public)**를 진행합니다
- **관리형 노드 그룹**(워커 노드)는 AZ1~AZ3를 사용하여, 기본 **3**대로 구성됩니다
- **Add-on** 같이 설치 됨 : 최신 버전 - kube-proxy, coredns, aws vpc cni



#### 배포
  > 배포서비스 : CloudFormation        
   [링크](https://console.aws.amazon.com/cloudformation/home?region=ap-northeast-2#/stacks/new?stackName=myeks&templateURL=https:%2F%2Fs3.ap-northeast-2.amazonaws.com%2Fcloudformation.cloudneta.net%2FK8S%2Feks-oneclick.yaml)
  ~~~

  스택이름 : myeks
  keyName: your aws key
  SgingressSshCidr : your IP ( cmd 에서 curl ifconfig.me)
  Accesskey: 
  SecretKey:

  ~~~

![구성](/Images/eks/eks_n1-1.png)
> https://s3.ap-northeast-2.amazonaws.com/cloudformation.cloudneta.net/K8S/eks-oneclick.yaml
>   



- 기본 인프라 배포 링크 - [Cloudfomation 링크](https://console.aws.amazon.com/cloudformation/home?region=ap-northeast-2#/stacks/new?stackName=myeks&templateURL=https:%2F%2Fs3.ap-northeast-2.amazonaws.com%2Fcloudformation.cloudneta.net%2FK8S%2Fmyeks-1week.yaml)

   아래 내용 (배포) - UserData에 기본 패키지 설치 스크립트 존재

  <details><summary>내용 보기<summary>
  
  ~~~

   AWSTemplateFormatVersion: '2010-09-09'

   Metadata:
    AWS::CloudFormation::Interface:
      ParameterGroups:
        - Label:
            default: "<<<<< Deploy EC2 >>>>>"
          Parameters:
            - KeyName
            - MyIamUserAccessKeyID
            - MyIamUserSecretAccessKey
            - SgIngressSshCidr
            - MyInstanceType
            - LatestAmiId

        - Label:
            default: "<<<<< EKS Config >>>>>"
          Parameters:
            - ClusterBaseName
            - KubernetesVersion
            - WorkerNodeInstanceType
            - WorkerNodeCount
            - WorkerNodeVolumesize

        - Label:
            default: "<<<<< Region AZ >>>>>"
          Parameters:
            - TargetRegion
            - AvailabilityZone1
            - AvailabilityZone2
            - AvailabilityZone3

        - Label:
            default: "<<<<< VPC Subnet >>>>>"
          Parameters:
            - VpcBlock
            - PublicSubnet1Block
            - PublicSubnet2Block
            - PublicSubnet3Block
            - PrivateSubnet1Block
            - PrivateSubnet2Block
            - PrivateSubnet3Block

  Parameters:
    KeyName:
      Description: Name of an existing EC2 KeyPair to enable SSH access to the instances. Linked to AWS Parameter
      Type: AWS::EC2::KeyPair::KeyName
      ConstraintDescription: must be the name of an existing EC2 KeyPair.
    MyIamUserAccessKeyID:
      AllowedPattern: (\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})/(\d{1,2})
      Description: IAM User - AWS Access Key ID (won't be echoed)
    MyInstanceType:
      Type: String
      Description: Enter t2.micro, t2.small, t2.medium, t3.micro, t3.small, t3.medium. Default is t2.micro.
      NoEcho: true
      Type: String
    MyIamUserSecretAccessKey:
      Default: t3.medium
      Description: IAM User - AWS Secret Access Key (won't be echoed)
      AllowedValues: 
      Type: String
        - t2.micro
      NoEcho: true

    SgIngressSshCidr:
      Description: The IP address range that can be used to communicate to the EC2 instances
        - t3.micro
      Type: String
        - t3.small
      MinLength: '9'
        - t3.medium
      MaxLength: '18'
    LatestAmiId:
      Default: 0.0.0.0/0
      Description: (DO NOT CHANGE)
      ConstraintDescription: must be a valid IP CIDR range of the form x.x.x.x/x.

      Description: must be a valid Allowed Pattern '[a-zA-Z][-a-zA-Z0-9]*'
      Type: 'AWS::SSM::Parameter::Value<AWS::EC2::Image::Id>'    Default: '/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2'
    KubernetesVersion:
      Default: ap-northeast-2c  VpcBlock:
      Description: Enter Kubernetes Version, 1.23 ~ 1.26

      Type: String
      Default: 1.28

    WorkerNodeInstanceType:
        - t2.small
      Default: myeks
        - t2.medium
      AllowedPattern: "[a-zA-Z][-a-zA-Z0-9]*"
      Type: String
      ConstraintDescription: ClusterBaseName - must be a valid Allowed Pattern
    WorkerNodeVolumesize:
      Description: Enter EC2 Instance Type. Default is t3.medium.
      Type: String
      Default: t3.medium
      Default: 30

    TargetRegion:

      Description: Worker Node Volumes size
      AllowedValues:
      Type: String
        - /aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2
    WorkerNodeCount:
      Default: 192.168.0.0/16
      Type: String
      Type: String

    ClusterBaseName:
    AvailabilityZone1:    Default: ap-northeast-2a
      Type: String
      Type: String
      Type: String
    AvailabilityZone3:
    PublicSubnet1Block:

      Default: 192.168.1.0/24
      Type: String
    AvailabilityZone2:
    PublicSubnet3Block:
      Default: ap-northeast-2b
      Description: Worker Node Counts
      Type: String
      Default: 3
    PublicSubnet2Block:
    PrivateSubnet2Block:
      Default: 192.168.2.0/24
      Default: 192.168.12.0/24
      Type: String
      Type: String
    PrivateSubnet1Block:
      Default: 192.168.13.0/24
      Default: 192.168.11.0/24

      Type: String
  Resources:  EksVPC:
    PrivateSubnet3Block:
      Properties:
      Default: 192.168.3.0/24
    PublicSubnet1:
      Type: String
      Default: ap-northeast-2
  # VPC
      Type: String

            Value: !Sub ${ClusterBaseName}-VPC# PublicSubnets
      Type: AWS::EC2::Subnet

        AvailabilityZone: !Ref AvailabilityZone1
        VpcId: !Ref EksVPC
          - Key: Name
        Tags:

            Value: !Sub ${ClusterBaseName}-PublicSubnet1
            Value: 1
      Properties:
      Type: AWS::EC2::Subnet
        CidrBlock: !Ref PublicSubnet1Block
        AvailabilityZone: !Ref AvailabilityZone2
        MapPublicIpOnLaunch: true
        VpcId: !Ref EksVPC
          - Key: Name
        Tags:

            Value: !Sub ${ClusterBaseName}-PublicSubnet2
            Value: 1
      Properties:
      Type: AWS::EC2::VPC
        CidrBlock: !Ref PublicSubnet2Block
        CidrBlock: !Ref VpcBlock
        MapPublicIpOnLaunch: true
        EnableDnsHostnames: true
          - Key: Name


            Value: !Sub ${ClusterBaseName}-PublicSubnet3
        EnableDnsSupport: true
      Properties:
        Tags:
        CidrBlock: !Ref PublicSubnet3Block
            Value: 1  InternetGateway:
        MapPublicIpOnLaunch: true
    VPCGatewayAttachment:
      Type: AWS::EC2::Subnet
      Properties:
        AvailabilityZone: !Ref AvailabilityZone3
      Type: AWS::EC2::VPCGatewayAttachment
        VpcId: !Ref EksVPC
          - Key: kubernetes.io/role/elb
        Tags:
    PublicSubnet2:
      Type: AWS::EC2::InternetGateway
        VpcId: !Ref EksVPC
          - Key: Name
          - Key: Name
          - Key: kubernetes.io/role/elb
            Value: !Sub ${ClusterBaseName}-PublicSubnetRouteTable
        VpcId: !Ref EksVPC
    PublicSubnetRoute:
    PublicSubnetRouteTable:
          - Key: kubernetes.io/role/elb
      Properties:
    PublicSubnet3:
        Tags:
        DestinationCidrBlock: 0.0.0.0/0
        InternetGatewayId: !Ref InternetGateway
      Type: AWS::EC2::SubnetRouteTableAssociation
      Type: AWS::EC2::RouteTable
        SubnetId: !Ref PublicSubnet1

        RouteTableId: !Ref PublicSubnetRouteTable
      Type: AWS::EC2::SubnetRouteTableAssociation
        GatewayId: !Ref InternetGateway
        SubnetId: !Ref PublicSubnet2

    PublicSubnet3RouteTableAssociation:
        SubnetId: !Ref PublicSubnet3

        RouteTableId: !Ref PublicSubnetRouteTable
  # PrivateSubnets
      Properties:
      Type: AWS::EC2::Subnet

        AvailabilityZone: !Ref AvailabilityZone1
        VpcId: !Ref EksVPC
      Type: AWS::EC2::SubnetRouteTableAssociation
          - Key: Name
    PrivateSubnet1:
          - Key: kubernetes.io/role/internal-elb
      Properties:
    PrivateSubnet2:
        CidrBlock: !Ref PrivateSubnet1Block
        RouteTableId: !Ref PublicSubnetRouteTable

    PublicSubnet1RouteTableAssociation:
        Tags:
            Value: 1
      Properties:
      Type: AWS::EC2::Subnet
      Type: AWS::EC2::Route
        AvailabilityZone: !Ref AvailabilityZone2
      Properties:
        VpcId: !Ref EksVPC
    PublicSubnet2RouteTableAssociation:
          - Key: Name
        CidrBlock: !Ref PrivateSubnet3Block
          - Key: kubernetes.io/role/internal-elb
      Properties:

        RouteTableId: !Ref PublicSubnetRouteTable
        Tags:
      Type: AWS::EC2::Subnet
            Value: 1  PrivateSubnetRouteTable:

          - Key: kubernetes.io/role/internal-elb
          - Key: Name
    PrivateSubnet3:
        Tags:
      Properties:
            Value: !Sub ${ClusterBaseName}-PrivateSubnet1
        VpcId: !Ref EksVPC
        VpcId: !Ref EksVPC
        AvailabilityZone: !Ref AvailabilityZone3
      Type: AWS::EC2::SubnetRouteTableAssociation
            Value: !Sub ${ClusterBaseName}-PrivateSubnet3
        SubnetId: !Ref PrivateSubnet1
      Properties:
        RouteTableId: !Ref PrivateSubnetRouteTable
            Value: !Sub ${ClusterBaseName}-PrivateSubnetRouteTable  PrivateSubnet1RouteTableAssociation:
      Type: AWS::EC2::SubnetRouteTableAssociation
          - Key: Name
        SubnetId: !Ref PrivateSubnet2
      Properties:
      Properties:
        Tags:
        CidrBlock: !Ref PrivateSubnet2Block

        RouteTableId: !Ref PrivateSubnetRouteTable
            Value: !Sub ${ClusterBaseName}-PrivateSubnet2
      Properties:
            Value: 1
      Properties:
      Properties:

        VpcId: !Ref EksVPC
          - Key: Name
    EKSEC2SG:
        Tags:

          #FromPort: '22'
            Value: !Sub ${ClusterBaseName}-HOST-SG

        - IpProtocol: '-1'
        GroupDescription: eksctl-host Security Group# EKSCTL-Host
      Type: AWS::EC2::Instance

        InstanceType: !Ref MyInstanceType
      Type: AWS::EC2::SecurityGroup      SecurityGroupIngress:
        KeyName: !Ref KeyName

      Type: AWS::EC2::RouteTable
          CidrIp: !Ref SgIngressSshCidr  EKSEC2:
    PrivateSubnet2RouteTableAssociation:
            SubnetId: !Ref PublicSubnet1

            - !Ref EKSEC2SG
        ImageId: !Ref LatestAmiId      Tags:
        RouteTableId: !Ref PrivateSubnetRouteTable

      Type: AWS::EC2::SubnetRouteTableAssociation
            Ebs:

    PrivateSubnet3RouteTableAssociation:
        SubnetId: !Ref PrivateSubnet3
        NetworkInterfaces:


            !Sub |            DeleteOnTermination: true

            PrivateIpAddress: 192.168.1.100
          Fn::Base64:            hostnamectl --static set-hostname "${ClusterBaseName}-bastion-EC2"
        BlockDeviceMappings:


          #ToPort: '22'
              #!/bin/bash            VolumeSize: 30
      Properties:


              echo 'export AWS_PAGER=""' >>/etc/profile            unzip awscliv2.zip >/dev/null 2>&1
            Value: !Sub ${ClusterBaseName}-bastion-EC2

          - DeviceIndex: 0
              complete -C '/usr/local/bin/aws_completer' aws            wget https://github.com/andreazorzetto/yh/releases/download/v0.4.0/yh-linux-amd64.zip
            GroupSet:
              echo "export AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" >> /etc/profile
            AssociatePublicIpAddress: true

          - Key: Name
              cd /root

          - DeviceName: /dev/xvda

            VolumeType: gp3
            curl -s https://raw.githubusercontent.com/helm/helm/master/scripts/get-helm-3 | bash            # Install eksctl
            install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl


      UserData:


            # Install Packages            ln -sf /usr/share/zoneinfo/Asia/Seoul /etc/localtime
            echo 'root:qwe123' | chpasswd            systemctl restart sshd            # Config convenience


            echo "sudo su -" >> /home/ec2-user/.bashrc
            sed -i "s/^PasswordAuthentication no/PasswordAuthentication yes/g" /etc/ssh/sshd_config
            KUBE_PS1_SYMBOL_ENABLE=false

            function get_cluster_short() {
            # Install YAML Highlighter
            export AWS_DEFAULT_REGION=${AWS::Region}            curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
            curl -L https://github.com/kubernetes-sigs/krew/releases/download/v0.4.4/krew-linux_amd64.tar.gz -o /root/krew-linux_amd64.tar.gz

            # Config Root account            sed -i "s/^#PermitRootLogin yes/PermitRootLogin yes/g" /etc/ssh/sshd_config
            # Install aws cli v2

            echo 'alias vi=vim' >> /etc/profile
            rm -rf /root/.ssh/authorized_keys

            ./krew-linux_amd64 install krew
            sed -i "s/UTC/Asia\/Seoul/g" /etc/sysconfig/clock

            yum -y install tree jq git htop            # Install kubectl & helm
            # Install krew            tar zxvf krew-linux_amd64.tar.gz
            source /root/kube-ps1/kube-ps1.sh            cat <<"EOT" >> /root/.bash_profile

            mv /tmp/eksctl /usr/local/bin
            echo 'source <(kubectl completion bash)' >> /root/.bashrc            echo 'complete -F __start_kubectl k' >> /root/.bashrc

            export PATH="$PATH:/root/.krew/bin"
            curl -O https://s3.us-west-2.amazonaws.com/amazon-eks/1.28.5/2024-01-04/bin/linux/amd64/kubectl

            curl -sL "https://github.com/eksctl-io/eksctl/releases/latest/download/eksctl_Linux_amd64.tar.gz" | tar xz -C /tmp
            ./aws/install


            echo 'alias k=kubectl' >> /root/.bashrc            
            PS1='$(kube_ps1)'$PS1            EOT            KUBE_PS1_CLUSTER_FUNCTION=get_cluster_short


            export CLUSTER_NAME=${ClusterBaseName}            export VPCID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=$CLUSTER_NAME-VPC" | jq -r .Vpcs[].VpcId)
            unzip yh-linux-amd64.zip
            export PubSubnet1=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet1" --query "Subnets[0].[SubnetId]" --output text)
            mv yh /usr/local/bin/

            # Create SSH Keypair
            export PubSubnet2=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet2" --query "Subnets[0].[SubnetId]" --output text)            echo "export PubSubnet1=$PubSubnet1" >> /etc/profile

            echo "export PubSubnet3=$PubSubnet3" >> /etc/profile
            systemctl start docker && systemctl enable docker            export AWS_ACCESS_KEY_ID=${MyIamUserAccessKeyID}
            export PrivateSubnet2=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PrivateSubnet2" --query "Subnets[0].[SubnetId]" --output text)

            echo "export KUBERNETES_VERSION=$KUBERNETES_VERSION" >> /etc/profile            # VPC & Subnet
            echo "export ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)" >> /etc/profile            # CLUSTER_NAME
            echo 'export PATH="$PATH:/root/.krew/bin"' >> /etc/profile
            kubectl krew install ctx ns get-all neat # ktop df-pv mtail tree            # Install Docker

            amazon-linux-extras install docker -y
            # Install kube-ps1
            ssh-keygen -t rsa -N "" -f /root/.ssh/id_rsa            # IAM User Credentials


            git clone https://github.com/jonmosco/kube-ps1.git /root/kube-ps1
            export AWS_DEFAULT_REGION=${AWS::Region}            echo "export AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID" >> /etc/profile


            KUBE_PS1_SUFFIX=') '              echo "$1" | cut -d . -f1
              attachPolicyARNs:              configurationValues: |-            cat <<EOT > precmd.yaml                - "yum install nvme-cli links tree tcpdump sysstat -y"


            }
            # Install krew plugin
            echo "export PrivateSubnet3=$PrivateSubnet3" >> /etc/profile
            echo "export PrivateSubnet2=$PrivateSubnet2" >> /etc/profile

            # Create EKS Cluster & Nodegroup
            sed -i 's/certManager: false/certManager: true/g' myeks.yaml


            export AWS_SECRET_ACCESS_KEY=${MyIamUserSecretAccessKey}            export ACCOUNT_ID=$(aws sts get-caller-identity --query 'Account' --output text)            echo "export AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY" >> /etc/profile

            export KUBERNETES_VERSION=${KubernetesVersion}
            echo "export AWS_DEFAULT_REGION=$AWS_DEFAULT_REGION" >> /etc/profile

            echo "export VPCID=$VPCID" >> /etc/profile
            echo "export CLUSTER_NAME=$CLUSTER_NAME" >> /etc/profile            # K8S Version            export PubSubnet3=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PublicSubnet3" --query "Subnets[0].[SubnetId]" --output text)

            echo "export PrivateSubnet1=$PrivateSubnet1" >> /etc/profile
            echo "export PubSubnet2=$PubSubnet2" >> /etc/profile
            export PrivateSubnet3=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PrivateSubnet3" --query "Subnets[0].[SubnetId]" --output text)
            export PrivateSubnet1=$(aws ec2 describe-subnets --filters Name=tag:Name,Values="$CLUSTER_NAME-PrivateSubnet1" --query "Subnets[0].[SubnetId]" --output text)
            sed -i 's/ebs: false/ebs: true/g' myeks.yaml
            eksctl create cluster --name $CLUSTER_NAME --region=$AWS_DEFAULT_REGION --nodegroup-name=ng1 --node-type=${WorkerNodeInstanceType} --nodes ${WorkerNodeCount} --node-volume-size=${WorkerNodeVolumesize} --vpc-public-subnets "$PubSubnet1","$PubSubnet2","$PubSubnet3" --version ${KubernetesVersion} --ssh-access --ssh-public-key /root/.ssh/id_rsa.pub --with-oidc --external-dns-access --full-ecr-access --dry-run > myeks.yaml
              version: latest # auto discovers the latest available
            addons:
                enableNetworkPolicy: "true"
                - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy

            cat <<EOT >> myeks.yaml
            - name: vpc-cni # no version is specified so it deploys the default version            - name: kube-proxy

              version: latest
              version: latest

            - name: coredns
            EOT

              preBootstrapCommands:            EOT
            sed -i -n -e '/instanceType/r precmd.yaml' -e '1,$p' myeks.yaml

            echo 'cloudinit End!'Outputs:
            nohup eksctl create cluster -f myeks.yaml --verbose 4 --kubeconfig "/root/.kube/config" 1> /root/create-eks.log 2>&1 &
    Value: !GetAtt EKSEC2.PublicIp
  eksctlhost:

  ~~~
  </details>

- 특이사항
  eksctl ~~ --dry-run 명령어로 yaml로 만든 후 add-on 을 아래와 같이 추가

  ~~~
  cat <<EOT >> myeks.yaml
  addons:
  - name: vpc-cni # no version is specified so it deploys the default version
    version: latest # auto discovers the latest available
    attachPolicyARNs:
      - arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy
    configurationValues: |-
      enableNetworkPolicy: "true"
  - name: kube-proxy
    version: latest
  - name: coredns
    version: latest
  EOT
  ~~~






