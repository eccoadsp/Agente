#!/bin/bash
# Script de provisionamento completo do ambiente DEV - versão atualizada

# Defina aqui sua conta de faturamento (substitua pelo seu billing ID real)
BILLING_ACCOUNT="INSIRA_SEU_BILLING_ID"

# 1. Criar projeto (com billing)
echo "[1/10] Criando projeto GCP com billing..." && gcloud projects create ecco-agent-dev --name="Ecco Agent Dev" && gcloud beta billing projects link ecco-agent-dev --billing-account=$BILLING_ACCOUNT && gcloud config set project ecco-agent-dev && 
echo "[2/10] Reservando IP estático..." && gcloud compute addresses create cloud-run-static-ip-dev --region=southamerica-east1 && 
echo "[3/10] Criando sub-rede..." && gcloud compute networks subnets create cloud-run-subnet-dev --network=default --range=10.11.0.0/28 --region=southamerica-east1 && 
echo "[4/10] Criando Cloud Router..." && gcloud compute routers create cloud-run-router-dev --region=southamerica-east1 --network=default && 
echo "[5/10] Criando Cloud NAT..." && gcloud compute routers nats create nat-dev --router=cloud-run-router-dev --region=southamerica-east1 --nat-external-ip-pool=cloud-run-static-ip-dev --nat-all-subnet-ip-ranges && 
echo "[6/10] Criando VPC Access Connector..." && gcloud compute networks vpc-access connectors create cr-connector-dev --region=southamerica-east1 --subnet=cloud-run-subnet-dev && 
echo "[7/10] Criando conta de serviço..." && gcloud iam service-accounts create agent-dev --display-name="Agent Dev Runner" && 
echo "[8/10] Concedendo permissões..." && gcloud projects add-iam-policy-binding ecco-agent-dev --member="serviceAccount:agent-dev@ecco-agent-dev.iam.gserviceaccount.com" --role="roles/editor" && 
echo "[9/10] Fazendo deploy do container..." && gcloud run deploy winrm-metrics-dev --source . --region=southamerica-east1 --platform=managed --allow-unauthenticated --service-account=agent-dev@ecco-agent-dev.iam.gserviceaccount.com && 
echo "[10/10] Atualizando configuração de rede do Cloud Run..." && gcloud run services update winrm-metrics-dev --region=southamerica-east1 --vpc-connector=cr-connector-dev --vpc-egress=all-traffic && 
echo "\n✅ Ambiente DEV provisionado com sucesso."

