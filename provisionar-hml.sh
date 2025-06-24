#!/bin/bash
# Script de provisionamento completo do ambiente HML - corrigido com base no padrão de Dev

# Defina aqui sua conta de faturamento (substitua pelo seu billing ID real)
BILLING_ACCOUNT="016721-177D1A-EFA886"

# 1. Criar projeto (com billing)
#echo "[1/10] Criando projeto GCP com billing..." && gcloud projects create ecco-agent-hml --name="Ecco Agent HML" && gcloud beta billing projects link ecco-agent-hml --billing-account=$BILLING_ACCOUNT && gcloud config set project ecco-agent-hml && 
#echo "[2/10] Reservando IP estático..." && gcloud compute addresses create cloud-run-static-ip-hml --region=southamerica-east1 && 
#echo "[3/10] Criando sub-rede..." && gcloud compute networks subnets create cloud-run-subnet-hml --network=default --range=10.21.0.0/28 --region=southamerica-east1 && 
#echo "[4/10] Criando Cloud Router..." && gcloud compute routers create cloud-run-router-hml --region=southamerica-east1 --network=default && 
#echo "[5/10] Criando Cloud NAT..." && gcloud compute routers nats create nat-hml --router=cloud-run-router-hml --region=southamerica-east1 --nat-external-ip-pool=cloud-run-static-ip-hml --nat-all-subnet-ip-ranges && 
#echo "[6/10] Criando VPC Access Connector..." && gcloud compute networks vpc-access connectors create cr-connector-hml --region=southamerica-east1 --subnet=cloud-run-subnet-hml && 
echo "[7/10] Criando conta de serviço..." && gcloud iam service-accounts create agent-hml --display-name="Agent HML Runner" && 
echo "[8/10] Concedendo permissões..." && gcloud projects add-iam-policy-binding ecco-agent-hml --member="serviceAccount:agent-hml@ecco-agent-hml.iam.gserviceaccount.com" --role="roles/editor" && 
echo "[9/10] Fazendo deploy do container..." && gcloud run deploy winrm-metrics-hml --source . --region=southamerica-east1 --platform=managed --allow-unauthenticated --service-account=agent-hml@ecco-agent-hml.iam.gserviceaccount.com && 
echo "[10/10] Atualizando configuração de rede do Cloud Run..." && gcloud run services update winrm-metrics-hml --region=southamerica-east1 --vpc-connector=cr-connector-hml --vpc-egress=all-traffic && 
echo "
✅ Ambiente HML provisionado com sucesso."
