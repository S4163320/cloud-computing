Music App Backend – ECS Deployment Guide

Build Docker Image
docker build -t music-app-backend .

Create ECR Repository
Go to AWS ECR → Create repository
Name: music-app-backend

Login to ECR
aws ecr get-login-password --region <your-region> | docker login --username AWS --password-stdin <your-account-id>.dkr.ecr.<your-region>.amazonaws.com

Tag Image
docker tag music-app-backend:latest <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/music-app-backend:latest

Push Image
docker push <your-account-id>.dkr.ecr.<your-region>.amazonaws.com/music-app-backend:latest

Create ECS Cluster
Name: music-app-cluster

Create Task Definition
Name: music-app-backend
Memory: 0.5 GB
CPU: 0.25 vCPU
Task role: <include your role>
Execution role: <include your role>

Container
Name: musicAppBackEnd
Image: <your-ecr-image-uri>
Port: 5000

Create Security Group
Name: sgMusicAppBackEnd
Inbound: Port 5000 (0.0.0.0/0 or restrict)
Outbound: default

Create Load Balancer (ALB)
Name: musicAppBackEnd-alb
Port: 5000
Security group: sgMusicAppBackEnd

Create Target Group
Name: musicAppBackEnd-target-group
Port: 5000
Target type: IP

Create ECS Service
Name: music-app-backend-service
Cluster: music-app-cluster
Task definition: select from dropdown
Health check: 60

Networking
Select 2 subnets
Security group: sgMusicAppBackEnd

Load Balancer
Use existing ALB
Select musicAppBackEnd-alb
Select musicAppBackEnd-target-group
Container: musicAppBackEnd:5000

Test
http://<your-alb-dns>:5000